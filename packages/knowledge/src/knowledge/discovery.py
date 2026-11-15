"""Bounded lexical .NET capability pack. Source is data; no build hooks execute."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
from .util import canonical_json, digest, fingerprint, loads, require, KnowledgeError
from .project import safe_path
from . import lifecycle as life

VERSION='dotnet-lexical-v3'
LEGACY_METHODS={'dotnet-lexical-v1','dotnet-lexical-v2'}
DISCOVERY_METHODS=LEGACY_METHODS|{VERSION}
EXCLUDED={'.git','.knowledge','.ai','.venv','.local','node_modules','vendor','packages','bin','obj','dist','build','.vs','TestResults'}
SUFFIXES={'.cs','.csproj','.props','.targets','.sln','.json','.md','.yaml','.yml','.xml','.config'}
LIMIT=512000


def has_git(root):
    return any((p/'.git').exists() for p in (Path(root),*Path(root).parents))

def git_process(root,*args,input=None):
    try:return subprocess.run(['git','-C',str(root),*args],input=input,capture_output=True,timeout=15,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0','GIT_TERMINAL_PROMPT':'0'})
    except subprocess.TimeoutExpired as e:raise KnowledgeError('git-operation-timeout') from e
    except FileNotFoundError as e:raise KnowledgeError('git-unavailable-for-existing-checkout') from e

def git(root,*args,required=False):
    if not has_git(root):
        require(not required,'invalid-git-range-or-checkout');return None
    p=git_process(root,*args)
    if required:require(p.returncode==0,'invalid-git-range-or-checkout')
    return p.stdout.decode('utf-8','replace').strip() if p.returncode==0 else None


def inventory(root,base=None,head=None):
    root=Path(root); files={}; excluded=[];repo=has_git(root);blobs={}
    object_format=git(root,'rev-parse','--show-object-format',required=True) if repo else 'sha1'
    require(object_format in ('sha1','sha256'),'unsupported-git-object-format')
    for folder,dirs,names in os.walk(root,followlinks=False):
        parent=Path(folder)
        for name in list(dirs):
            p=parent/name
            if name in EXCLUDED or p.is_symlink() or p.is_junction() or name.startswith('.'):
                excluded.append({'path':p.relative_to(root).as_posix(),'status':'excluded','reason':'dependency/generated/hidden or linked directory'})
                dirs.remove(name)
        for name in names:
            p=parent/name; rel=p.relative_to(root).as_posix()
            if p.is_symlink() or p.suffix.lower() not in SUFFIXES or re.search(r'(?i)(secret|credential|\.env|appsettings\.(?!json)|\.g\.cs|\.designer\.cs)',name):
                excluded.append({'path':rel,'status':'excluded','reason':'binary/unsupported/generated/credential-risk'});continue
            try:
                safe_path(p)
                with p.open('rb') as source:data=source.read(LIMIT+1)
                if repo:blobs[rel]=hashlib.new(object_format,b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
                text=data.decode('utf-8-sig')
                require(len(data)<=LIMIT,'source-too-large')
                files[rel]={'hash':'sha256:'+hashlib.sha256(data).hexdigest(),'status':'not-analyzed','partition':'.','bytes':len(data)}
                if p.suffix.lower() in ('.csproj','.props','.targets'):
                    try:
                        project_xml=ET.fromstring(text)
                        custom=any((node.tag.rsplit('}',1)[-1]=='Compile' and 'Include' in node.attrib) or node.tag.rsplit('}',1)[-1] in ('Import','EnableDefaultCompileItems') for node in project_xml.iter())
                        sdk=project_xml.attrib.get('Sdk','')
                        if custom or (p.suffix.lower()=='.csproj' and not sdk.startswith('Microsoft.NET.Sdk')):
                            files[rel]['negative_scope_reason']='custom source inclusion/import/SDK requires manual coverage validation'
                    except ET.ParseError:files[rel]['negative_scope_reason']='invalid project/source-inclusion XML'

            except (OSError,UnicodeError,ValueError):
                files[rel]={'hash':None,'status':'blocked','partition':'.','reason':'unreadable, non-UTF8 or oversized source'}
    projects=[p for p in files if p.endswith('.csproj')]
    for p,item in files.items():
        ancestors=[proj for proj in projects if Path(proj).parent==Path(p).parent or Path(proj).parent in Path(p).parents]
        if ancestors:
            depth=max(len(Path(proj).parent.parts) for proj in ancestors)
            nearest=sorted(proj for proj in ancestors if len(Path(proj).parent.parts)==depth)
            item['partition']=p if p.endswith('.csproj') else nearest[0]
            item['partition_ambiguous']=not p.endswith('.csproj') and len(nearest)>1
    revision=git(root,'rev-parse','--verify','HEAD')
    delta=None
    if base or head:
        require(base is not None and head is not None,'base-and-head-required')
        b=git(root,'rev-parse','--verify',base+'^{commit}',required=True);h=git(root,'rev-parse','--verify',head+'^{commit}',required=True)
        require(h==revision,'checkout-requested-head-first')
        git(root,'merge-base','--is-ancestor',b,h,required=True)
        delta={'base':b,'head':h,'committed':git(root,'diff','--name-status','-M',b,h,required=True)}
    dirty_raw=git_process(root,'status','--porcelain=v1','-z','--untracked-files=all') if repo else subprocess.CompletedProcess([],128,b'',b'')
    dirty=[]
    fields=dirty_raw.stdout.decode('utf-8','replace').split('\0');index=0
    while index<len(fields):
        item=fields[index];index+=1
        if len(item)<4:continue
        status=item[:2];path=item[3:]
        original=None
        if 'R' in status or 'C' in status:
            original=fields[index];index+=1
        allowed=path in files or (status.strip()=='D' and Path(path).suffix in SUFFIXES and not any(p in EXCLUDED or p.startswith('.') for p in Path(path).parts))
        if allowed:dirty.append({'path':path,'status':status,'original':original})
    dirty=sorted(dirty,key=lambda x:x['path'])
    index_raw=git_process(root,'ls-files','--stage','-z') if repo else subprocess.CompletedProcess([],128,b'',b'')
    index_blobs={}
    for entry in index_raw.stdout.decode('utf-8','replace').split('\0'):
        if '\t' not in entry:continue
        meta,path=entry.split('\t',1)
        if path in files:
            index_blobs.setdefault(path,[]).append(meta)
            if not meta.endswith(' 0'):
                files[path].update(status='blocked',reason='unmerged Git index requires resolution')

    if revision:
        head_raw=git_process(root,'ls-tree','-r','-z',revision);require(head_raw.returncode==0,'invalid-git-range-or-checkout')
        head_blobs={}
        for entry in head_raw.stdout.decode('utf-8','replace').split('\0'):
            if '\t' in entry:
                meta,path=entry.split('\t',1);head_blobs[path]=meta.split()[-1]
        dirty_paths={d['path'] for d in dirty}
        ignored_raw=git_process(root,'check-ignore','--stdin','-z',input=b''.join(p.encode('utf-8')+b'\0' for p in files))
        ignored_paths=set(ignored_raw.stdout.decode('utf-8','replace').split('\0'))
        for path,entry in files.items():
            blob=blobs.get(path)
            indexed=index_blobs.get(path,[])
            if entry['hash'] is None:
                entry.update(git_state='unverifiable',head_blob=head_blobs.get(path));continue
            if path not in head_blobs or blob!=head_blobs[path] or path in dirty_paths:
                ignored=path in ignored_paths
                entry['git_state']='ignored' if ignored else 'untracked' if not indexed else 'staged-or-unstaged'
                if path not in dirty_paths:dirty.append({'path':path,'status':'!!' if ignored else '??' if not indexed else ' M','original':None})
            else:entry['git_state']='committed'
            entry['head_blob']=head_blobs.get(path)
        dirty.sort(key=lambda d:d['path'])
    core={'index_blobs':index_blobs,'policy':{'excluded_dirs':sorted(EXCLUDED),'suffixes':sorted(SUFFIXES),'max_file_bytes':LIMIT},'extractor':VERSION,'files':{p:{k:v for k,v in item.items() if k!='status'} for p,item in sorted(files.items())},'exclusions':sorted(excluded,key=lambda x:x['path']), 'revision':revision,'dirty':dirty}
    return {'identity':digest(core),**core,'files':files,'delta':delta,'snapshot_kind':'working-tree-with-hashes' if dirty else 'committed' if revision else 'filesystem-no-history'}


def extract(root,path,entry):
    text=(Path(root)/path).read_text(encoding='utf-8-sig');lines=text.splitlines(); project=entry['partition']
    project_name=(Path(project).stem+' ['+project+']') if project!='.' else 'root [.]'
    observations=[]
    scope_unsupported=entry.get('partition_ambiguous',False)
    def emit(category,key,statement,line,subject):
        anchor=lines[line-1].strip()
        identifier='scan.'+digest(['identity-v3',project,category,key])[:32]
        observations.append(dict(id=identifier,category=category,project=project,path=path,line=line,anchor=anchor,
                                 statement=statement,subject=subject,legacy_id='scan.'+digest([Path(project).stem if project!='.' else 'root',category,key.split('.')[-1].split('`')[0] if category=='declaration' else key])[:32],method=VERSION,content_hash=entry['hash'],unsupported=scope_unsupported))
    if path.endswith('.csproj'):
        try: tree=ET.fromstring(text)
        except ET.ParseError:return [],'partial','invalid project XML'
        xml_code=re.sub(r'<!--.*?-->',lambda m:''.join('\n' if c=='\n' else ' ' for c in m[0]),text,flags=re.S)
        for index,line in enumerate(xml_code.splitlines(),1):
            if '<Project ' in line:emit('project','project',f'{project_name} declares a .NET project using {tree.attrib.get("Sdk","an unspecified SDK")}.',index,project_name)
            for tag in ('ProjectReference','PackageReference'):
                m=re.search(r'<'+tag+r'\b[^>]*Include="([^"]+)"',line)
                if m:emit('dependency',tag+':'+m[1],f'{project_name} declares {tag} {m[1]}.',index,m[1])
        return observations,'analyzed',None
    if path.endswith('.cs'):
        code,literals=csharp_masks(text)
        contexts=declaration_contexts(code)
        namespace_pattern=r'\bnamespace\s+((?:[^\W\d]|_)\w*(?:\.(?:[^\W\d]|_)\w*)*)\s*([;{])'
        if len(re.findall(r'\bnamespace\b',code))!=len(re.findall(namespace_pattern,code)):
            scope_unsupported=True
        offset=0
        literal_lines=literals.splitlines()
        for index,line in enumerate(code.splitlines(keepends=True),1):
            for m in re.finditer(r'\b(class|interface|record)\s+(\w+)(?:\s*<[^>]+>)?\s*(?::\s*([^\{]+))?',line):
                kind,name,bases=m.groups();bases=(bases or '').strip()
                qualified=contexts.get(offset+m.start(),name)
                emit('declaration',qualified,f'{project_name} declares {kind} {qualified}'+(f' with declared bases {bases}' if bases else '')+'.',index,name)
                if re.search(r'\bpartial\s*$',line[:m.start()]) or (kind=='record' and name in ('class','struct')):observations[-1]['unsupported']=True
            for m in re.finditer(r'\bAdd(Scoped|Singleton|Transient)\s*<([^>]+)>',line):
                emit('wiring',m[2].split(',')[0].strip(),f'{project_name} contains Add{m[1]}<{m[2]}> registration syntax.',index,m[2].split(',')[0].strip())
            for m in re.finditer(r'\b(MapGet|MapPost|MapPut|MapDelete|Route|HttpGet|HttpPost|HttpPut|HttpDelete)\s*\(\s*"([^"]*)"',literal_lines[index-1]):
                if not line[m.start():m.start()+1].strip():continue
                emit('routing',Path(path).stem+':'+m[1]+':'+m[2],f'{project_name} declares {m[1]} route literal "{m[2]}" in {Path(path).stem}.',index,m[2])
            for m in re.finditer(r'\b(AddDbContext|UseSqlServer|UseSqlite|GetConnectionString)\s*(?:<([^>]+)>)?\s*\(',line):
                emit('persistence',Path(path).stem+':'+m[1]+':'+str(m[2]),f'{project_name} contains {m[1]}'+(f'<{m[2]}>' if m[2] else '')+' persistence/configuration syntax.',index,m[2] or m[1])
            offset+=len(line)
        return observations,'partial','lexical extraction only; no Roslyn symbol resolution, preprocessor or runtime proof'
    return [],'partial','inventory/content hash only; semantic extractor unavailable for this file type'


def fresh_evidence(root,e,scope=None):
    path=e.get('source'); path=path.get('reference') if isinstance(path,dict) else path
    location=e.get('location','');location=location.get('reference','') if isinstance(location,dict) else location
    if not e.get('content_hash') or not isinstance(path,str):return 'not-verifiable'
    p=Path(path)
    if p.is_absolute() or '..' in p.parts:return 'not-verifiable'
    p=Path(root)/p
    try:safe_path(p)
    except (KnowledgeError,OSError):return 'not-verifiable'
    if not p.is_file() or p.is_symlink():return 'missing'
    try:
        with p.open('rb') as source:data=source.read(LIMIT+1)
        if len(data)>LIMIT:return 'not-verifiable'
        method=e.get('provenance',{}).get('method')
        if method in DISCOVERY_METHODS:
            # Re-extract syntax before trusting unchanged hashes or surviving lines:
            # an old v1 false positive or a newly commented anchor is not current.
            if method in LEGACY_METHODS:return 'legacy-identity-review-required'
            scope=scope if scope is not None else analysis_scope(root)
            if not scope.get('complete',True):return 'not-analyzed'
            observations=scope['observations']
            if any(i in scope['ambiguous'] for i in e['substantiates']):return 'ambiguous-identity'
            if not any(o['id'] in e['substantiates'] and o['path']==p.relative_to(root).as_posix() and o['anchor']==e['description'] for o in observations):return 'changed'
        if 'sha256:'+hashlib.sha256(data).hexdigest()==e['content_hash']:return 'unchanged'
        if method in DISCOVERY_METHODS and e['description'] in [line.strip() for line in data.decode('utf-8-sig').splitlines()]:return 'anchor-valid-file-changed'
    except (OSError,UnicodeError):return 'not-verifiable'
    return 'changed'


def freshness(root,claim,records,scope=None):
    evidence={e['id']:e for e in records['evidence']}
    results={i:fresh_evidence(root,evidence[i],scope) for i in claim['evidence'] if i in evidence}
    trusted=bool(results) and all(v in ('unchanged','anchor-valid-file-changed') and evidence[i]['status']=='active' for i,v in results.items())
    return {'trusted':trusted,'evidence':results,'policy':'all supporting evidence current; confidence unchanged'}


def proposal(store,db,obs,snapshot,captured,records,states,scope=None):
    from .store import empty
    current={r['id']:r for r in records['claims']};known=current.get(obs['id'])
    if known and states[obs['id']]['lifecycle']=='active' and known['statement']==obs['statement'] and freshness(store.project.root,known,records,scope)['trusted']:return None
    if known and (not discovery_owned(db,known,records)):
        # A reviewed meaning is not automatically overwritten by a lexical re-observation.
        return None
    if known and states[obs['id']]['lifecycle']=='superseded':return None
    eid='evidence.'+digest([obs['id'],obs['path'],obs['content_hash'],obs['anchor']])
    evidence=dict(id=eid,type='direct-technical',status='active',source=obs['path'],location=obs['path']+'#L'+str(obs['line']),content_hash=obs['content_hash'],
                  description=obs['anchor'],substantiates=[obs['id']],captured_at=captured,provenance=dict(actor='deterministic-discovery',method=VERSION))
    claim=dict(id=obs['id'],statement=obs['statement'],type='technical_fact',status='CONFIRMED',evidence=[eid],
               provenance=dict(actor='deterministic-discovery',method=VERSION),last_verified=captured[:10],depends_on=[],conflicts_with=[])
    if known:
        # Re-observation does not authorize promotion or loss of reviewed graph state.
        claim.update(status=known['status'],type=known['type'],depends_on=list(known['depends_on']),
                     conflicts_with=list(known['conflicts_with']),provenance=dict(known['provenance']))
        if known['status']!='CONFIRMED':claim['last_verified']=known['last_verified']
        evidence_by_id={e['id']:e for e in records['evidence']}
        claim['evidence'].extend(i for i in known['evidence'] if evidence_by_id[i]['provenance']['method'] not in DISCOVERY_METHODS)
    ops=[]
    if not db.execute('SELECT 1 FROM records WHERE id=?',(eid,)).fetchone():ops.append(life.op('add','evidence',eid,0,evidence))
    ops.append(life.op('reactivate' if known and states[obs['id']]['lifecycle']=='retired' else 'update' if known else 'add','claims',obs['id'],life.revision(db,obs['id']),claim))
    return life.batch(ops,'Source-backed lexical observation; not runtime or business semantics',{'identity':snapshot['identity'],'revision':snapshot['revision'],'kind':snapshot['snapshot_kind']})


def scan(store,scan_id=None,max_files=50,base=None,head=None,restart=False):
    require(type(max_files) is int and 1<=max_files<=10000,'invalid-scan-bound')
    snap=inventory(store.project.root,base,head)
    with store.connection(True) as db:
        require(life.enabled(db),'upgrade-required')
        if scan_id and not restart:
            row=db.execute('SELECT payload FROM scans WHERE id=?',(scan_id,)).fetchone();require(row is not None,'unknown-scan')
            state=loads(row[0]);require(state['snapshot']['identity']==snap['identity'],'stale-scan-restart-required')
            require(state['extractor']==VERSION,'stale-extractor-restart-required')
            if base or head:require(state['snapshot']['delta']==snap['delta'],'scan-range-mismatch-restart-required')
        else:
            scan_id=digest([store.project.identity,snap['identity'],snap['delta'],VERSION])
            row=db.execute('SELECT payload FROM scans WHERE id=?',(scan_id,)).fetchone()
            state=loads(row[0]) if row else dict(id=scan_id,extractor=VERSION,snapshot=snap,coverage=deep_files(snap['files']),observations=[],candidates=[],captured_at=life.now(),complete=False)
        pending=sorted((p for p,e in state['coverage'].items() if e['status']=='not-analyzed'),key=lambda p:(not p.endswith(('.csproj','.cs')),p))
        extracted_this_call=[]
        for path in pending[:max_files]:
            observations,status,reason=extract(store.project.root,path,state['coverage'][path])
            extracted_this_call.append(path)
            # Ambiguous identities from overloads/duplicate declarations are gaps, never guessed.
            existing={o['id'] for o in state['observations']}
            ambiguous=set(state.get('ambiguous',[]))
            for o in observations:
                prior=next((prior for prior in state['observations'] if prior['id']==o['id']),None)
                if prior and equivalent_occurrence(prior,o):
                    prior.setdefault('occurrences',[occurrence(prior)]).append(occurrence(o))
                    continue
                if o['id'] in existing or o['id'] in ambiguous or o.get('unsupported'):
                    ambiguous.add(o['id'])
                    state['observations']=[prior for prior in state['observations'] if prior['id']!=o['id']]
                    state.setdefault('gaps',[]).append({'id':o['id'],'reason':'ambiguous lexical identity: all members withheld','path':path});continue
                existing.add(o['id']);state['observations'].append(o)
            state['ambiguous']=sorted(ambiguous)
            state['coverage'][path].update(status=status,reason=reason)
        state['complete']=not any(e['status'] in ('not-analyzed','blocked') for e in state['coverage'].values())
        # The durable snapshot-bound chunks already contain global ambiguity state.
        # Do not re-extract completed or not-yet-budgeted files for this scan.
        scope={'snapshot':state['snapshot'],'observations':state['observations'],
               'ambiguous':dict.fromkeys(state.get('ambiguous',[])), 'complete':state['complete']}
        state['work']={'version':1,'extracted_this_call':len(extracted_this_call),'paths_this_call':extracted_this_call,
                       'durable_extracted_files':sum(e['status'] not in ('not-analyzed','blocked') for e in state['coverage'].values()),
                       'remaining_files':sum(e['status']=='not-analyzed' for e in state['coverage'].values()),
                       'enumeration_and_hashing':'whole-snapshot; distinct from bounded extraction'}
        records=store._records(db)
        changed={e['id'] for e in records['evidence'] if fresh_evidence(store.project.root,e,scope) not in ('unchanged','anchor-valid-file-changed')}
        owners={c['id'] for c in records['claims'] if changed.intersection(c['evidence'])}
        closure=set(owners)
        while True:
            expanded=closure|{c['id'] for c in records['claims'] if closure.intersection(c['depends_on'])}
            if expanded==closure:break
            closure=expanded
        state['impact']={'changed_or_unverifiable_evidence':sorted(changed),'direct_claims':sorted(owners),
                         'dependent_claims':sorted(closure-owners),
                         'relationships':[r['id'] for r in records['relationships'] if r['from'] in closure or r['to'] in closure],
                         'policy':('completed included scope reused' if state['complete'] else 'partial durable scope; unexamined discovery evidence is not freshly verified')+'; impact is a review request, not retirement'}
        state['semantic_coverage_complete']=False
        state['limits']=['No runtime/deployment proof or business rationale','C# lexical matches are partial, not compiler analysis','Non-code files are content inventory only','Untracked permitted source is included with dirty hashes; Git dirty state is separate from committed HEAD']
        # Enqueue only at completion: partial scan observations remain durable, no claim of absence.
        if state['complete']:
            records=store._records(db);states=life.latest(db)
            signatures={proposal_identity(loads(p)) for p, in db.execute('SELECT payload FROM queue') if loads(p)['version']==2}
            state['compatibility']=[]
            state['reintroductions']=[]
            state['review_required']=[]
            for obs in state['observations']:
                known=next((c for c in records['claims'] if c['id']==obs['id']),None)
                if known and (states[known['id']]['lifecycle']=='superseded' or not discovery_owned(db,known,records)):
                    state['review_required'].append({'id':known['id'],'reason':'supersession or reviewed assertion ownership requires manual review; no automatic overwrite/reactivation'})
                legacy=[c for c in records['claims'] if c['provenance']['method'] in LEGACY_METHODS and states[c['id']]['lifecycle']=='active' and (c['id']==obs['legacy_id'] or c['statement']==obs['statement'])]
                if legacy:
                    state['compatibility'].append({'observation':obs,'legacy_ids':[c['id'] for c in legacy],'reason':'identity-v3 requires explicit reviewed migration; no automatic reassignment'})
                    continue
                value=proposal(store,db,obs,snap,state['captured_at'],records,states,scope)
                if value:
                    if any(o['action']=='reactivate' for o in value['operations']):
                        state['reintroductions'].append({'id':obs['id'],'expected_revision':states[obs['id']]['revision'],
                            'relationships':[r['id'] for r in records['relationships'] if obs['id'] in (r['from'],r['to'])],
                            'policy':'explicit fresh approval required; relationships and superseded successors are not automatically restored'})
                    cid=digest(value)
                    # Repeated scans retain disposition; compare unchanged operation payloads even if snapshot differs.
                    if proposal_identity(value) not in signatures:
                        signatures.add(proposal_identity(value))
                        db.execute('INSERT OR IGNORE INTO queue VALUES (?,?,?,NULL)',(cid,canonical_json(value),'pending'))
                        state['candidates'].append(cid)
        require(inventory(store.project.root)['identity']==snap['identity'],'source-changed-during-scan-restart')
        db.execute('INSERT OR REPLACE INTO scans VALUES (?,?)',(scan_id,canonical_json(state)))
    return {'ok':True,**state}


def deep_files(files):
    return {p:dict(v) for p,v in files.items()}


def reconcile(store,scan_id):
    with store.connection() as db:
        require(life.enabled(db),'upgrade-required')
        row=db.execute('SELECT payload FROM scans WHERE id=?',(scan_id,)).fetchone();require(row is not None,'unknown-scan')
        scan=loads(row[0]);require(inventory(store.project.root)['identity']==scan['snapshot']['identity'],'stale-scan-restart-required')
        records=store._records(db);states=life.latest(db);out=[]
        scope=analysis_scope(store.project.root,snapshot=scan['snapshot'])
        observed={o['id']:o for o in scan['observations']}
        for c in records['claims']:
            fresh=freshness(store.project.root,c,records,scope)
            classification='unchanged' if fresh['trusted'] else 'not-verifiable'
            if states[c['id']]['lifecycle']!='active':classification='historical'
            elif not fresh['trusted'] and c['id'] in observed:classification='changed'
            elif not fresh['trusted'] and c['provenance']['method'] in DISCOVERY_METHODS:classification='suspected-obsolete'
            dependents=[d['id'] for d in records['claims'] if c['id'] in d['depends_on']]
            out.append(dict(id=c['id'],classification=classification,freshness=fresh,lifecycle=states[c['id']]['lifecycle'],dependents=dependents,
                            retirement_proposed=False,reason='Retirement requires reviewed positive corroboration; lexical absence alone is insufficient.'))
        retirement=[]
        current={c['id']:c for c in records['claims']}
        negative_gaps=negative_coverage_gaps(scan['snapshot'])
        delta=scan['snapshot'].get('delta')
        if scan['complete'] and delta and not scan.get('gaps'):
            before={}
            for payload, in db.execute('SELECT payload FROM scans'):
                old=loads(payload)
                if old['snapshot']['revision']==delta['base'] and old['complete']:
                    before.update({o['id']:o for o in old['observations']})
            texts='\n'.join((store.project.root/p).read_text(encoding='utf-8-sig') for p,e in scan['coverage'].items() if e['status']!='blocked')
            for row in out:
                old=before.get(row['id'])
                if not old or row['id'] in observed or row['lifecycle']!='active':continue
                claim=current[row['id']]
                if old.get('method')!=VERSION or claim['provenance']!={'actor':'deterministic-discovery','method':VERSION} or claim['statement']!=old['statement']:
                    row.update(classification='not-verifiable',reason='Current reviewed meaning/ownership does not match the source assertion; manual review required.')
                    continue
                relevant=[g for g in negative_gaps if g['project']==old['project']]
                if relevant:
                    row.update(classification='not-verifiable',reason='Excluded/unsupported source prevents negative evidence proof.',coverage_gaps=relevant)
                    continue
                # Before/after exact source proof + complete lexical inventory + reference/consumer search.
                raw=subprocess.run(['git','-C',str(store.project.root),'show',delta['base']+':'+old['path']],capture_output=True)
                if raw.returncode or 'sha256:'+hashlib.sha256(raw.stdout).hexdigest()!=old['content_hash']:continue
                if re.search(r'(?<![A-Za-z0-9_])'+re.escape(old['subject'])+r'(?![A-Za-z0-9_])',texts):continue
                row.update(classification='proposed-retirement',retirement_proposed=True,
                           reason='Verified base source contained this lexical declaration; current full lexical inventory and consumers no longer contain its subject. No claim about external deployment.')
                retirement.append(life.op('retire','claims',row['id'],life.revision(db,row['id'])))
            retiring={o['id'] for o in retirement}
            for r in records['relationships']:
                if states[r['id']]['lifecycle']=='active' and (r['from'] in retiring or r['to'] in retiring):
                    retirement.append(life.op('retire','relationships',r['id'],life.revision(db,r['id'])))
        proposal=life.batch(retirement,'Reviewed source removal corroborated by before/after and consumer inventory',
                            {'identity':scan['snapshot']['identity'],'revision':scan['snapshot']['revision'],'kind':scan['snapshot']['snapshot_kind'],'delta':delta}) if retirement else None
        return {'ok':True,'scan':scan_id,'complete':scan['complete'],'claims':out,'source':scan['snapshot'],'canonical_unchanged':True,'negative_evidence_gaps':negative_gaps,'proposal':proposal}


def status(store,scan_id=None):
    with store.connection() as db:
        require(life.enabled(db),'upgrade-required')
        rows=[loads(p) for p, in db.execute('SELECT payload FROM scans')]
        return {'ok':True,'scans':[r for r in rows if scan_id is None or r['id']==scan_id]}


def proposal_identity(value):
    from copy import deepcopy
    operations=deepcopy(value['operations'])
    for change in operations:
        if change['payload']:
            change['payload'].pop('captured_at',None)
            change['payload'].pop('last_verified',None)
    return digest(operations)


def csharp_masks(text):
    """Keep offsets/newlines: code masks literals+comments; literals masks comments.

    Interpolation contents are conservatively opaque. Normal, verbatim, raw
    strings and character literals cannot manufacture declarations or comments.
    """
    code=list(text);literals=list(text);length=len(text);i=0
    def blank(start,end,comment=False):
        for k in range(start,end):
            if text[k] not in '\r\n':
                code[k]=' '
                if comment:literals[k]=' '
    while i<length:
        if text.startswith('//',i):
            end=text.find('\n',i+2);end=length if end<0 else end
            blank(i,end,True);i=end;continue
        if text.startswith('/*',i):
            end=text.find('*/',i+2);end=length if end<0 else end+2
            blank(i,end,True);i=end;continue
        if text[i] not in ('"',"'"):i+=1;continue
        start=i;quote=text[i]
        count=1
        while i+count<length and text[i+count]==quote:count+=1
        if quote=='"' and count>=3:
            end=text.find('"'*count,i+count);i=length if end<0 else end+count
        else:
            verbatim=quote=='"' and (i>0 and text[i-1]=='@' or i>1 and text[i-2:i]=='@$')
            i+=1
            while i<length:
                if verbatim and text.startswith('""',i):i+=2;continue
                if not verbatim and text[i]=='\\':i+=2;continue
                if text[i]==quote:i+=1;break
                i+=1
            i=min(i,length)
        blank(start,i)
    return ''.join(code),''.join(literals)


def declaration_contexts(code):
    """Qualified lexical type identity; no compiler binding is claimed.

    Partial declarations with the same qualified identity are withheld as a group.
    Braces in strings/comments have already been masked.
    """
    token=re.compile(r'\bnamespace\s+((?:[^\W\d]|_)\w*(?:\.(?:[^\W\d]|_)\w*)*)\s*([;{])|\b(class|interface|record)\s+(\w+)(?:\s*<([^>]+)>)?|[{}]')
    stack=[];file_namespace='';pending=None;result={}
    for m in token.finditer(code):
        if m[1]:
            if m[2]==';':file_namespace=m[1]
            else:stack.append(('namespace',m[1]))
        elif m[3]:
            name=m[4]+('`'+str(len(m[5].split(','))) if m[5] else '')
            prefix=[file_namespace] if file_namespace else []
            prefix.extend(name for kind,name in stack if kind in ('namespace','type'))
            result[m.start()]='.'.join([*prefix,name]);pending=('type',name)
        elif m[0]=='{':stack.append(pending or ('block',''));pending=None
        elif m[0]=='}':
            if stack:stack.pop()
            pending=None
    return result


def analysis_scope(root,snapshot=None):
    """One complete included-scope analysis for ambiguity-sensitive reads."""
    snapshot=snapshot if snapshot is not None else inventory(root)
    groups={}
    for path,entry in sorted(snapshot['files'].items()):
        if entry['status']=='blocked':continue
        try:observations,_,_=extract(root,path,entry)
        except (OSError,UnicodeError):continue
        for observation in observations:groups.setdefault(observation['id'],[]).append(observation)
    for identifier,items in list(groups.items()):
        if len(items)>1 and all(equivalent_occurrence(items[0],o) for o in items[1:]):
            merged=dict(items[0],occurrences=[occurrence(o) for o in items]);groups[identifier]=[merged]
    ambiguous={i:items for i,items in groups.items() if len(items)>1 or any(o.get('unsupported') for o in items)}
    return {'snapshot':snapshot,'observations':[items[0] for i,items in groups.items() if i not in ambiguous],
            'ambiguous':ambiguous}


def negative_coverage_gaps(snapshot):
    """Excluded source is not negative evidence. No excluded content is loaded.

    Administrative storage is exempt. Other excluded source/output directories
    block negative proof: arbitrary Compile Include rules may make them live.
    """
    projects=[p for p in snapshot['files'] if p.endswith('.csproj')]
    result=[]
    administrative={'.maintenance','.harness','.knowledge-control.lock','.git','.gitignore','.gitattributes','.editorconfig','.knowledge','.ai','.venv','.local','.vs','TestResults'}
    for excluded in snapshot['exclusions']:
        path=Path(excluded['path'])
        if any(part in administrative for part in path.parts):continue
        relevant=path.suffix.lower() in {'.cs','.csproj','.props','.targets','.fs','.vb','.razor','.json','.config'} or not path.suffix
        if not relevant:continue
        for project in projects:
            directory=Path(project).parent
            if directory==path.parent or directory in path.parents or directory==Path('.'):
                result.append({'project':project,'path':str(path),'reason':'excluded potentially live source/configuration; no absence proof'})
    for path,entry in snapshot['files'].items():
        if entry.get('negative_scope_reason'):
            affected=[path] if path.endswith('.csproj') else projects
            result.extend({'project':project,'path':path,'reason':entry['negative_scope_reason']} for project in affected)
        if entry['status']=='blocked':result.append({'project':entry['partition'],'path':path,'reason':entry.get('reason','blocked source')})
    return result


def discovery_owned(db,claim,records):
    """A former ID/provenance alone does not own a later reviewed assertion."""
    if claim['provenance']!={'actor':'deterministic-discovery','method':VERSION}:return False
    evidence={e['id']:e for e in records['evidence']}
    for payload, in db.execute('SELECT payload FROM scans'):
        prior=loads(payload)
        if prior.get('extractor')!=VERSION or not prior['complete']:continue
        for observation in prior['observations']:
            if observation['id']==claim['id'] and observation['statement']==claim['statement']:
                if any(evidence[i].get('content_hash')==observation['content_hash'] and evidence[i]['source']==observation['path'] for i in claim['evidence']):return True
    return capture_owned(db,claim,records)


def occurrence(observation):
    return {k:observation[k] for k in ('path','line','anchor','content_hash')}


def equivalent_occurrence(first,second):
    # These claims only assert that one file contains literal syntax; multiple
    # identical occurrences support the same assertion, not distinct type owners.
    return first['category']!='declaration' and not first.get('unsupported') and not second.get('unsupported') and all(first[k]==second[k] for k in ('id','project','category','statement','path','subject'))


CAPTURE_RECEIPT='capture-observation-v1:'


def validate_capture_receipt(key,receipt):
    require(isinstance(receipt,dict) and set(receipt)=={'version','extractor','observation','candidate','source'} and type(receipt['version']) is int and receipt['version']==1,'corrupt-capture-observation-receipt')
    observation=receipt['observation']
    require(isinstance(observation,dict) and all(isinstance(observation.get(k),str) for k in ('id','statement','path','content_hash','anchor')) and isinstance(receipt['extractor'],str),'corrupt-capture-observation-receipt')
    require(all(isinstance(receipt[k],str) and re.fullmatch('[a-f0-9]{64}',receipt[k]) for k in ('candidate','source')) and key==CAPTURE_RECEIPT+digest(receipt),'corrupt-capture-observation-receipt')


def validate_capture_receipts(db):
    for key,payload in db.execute("SELECT key,value FROM metadata WHERE key LIKE 'capture-observation-v1:%'"):
        validate_capture_receipt(key,loads(payload))


def capture_owned(db,claim,records):
    """Ownership requires verified observation AND the exact approved candidate.

    Unlike a completed scan this receipt proves only one positive observation;
    it never authorizes negative coverage/automatic retirement. Historical receipts
    remain useful after explicit retirement, but cannot own a different meaning.
    """
    evidence={e['id']:e for e in records['evidence']}
    for key,payload in db.execute("SELECT key,value FROM metadata WHERE key LIKE 'capture-observation-v1:%'"):
        receipt=loads(payload)
        validate_capture_receipt(key,receipt)
        observation=receipt['observation']
        if receipt['extractor']!=VERSION or observation['id']!=claim['id'] or observation['statement']!=claim['statement']:continue
        if not any(evidence[i]['provenance']=={'actor':'deterministic-discovery','method':VERSION} and evidence[i]['content_hash']==observation['content_hash'] and evidence[i]['source']==observation['path'] and evidence[i]['description']==observation['anchor'] and claim['id'] in evidence[i]['substantiates'] for i in claim['evidence']):continue
        for pid,plan_json in db.execute('SELECT plan,payload FROM receipts'):
            plan=loads(plan_json);candidate=plan['candidates'].get(receipt['candidate'])
            if candidate is None or digest(candidate)!=receipt['candidate']:continue
            for change in candidate.get('operations',[]):
                if change['kind']!='claims' or change['id']!=claim['id'] or change['payload'] is None:continue
                if change['payload']['statement']!=observation['statement']:continue
                version=db.execute('SELECT payload FROM revisions WHERE id=? AND revision=?',(claim['id'],change['expected']+1)).fetchone()
                if version and loads(version[0])['plan']==pid and loads(version[0])['record']==change['payload']:return True
    return False


def capture_observation_receipts(store):
    """Read-only audit of positive receipts; never asserts full scan coverage."""
    with store.connection() as db:
        require(life.enabled(db),'upgrade-required')
        return {'version':1,'positive_observations_only':True,'receipts':[loads(p) for p, in db.execute("SELECT value FROM metadata WHERE key LIKE 'capture-observation-v1:%' ORDER BY key")]}


def candidate_preview(store,paths,captured_at=None):
    """Read-only positive proposal preview; unresolved ownership is manual review."""
    return _candidate_preview(store,paths,captured_at,False)


def candidate_observe(store,paths,captured_at=None):
    """Coordinated Knowledge writer records exact positive observation ownership.

    Does not submit, prepare, approve/apply, or create a completed scan. The caller
    retains its exact delivery payload in an outbox and submits via Store.submit.
    Receipts are additive metadata compatible with existing P1 stores. Old capture
    records without proof require explicit manual review, never fabricated scans.
    """
    return _candidate_preview(store,paths,captured_at,True)


def _candidate_preview(store,paths,captured_at,record_ownership):
    require(isinstance(paths,list) and all(isinstance(p,str) for p in paths),'invalid-preview-paths')
    scope=analysis_scope(store.project.root);snapshot=scope['snapshot'];decisions=[]
    with store.connection(record_ownership) as db:
        require(life.enabled(db),'upgrade-required')
        records=store._records(db);states=life.latest(db)
        known_candidates=[(cid,loads(payload),status) for cid,payload,status in db.execute('SELECT id,payload,status FROM queue')]
        current={c['id']:c for c in records['claims']}
        for obs in scope['observations']:
            if obs['path'] not in paths:continue
            legacy=[c['id'] for c in records['claims'] if c['provenance']['method'] in LEGACY_METHODS and c['id']==obs['legacy_id']]
            if legacy:
                decisions.append({'observation':obs['id'],'decision':'manual-review','legacy_ids':legacy});continue
            known=current.get(obs['id'])
            if known and (states[obs['id']]['lifecycle']=='superseded' or not discovery_owned(db,known,records)):
                decisions.append({'observation':obs['id'],'decision':'manual-review','reason':'positive observation ownership or successor requires explicit review; no automatic overwrite/reactivation','current_revision':states[obs['id']]['revision']});continue
            value=proposal(store,db,obs,snapshot,captured_at or life.now(),records,states,scope)
            if value is None:continue
            equivalent=next(((cid,status) for cid,item,status in known_candidates if item['version']==2 and proposal_identity(item)==proposal_identity(value)),None)
            if equivalent:decisions.append({'observation':obs['id'],'decision':'existing','candidate':equivalent[0],'status':equivalent[1]})
            else:
                decisions.append({'observation':obs['id'],'decision':'submit','payload':value})
                if record_ownership:
                    receipt=dict(version=1,extractor=VERSION,observation=obs,candidate=digest(value),source=snapshot['identity'])
                    db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)',(CAPTURE_RECEIPT+digest(receipt),canonical_json(receipt)))
        require(inventory(store.project.root)['identity']==snapshot['identity'],'source-changed-during-preview')
    return {'ok':True,'source':snapshot['identity'],'decisions':decisions,'gaps':list(scope['ambiguous']),
            'reason':'eligible changed-source syntax or explicit review' if decisions else 'no new eligible supported source fact'}
