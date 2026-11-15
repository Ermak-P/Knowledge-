"""Bounded lexical .NET capability pack. Source is data; no build hooks execute."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
from .util import canonical_json, digest, fingerprint, loads, require
from . import lifecycle as life

VERSION='dotnet-lexical-v1'
EXCLUDED={'.git','.knowledge','.ai','.venv','.local','node_modules','vendor','packages','bin','obj','dist','build','.vs','TestResults'}
SUFFIXES={'.cs','.csproj','.props','.targets','.sln','.json','.md','.yaml','.yml','.xml','.config'}
LIMIT=512000


def git(root,*args,required=False):
    p=subprocess.run(['git','-C',str(root),*args],capture_output=True)
    if required:require(p.returncode==0,'invalid-git-range-or-checkout')
    return p.stdout.decode('utf-8','replace').strip() if p.returncode==0 else None


def inventory(root,base=None,head=None):
    root=Path(root); files={}; excluded=[]
    for folder,dirs,names in os.walk(root,followlinks=False):
        parent=Path(folder)
        for name in list(dirs):
            p=parent/name
            if name in EXCLUDED or p.is_symlink() or name.startswith('.'):
                excluded.append({'path':p.relative_to(root).as_posix(),'status':'excluded','reason':'dependency/generated/hidden or linked directory'})
                dirs.remove(name)
        for name in names:
            p=parent/name; rel=p.relative_to(root).as_posix()
            if p.is_symlink() or p.suffix.lower() not in SUFFIXES or re.search(r'(?i)(secret|credential|\.env|appsettings\.(?!json)|\.g\.cs|\.designer\.cs)',name):
                excluded.append({'path':rel,'status':'excluded','reason':'binary/unsupported/generated/credential-risk'});continue
            try:
                with p.open('rb') as source:data=source.read(LIMIT+1)
                text=data.decode('utf-8-sig')
                require(len(data)<=LIMIT,'source-too-large')
                files[rel]={'hash':'sha256:'+hashlib.sha256(data).hexdigest(),'status':'not-analyzed','partition':'.','bytes':len(data)}
            except (OSError,UnicodeError,ValueError):
                files[rel]={'hash':None,'status':'blocked','partition':'.','reason':'unreadable, non-UTF8 or oversized source'}
    projects=[p for p in files if p.endswith('.csproj')]
    for p,item in files.items():
        ancestors=[proj for proj in projects if Path(proj).parent==Path(p).parent or Path(proj).parent in Path(p).parents]
        if ancestors:item['partition']=max(ancestors,key=len)
    revision=git(root,'rev-parse','--verify','HEAD')
    delta=None
    if base or head:
        require(base is not None and head is not None,'base-and-head-required')
        b=git(root,'rev-parse','--verify',base+'^{commit}',required=True);h=git(root,'rev-parse','--verify',head+'^{commit}',required=True)
        require(h==revision,'checkout-requested-head-first')
        git(root,'merge-base','--is-ancestor',b,h,required=True)
        delta={'base':b,'head':h,'committed':git(root,'diff','--name-status','-M',b,h,required=True)}
    dirty_raw=subprocess.run(['git','-C',str(root),'status','--porcelain=v1','-z','--untracked-files=all'],capture_output=True)
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
    index_raw=subprocess.run(['git','-C',str(root),'ls-files','--stage','-z'],capture_output=True)
    index_blobs={}
    for entry in index_raw.stdout.decode('utf-8','replace').split('\0'):
        if '\t' not in entry:continue
        meta,path=entry.split('\t',1)
        if path in files:
            index_blobs.setdefault(path,[]).append(meta)
            if not meta.endswith(' 0'):
                files[path].update(status='blocked',reason='unmerged Git index requires resolution')

    core={'index_blobs':index_blobs,'policy':{'excluded_dirs':sorted(EXCLUDED),'suffixes':sorted(SUFFIXES),'max_file_bytes':LIMIT},'extractor':VERSION,'files':{p:{k:v for k,v in item.items() if k!='status'} for p,item in sorted(files.items())},'exclusions':sorted(excluded,key=lambda x:x['path']), 'revision':revision,'dirty':dirty}
    return {'identity':digest(core),**core,'files':files,'delta':delta,'snapshot_kind':'working-tree-with-hashes' if dirty else 'committed' if revision else 'filesystem-no-history'}


def extract(root,path,entry):
    text=(Path(root)/path).read_text(encoding='utf-8-sig');lines=text.splitlines(); project=entry['partition']
    project_name=Path(project).stem if project!='.' else 'root'
    observations=[]
    def emit(category,key,statement,line,subject):
        anchor=lines[line-1].strip()
        identifier='scan.'+digest([project_name,category,key])[:32]
        observations.append(dict(id=identifier,category=category,project=project,path=path,line=line,anchor=anchor,
                                 statement=statement,subject=subject,method=VERSION,content_hash=entry['hash']))
    if path.endswith('.csproj'):
        try: tree=ET.fromstring(text)
        except ET.ParseError:return [],'partial','invalid project XML'
        for index,line in enumerate(lines,1):
            if '<Project ' in line:emit('project','project',f'{project_name} declares a .NET project using {tree.attrib.get("Sdk","an unspecified SDK")}.',index,project_name)
            for tag in ('ProjectReference','PackageReference'):
                m=re.search(r'<'+tag+r'\b[^>]*Include="([^"]+)"',line)
                if m:emit('dependency',tag+':'+m[1],f'{project_name} declares {tag} {m[1]}.',index,m[1])
        return observations,'analyzed',None
    if path.endswith('.cs'):
        # Strip comments, maintaining line offsets. Strings are retained for literal routes.
        clean=re.sub(r'/\*.*?\*/',lambda m:'\n'*m[0].count('\n'),text,flags=re.S)
        clean=re.sub(r'//[^\n]*','',clean)
        for index,line in enumerate(clean.splitlines(),1):
            for m in re.finditer(r'\b(class|interface|record)\s+(\w+)(?:\s*<[^>]+>)?\s*(?::\s*([^\{]+))?',line):
                kind,name,bases=m.groups();bases=(bases or '').strip()
                emit('declaration',name,f'{project_name} declares {kind} {name}'+(f' with declared bases {bases}' if bases else '')+'.',index,name)
            for m in re.finditer(r'\bAdd(Scoped|Singleton|Transient)\s*<([^>]+)>',line):
                emit('wiring',m[2].split(',')[0].strip(),f'{project_name} contains Add{m[1]}<{m[2]}> registration syntax.',index,m[2].split(',')[0].strip())
            for m in re.finditer(r'\b(MapGet|MapPost|MapPut|MapDelete|Route|HttpGet|HttpPost|HttpPut|HttpDelete)\s*\(\s*"([^"]*)"',line):
                emit('routing',Path(path).stem+':'+m[1]+':'+m[2],f'{project_name} declares {m[1]} route literal "{m[2]}" in {Path(path).stem}.',index,m[2])
            for m in re.finditer(r'\b(AddDbContext|UseSqlServer|UseSqlite|GetConnectionString)\s*(?:<([^>]+)>)?\s*\(',line):
                emit('persistence',Path(path).stem+':'+m[1]+':'+str(m[2]),f'{project_name} contains {m[1]}'+(f'<{m[2]}>' if m[2] else '')+' persistence/configuration syntax.',index,m[2] or m[1])
        return observations,'partial','lexical extraction only; no Roslyn symbol resolution, preprocessor or runtime proof'
    return [],'partial','inventory/content hash only; semantic extractor unavailable for this file type'


def fresh_evidence(root,e):
    path=e.get('source'); path=path.get('reference') if isinstance(path,dict) else path
    location=e.get('location','');location=location.get('reference','') if isinstance(location,dict) else location
    if not e.get('content_hash') or not isinstance(path,str):return 'not-verifiable'
    p=Path(path)
    if p.is_absolute() or '..' in p.parts:return 'not-verifiable'
    p=Path(root)/p
    if not p.is_file() or p.is_symlink():return 'missing'
    try:
        data=p.read_bytes()
        if 'sha256:'+hashlib.sha256(data).hexdigest()==e['content_hash']:return 'unchanged'
        # Exact anchored excerpt survives unrelated edits and line movement.
        if e.get('provenance',{}).get('method')==VERSION and e['description'] in [line.strip() for line in data.decode('utf-8-sig').splitlines()]:return 'anchor-valid-file-changed'
    except (OSError,UnicodeError):return 'not-verifiable'
    return 'changed'


def freshness(root,claim,records):
    evidence={e['id']:e for e in records['evidence']}
    results={i:fresh_evidence(root,evidence[i]) for i in claim['evidence'] if i in evidence}
    trusted=bool(results) and all(v in ('unchanged','anchor-valid-file-changed') and evidence[i]['status']=='active' for i,v in results.items())
    return {'trusted':trusted,'evidence':results,'policy':'all supporting evidence current; confidence unchanged'}


def proposal(store,db,obs,snapshot,captured,records,states):
    from .store import empty
    current={r['id']:r for r in records['claims']};known=current.get(obs['id'])
    if known and known['statement']==obs['statement'] and freshness(store.project.root,known,records)['trusted']:return None
    if known and states[obs['id']]['lifecycle']!='active':return None
    eid='evidence.'+digest([obs['id'],obs['path'],obs['content_hash'],obs['anchor']])
    evidence=dict(id=eid,type='direct-technical',status='active',source=obs['path'],location=obs['path']+'#L'+str(obs['line']),content_hash=obs['content_hash'],
                  description=obs['anchor'],substantiates=[obs['id']],captured_at=captured,provenance=dict(actor='deterministic-discovery',method=VERSION))
    claim=dict(id=obs['id'],statement=obs['statement'],type='technical_fact',status='CONFIRMED',evidence=[eid],
               provenance=dict(actor='deterministic-discovery',method=VERSION),last_verified=captured[:10],depends_on=[],conflicts_with=[])
    ops=[]
    if not db.execute('SELECT 1 FROM records WHERE id=?',(eid,)).fetchone():ops.append(life.op('add','evidence',eid,0,evidence))
    ops.append(life.op('update' if known else 'add','claims',obs['id'],life.revision(db,obs['id']),claim))
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
        else:
            scan_id=digest([store.project.identity,snap['identity'],snap['delta'],VERSION])
            row=db.execute('SELECT payload FROM scans WHERE id=?',(scan_id,)).fetchone()
            state=loads(row[0]) if row else dict(id=scan_id,extractor=VERSION,snapshot=snap,coverage=deep_files(snap['files']),observations=[],candidates=[],captured_at=life.now(),complete=False)
        pending=sorted((p for p,e in state['coverage'].items() if e['status']=='not-analyzed'),key=lambda p:(not p.endswith(('.csproj','.cs')),p))
        for path in pending[:max_files]:
            observations,status,reason=extract(store.project.root,path,state['coverage'][path])
            # Ambiguous identities from overloads/duplicate declarations are gaps, never guessed.
            existing={o['id'] for o in state['observations']}
            for o in observations:
                if o['id'] in existing:
                    state.setdefault('gaps',[]).append({'id':o['id'],'reason':'duplicate lexical identity','path':path});continue
                existing.add(o['id']);state['observations'].append(o)
            state['coverage'][path].update(status=status,reason=reason)
        state['complete']=not any(e['status'] in ('not-analyzed','blocked') for e in state['coverage'].values())
        records=store._records(db)
        changed={e['id'] for e in records['evidence'] if fresh_evidence(store.project.root,e) not in ('unchanged','anchor-valid-file-changed')}
        owners={c['id'] for c in records['claims'] if changed.intersection(c['evidence'])}
        closure=set(owners)
        while True:
            expanded=closure|{c['id'] for c in records['claims'] if closure.intersection(c['depends_on'])}
            if expanded==closure:break
            closure=expanded
        state['impact']={'changed_or_unverifiable_evidence':sorted(changed),'direct_claims':sorted(owners),
                         'dependent_claims':sorted(closure-owners),
                         'relationships':[r['id'] for r in records['relationships'] if r['from'] in closure or r['to'] in closure],
                         'policy':'full included scope reexamined; impact is a review request, not retirement'}
        state['semantic_coverage_complete']=False
        state['limits']=['No runtime/deployment proof or business rationale','C# lexical matches are partial, not compiler analysis','Non-code files are content inventory only','Untracked permitted source is included with dirty hashes; Git dirty state is separate from committed HEAD']
        # Enqueue only at completion: partial scan observations remain durable, no claim of absence.
        if state['complete']:
            records=store._records(db);states=life.latest(db)
            signatures={proposal_identity(loads(p)) for p, in db.execute('SELECT payload FROM queue') if loads(p)['version']==2}
            for obs in state['observations']:
                value=proposal(store,db,obs,snap,state['captured_at'],records,states)
                if value:
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
        observed={o['id']:o for o in scan['observations']}
        for c in records['claims']:
            fresh=freshness(store.project.root,c,records)
            classification='unchanged' if fresh['trusted'] else 'not-verifiable'
            if states[c['id']]['lifecycle']!='active':classification='historical'
            elif not fresh['trusted'] and c['id'] in observed:classification='changed'
            elif not fresh['trusted'] and c['provenance']['method']==VERSION:classification='suspected-obsolete'
            dependents=[d['id'] for d in records['claims'] if c['id'] in d['depends_on']]
            out.append(dict(id=c['id'],classification=classification,freshness=fresh,lifecycle=states[c['id']]['lifecycle'],dependents=dependents,
                            retirement_proposed=False,reason='Retirement requires reviewed positive corroboration; lexical absence alone is insufficient.'))
        retirement=[]
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
        return {'ok':True,'scan':scan_id,'complete':scan['complete'],'claims':out,'source':scan['snapshot'],'canonical_unchanged':True,'proposal':proposal}


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
