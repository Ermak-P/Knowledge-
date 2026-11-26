"""Foreground /update-by-CR backend, using existing Knowledge ownership/APIs.

Optional sealed metadata records hold progress; immutable bounded supporting
artifacts and ordinary claims/evidence hold explanations. No second database,
model, write-MCP tool, executable memory or automatic plan approval is created.
"""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,os,re,uuid
from pathlib import Path
from . import cr_sources as src,lifecycle as life
from .project import safe_path,safe_tree
from .store import Store
from .util import canonical_json,digest,fingerprint,loads,read_text,require,KnowledgeError

PREFIX='update-by-cr:'
STATES={'awaiting_links','awaiting_sources','analyzing','awaiting_answers','ready_for_review','preparing','awaiting_approval','persisting','saved','partial_saved','blocked','stale'}
CATEGORIES={'implementation','requirement','decision','alternative','nonchange','applicability','verification','open'}
COMPLETED={'saved','partial_saved'}


def now():return datetime.now(timezone.utc).isoformat()
def fault(phase):pass
def is_completed(state):return state['state'] in COMPLETED or state['state']=='stale' and state['receipt'] is not None
def source_hash(snapshot):return digest({k:v for k,v in snapshot.items() if k!='observed_at'})
def automatic_claim_id(state,item):
    merged=state['source']['pr']['status']=='merged'
    prefix='ucr.'+digest([state['project'],state['links']['cr']])[:16] if merged else 'ucr.proposal.'+digest([state['project'],state['links']['cr'],state['links']['pr']])[:16]
    return prefix+'.'+item['key']
def sealed(state):
    value=deepcopy(state);value.pop('seal',None);value['seal']=digest(value);return value


def validate_state(value,project,key=None):
    fields={'version','id','project','revision','host_session','language','links','state','source','binding','knowledge_base','map','questions','answers','turns','history','proposal','approved','receipt','artifacts','closed','seal'}
    require(isinstance(value,dict) and set(value)==fields and value['version']==1 and isinstance(value['id'],str) and re.fullmatch('[a-f0-9]{32}',value['id']) and value['project']==project,'ucr-corrupt-session')
    require(key is None or key==PREFIX+value['id'],'ucr-corrupt-session-identity')
    require(type(value['revision']) is int and value['revision']>0 and value['state'] in STATES and value['language'] in ('en','ru') and type(value['closed']) is bool,'ucr-corrupt-session-state')
    require(value['seal']==digest({k:v for k,v in value.items() if k!='seal'}) and len(canonical_json(value).encode())<=1024000,'ucr-corrupt-session-seal')
    require(isinstance(value['links'],dict) and set(value['links'])<={'cr','pr'},'ucr-corrupt-links')
    for kind,url in value['links'].items():src.link(url,kind)
    if value['source'] is not None:src.validate(value['source'])
    for key in ('map','questions','history','artifacts'):require(isinstance(value[key],list) and len(value[key])<=200,'ucr-corrupt-session-list')
    for key in ('answers','turns'):require(isinstance(value[key],dict) and len(value[key])<=200,'ucr-corrupt-session-map')
    require(value['host_session'] is None or isinstance(value['host_session'],str),'ucr-corrupt-host-session')
    for artifact in value['artifacts']:
        require(isinstance(artifact,dict) and set(artifact)=={'path','hash'} and re.fullmatch(r'\.knowledge/update-cr/'+value['id']+r'/[a-f0-9]{64}\.json',artifact['path']) and re.fullmatch('sha256:[a-f0-9]{64}',artifact['hash']),'ucr-corrupt-artifact-reference')
    return value


def validate_workflows(db,project):
    for key,payload in db.execute('SELECT key,value FROM metadata WHERE key LIKE ?',(PREFIX+'%',)):validate_state(loads(payload),project,key)


def artifact_freshness(root, evidence, db=None):
    """Verify a registered CR receipt without treating runtime files as sources."""
    path, expected = evidence['source'], evidence['content_hash']
    match = re.fullmatch(r'\.knowledge/update-cr/([a-f0-9]{32})/([a-f0-9]{64})\.json', path)
    if not match or expected != 'sha256:' + match[2] or evidence['id'] != 'ucr.evidence.' + match[2]:
        return 'not-verifiable'
    if db is None:
        with Store(root).connection() as connection:
            return artifact_freshness(root, evidence, connection)
    row = db.execute('SELECT value FROM metadata WHERE key=?', (PREFIX + match[1],)).fetchone()
    if row is None or {'path': path, 'hash': expected} not in loads(row[0])['artifacts']:
        return 'not-verifiable'
    artifact = safe_path(Path(root) / path)
    if not artifact.is_file():
        return 'missing'
    with artifact.open('rb') as stream:
        data = stream.read(src.LIMIT + 1)
    if len(data) > src.LIMIT:
        return 'not-verifiable'
    return 'unchanged' if 'sha256:' + hashlib.sha256(data).hexdigest() == expected else 'changed'


class Workflow:
    def __init__(self,root):self.store=Store(root);self.root=self.store.project.root
    def _load(self,db,sid):
        require(isinstance(sid,str) and re.fullmatch('[a-f0-9]{32}',sid),'ucr-invalid-session-id')
        row=db.execute('SELECT value FROM metadata WHERE key=?',(PREFIX+sid,)).fetchone();require(row is not None,'ucr-unknown-session')
        return validate_state(loads(row[0]),self.store.project.identity,PREFIX+sid)
    def get(self,sid):
        with self.store.connection() as db:return deepcopy(self._load(db,sid))
    def _change(self,sid,expected,mutate):
        with self.store.connection(True) as db:
            state=deepcopy(self._load(db,sid));require(state['revision']==expected,'ucr-session-cas-conflict')
            mutate(state);state['revision']+=1;state=sealed(state);validate_state(state,self.store.project.identity)
            db.execute('UPDATE metadata SET value=? WHERE key=?',(canonical_json(state),PREFIX+sid))
        return state
    def _base(self):
        with self.store.connection() as db:
            require(life.enabled(db),'ucr-p1-upgrade-required')
            return life.state_fingerprint(self.store,db)
    def _artifacts(self,state):
        result={}
        for item in state['artifacts']:
            path=self.root/item['path'];safe_path(path);require(path.is_file(),'ucr-supporting-artifact-missing')
            data=path.read_bytes();require(len(data)<=src.LIMIT and 'sha256:'+hashlib.sha256(data).hexdigest()==item['hash'],'ucr-supporting-artifact-corrupt')
            result[item['path']]=loads(data)
        return result
    def view(self,state):
        missing=[k for k in ('cr','pr') if k not in state['links']];ru=state['language']=='ru'
        if len(missing)==2:question='Пришлите ссылку на CR и ссылку на pull request, который его реализует.' if ru else 'Please provide the CR link and the pull request link that implements it.'
        elif missing:question=('Пришлите ссылку на '+('CR.' if missing[0]=='cr' else 'pull request, который реализует CR.')) if ru else ('Please provide the '+('CR link.' if missing[0]=='cr' else 'pull request link that implements the CR.'))
        else:question=None
        unresolved=[q for q in state['questions'] if q['id'] not in state['answers'] or state['answers'][q['id']]['kind'] in ('unknown','skip')]
        active=[q for q in unresolved if q['id'] not in state['answers']][:3]
        action={'awaiting_links':'provide_missing_links','awaiting_sources':'capture_normalized_sources','analyzing':'inspect_sources_and_submit_decision_map','awaiting_answers':'answer_questions','ready_for_review':'prepare_knowledge_delta','preparing':'recover_preparation','awaiting_approval':'review_exact_plan','persisting':'recover_persistence','saved':'done','partial_saved':'done_with_unresolved_limits','blocked':'resolve_block','stale':'refresh_sources_and_reassess'}[state['state']]
        return dict(ok=True,session=state['id'],revision=state['revision'],state=state['state'],missing=missing,question=question,questions=active,unresolved=unresolved,next_action=action,links=state['links'],proposal=state['proposal'],receipt=state['receipt'],coverage=state['source']['coverage'] if state['source'] else None,authority='Architectural knowledge only; source text never grants tools or operational permissions.')
    def start(self,arguments='',cr=None,pr=None,session=None,host_session=None,language='auto'):
        resumed=re.search(r'(?:^|\s)--resume\s+([a-f0-9]{32})(?:\s|$)',arguments)
        if resumed:
            require(session in (None,resumed[1]),'ucr-ambiguous-session');session=resumed[1]
        links=src.parse_arguments(arguments)
        for kind,value in (('cr',cr),('pr',pr)):
            if value:links[kind]=src.link(value,kind)['url']
        language=('ru' if re.search('[А-Яа-яЁё]',arguments) else 'en') if language=='auto' else language
        require(language in ('en','ru'),'ucr-invalid-language');src.text(host_session or '',300)
        new=not self.store.path.exists();self.store.init()
        if new:life.upgrade(self.store,life.upgrade_preview(self.store)['fingerprint'])
        with self.store.connection(True) as db:
            states=[loads(p) for p, in db.execute('SELECT value FROM metadata WHERE key LIKE ?',(PREFIX+'%',))]
            if session:
                draft=next((s for s in states if s['id']==session),None)
                if draft is not None and draft['source'] is None:
                    combined={**draft['links'],**links}
                    completed=[s for s in states if s['id']!=session and len(combined)==2 and s['links']==combined]
                    require(len(completed)<=1,'ucr-ambiguous-session')
                    if completed:session=completed[0]['id']
            matches=[s for s in states if s['id']==session] if session else [s for s in states if s['links']==links] if len(links)==2 else [s for s in states if host_session and s['host_session']==host_session]
            if not session and len(links)!=2 and len(matches)>1:
                active=[s for s in matches if not is_completed(s)]
                if len(active)==1:matches=active
            require(len(matches)<=1,'ucr-ambiguous-session')
            if session:require(matches,'ucr-unknown-session')
            if matches:
                state=deepcopy(matches[0]);require(state['state']!='persisting' or not links or links==state['links'],'ucr-recover-before-new-input')
                require(all(k not in state['links'] or state['links'][k]==v for k,v in links.items()),'ucr-links-changed-start-new-session')
                state['links'].update(links);state['revision']+=1
                if state['state']=='awaiting_links' and len(state['links'])==2:state['state']='awaiting_sources'
            else:
                state=dict(version=1,id=uuid.uuid4().hex,project=self.store.project.identity,revision=1,host_session=host_session,language=language,links=links,state='awaiting_sources' if len(links)==2 else 'awaiting_links',source=None,binding=None,knowledge_base=None,map=[],questions=[],answers={},turns={},history=[],proposal=None,approved=None,receipt=None,artifacts=[],closed=False)
            if host_session:
                for other in states:
                    if other['id']!=state['id'] and other['host_session']==host_session:
                        require(other['source'] is None or is_completed(other),'ucr-host-already-has-active-workflow')
                        other['host_session']=None;other['revision']+=1
                        db.execute('UPDATE metadata SET value=? WHERE key=?',(canonical_json(sealed(other)),PREFIX+other['id']))
                state['host_session']=host_session
            state=sealed(state);validate_state(state,self.store.project.identity)
            db.execute('INSERT INTO metadata VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(PREFIX+state['id'],canonical_json(state)))
        return self.view(state)
    def sources(self,sid,snapshot,expected):
        snapshot=src.validate(snapshot);state=self.get(sid);require(state['revision']==expected,'ucr-session-cas-conflict');require(state['state']!='persisting','ucr-recover-before-new-input')
        require(state['links']=={'cr':snapshot['cr']['url'],'pr':snapshot['pr']['url']},'ucr-snapshot-link-mismatch')
        binding=src.checkout(self.root,snapshot);base=self._base();changed=state['source'] is not None and (source_hash(state['source'])!=source_hash(snapshot) or state['binding']!=binding or state['knowledge_base']!=base or not self._proposal_in_scope(state))
        def change(s):
            if changed:
                s['history'].append(dict(event='source-stale',source=source_hash(s['source']),questions=s['questions'],answers=s['answers'],proposal=s['proposal']))
                s.update(map=[],questions=[],answers={},proposal=None,approved=None,receipt=None,closed=False)
            s.update(source=snapshot,binding=binding,knowledge_base=base)
            if changed or s['state'] in ('awaiting_links','awaiting_sources','stale','blocked'):s['state']='analyzing'
        return self.view(self._change(sid,expected,change))
    def _fresh(self,state):
        require(state['source'] is not None,'ucr-sources-required')
        require(src.checkout(self.root,state['source'])==state['binding'] and self._base()==state['knowledge_base'],'ucr-analysis-stale')
        self._artifacts(state)
    def inspect(self,sid,paths=()):
        state=self.get(sid);self._fresh(state)
        result=src.inspect(self.root,state['source'],paths)
        result['knowledge']=self.store.context(state['source']['cr']['title'],max_bytes=16000,include_unconfirmed=True)
        return dict(ok=True,session=sid,revision=state['revision'],inspection=result)
    def _known(self,state):
        known=src.references(state['source'])
        with self.store.connection() as db:
            if life.enabled(db):
                records=self.store._records(db);states=life.latest(db)
                from .discovery import freshness
                for c in records['claims']:
                    if states[c['id']]['lifecycle']=='active' and freshness(self.root,c,records)['trusted']:
                        known['knowledge:'+c['id']+'@'+str(states[c['id']]['revision'])]=dict(text=c['statement'],reference='knowledge:'+c['id'])
        return known
    def analyze(self,sid,items,expected):
        state=self.get(sid);self._fresh(state);require(state['state'] not in ('preparing','persisting','awaiting_approval'),'ucr-finish-or-revise-current-plan-first')
        require(isinstance(items,list) and 0<len(items)<=24,'ucr-invalid-decision-map');known=self._known(state);mapped=[];questions=[];keys=set()
        inspection=src.inspect(self.root,state['source'],list(dict.fromkeys(a['path'] for item in items if isinstance(item,dict) for a in item.get('anchors',[]) if isinstance(a,dict) and isinstance(a.get('path'),str))))
        require(not any(g.get('reason')=='reported-diff-file-coverage-mismatch' for g in inspection['gaps']) or state['source']['coverage']['files']!='complete','ucr-comparison-revisions-inconsistent')
        for raw in items:
            fields={'key','category','statement','condition','preserve','reconsider','reason','refs','anchors','terms','confidence','existing_id','change'}
            require(isinstance(raw,dict) and set(raw)==fields,'ucr-invalid-decision-item')
            item=deepcopy(raw);key=item['key'];require(isinstance(key,str) and re.fullmatch('[A-Za-z][A-Za-z0-9._-]{0,79}',key) and key not in keys,'ucr-invalid-decision-key');keys.add(key)
            require(item['category'] in CATEGORIES and item['confidence'] in ('CONFIRMED','INFERRED','UNKNOWN','NEEDS_HUMAN_CONFIRMATION') and item['change'] in ('upsert','retire'),'ucr-invalid-decision-classification')
            for k in ('statement','condition','preserve','reconsider'):src.text(item[k],3000)
            require(item['statement'].strip() and item['condition'].strip(),'ucr-decision-scope-required')
            require(item['existing_id'] is None or isinstance(item['existing_id'],str) and re.fullmatch('[A-Za-z][A-Za-z0-9._:-]*',item['existing_id']),'ucr-invalid-existing-id')
            require(isinstance(item['refs'],list) and item['refs'] and len(item['refs'])<=12 and all(r in known for r in item['refs']),'ucr-unknown-source-reference')
            require(isinstance(item['terms'],list) and len(item['terms'])<=12 and all(isinstance(t,str) for t in item['terms']),'ucr-invalid-search-terms')
            for t in item['terms']:src.text(t,150)
            require(isinstance(item['anchors'],list) and 0<len(item['anchors'])<=8,'ucr-code-context-required')
            item['anchors']=[src.anchor(self.root,a,state['source']) for a in item['anchors']]
            require(item['category']!='nonchange' or any(a['role'] in ('neighbor','contract') for a in item['anchors']),'ucr-nonchange-context-required')
            if item['category']=='nonchange':
                require(not any(g.get('reason')=='reported-diff-file-coverage-mismatch' for g in inspection['gaps']),'ucr-nonchange-coverage-incomplete')
                for a in item['anchors']:
                    if a['role'] in ('neighbor','contract'):
                        src.nonchange(self.root,a,state['source'])
            if item['reason'] is not None:
                r=item['reason'];require(isinstance(r,dict) and set(r)=={'text','refs'} and r['text'] and isinstance(r['refs'],list) and r['refs'] and all(ref in known for ref in r['refs']),'ucr-unsourced-reason');src.text(r['text'],4000)
            elif item['category'] in ('decision','alternative','nonchange'):
                a=item['anchors'][0];anchor=f"{a['path']}@{a['revision']}#L{a['start']}-L{a['end']}"
                prompt=(f"{anchor}: {item['statement']} Почему выбран или сохранён этот вариант? Укажите причину и условия применимости; это важно для сохранения ограничения: {item['preserve'] or item['condition']}. Неизвестно/пропустить — допустимый ответ." if state['language']=='ru' else f"{anchor}: {item['statement']} What explains choosing or preserving this approach, and when does that reason apply? This matters to preserve: {item['preserve'] or item['condition']}. Unknown/skip is acceptable.")
                q=dict(id=digest([source_hash(state['source']),item['key'],'reason',item]),item=key,kind='reason',text=prompt,anchor=anchor)
                questions.append(q)
            if item['change']=='retire':require(item['existing_id'] is not None and item['reason'] is not None,'ucr-retirement-evidence-required')
            mapped.append(item)
        cr_url=state['links']['cr']
        if cr_url not in state['source']['pr']['cr_links']:
            require(not state['source']['pr']['cr_links'],'ucr-source-association-mismatch')
            questions.insert(0,dict(id=digest([source_hash(state['source']),'association']),item=None,kind='association',text=('Источник PR не подтверждает связь с этим CR. Вы подтверждаете, что эти ссылки относятся к одной задаче?' if state['language']=='ru' else 'The PR source does not establish its association with this CR. Do you confirm these links belong to the same change?'),anchor=state['links']['pr']))
        def change(s):
            s['history'].append(dict(event='analysis-coverage',gaps=inspection['gaps'],actual_changed=inspection['actual_changed']))
            if s['proposal']:s['history'].append(dict(event='proposal-superseded',proposal=s['proposal']))
            s.update(map=mapped,questions=questions,proposal=None,approved=None,receipt=None)
            s['state']='awaiting_answers' if any(q['id'] not in s['answers'] for q in questions) else 'ready_for_review'
        return self.view(self._change(sid,expected,change))
    def user_turn(self,sid,host_session,message_id,text):
        state=self.get(sid);require(state['host_session']==host_session and host_session,'ucr-host-session-mismatch');src.text(text,16000);src.text(message_id,300)
        if message_id in state['turns']:
            require(state['turns'][message_id]==text,'ucr-user-message-id-reused');return self.view(state)
        return self.view(self._change(sid,state['revision'],lambda s:s['turns'].update({message_id:text})))
    def answer(self,sid,question,text,delivery_id,expected,kind='historical_reason',turn=None):
        state=self.get(sid);self._fresh(state);require(state['state'] not in ('preparing','persisting','saved','partial_saved'),'ucr-recover-or-reopen-before-answer')
        src.text(text,8000);src.text(delivery_id,300);require(kind in ('historical_reason','future_preference','unknown','skip','correction','association'),'ucr-invalid-answer-kind')
        q=next((q for q in state['questions'] if q['id']==question),None);require(q is not None,'ucr-unknown-question')
        if state['host_session']:require(turn in state['turns'] and text in state['turns'][turn],'ucr-answer-requires-actual-user-turn')
        value=dict(text=text,delivery_id=delivery_id,kind=kind,turn=turn,source='user-message',binding=source_hash(state['source']))
        for old in [*state['answers'].values(),*[h['answer'] for h in state['history'] if h.get('event')=='answer-corrected']]:
            if old['delivery_id']==delivery_id:
                require(old==value,'ucr-answer-delivery-id-reused');return self.view(state)
        if q['kind']=='association':require(kind=='association' and text.strip().casefold() in ('yes','да','confirm','подтверждаю'),'ucr-association-confirmation-required')
        def change(s):
            old=s['answers'].get(question)
            if old:s['history'].append(dict(event='answer-corrected',question=question,answer=old))
            s['answers'][question]=value;s['approved']=None;s['receipt']=None
            s['state']='awaiting_answers' if any(q['id'] not in s['answers'] for q in s['questions']) and not s['closed'] else 'ready_for_review'
        return self.view(self._change(sid,expected,change))
    def finish(self,sid,expected):
        state=self.get(sid);self._fresh(state);require(state['state'] in ('awaiting_answers','ready_for_review'),'ucr-interview-not-active')
        return self.view(self._change(sid,expected,lambda s:s.update(closed=True,state='ready_for_review')))
    def _write_artifact(self,sid,value):
        from .coordination import gate
        with gate(self.root):return self._write_artifact_owned(sid,value)
    def _write_artifact_owned(self,sid,value):
        data=canonical_json(value).encode();require(len(data)<=src.LIMIT,'ucr-artifact-too-large');name=hashlib.sha256(data).hexdigest();rel=f'.knowledge/update-cr/{sid}/{name}.json';path=self.root/rel
        safe_path(path);safe_tree(path.parent);path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():require(path.read_bytes()==data,'ucr-artifact-conflict')
        else:
            tmp=path.with_name(uuid.uuid4().hex+'.tmp')
            try:
                with tmp.open('xb') as out:out.write(data);out.flush();os.fsync(out.fileno())
                os.replace(tmp,path)
            finally:
                if tmp.exists():tmp.unlink()
        return dict(path=rel,hash='sha256:'+name)
    def _build(self,state):
        known=self._known(state);source=state['source'];ops=[];artifacts=[];claims=[]
        with self.store.connection() as db:
            records=self.store._records(db);states=life.latest(db);existing={r['id']:r for g,rs in records.items() for r in rs}
        merged=source['pr']['status']=='merged';scope=('reviewed target '+source['target']['commit']) if merged else ('unmerged PR proposal '+source['pr']['url']+' @ '+source['pr']['head']+'; not target behavior')
        if not merged:
            require(all(i['existing_id'] is None and i['change']=='upsert' for i in state['map']),'ucr-unmerged-target-mutation-refused',{'resolution':'Save branch proposals with automatic scoped IDs; existing-ID updates and retirement require a merged PR present on the target.'})
        for item in state['map']:
            identifier=item['existing_id'] or automatic_claim_id(state,item)
            old=existing.get(identifier);require(not item['existing_id'] or old is not None,'ucr-existing-record-missing')
            q=next((q for q in state['questions'] if q['item']==item['key'] and q['kind']=='reason'),None);answer=state['answers'].get(q['id']) if q else None
            unresolved=q is not None and (answer is None or answer['kind'] in ('unknown','skip'))
            reason=item['reason']['text'] if item['reason'] else answer['text'] if answer and not unresolved else None
            future=bool(answer and answer['kind']=='future_preference')
            confidence='UNKNOWN' if unresolved or item['category']=='open' else 'NEEDS_HUMAN_CONFIRMATION' if future or not merged else item['confidence']
            if item['category']=='verification' and not any(r.startswith('pr:check:') for r in item['refs']):confidence='UNKNOWN'
            label=('Unresolved / Не установлено: ' if unresolved else 'New future preference, not historical rationale / Новое пожелание: ' if future else '')
            statement=f"{label}{item['statement']} When / Условия: {item['condition']}. "+(f"Reason / Причина: {reason}. " if reason else 'Reason not established / Причина не установлена. ' if unresolved else '')
            if item['preserve']:statement+='Preserve / Сохранить: '+item['preserve']+'. '
            if item['reconsider']:statement+='Reassess / Пересмотреть: '+item['reconsider']+'. '
            statement+=f"Topic / Тема: {source['cr']['title']}. Scope: {source['pr']['repository']} — {scope}."
            if item['terms']:statement+=' Terms: '+', '.join(item['terms'])+'.'
            src.text(statement,8000)
            explanation=dict(version=1,format='knowledge-update-cr-evidence-v1',project=state['project'],source_fingerprint=source_hash(source),cr=source['cr']['url'],pr=source['pr']['url'],pr_status=source['pr']['status'],base=source['pr']['base'],head=source['pr']['head'],target=source['target'],acquisition=source['acquisition'],observed_at=source['observed_at'],coverage=source['coverage'],item=item,user_answer=answer,references={r:known[r] for r in dict.fromkeys(item['refs']+(item['reason']['refs'] if item['reason'] else []))})
            artifact=self._write_artifact(state['id'],explanation);artifacts.append(artifact)
            eid='ucr.evidence.'+artifact['hash'][7:];evidence=dict(id=eid,type='direct-authoritative',status='active',source=artifact['path'],location={'reference':source['cr']['url']+' | '+source['pr']['url']+' | '+item['key']},content_hash=artifact['hash'],description=reason or item['statement'],substantiates=[identifier],captured_at=source['observed_at'],provenance={'actor':'user-CR-interview' if answer else source['acquisition']['kind'],'method':'update-by-cr-v1'})
            evidence_ids=[eid]
            if existing.get(eid)!=evidence:ops.append(life.op('add' if eid not in existing else 'update','evidence',eid,states[eid]['revision'] if eid in states else 0,evidence))
            if merged:
                for anchor in item['anchors']:
                    require(anchor['revision']==source['target']['commit'],'ucr-target-fact-requires-target-anchors')
                    path=self.root/anchor['path'];safe_path(path);require(path.is_file() and 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()==anchor['hash'],'ucr-target-anchor-not-current')
                    codeid='ucr.code.'+digest([identifier,anchor]);code=dict(id=codeid,type='direct-technical',status='active',source=anchor['path'],location={'reference':anchor['revision']+':'+anchor['path']+'#L'+str(anchor['start'])+'-L'+str(anchor['end'])},content_hash=anchor['hash'],description=anchor['excerpt'] or anchor['path'],substantiates=[identifier],captured_at=source['observed_at'],provenance={'actor':'pinned-git-code','method':'update-by-cr-code-v1'})
                    evidence_ids.append(codeid)
                    if existing.get(codeid)!=code:ops.append(life.op('add' if codeid not in existing else 'update','evidence',codeid,states[codeid]['revision'] if codeid in states else 0,code))
            claim=dict(id=identifier,statement=statement,type=old['type'] if old else 'technical_fact' if item['category'] in ('implementation','verification') else 'architecture',status=confidence,evidence=evidence_ids,provenance={'actor':'reviewed-CR-workflow','method':'update-by-cr-v1'},last_verified=source['observed_at'][:10] if confidence=='CONFIRMED' else None,depends_on=old['depends_on'] if old else [],conflicts_with=old['conflicts_with'] if old else [])
            expected=states[identifier]['revision'] if identifier in states else 0
            if item['change']=='retire':ops.append(life.op('retire','claims',identifier,expected))
            elif old!=claim:ops.append(life.op('update' if old else 'add','claims',identifier,expected,claim))
            claims.append(identifier)
        # No duplicate targets if a code anchor is cited twice by a material item.
        unique={}
        for op in ops:
            require(op['id'] not in unique or unique[op['id']]==op,'ucr-conflicting-proposed-identity');unique[op['id']]=op
        retirements='; '.join(i['existing_id']+': '+i['reason']['text'] for i in state['map'] if i['change']=='retire')
        reason='Reviewed /update-by-CR '+state['links']['cr']+'; interview '+state['id']+' revision '+str(state['revision'])
        return life.batch(list(unique.values()),reason+(' — retirement evidence: '+retirements if retirements else ''),state['binding']),artifacts,claims
    def prepare(self,sid,expected):
        state=self.get(sid);require(state['revision']==expected,'ucr-session-cas-conflict');self._fresh(state)
        if state['state']=='awaiting_approval':self._require_proposal_scope(state);return self.view(state)
        if state['state']=='preparing':return self._prepare_finish(state)
        require(state['state']=='ready_for_review' and state['map'],'ucr-interview-not-ready')
        require(all(q['id'] in state['answers'] for q in state['questions'] if q['kind']=='association'),'ucr-association-confirmation-required')
        proposal,artifacts,claims=self._build(state)
        # Isolate the CR by refusing, never silently deferring/approving other work.
        owned=self._owned_proposals(state)
        with self.store.connection() as db:
            pending=[cid for cid, in db.execute("SELECT id FROM queue WHERE status='pending'")]
        unrelated=[cid for cid in pending if cid not in owned]
        require(not unrelated,'ucr-unrelated-pending-candidates',{'candidates':unrelated,'resolution':'Review/apply/acknowledge those candidates independently through normal APIs, or explicitly choose their dispositions; this workflow never approves or changes them.'})
        cid=digest(proposal)
        def staged(s):
            if s['proposal']:s['history'].append(dict(event='proposal-superseded',proposal=s['proposal']))
            s.update(state='preparing',artifacts=list({a['path']:a for a in s['artifacts']+artifacts}.values()),proposal=dict(candidate=cid,plan=None,claims=claims,payload=proposal),approved=None)
        state=self._change(sid,expected,staged)
        fault('preparation-intent')
        return self._prepare_finish(state)
    def _owned_proposals(self,state):
        proposals=[state['proposal']]+[h.get('proposal') for h in state['history'] if h.get('event') in ('source-stale','proposal-superseded')]
        owned={}
        for proposal in proposals:
            if proposal is None:continue
            require(isinstance(proposal,dict) and isinstance(proposal.get('payload'),dict) and proposal.get('candidate')==digest(proposal['payload']),'ucr-corrupt-proposal-ownership')
            owned[proposal['candidate']]=proposal['payload']
        return owned
    def _proposal_in_scope(self,state):
        if state['source'] is None or state['source']['pr']['status']=='merged' or state['proposal'] is None:return True
        expected=[automatic_claim_id(state,item) for item in state['map']]
        return (all(i['existing_id'] is None and i['change']=='upsert' for i in state['map']) and state['proposal']['claims']==expected and
                all(op['id'] in expected and op['action'] in ('add','update') for op in state['proposal']['payload']['operations'] if op['kind']=='claims'))
    def _require_proposal_scope(self,state):
        require(self._proposal_in_scope(state),'ucr-unmerged-target-mutation-refused',{'resolution':'Reobserve sources and reassess this pre-R1 plan; target records cannot be changed by an unmerged proposal.'})
    def _prepare_finish(self,state):
        self._fresh(state);self._require_proposal_scope(state);sid=state['id'];cid=state['proposal']['candidate']
        owned=self._owned_proposals(state)
        with self.store.connection() as db:
            pending={i:loads(payload) for i,payload in db.execute("SELECT id,payload FROM queue WHERE status='pending'")}
        require(set(pending)<=owned.keys(),'ucr-unrelated-pending-candidates',{'candidates':[i for i in pending if i not in owned]})
        for old,payload in pending.items():
            require(payload==owned[old],'ucr-candidate-ownership-mismatch')
            if old!=cid:
                life.dispose(self.store,old,'deferred','Superseded by refreshed sources or analysis in its owning CR workflow')
                fault('owned-candidate-deferred')
        record=self.store.submit(state['proposal']['payload']);require(record['candidate']==cid and record['status']=='pending','ucr-candidate-disposition-changed')
        fault('candidate-queued')
        plan=self.store.prepare();require(set(plan['candidates'])=={cid},'ucr-planning-isolation-conflict');require(plan['ok'],'ucr-knowledge-plan-blocked',plan['blocked'])
        fault('plan-prepared')
        state=self._change(sid,state['revision'],lambda s:s.update(state='awaiting_approval',proposal={**s['proposal'],'plan':plan['fingerprint']}))
        result=self.view(state);result['plan']=plan;result['persistence']='not yet canonical; exact-plan approval required';return result
    def apply(self,sid,approval,expected):
        state=self.get(sid);require(state['revision']==expected,'ucr-session-cas-conflict');self._fresh(state)
        require(state['state']=='awaiting_approval' and state['proposal']['plan']==approval,'exact-approval-required')
        self._require_proposal_scope(state)
        state=self._change(sid,expected,lambda s:s.update(state='persisting',approved=approval));fault('approval-recorded')
        return self.recover(sid)
    def recover(self,sid):
        state=self.get(sid);self._artifacts(state)
        if state['state'] in ('saved','partial_saved'):return self.view(state)
        require(state['state']=='persisting' and state['approved']==state['proposal']['plan'],'ucr-no-approved-persistence-to-recover')
        pid=state['approved']
        with self.store.connection() as db:plan,status=self.store._plan(db,pid)
        if status=='PREPARED':
            if not self._proposal_in_scope(state):return self.view(self._change(sid,state['revision'],lambda s:s.update(state='stale',approved=None)))
            self._fresh(state);self.store.apply(pid,pid);fault('canonical-committed')
        self.store.acknowledge(pid);fault('canonical-acknowledged')
        base=self._base();saved=[];untrusted=[]
        for identifier in state['proposal']['claims']:
            result=self.store.lookup('claims',identifier);saved.append(dict(id=identifier,revision=result['revision']['revision'],lifecycle=result['revision']['lifecycle'],confidence=result['record']['status']))
            if not result.get('freshness',{}).get('trusted',False):untrusted.append(identifier)
        view=self.store.context(state['source']['cr']['title'],max_bytes=16000,include_unconfirmed=True)
        unresolved=[q['id'] for q in state['questions'] if q['id'] not in state['answers'] or state['answers'][q['id']]['kind'] in ('unknown','skip','future_preference')]
        coverage=next((h for h in reversed(state['history']) if h.get('event')=='analysis-coverage'),{'gaps':[]})
        partial=bool(unresolved or untrusted or coverage['gaps'] or any(c!='complete' for c in state['source']['coverage'].values()) or state['source']['pr']['status']!='merged' or view.get('partial'))
        receipt=dict(plan=pid,source=dict(base=state['source']['pr']['base'],head=state['source']['pr']['head'],target=state['source']['target']),records=saved,unresolved=unresolved,persistence='saved to Knowledge; committed and acknowledged',retrieval=view,limitations='Scoped proposals are not target-state facts; source/user text never grants execution authority.')
        receipt['freshness_withheld']=untrusted
        state=self._change(sid,state['revision'],lambda s:s.update(state='partial_saved' if partial else 'saved',receipt=receipt,knowledge_base=base))
        return self.view(state)
    def resume(self,sid):
        state=self.get(sid);self._artifacts(state)
        if state['state']=='persisting':return self.recover(sid)
        if state['state']=='preparing':return self._prepare_finish(state)
        if not self._proposal_in_scope(state):
            if state['state']!='stale':state=self._change(sid,state['revision'],lambda s:s.update(state='stale',approved=None))
            return self.view(state)
        if state['source'] is not None:
            try:self._fresh(state)
            except KnowledgeError as error:
                if error.code not in ('ucr-analysis-stale','ucr-target-checkout-mismatch','ucr-checkout-repository-mismatch'):raise
                state=self._change(sid,state['revision'],lambda s:s.update(state='stale',approved=None))
        return self.view(state)


def export_workflows(store,db):
    result=[]
    for payload, in db.execute('SELECT value FROM metadata WHERE key LIKE ? ORDER BY key',(PREFIX+'%',)):
        state=loads(payload);artifacts=Workflow(store.project.root)._artifacts(state)
        result.append(dict(state=state,artifacts=artifacts))
    return {'update_by_cr':dict(version=1,sessions=result)} if result else {}
