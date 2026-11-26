"""Bounded lexical .NET capability pack. Source is data; no build hooks execute."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from .util import canonical_json, digest, fingerprint, loads, require, KnowledgeError
from .project import safe_path
from . import lifecycle as life
from . import source_reader
from . import discovery_checkpoint as scan_checkpoint
from . import discovery_cache as file_cache
from . import discovery_history as scan_history

VERSION='dotnet-lexical-v3'
LEGACY_METHODS={'dotnet-lexical-v1','dotnet-lexical-v2'}
DISCOVERY_METHODS=LEGACY_METHODS|{VERSION}
CURRENT_EVIDENCE=('unchanged','anchor-valid-file-changed','current-registered-confluence-snapshot','unchanged-content-newer-confluence-version')
EXCLUDED={'.git','.knowledge','.ai','.venv','.local','node_modules','vendor','packages','bin','obj','dist','build','.vs','TestResults'}
SUFFIXES={'.cs','.csproj','.props','.targets','.sln','.json','.md','.yaml','.yml','.xml','.config'}
LIMIT=512000


def has_git(root):
    root=Path(root).absolute()
    # Sandboxed workspaces can expose empty .git mount placeholders. They are
    # not repository metadata and must not disable filesystem-only capture.
    return any((p/'.git').is_file() or (p/'.git/HEAD').is_file() for p in (root,*root.parents))

def git_process(root,*args,input=None):
    command=['git','-c','core.fsmonitor=false','-C',str(root),*args]
    # A Git subprocess must never inherit an MCP named-pipe input. Regular
    # output files also avoid communicate() waiting forever on inherited pipes
    # after a Windows wrapper has timed out and been terminated.
    with tempfile.TemporaryFile() as incoming,tempfile.TemporaryFile() as output,tempfile.TemporaryFile() as errors:
        if input is not None:incoming.write(input);incoming.seek(0)
        try:
            process=subprocess.Popen(command,stdin=incoming if input is not None else subprocess.DEVNULL,stdout=output,stderr=errors,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0','GIT_TERMINAL_PROMPT':'0'})
        except FileNotFoundError as e:raise KnowledgeError('git-unavailable-for-existing-checkout') from e
        try:process.wait(timeout=15)
        except subprocess.TimeoutExpired as e:
            process.kill();process.wait(timeout=3);raise KnowledgeError('git-operation-timeout') from e
        output.seek(0);errors.seek(0);stdout=output.read(16*1024*1024+1);stderr=errors.read(1024*1024+1)
        require(len(stdout)<=16*1024*1024 and len(stderr)<=1024*1024,'git-output-too-large')
        return subprocess.CompletedProcess(command,process.returncode,stdout,stderr)

def git(root,*args,required=False):
    if not has_git(root):
        require(not required,'invalid-git-range-or-checkout');return None
    p=git_process(root,*args)
    if required:require(p.returncode==0,'invalid-git-range-or-checkout')
    return p.stdout.decode('utf-8','replace').strip() if p.returncode==0 else None


def git_blob(data,algorithm):
    return hashlib.new(algorithm,b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()


def base_source_matches(data,observation,snapshot):
    """Compare a Git blob and prior raw evidence without mixing hash domains."""
    hashed=lambda b:'sha256:'+hashlib.sha256(b).hexdigest()
    if hashed(data)==observation['content_hash']:return True
    entry=snapshot['files'].get(observation['path'],{})
    head=entry.get('head_blob')
    if entry.get('hash')!=observation['content_hash'] or not head:return False
    if git_blob(data,'sha256' if len(head)==64 else 'sha1')!=head:return False
    # This also recovers prior-release CRLF evidence, which retained its raw
    # digest and HEAD identity but had no explicit normalized working blob.
    return b'\r' not in data and hashed(data.replace(b'\n',b'\r\n'))==observation['content_hash']


def inventory(root,base=None,head=None):
    root=Path(root); files={}; excluded=[];errors=[];repo=has_git(root);blobs={};lf_blobs={}
    config=source_reader.policy(root,LIMIT)
    def gap(error,phase='enumerate'):
        path=Path(error.filename) if error.filename else root
        try:relative=path.relative_to(root).as_posix()
        except ValueError:relative='.'
        value={'path':relative,'phase':phase,'stage':phase,'errno':error.errno,'scope':'.','reason':'included source unavailable; negative proof blocked',
               'reason_code':'ACCESS_DENIED' if isinstance(error,PermissionError) else 'UNREADABLE','retry_eligible':False}
        if value not in errors:errors.append(value)
    object_format=git(root,'rev-parse','--show-object-format',required=True) if repo else 'sha1'
    require(object_format in ('sha1','sha256'),'unsupported-git-object-format')
    for folder,dirs,names in os.walk(root,followlinks=False,onerror=gap):
        parent=Path(folder)
        for name in list(dirs):
            p=parent/name
            relative=p.relative_to(root).as_posix()
            rule=source_reader.exclusion(relative+'/',config)
            included=any(source_reader.matches(relative+'/',pattern) or pattern.startswith(relative+'/') for pattern in config['include'])
            administrative=name in {'.git','.knowledge','.ai','.venv','.local','.harness','.maintenance'}
            try:excluded_dir=administrative or p.is_symlink() or p.is_junction() or ((name in EXCLUDED or name.startswith('.')) and not included)
            except OSError as error:
                gap(error,'inspect-directory');dirs.remove(name);continue
            if excluded_dir or rule:
                excluded.append({'path':relative,'status':'excluded','kind':'directory',
                                 **(rule or {'reason':'EXCLUDED_GENERATED','rule':'default-directory-filter'})})
                dirs.remove(name)
        for name in names:
            p=parent/name; rel=p.relative_to(root).as_posix()
            rule=source_reader.exclusion(rel,config)
            if rule:
                excluded.append({'path':rel,'status':'excluded','kind':'file',**rule});continue
            if p.suffix.lower() not in SUFFIXES or re.search(r'(?i)(secret|credential|\.env|appsettings\.(?!json)|\.g\.cs|\.designer\.cs)',name):
                excluded.append({'path':rel,'status':'excluded','kind':'file','reason':'EXCLUDED_GENERATED' if p.suffix.lower() in SUFFIXES else 'EXCLUDED_BINARY','rule':'default-extension/generated/credential-filter'});continue
            try:
                if p.is_symlink():
                    excluded.append({'path':rel,'status':'excluded','reason':'linked file'});continue
                item=source_reader.fingerprint(p,config,object_format if repo else None,relative=rel,classify=True)
                blobs[rel]=item.pop('working_blob',None);lf_blobs[rel]=item.pop('lf_blob',None)
                files[rel]={**item,'partition':'.'}
                if p.suffix.lower() in ('.csproj','.props','.targets'):
                    try:
                        text,_=source_reader.read(root,rel,files[rel],config)
                        project_xml=ET.fromstring(text)
                        custom=any((node.tag.rsplit('}',1)[-1]=='Compile' and 'Include' in node.attrib) or node.tag.rsplit('}',1)[-1] in ('Import','EnableDefaultCompileItems') for node in project_xml.iter())
                        sdk=project_xml.attrib.get('Sdk','')
                        if custom or (p.suffix.lower()=='.csproj' and not sdk.startswith('Microsoft.NET.Sdk')):
                            files[rel]['negative_scope_reason']='custom source inclusion/import/SDK requires manual coverage validation'
                    except (ET.ParseError,KnowledgeError,UnicodeError):files[rel]['negative_scope_reason']='unverifiable project/source-inclusion XML'
            except KnowledgeError as error:
                # Refuse this object before opening it, while retaining an
                # explicit coverage gap. Integrity/source-change errors still
                # abort; they are not recoverable extraction failures.
                if error.code not in ('unsafe-filesystem-object','linked-path','unsupported-windows-path'):
                    raise
                files[rel]={'hash':None,'status':'blocked','partition':'.','reason':error.code,
                            'reason_code':'UNSAFE_PATH','stage':'inventory','retry_eligible':False,
                            'exception':type(error).__name__}
            except OSError as error:
                code='ACCESS_DENIED' if isinstance(error,PermissionError) else 'UNREADABLE'
                files[rel]={'hash':None,'status':'blocked','partition':'.','reason':code,'reason_code':code,
                            'stage':'inventory','retry_eligible':False,'exception':type(error).__name__,'errno':error.errno}
    # Resolve nearest projects by lexical directory ancestry. The old nested
    # scan compared every source with every project, repeatedly constructing
    # Paths, which becomes quadratic in large multi-project repositories.
    projects_by_directory={}
    for path in files:
        if path.endswith('.csproj'):
            projects_by_directory.setdefault(Path(path).parent,[]).append(path)
    for projects in projects_by_directory.values():
        projects.sort()
    nearest_by_directory={}
    for p,item in files.items():
        directory=Path(p).parent
        if directory not in nearest_by_directory:
            nearest=[]
            for parent in (directory,*directory.parents):
                if parent in projects_by_directory:
                    nearest=projects_by_directory[parent]
                    break
            nearest_by_directory[directory]=nearest
        nearest=nearest_by_directory[directory]
        if nearest:
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
    require(not repo or dirty_raw.returncode==0,'invalid-git-range-or-checkout')
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
    require(not repo or index_raw.returncode==0,'invalid-git-range-or-checkout')
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
        # Without --no-index Git never reports tracked paths as ignored.
        # Supplying every tracked path makes check-ignore quadratic on big trees.
        unindexed=[p for p in files if p not in index_blobs]
        ignored_paths=set()
        if unindexed:
            ignored_raw=git_process(root,'check-ignore','--stdin','-z',input=b''.join(p.encode('utf-8')+b'\0' for p in unindexed))
            require(ignored_raw.returncode in (0,1),'invalid-git-range-or-checkout')
            ignored_paths.update(ignored_raw.stdout.decode('utf-8','replace').split('\0'))
        for path,entry in files.items():
            blob=blobs.get(path)
            indexed=index_blobs.get(path,[])
            entry['working_blob']=blob
            # Git status compares in Git's attribute/filter domain. Independently
            # prove the only normalization we use; retain raw evidence hashes.
            if blob!=head_blobs.get(path) and path not in dirty_paths and lf_blobs.get(path)==head_blobs.get(path):
                blob=lf_blobs[path]
            entry['git_blob']=blob
            if entry['hash'] is None:
                entry.update(git_state='unverifiable',head_blob=head_blobs.get(path));continue
            if path not in head_blobs or blob!=head_blobs[path] or path in dirty_paths:
                ignored=path in ignored_paths
                entry['git_state']='ignored' if ignored else 'untracked' if not indexed else 'staged-or-unstaged'
                if path not in dirty_paths:dirty.append({'path':path,'status':'!!' if ignored else '??' if not indexed else ' M','original':None})
            else:entry['git_state']='committed'
            entry['head_blob']=head_blobs.get(path)
        dirty.sort(key=lambda d:d['path'])
    core={'index_blobs':index_blobs,'policy':{**config,'excluded_dirs':sorted(EXCLUDED),'suffixes':sorted(SUFFIXES)},'extractor':VERSION,'files':{p:{k:v for k,v in item.items() if k!='status'} for p,item in sorted(files.items())},'exclusions':sorted(excluded,key=lambda x:x['path']), 'revision':revision,'dirty':dirty}
    if errors:core['coverage_errors']=sorted(errors,key=lambda e:(e['path'],e['phase'],e['errno'] or 0))
    return {'identity':digest(core),**core,'files':files,'delta':delta,'snapshot_kind':'working-tree-with-hashes' if dirty else 'committed' if revision else 'filesystem-no-history'}


def extract(root,path,entry):
    from .persistence_identity import POLICY,LEGACY
    identity_policy=entry.pop('_identity_policy',POLICY)
    config=entry.pop('_source_policy',None)
    text,metadata=source_reader.read(root,path,entry,config if config is not None else source_reader.policy(root,LIMIT))
    entry.update(metadata,processing_status='partial' if metadata['partial'] else 'processed')
    lines=text.splitlines(); project=entry['partition']
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
                key=(Path(path).stem+':' if identity_policy==LEGACY else '')+m[1]+':'+str(m[2])
                emit('persistence',key,f'{project_name} contains {m[1]}'+(f'<{m[2]}>' if m[2] else '')+' persistence/configuration syntax.',index,m[2] or m[1])
                observations[-1]['identity_policy']=identity_policy
            offset+=len(line)
        return observations,'partial','lexical extraction only; no Roslyn symbol resolution, preprocessor or runtime proof'
    return [],'partial','bounded content preview; source regions remain unanalyzed' if metadata['partial'] else 'inventory/content hash only; semantic extractor unavailable for this file type'


def fresh_evidence(root,e,scope=None,db=None):
    from .confluence import is_binding,evidence_freshness
    if is_binding(e.get('source')):
        from .store import Store
        return evidence_freshness(Store(root),e,db)
    path=e.get('source'); path=path.get('reference') if isinstance(path,dict) else path
    location=e.get('location','');location=location.get('reference','') if isinstance(location,dict) else location
    if not e.get('content_hash') or not isinstance(path,str):return 'not-verifiable'
    p=Path(path)
    if p.is_absolute() or '..' in p.parts:return 'not-verifiable'
    relative = p.as_posix()
    method=e.get('provenance',{}).get('method')
    try:
        if method in DISCOVERY_METHODS and method not in LEGACY_METHODS and scope is None:
            scope = analysis_scope(root)
        reads = scope.get('_evidence_sources') if scope is not None else None
        wanted = scope.get('_evidence_anchors', {}).get(relative, ()) if reads is not None else ()
        reusable = reads is not None and (method not in DISCOVERY_METHODS or e['description'] in wanted)
        if reusable and relative in reads:
            source = reads[relative]
        else:
            source = _evidence_source(root, relative, scope, wanted if reusable else (e['description'],))
            if reusable:
                reads[relative] = source
        if isinstance(source, str):
            return source
        entry, anchors = source
        if method in DISCOVERY_METHODS:
            if method in LEGACY_METHODS:return 'legacy-identity-review-required'
            aliases=scope.get('identity_aliases',{});ids={aliases.get(i,i) for i in e['substantiates']}
            if not scope.get('complete',True) and not positive_scope_complete(scope,ids):return 'not-analyzed'
            if any(i in scope['ambiguous'] for i in set(e['substantiates'])|ids):return 'ambiguous-identity'
            by_id=scope.get('_observations_by_id')
            observations=(o for identifier in ids for o in by_id.get(identifier, ())) if by_id is not None else (
                o for o in scope['observations'] if o['id'] in ids)
            if not any(any(loc['path']==relative and loc['anchor']==e['description']
                           for loc in o.get('occurrences',[o])) for o in observations):return 'changed'
        if entry['hash']==e['content_hash']:return 'unchanged'
        if method in DISCOVERY_METHODS and e['description'] in anchors:return 'anchor-valid-file-changed'
    except (OSError,UnicodeError,KnowledgeError):return 'not-verifiable'
    return 'changed'


def _evidence_source(root, relative, scope, wanted):
    path = safe_path(Path(root)/relative)
    if not path.is_file() or path.is_symlink():
        return 'missing'
    if scope is None:
        config = source_reader.policy(root,LIMIT)
        entry = source_reader.fingerprint(path,config)
    else:
        snapshot = scope['snapshot']
        config = snapshot['policy']
        entry = snapshot['files'].get(relative)
        if entry is None:
            return 'not-analyzed'
    if entry['status']=='blocked':
        return 'not-verifiable'
    text, metadata = source_reader.read(root,relative,entry,config)
    if metadata['partial']:
        return 'not-analyzed'
    return entry, {line for raw in text.splitlines() if (line := raw.strip()) in wanted} if wanted else set()


def positive_scope_complete(scope,identifiers):
    """Positive syntax proof tolerates unrelated data gaps, never missing code."""
    if scope['snapshot'].get('coverage_errors'):return False
    by_id=scope.get('_observations_by_id')
    observations=(o for identifier in identifiers for o in by_id.get(identifier, ())) if by_id is not None else (
        o for o in scope['observations'] if o['id'] in identifiers)
    projects={o['project'] for o in observations}
    if not projects:return False
    if '_incomplete_projects' in scope:return not projects.intersection(scope['_incomplete_projects'])
    coverage=scope.get('verification_coverage',scope['snapshot']['files'])
    return all(p in coverage and coverage[p].get('processing_status')=='processed' and coverage[p]['status'] not in ('blocked','excluded')
               for p,e in scope['snapshot']['files'].items() if p.endswith(('.cs','.csproj')) and e['partition'] in projects)


def freshness(root,claim,records,scope=None,db=None):
    evidence=scope['_evidence_by_id'] if scope is not None and scope.get('_identity_records') is records else {e['id']:e for e in records['evidence']}
    if any(evidence[i]['provenance']['method'] in DISCOVERY_METHODS for i in claim['evidence'] if i in evidence):
        scope=scope if scope is not None else analysis_scope(root)
        scope=identity_scope(scope,records)
    results={i:fresh_evidence(root,evidence[i],scope,db=db) for i in claim['evidence'] if i in evidence}
    good=CURRENT_EVIDENCE
    native=any(isinstance(evidence[i]['source'],dict) and evidence[i]['source'].get('kind')=='confluence' for i in results)
    valid=[i for i,v in results.items() if v in good and evidence[i]['status']=='active']
    trusted=bool(valid) if native else bool(results) and len(valid)==len(results)
    if native and claim['status']=='CONFIRMED':
        qualifying=[i for i in valid if evidence[i]['type'] in (('direct-authoritative',) if claim['type']=='business_rule' else ('direct-authoritative','direct-technical'))
                    and not (isinstance(evidence[i]['source'],dict) and evidence[i]['source'].get('role')=='implementation')]
        trusted=bool(qualifying)
    return {'trusted':trusted,'evidence':results,'policy':'independent current registered evidence; confidence unchanged; no live Confluence verification' if native else 'all supporting evidence current; confidence unchanged',
            **({'evidence_scopes':{i:evidence[i]['source'].get('role','documentation') if isinstance(evidence[i]['source'],dict) and evidence[i]['source'].get('kind')=='confluence' else 'local-source' for i in results}} if native else {})}


def identity_scope(scope,records):
    from .persistence_identity import CanonicalIndex, describe
    if scope.get('_identity_records') is records:return scope
    canonical = CanonicalIndex(records)
    aliases = dict(scope.get('identity_aliases', {}))
    by_id = {}
    for observation in scope['observations']:
        by_id.setdefault(observation['id'], []).append(observation)
        known = canonical.match(observation) if describe(observation) is not None else None
        if known:aliases[known['id']] = observation['id']
    coverage = scope.get('verification_coverage', scope['snapshot']['files'])
    incomplete = {e['partition'] for path, e in scope['snapshot']['files'].items()
                  if file_cache.code_file(path) and (path not in coverage or not file_cache.verified(coverage[path]))}
    anchors = {}
    for evidence in records['evidence']:
        path = evidence['source']
        if isinstance(path, dict):
            path = path.get('reference')
        if evidence['provenance']['method'] in DISCOVERY_METHODS and isinstance(path, str):
            anchors.setdefault(Path(path).as_posix(), set()).add(evidence['description'])
    dependents = {}
    by_statement = {}
    for claim in records['claims']:
        by_statement.setdefault(claim['statement'], []).append(claim)
        for dependency in claim['depends_on']:
            dependents.setdefault(dependency, []).append(claim['id'])
    return {**scope, 'identity_aliases': aliases, '_identity_records': records, '_canonical_index': canonical,
            '_observations_by_id': by_id, '_incomplete_projects': incomplete, '_dependents': dependents,
            '_evidence_sources': {}, '_evidence_anchors': anchors,
            '_evidence_by_id': {e['id']: e for e in records['evidence']},
            '_claims_by_id': {c['id']: c for c in records['claims']}, '_claims_by_statement': by_statement}


def proposal(store,db,obs,snapshot,captured,records,states,scope=None):
    from .persistence_identity import describe, canonical_match
    if scope is not None:
        scope = identity_scope(scope, records)
    if scope is not None and obs['category']=='persistence' and obs.get('identity_policy')=='project-presence-v1':
        locations={}
        for other in scope['_observations_by_id'].get(obs['id'], ()):
            if equivalent_occurrence(obs,other):
                for location in other.get('occurrences',[occurrence(other)]):locations[(location['path'],location['line'],location['anchor'],location['content_hash'])]=location
        if locations:obs={**obs,'occurrences':[v for _,v in sorted(locations.items())]}
    current=scope['_claims_by_id'] if scope is not None else {r['id']:r for r in records['claims']}
    existing=scope['_evidence_by_id'] if scope is not None else {e['id']:e for e in records['evidence']}
    known=current.get(obs['id'])
    if known is None and describe(obs) is not None:
        known=scope['_canonical_index'].match(obs) if scope is not None else canonical_match(obs,records,states)
    def documented(c):
        if c['statement']!=obs['statement'] or c['type']!='technical_fact':return False
        return any(isinstance(e['source'],dict) and e['source'].get('kind')=='confluence' and e['source'].get('role')=='implementation'
                   for i in c['evidence'] if (e:=existing.get(i)) is not None)
    if known is None:
        candidates=scope['_claims_by_statement'].get(obs['statement'], ()) if scope is not None else records['claims']
        matches=[c for c in candidates if states[c['id']]['lifecycle']=='active' and documented(c)]
        require(len(matches)<=1,'ambiguous-shared-confluence-claim')
        if matches:known=matches[0]
    shared=bool(known and documented(known))
    identifier=known['id'] if known else obs['id']
    if known and (not shared and not discovery_owned(db,known,records,scope)):
        # A reviewed meaning is not automatically overwritten by a lexical re-observation.
        return None
    if known and states[identifier]['lifecycle']=='superseded':return None
    proofs=[]
    signatures={(e['source'],e['location'],e['content_hash'],e['description']):e for i in (known['evidence'] if known else ())
                if (e:=existing.get(i)) is not None and e['status']=='active' and e['substantiates']==[identifier]
                and e['provenance']==dict(actor='deterministic-discovery',method=VERSION)}
    for index,location in enumerate(obs.get('occurrences',[occurrence(obs)])):
        source=location['path'];anchor=location['anchor'];line=source+'#L'+str(location['line']);raw=location['content_hash']
        evidence=signatures.get((source,line,raw,anchor))
        if evidence is None:
            eid='evidence.'+digest([identifier,source,raw,anchor] if index==0 else ['occurrence-v1',identifier,source,raw,line,anchor])
            evidence=existing.get(eid) or dict(id=eid,type='direct-technical',status='active',source=source,location=line,content_hash=raw,
                      description=anchor,substantiates=[identifier],captured_at=captured,provenance=dict(actor='deterministic-discovery',method=VERSION))
        if evidence['id'] not in {e['id'] for e in proofs}:proofs.append(evidence)
    claim=dict(id=identifier,statement=obs['statement'],type='technical_fact',status='CONFIRMED',evidence=[e['id'] for e in proofs],
               provenance=dict(actor='deterministic-discovery',method=VERSION),last_verified=captured[:10],depends_on=[],conflicts_with=[])
    if known:
        # Re-observation does not authorize promotion or loss of reviewed graph state.
        claim.update(status=known['status'],type=known['type'],depends_on=list(known['depends_on']),
                     conflicts_with=list(known['conflicts_with']),provenance=dict(known['provenance']))
        if known['status']!='CONFIRMED':claim['last_verified']=known['last_verified']
        claim['evidence'].extend(i for i in known['evidence'] if existing[i]['provenance']['method'] not in DISCOVERY_METHODS)
    if known and states[identifier]['lifecycle']=='active' and set(known['evidence'])==set(claim['evidence']) and freshness(store.project.root,known,records,scope,db=db)['trusted']:return None
    ops=[life.op('add','evidence',e['id'],0,e) for e in proofs if e['id'] not in existing]
    ops.append(life.op('reactivate' if known and states[identifier]['lifecycle']=='retired' else 'update' if known else 'add','claims',identifier,states[identifier]['revision'] if known else 0,claim))
    return life.batch(ops,'Source-backed lexical observation; not runtime or business semantics',{'identity':snapshot['identity'],'revision':snapshot['revision'],'kind':snapshot['snapshot_kind']})


def _validate_snapshot(snapshot):
    core={k:v for k,v in snapshot.items() if k not in ('identity','delta','snapshot_kind')}
    core['files']={p:{k:v for k,v in item.items() if k!='status'} for p,item in snapshot['files'].items()}
    require(digest(core)==snapshot['identity'],'corrupt-scan-snapshot')


def _historical_baseline(db, snapshot):
    context = file_cache.configuration(snapshot)
    for _, old in scan_history.scan_rows(db, full=True, complete=True, extractor=VERSION, newest=True):
        if old.get('ambiguous') or file_cache.configuration(old['snapshot']) != context:
            continue
        _validate_snapshot(old['snapshot'])
        return old
    return None


def _group_observations(by_file):
    groups = {}
    for path in sorted(by_file):
        for observation in by_file[path]:
            groups.setdefault(observation['id'], []).append(observation)
    ambiguous = {}
    observations = []
    for identifier, members in groups.items():
        first = members[0]
        if first.get('unsupported') or (len(members) > 1 and not all(
                equivalent_occurrence(first, other) for other in members[1:])):
            ambiguous[identifier] = members
        elif len(members) > 1:
            observations.append(dict(first, occurrences=[occurrence(o) for o in members]))
        else:
            observations.append(first)
    return observations, ambiguous


def _cached_scope(db, project, state, by_file, *, dependencies=False, root=None):
    snapshot = state['snapshot']
    outside = {p for p in snapshot['files'] if file_cache.code_file(p) and p not in state['coverage']}
    context = file_cache.configuration(snapshot)
    cached = file_cache.compatible(db, project, snapshot, outside, context, lambda: _historical_baseline(db, snapshot))
    extracted_dependencies = []
    if dependencies:
        # Partition metadata contributes its own observations. A cold capture
        # can check that bounded prerequisite without analyzing unrelated code.
        projects = {e['partition'] for p, e in state['coverage'].items() if file_cache.code_file(p)}
        for path in sorted((outside - cached.keys()) & projects):
            entry = snapshot['files'][path]
            if entry['status'] != 'not-analyzed':
                continue
            dependency = dict(snapshot=snapshot, coverage={path: dict(entry)})
            observations = _extract_path(root, dependency, path)
            extracted_dependencies.append(path)
            if file_cache.verified(dependency['coverage'][path]):
                cached[path] = observations
    missing = sorted(outside - cached.keys())
    observations, ambiguous = _group_observations({**cached, **by_file})
    ambiguous.update({identifier: ambiguous.get(identifier, []) for identifier in state.get('ambiguous', [])})
    state['identity_verification'] = {
        'complete': not missing, 'cached_files': len(cached) - sum(p in cached for p in extracted_dependencies),
        'missing_files': missing, 'ambiguous_ids': sorted(ambiguous), 'unrelated_files_extracted': 0,
        'dependency_files_extracted': extracted_dependencies,
    }
    covered = {'status': 'analyzed', 'processing_status': 'processed'}
    coverage = dict.fromkeys(cached, covered)
    coverage.update(state['coverage'])
    return {'snapshot': snapshot, 'observations': observations, 'ambiguous': ambiguous,
            'complete': state['complete'] and not missing, 'verification_coverage': coverage,
            'cached_sources': cached, 'cache_context': context}


def incremental_scope(db, state, by_file=None):
    """Join exact, configuration-bound file observations and verify identities globally."""
    project = db.execute("SELECT value FROM metadata WHERE key='project'").fetchone()[0]
    if by_file is None:
        # Completed incremental artifacts keep raw observations via the cache.
        # Rebuild legacy aggregate occurrences if their identities were retained.
        by_file = file_cache.historical_observations(state)
        by_file.update(file_cache.compatible(db, project, state['snapshot'],
                       {p for p in state['coverage'] if file_cache.code_file(p)},
                       file_cache.configuration(state['snapshot']), lambda: None))
    scope = _cached_scope(db, project, state, by_file)
    verification = state['identity_verification']
    gaps = [{'path': path, 'reason': 'missing compatible cached analysis; explicitly run full knowledge-init or submit reviewed v2 candidates',
             'capability': 'incremental-global-identity'} for path in verification['missing_files']]
    gaps.extend({'id': o['id'], 'path': o['path'], 'reason': 'identity is ambiguous against current cached or changed source; withheld',
                 'capability': 'incremental-global-identity'} for o in state['observations'] if o['id'] in scope['ambiguous'])
    state['gaps'] = [gap for gap in state.get('gaps', []) if gap.get('capability') != 'incremental-global-identity'] + gaps
    return scope


def _selected_paths(root, snap, incremental):
    selected=None
    if incremental:
        require(snap['delta'] is not None,'incremental-requires-git-range')
        changed=git_process(root,'diff','--name-only','-z','--no-renames',snap['delta']['base'],snap['delta']['head'])
        require(changed.returncode==0,'invalid-git-range-or-checkout')
        selected=set(changed.stdout.decode('utf-8').split('\0'))-{''}
        selected.update(item['path'] for item in snap['dirty'])
    return selected


def _branch(root, snapshot):
    return git(root, 'symbolic-ref', '--quiet', 'HEAD') if snapshot['revision'] else None


def _initial_coverage(state):
    selected = set(state['scope_paths']) if state.get('incremental') else None
    return {p: dict(e) for p, e in state['snapshot']['files'].items() if selected is None or p in selected}


def _extract_path(root, state, path):
    from .persistence_identity import LEGACY
    state['coverage'][path]['_identity_policy']=state.get('identity_policy',LEGACY)
    state['coverage'][path]['_source_policy']=state['snapshot']['policy']
    try:observations,status,reason=extract(root,path,state['coverage'][path])
    except (OSError,UnicodeError) as error:
        reason='ACCESS_DENIED' if isinstance(error,PermissionError) else 'INVALID_ENCODING' if isinstance(error,UnicodeError) else 'UNREADABLE'
        observations,status=[],'blocked'
        state['coverage'][path].update(reason_code=reason,stage='extract',exception=type(error).__name__,
                                       processing_status='failed',retry_eligible=isinstance(error,OSError))
    except KnowledgeError as error:
        if error.code not in ('FILE_TOO_LARGE','INVALID_ENCODING','UNSUPPORTED_ENCODING','EXTRACTION_FAILED','EXCLUDED_BINARY'):
            if error.code == 'FILE_CHANGED_DURING_SCAN':
                raise KnowledgeError('source-changed-during-scan-restart', error.details) from error
            raise  # Integrity, ownership and linked-path violations are fatal.
        observations,status,reason=[],'excluded' if error.code=='EXCLUDED_BINARY' else 'blocked',error.code
        state['coverage'][path].update(error.details or {},processing_status='excluded' if status=='excluded' else 'failed')
    except (ValueError,TypeError,RuntimeError) as error:
        observations,status,reason=[],'blocked','EXTRACTION_FAILED'
        state['coverage'][path].update(reason_code=reason,stage='extract',exception=type(error).__name__,processing_status='failed',retry_eligible=False)
    state['coverage'][path].pop('_source_policy',None)
    state['coverage'][path].pop('_identity_policy',None)
    state['coverage'][path].update(status=status, reason=reason)
    return observations


def _scan_progress(state, paths, retried=None):
    snap = state['snapshot']
    remaining = state['counters']['remaining_files']
    state['processing_complete'] = remaining == 0
    state['complete'] = remaining == 0 and not snap.get('coverage_errors') and not any(
        state['counters'][key] for key in ('failed_files', 'partially_processed_files'))
    state['state'] = 'IN_PROGRESS' if remaining else 'COMPLETED' if state['complete'] else 'COMPLETED_WITH_GAPS'
    state['semantic_coverage_complete'] = False
    state['source_verified'] = False
    state['work'] = {'version': 1, 'extracted_this_call': len(paths), 'paths_this_call': paths,
                     'durable_extracted_files': len(state['coverage']) - remaining, 'remaining_files': remaining,
                     'enumeration_and_hashing': 'exact bytes checked at extraction and authoritative snapshot boundaries'}
    if retried is not None:
        state['work']['retried_blocked_files'] = retried


def _coverage_bucket(entry):
    status = entry['status']
    if status == 'excluded': return 'classified_excluded_files'
    if status == 'blocked': return 'failed_files'
    if status == 'not-analyzed': return 'remaining_files'
    if entry.get('processing_status') == 'partial': return 'partially_processed_files'
    return 'processed_files'


def _coverage_transition(state, before, after):
    counters = state['counters']
    previous, current = _coverage_bucket(before), _coverage_bucket(after)
    counters[previous] -= 1
    counters[current] += 1
    counters['eligible_files'] += (previous == 'classified_excluded_files') - (current == 'classified_excluded_files')
    counters['pending_retries'] += (current == 'failed_files' and after.get('retry_eligible', False)) - (
        previous == 'failed_files' and before.get('retry_eligible', False))


def _replay(state, delta, index, by_file):
    if 'coverage' not in state:
        state['coverage'] = _initial_coverage(state)
    if 'counters' not in state:
        state['counters'] = coverage_counters(state)
    for path, entry, observations in delta['updates']:
        expected = state['snapshot']['files'].get(path)
        require(expected is not None and path in state['coverage'] and entry['hash'] == expected['hash'],
                'corrupt-scan-checkpoint')
        require(all(o['path'] == path and o['content_hash'] == expected['hash'] for o in observations),
                'corrupt-scan-checkpoint')
        _coverage_transition(state, state['coverage'][path], entry)
        state['coverage'][path] = entry
        by_file[path] = observations
        aggregate_observations(state, [dict(o) for o in observations], path, index)
    _scan_progress(state, delta['paths'], delta.get('retried'))
    state.update(delta.get('details', {}))


def _load_checkpoint(db, scan_id, by_file=None):
    index = None
    if by_file is None:
        by_file = {}

    def replay(state, delta):
        nonlocal index
        if index is None:
            index = {o['id']: o for o in state['observations']}
            if 'coverage' in state:
                by_file.update(file_cache.historical_observations(state))
        _replay(state, delta, index, by_file)

    return scan_checkpoint.load(db, scan_id, replay)


def _legacy_scan(db, scan_id):
    row = db.execute('SELECT payload FROM scans WHERE id=?', (scan_id,)).fetchone()
    return row[0] if row else None


def _retry_busy(operation):
    # A SQLite BUSY commit is rolled back when the connection closes. Retry the
    # same durable operation without repeating extraction or widening timeouts.
    delays = (.025, .075, .150)
    for delay in delays:
        try:
            return operation()
        except KnowledgeError as error:
            if error.code != 'store-busy-retry':
                raise
            time.sleep(delay)
    return operation()


class ScanSession:
    # One bounded, reusable source snapshot owned by a scan execution.

    def __init__(self, store):
        self.store = store
        self.state = None
        self.generation = None
        self.by_file = {}

    def _open(self, scan_id, base, head, restart, incremental):
        from .persistence_identity import POLICY
        from uuid import uuid4

        root = self.store.project.root
        snap = inventory(root, base, head)
        self.branch = _branch(root, snap)
        chosen = _selected_paths(root, snap, incremental)
        provided = scan_id
        if scan_id is None or restart:
            scan_id = digest([self.store.project.identity, snap['identity'], snap['delta'], VERSION]
                             + (['incremental-v1', sorted(chosen)] if incremental else [])
                             + ([uuid4().hex] if restart else []))
        with self.store.connection() as db:
            require(life.enabled(db), 'upgrade-required')
            persisted = _load_checkpoint(db, scan_id, self.by_file)
            self.legacy = _legacy_scan(db, scan_id)
            terminal = scan_history.decode(db, scan_id, self.legacy) if self.legacy and not persisted else None
        if persisted:
            state, self.generation = persisted
        elif self.legacy:
            state = terminal
            self.by_file.update(file_cache.historical_observations(state))
        else:
            require(not provided or restart, 'unknown-scan')
            state = dict(id=scan_id, extractor=VERSION, identity_policy=POLICY, snapshot=snap,
                         observations=[], candidates=[], captured_at=life.now(), complete=False)
            if incremental:
                state.update(incremental=True, scope_paths=sorted(chosen))
        require(state['snapshot']['identity'] == snap['identity'], 'stale-scan-restart-required')
        require(state['extractor'] == VERSION, 'stale-extractor-restart-required')
        if base or head:
            require(state['snapshot']['delta'] == snap['delta'], 'scan-range-mismatch-restart-required')
        require(bool(state.get('incremental')) == incremental, 'scan-scope-mismatch-restart-required')
        require(state.get('git_branch', self.branch) == self.branch, 'stale-scan-restart-required')
        state['git_branch'] = self.branch
        self.initial = None
        if not persisted:
            if self.legacy:
                # A legacy partial artifact can start a new provisional chain.
                from copy import deepcopy
                if any(entry['status'] in ('not-analyzed','blocked') for entry in state['coverage'].values()):
                    self.initial = deepcopy({k: v for k, v in state.items() if k != 'snapshot'})
                    self.initial['snapshot'] = state['snapshot']
            else:
                self.initial = dict(state, observations=[], candidates=[])
        if 'coverage' not in state:
            state['coverage'] = _initial_coverage(state)
        if not persisted:
            state['counters'] = coverage_counters(state)
        self.state = state
        self.arguments = (base, head, incremental)
        self.index = {o['id']: o for o in state['observations']}
        self.pending = iter(self._pending())

    def _pending(self):
        return sorted((p for p, e in self.state['coverage'].items() if e['status'] == 'not-analyzed'),
                      key=lambda p: (not p.endswith(('.csproj', '.cs')), p))

    def scan(self, scan_id=None, max_files=50, base=None, head=None, restart=False, incremental=False,
             retry_blocked=False, details=False, reconcile_result=False):
        from itertools import islice
        require(type(max_files) is int and 1 <= max_files <= 10000, 'invalid-scan-bound')
        require(not retry_blocked or (scan_id is not None and not restart), 'retry-blocked-requires-current-scan-id')
        if self.state is None:
            self._open(scan_id, base, head, restart, incremental)
        else:
            require(scan_id == self.state['id'] and not restart and (base, head, incremental) == self.arguments,
                    'scan-execution-binding-mismatch')
        state = self.state
        root = self.store.project.root
        snap = state['snapshot']
        retried = []
        if retry_blocked:
            for path, entry in state['coverage'].items():
                original = snap['files'][path]
                if entry['status'] == 'blocked' and entry.get('retry_eligible', True) and original['status'] != 'blocked' and original.get('hash') is not None:
                    retried_entry = dict(entry, status='not-analyzed', reason='explicit retry after observation')
                    _coverage_transition(state, entry, retried_entry)
                    state['coverage'][path] = retried_entry
                    retried.append(path)
            self.pending = iter(self._pending())
        paths = list(islice(self.pending, max_files))
        updates = []
        for path in paths:
            before = dict(state['coverage'][path])
            observations = _extract_path(root, state, path)
            after = state['coverage'][path]
            _coverage_transition(state, before, after)
            updates.append((path, after, observations))
            self.by_file[path] = observations
            aggregate_observations(state, [dict(o) for o in observations], path, self.index)
        updates.extend((p, state['coverage'][p], []) for p in retried if state['coverage'][p]['status'] == 'not-analyzed')
        _scan_progress(state, paths, len(retried) if retry_blocked else None)
        reconciliation = None
        if not state['processing_complete']:
            diagnostic = {}
            if details:
                with self.store.connection() as db:
                    records = self.store._records(db)
                    scope = identity_scope(_scan_scope(db,state,self.by_file), records)
                    state['impact'] = _scan_impact(self.store, db, state, records, scope)
                    diagnostic = {key: state[key] for key in ('impact','identity_verification','gaps') if key in state}
            delta = {'paths': paths, 'updates': updates, 'retried': len(retried) if retry_blocked else None}
            if diagnostic:
                delta['details'] = diagnostic
            encoded = scan_checkpoint.encode(state['id'], self.generation, self.initial, delta)
            def append():
                with self.store.discovery_checkpoint_connection() as db:
                    if self.generation is None:
                        require(_legacy_scan(db, state['id']) == self.legacy, 'concurrent-scan-checkpoint-changed')
                    return scan_checkpoint.append(db, state['id'], self.generation, encoded)

            self.generation = _retry_busy(append)
            self.initial = None
        else:
            state, reconciliation = _retry_busy(lambda: self._complete(base, head, reconcile_result))
            self.state = state
        result = {'ok': True, **state}
        if reconciliation is not None:
            result['reconciliation'] = reconciliation
        return result

    def _complete(self, base, head, reconcile_result):
        state = dict(self.state, candidates=list(self.state['candidates']))
        root = self.store.project.root
        snap = state['snapshot']
        with self.store.discovery_completion_connection() as db:
            require(life.enabled(db), 'upgrade-required')
            require(_legacy_scan(db, state['id']) == self.legacy and scan_checkpoint.generation(db, state['id']) == self.generation,
                    'concurrent-scan-checkpoint-changed')
            records = self.store._records(db)
            states = life.latest(db)
            scope = identity_scope(_scan_scope(db, state, self.by_file), records)
            new_queue, receipts, refreshes, cache_rows = _prepare_completion(self.store, db, state, self.by_file, records, states, scope)
            reconciliation = _reconcile(self.store, db, state, records, states, scope) if reconcile_result else None
            state['source_verified'] = True
            payload, blocks = scan_history.prepare(db, state)
            current = inventory(root, base, head)
            require(current['identity'] == snap['identity'] and (not (base or head) or current['delta'] == snap['delta'])
                    and _branch(root, current) == self.branch, 'source-changed-during-scan-restart')
            db.executemany('INSERT INTO queue VALUES (?,?,?,NULL)', new_queue)
            db.executemany('INSERT OR IGNORE INTO metadata VALUES (?,?)', receipts)
            _write_refreshes(db, refreshes)
            if cache_rows is not None:
                file_cache.save(db, *cache_rows)
            scan_history.write_blocks(db, blocks)
            scan_checkpoint.publish(db, state['id'], self.generation, payload)
        return state, reconciliation


def scan(store, scan_id=None, max_files=50, base=None, head=None, restart=False, incremental=False,
         retry_blocked=False):
    return ScanSession(store).scan(scan_id, max_files, base, head, restart, incremental, retry_blocked, details=True)


def _scan_scope(db, state, by_file=None):
    if state.get('incremental'):
        return incremental_scope(db, state, by_file)
    return {'snapshot': state['snapshot'], 'observations': state['observations'],
            'ambiguous': dict.fromkeys(state.get('ambiguous', [])), 'complete': state['complete'],
            'verification_coverage': state['coverage']}


def _prepare_completion(store, db, state, by_file, records, states, scope):
    snap = state['snapshot']
    incremental = state.get('incremental', False)
    state['impact'] = _scan_impact(store, db, state, records, scope)
    state['semantic_coverage_complete']=False
    state['limits']=['No runtime/deployment proof or business rationale','C# lexical matches are partial, not compiler analysis','Non-code files are content inventory only','Untracked permitted source is included with dirty hashes; Git dirty state is separate from committed HEAD']
    # After all chunks, positive source-backed proposals may survive unrelated
    # file failures. Never guess identity in a partition with unexamined code.
    new_queue = []
    receipts = []
    refreshes = []
    candidate_index=CandidateIndex(db, store._queue_rows(db))
    state['compatibility']=[]
    state['reintroductions']=[]
    state['review_required']=[]
    incomplete_projects={e['partition'] for p,e in state['coverage'].items()
                          if p.endswith(('.cs','.csproj')) and (e['status'] in ('not-analyzed','blocked')
                          or e.get('processing_status')=='partial')}
    known_claims={c['id']:c for c in records['claims']}
    legacy_claims=[c for c in records['claims'] if c['provenance']['method'] in LEGACY_METHODS and states[c['id']]['lifecycle']=='active']
    added=set(state['candidates'])
    for obs in state['observations']:
        if incremental and (not scope['complete'] or obs['id'] in scope['ambiguous']):continue
        if obs['project'] in incomplete_projects:continue
        if snap.get('coverage_errors'):continue
        known=known_claims.get(obs['id'])
        if known and (states[known['id']]['lifecycle']=='superseded' or not discovery_owned(db,known,records,scope)):
            state['review_required'].append({'id':known['id'],'reason':'supersession or reviewed assertion ownership requires manual review; no automatic overwrite/reactivation'})
        legacy=[c for c in legacy_claims if c['id']==obs['legacy_id'] or c['statement']==obs['statement']]
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
            # Equivalent decided observations retain their disposition.
            # Pending old snapshots get a new, separately approved binding.
            if equivalent_candidate(db,value,candidate_index) is None:
                if cid in candidate_index.ids:
                    matching = candidate_index.groups.get(proposal_identity(value), [])
                    registered = next((prior for identifier,prior,_ in matching if identifier == cid), None)
                    require(registered == value, 'candidate-identity-conflict')
                else:
                    new_queue.append((cid, canonical_json(value), 'pending'))
                candidate_index.add(cid,value,'pending')
                refresh_pending(db,cid,value,candidate_index,staged=refreshes)
                if not state['complete']:
                    receipt=dict(version=1,extractor=VERSION,observation=obs,candidate=cid,source=snap['identity'])
                    receipts.append((CAPTURE_RECEIPT + digest(receipt), canonical_json(receipt)))
                if cid not in added:
                    added.add(cid);state['candidates'].append(cid)


    cacheable = {p: observations for p, observations in by_file.items()
                 if file_cache.code_file(p) and file_cache.verified(state['coverage'][p])}
    cache_rows = None
    if not snap.get('coverage_errors') and (cacheable or scope.get('cached_sources')):
        if not file_cache.exists(db):
            cacheable = {**scope.get('cached_sources', {}), **cacheable}
        cache_rows = file_cache.rows(db, store.project.identity, snap,
                                    scope.get('cache_context') or file_cache.configuration(snap), cacheable)
    return new_queue, receipts, refreshes, cache_rows


def _scan_impact(store, db, state, records, scope):
    changed={e['id'] for e in records['evidence'] if fresh_evidence(store.project.root,e,scope,db=db) not in CURRENT_EVIDENCE}
    owners={c['id'] for c in records['claims'] if changed.intersection(c['evidence'])}
    reverse = scope['_dependents']
    closure = set(owners)
    pending = list(owners)
    while pending:
        for dependent in reverse.get(pending.pop(), ()):
            if dependent not in closure:
                closure.add(dependent)
                pending.append(dependent)
    return {'changed_or_unverifiable_evidence':sorted(changed),'direct_claims':sorted(owners),
                     'dependent_claims':sorted(closure-owners),
                     'relationships':[r['id'] for r in records['relationships'] if r['from'] in closure or r['to'] in closure],
                     'policy':('completed included scope reused' if state['complete'] else 'partial durable scope; unexamined discovery evidence is not freshly verified')+'; impact is a review request, not retirement'}

def coverage_counters(state):
    from collections import Counter
    entries = list(state['coverage'].values())
    numbers = Counter(_coverage_bucket(entry) for entry in entries)
    excluded = numbers['classified_excluded_files']
    failures = numbers['failed_files']
    partial = numbers['partially_processed_files']
    remaining = numbers['remaining_files']
    processed = numbers['processed_files']
    snapshot=state['snapshot']
    policy_files=sum(e.get('kind','file')=='file' for e in snapshot['exclusions'])
    return {'discovered_files':len(snapshot['files'])+policy_files, 'eligible_files':len(entries)-excluded,
            'policy_excluded_files':policy_files, 'classified_excluded_files':excluded,
            'pruned_directories':sum(e.get('kind')=='directory' for e in snapshot['exclusions']),
            'out_of_scope_files':len(snapshot['files'])-len(entries),
            'processed_files':processed,'partially_processed_files':partial,'failed_files':failures,'remaining_files':remaining,
            'pending_retries':sum(e['status']=='blocked' and e.get('retry_eligible',False) for e in entries)}


def reconcile(store,scan_id):
    with store.connection() as db:
        require(life.enabled(db),'upgrade-required')
        pending=_load_checkpoint(db,scan_id)
        payload=_legacy_scan(db,scan_id) if pending is None else None
        require(pending is not None or payload is not None,'unknown-scan')
        scan=pending[0] if pending else scan_history.decode(db, scan_id, payload)
        current=inventory(store.project.root)
        require(current['identity']==scan['snapshot']['identity'] and
                ('git_branch' not in scan or _branch(store.project.root,current)==scan['git_branch']),
                'stale-scan-restart-required')
        records=store._records(db)
        return _reconcile(store, db, scan, records, life.latest(db), identity_scope(_scan_scope(db,scan),records))


def _reconcile(store, db, scan, records, states, scope):
    out = []
    observed={o['id']:o for o in scan['observations']}
    for c in records['claims']:
        fresh=freshness(store.project.root,c,records,scope,db=db)
        classification='unchanged' if fresh['trusted'] else 'not-verifiable'
        if states[c['id']]['lifecycle']!='active':classification='historical'
        elif not fresh['trusted'] and c['id'] in observed:classification='changed'
        elif scan['complete'] and not fresh['trusted'] and c['provenance']['method'] in DISCOVERY_METHODS:classification='suspected-obsolete'
        dependents=scope['_dependents'].get(c['id'],[])
        out.append(dict(id=c['id'],classification=classification,freshness=fresh,lifecycle=states[c['id']]['lifecycle'],dependents=dependents,
                        retirement_proposed=False,reason='Retirement requires reviewed positive corroboration; lexical absence alone is insufficient.'))
    retirement=[]
    current={c['id']:c for c in records['claims']}
    negative_gaps=negative_coverage_gaps(scan['snapshot'])
    negative_gaps.extend({'project':e['partition'],'path':p,'reason':e.get('reason_code') or e.get('reason','incomplete extraction')}
                         for p,e in scan['coverage'].items() if e['status'] in ('blocked','excluded') or e.get('processing_status')=='partial')
    delta=scan['snapshot'].get('delta')
    if scan['complete'] and not scan.get('incremental') and delta and not scan.get('gaps'):
        before={}
        for _, old in scan_history.scan_rows(db, revision=delta['base'], complete=True):
            before.update({o['id']:(o,old['snapshot']) for o in old['observations']})
        # Search one bounded source at a time; do not concatenate an entire
        # repository into memory for negative proof.
        def referenced(subject):
            pattern=re.compile(r'(?<![A-Za-z0-9_])'+re.escape(subject)+r'(?![A-Za-z0-9_])')
            for path,entry in scan['coverage'].items():
                if entry['status'] in ('blocked','excluded') or entry.get('processing_status')=='partial':return True
                try:text,_=source_reader.read(store.project.root,path,entry,scan['snapshot']['policy'])
                except (KnowledgeError,OSError,UnicodeError):return True
                if pattern.search(text):return True
            return False
        for row in out:
            prior=before.get(row['id'])
            if not prior:continue
            old,old_snapshot=prior
            if row['id'] in observed or row['lifecycle']!='active':continue
            claim=current[row['id']]
            if old.get('method')!=VERSION or claim['provenance']!={'actor':'deterministic-discovery','method':VERSION} or claim['statement']!=old['statement']:
                row.update(classification='not-verifiable',reason='Current reviewed meaning/ownership does not match the source assertion; manual review required.')
                continue
            relevant=[g for g in negative_gaps if g['project'] in (old['project'],'.')]
            if relevant:
                row.update(classification='not-verifiable',reason='Excluded/unsupported source prevents negative evidence proof.',coverage_gaps=relevant)
                continue
            # Before/after exact source proof + complete lexical inventory + reference/consumer search.
            raw=git_process(store.project.root,'show',delta['base']+':'+old['path'])
            if raw.returncode or not base_source_matches(raw.stdout,old,old_snapshot):continue
            if referenced(old['subject']):continue
            row.update(classification='proposed-retirement',retirement_proposed=True,
                       reason='Verified base source contained this lexical declaration; current full lexical inventory and consumers no longer contain its subject. No claim about external deployment.')
            retirement.append(life.op('retire','claims',row['id'],life.revision(db,row['id'])))
        retiring={o['id'] for o in retirement}
        for r in records['relationships']:
            if states[r['id']]['lifecycle']=='active' and (r['from'] in retiring or r['to'] in retiring):
                retirement.append(life.op('retire','relationships',r['id'],life.revision(db,r['id'])))
    proposal=life.batch(retirement,'Reviewed source removal corroborated by before/after and consumer inventory',
                        {'identity':scan['snapshot']['identity'],'revision':scan['snapshot']['revision'],'kind':scan['snapshot']['snapshot_kind'],'delta':delta}) if retirement else None
    return {'ok':True,'scan':scan['id'],'complete':scan['complete'],'claims':out,'source':scan['snapshot'],'canonical_unchanged':True,'negative_evidence_gaps':negative_gaps,'proposal':proposal}

def status(store,scan_id=None,*,summaries=False):
    with store.connection() as db:
        require(life.enabled(db),'upgrade-required')
        active=scan_checkpoint.identities(db) if scan_id is None else [scan_id]
        scanned={identifier: pending[0] for identifier in active if (pending:=_load_checkpoint(db,identifier)) is not None}
        scanned.update((identifier,state) for identifier,state in scan_history.scan_rows(db,scan_id,summaries=summaries) if identifier not in scanned)
        return {'ok':True,'scans':list(scanned.values())}


def completed_artifact(store,scan_id):
    """Validate persisted positive extraction without starting/extracting a scan."""
    require(isinstance(scan_id,str) and re.fullmatch('[a-f0-9]{64}',scan_id),'invalid-scan-id')
    with store.connection() as db:
        require(scan_checkpoint.generation(db,scan_id) is None, 'scan-artifact-not-completed',
                {'next_action':'Observe compatible resume options before rebuilding a candidate plan.'})
        row=db.execute('SELECT payload FROM scans WHERE id=?',(scan_id,)).fetchone();require(row is not None,'unknown-scan-artifact')
        state=scan_history.decode(db,scan_id,row[0]);require(state.get('id')==scan_id and state.get('extractor')==VERSION,'incompatible-scan-artifact-extractor',
            {'supported':VERSION,'next_action':'Preserve artifacts; review existing queue or explicitly migrate unsupported extraction. No automatic fresh scan.'})
        snap=state['snapshot'];_validate_snapshot(snap)
        coverage=state['coverage'];require(set(coverage)<=set(snap['files']),'corrupt-scan-coverage')
        expected=(set(state['scope_paths'])&set(snap['files'])) if state.get('incremental') else set(snap['files'])
        require(set(coverage)==expected and all(e.get('hash')==snap['files'][p].get('hash') for p,e in coverage.items()),'corrupt-scan-coverage')
        remaining=sum(e['status']=='not-analyzed' for e in coverage.values())
        require(remaining==0 and state.get('work',{}).get('remaining_files',0)==0,'scan-artifact-not-completed',{'remaining':remaining,'next_action':'Observe compatible resume options; no automatic fresh scan.'})
        require(state.get('complete') or state.get('state')=='COMPLETED_WITH_GAPS' or any(e['status']=='blocked' or e.get('processing_status')=='partial' for e in coverage.values()),'scan-artifact-terminal-state-unknown')
        for observation in state['observations']:
            for location in observation.get('occurrences',[observation]):
                p=location['path'];require(p in snap['files'] and location['content_hash']==snap['files'][p]['hash'],'corrupt-scan-observation')
        queued={cid:loads(p) for cid,p in db.execute('SELECT id,payload FROM queue')}
        for cid in state['candidates']:
            require(cid in queued and (queued[cid].get('source') or {}).get('identity')==snap['identity'],'scan-candidate-binding-incompatible',{'candidate':cid})
        return {'scan_id':scan_id,'source_identity':snap['identity'],'state':state.get('state','COMPLETED' if state['complete'] else 'COMPLETED_WITH_GAPS'),
                'coverage_complete':state['complete'],'coverage':state.get('counters'),'extraction_reused':True,'fresh_scan_started':False}



REFRESH_PREFIX='candidate-refresh-v1:'


def candidate_refreshes(db):
    """Additive audit links; original queue payloads and human decisions survive."""
    links={}
    for key,payload in db.execute("SELECT key,value FROM metadata WHERE key LIKE 'candidate-refresh-v1:%'"):
        value=loads(payload)
        require(isinstance(value,dict) and set(value)=={'version','previous','replacement','at'} and type(value['version']) is int and value['version']==1 and isinstance(value['at'],str),'corrupt-candidate-refresh')
        old,new=value['previous'],value['replacement']
        require(isinstance(old,str) and isinstance(new,str) and old!=new and key==REFRESH_PREFIX+old,'corrupt-candidate-refresh')
        pair=[db.execute('SELECT payload FROM queue WHERE id=?',(cid,)).fetchone() for cid in (old,new)]
        require(all(pair),'corrupt-candidate-refresh')
        first,second=(loads(row[0]) for row in pair)
        require(all(v['version']==2 and v['source'] is not None for v in (first,second)) and proposal_identity(first)==proposal_identity(second) and first['source']['identity']!=second['source']['identity'],'corrupt-candidate-refresh')
        links[old]=value
    from .confluence_sync import refresh_links
    links.update(refresh_links(db))
    for old in links:
        seen=set();current=old
        while current in links:
            require(current not in seen,'corrupt-candidate-refresh-cycle');seen.add(current);current=links[current]['replacement']
    return links


class CandidateIndex:
    """One validated transaction-local index, incrementally updated by this writer.

    Avoid rescanning/decoding the whole queue for every extracted declaration.
    Human dispositions, committed plans and source refresh links keep the same
    precedence as the non-batch APIs. No schema or persistent index migration.
    """
    def __init__(self,db,queue=None):
        from .providers import semantic_bindings
        self.groups={};self.ids=set();self.links=candidate_refreshes(db);self.semantic=semantic_bindings(db)
        self.owned={cid for payload, in db.execute("SELECT payload FROM plans WHERE status='COMMITTED'") for cid in loads(payload)['included']}
        if queue is None:
            queue = ((cid,status,raw,loads(raw)) for cid,raw,status in db.execute('SELECT id,payload,status FROM queue ORDER BY id'))
        for cid,status,_,item in queue:
            self.add(cid,item,status)
    def add(self,cid,item,status):
        if cid in self.ids:return
        self.ids.add(cid)
        if item['version']==2:
            group=self.groups.setdefault(proposal_identity(item),[]);group.append((cid,item,status));group.sort(key=lambda row:row[0])


def equivalent_candidate(db,value,index=None):
    if index is not None:
        matches=index.groups.get(proposal_identity(value),[])
        decided=next(((cid,status) for cid,item,status in matches if status in ('rejected','deferred','imported')),None)
        return decided or next(((cid,status) for cid,item,status in matches if cid not in index.links and item['source']==value['source']),None)
    signature=proposal_identity(value);links=candidate_refreshes(db);matches=[]
    for cid,payload,status in db.execute('SELECT id,payload,status FROM queue ORDER BY id'):
        item=loads(payload)
        if item['version']==2 and proposal_identity(item)==signature:matches.append((cid,item,status))
    # A deliberate human disposition is not a stale pending source binding.
    decided=next(((cid,status) for cid,item,status in matches if status in ('rejected','deferred','imported')),None)
    if decided:return decided
    return next(((cid,status) for cid,item,status in matches if cid not in links and item['source']==value['source']),None)


def refresh_pending(db,cid,value,index=None,staged=None):
    """Called only after a freshly observed replacement enters the durable queue."""
    if value['version']!=2 or value['source'] is None:return
    links=index.links if index else candidate_refreshes(db)
    require(cid not in links,'historical-candidate-refresh-requires-new-observation')
    owned=index.owned if index else {c for payload, in db.execute("SELECT payload FROM plans WHERE status='COMMITTED'") for c in loads(payload)['included']}
    signature=proposal_identity(value)
    from .providers import semantic_bindings
    semantic=index.semantic if index else semantic_bindings(db)
    rows=index.groups.get(signature,[])[:] if index else [(old,loads(payload),status) for old,payload,status in db.execute('SELECT id,payload,status FROM queue')]
    for old,prior,status in rows:
        if old==cid or old in links or old in owned or old in semantic or status!='pending' or prior['version']!=2 or prior['source'] is None:continue
        if prior['source']['identity']==value['source']['identity'] or proposal_identity(prior)!=signature:continue
        receipt=dict(version=1,previous=old,replacement=cid,at=life.now())
        if staged is None:
            _write_refreshes(db, [receipt])
        else:
            staged.append(receipt)
        if index is not None:index.links[old]=receipt


def _write_refreshes(db, receipts):
    db.executemany('INSERT INTO metadata VALUES (?,?)',
                   ((REFRESH_PREFIX + row['previous'], canonical_json(row)) for row in receipts))
    db.executemany('INSERT INTO history(payload) VALUES (?)',
                   ((canonical_json(dict(event='candidate-refreshed', **row)),) for row in receipts))


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
    by_file = {}
    coverage = {}
    complete = not snapshot.get('coverage_errors')
    for path, original in sorted(snapshot['files'].items()):
        entry = coverage[path] = dict(original)
        if entry['status'] == 'blocked':
            complete = False
            continue
        try:
            by_file[path], entry['status'], _ = extract(root,path,entry)
        except (OSError,UnicodeError,KnowledgeError):
            entry['status'] = 'blocked'
            complete = False
        if entry.get('processing_status') == 'partial':
            complete = False
    observations, ambiguous = _group_observations(by_file)
    return {'snapshot': snapshot, 'observations': observations, 'ambiguous': ambiguous,
            'complete': complete, 'verification_coverage': coverage}

def negative_coverage_gaps(snapshot):
    """Excluded source is not negative evidence. No excluded content is loaded.

    Administrative storage is exempt. Other excluded source/output directories
    block negative proof: arbitrary Compile Include rules may make them live.
    """
    projects=[p for p in snapshot['files'] if p.endswith('.csproj')]
    result=[{'project':project,'path':error['path'],'reason':error['reason']} for error in snapshot.get('coverage_errors',[]) for project in projects or ['.']]
    administrative={'.maintenance','.harness','.knowledge-control.lock','.git','.gitignore','.gitattributes','.editorconfig','.knowledge','.ai','.venv','.local','.vs','TestResults'}
    for excluded in snapshot['exclusions']:
        path=Path(excluded['path'])
        if any(part in administrative for part in path.parts):continue
        relevant=path.suffix.lower() in {'.cs','.csproj','.props','.targets','.fs','.vb','.razor','.json','.config'} or not path.suffix
        if not relevant:continue
        for project in projects or ['.']:
            directory=Path(project).parent
            if directory==path.parent or directory in path.parents or directory==Path('.'):
                result.append({'project':project,'path':str(path),'reason':'excluded potentially live source/configuration; no absence proof'})
    for path,entry in snapshot['files'].items():
        if entry.get('negative_scope_reason'):
            affected=[path] if path.endswith('.csproj') else projects
            result.extend({'project':project,'path':path,'reason':entry['negative_scope_reason']} for project in affected)
        if entry['status']=='blocked':result.append({'project':entry['partition'],'path':path,'reason':entry.get('reason','blocked source')})
    return result


def discovery_owned(db, claim, records, scope=None):
    """A former ID/provenance alone does not own a later reviewed assertion."""
    if claim['provenance'] != {'actor':'deterministic-discovery','method':VERSION}:
        return False
    from .persistence_identity import CanonicalIndex, describe

    context = scope if scope is not None else {}
    if '_historical_ownership' not in context:
        canonical = context.get('_canonical_index') or CanonicalIndex(records)
        current = context.get('_claims_by_id') or {c['id']: c for c in records['claims']}
        index = {}
        for _, prior in scan_history.scan_rows(db, complete=True, extractor=VERSION, observations_only=True):
            for observation in prior['observations']:
                identifiers = {observation['id']}
                known = canonical.match(observation) if describe(observation) is not None else None
                if known is not None:
                    identifiers.add(known['id'])
                for identifier in identifiers & current.keys():
                    key = (identifier, observation['statement'])
                    index.setdefault(key, set()).add((observation['content_hash'], observation['path']))
        context['_historical_ownership'] = index
    evidence = context.get('_evidence_by_id') or {e['id']: e for e in records['evidence']}
    sources = context['_historical_ownership'].get((claim['id'], claim['statement']), set())
    if any(isinstance(evidence[i]['source'], str) and (evidence[i].get('content_hash'),evidence[i]['source']) in sources
           for i in claim['evidence']):
        return True
    return capture_owned(db,claim,records)


def occurrence(observation):
    return {k:observation[k] for k in ('path','line','anchor','content_hash')}


def aggregate_observations(state,observations,path,index=None):
    """Chunk-local index is reconstructed from the durable ordered checkpoint."""
    if index is None:index={o['id']:o for o in state['observations']}
    ambiguous=set(state.get('ambiguous',[]))
    for observation in observations:
        identifier=observation['id'];prior=index.get(identifier)
        if prior and equivalent_occurrence(prior,observation):
            prior.setdefault('occurrences',[occurrence(prior)]).append(occurrence(observation));continue
        if prior or identifier in ambiguous or observation.get('unsupported'):
            ambiguous.add(identifier)
            if identifier in index:
                del index[identifier]
                state['observations']=[o for o in state['observations'] if o['id']!=identifier]
            state.setdefault('gaps',[]).append({'id':identifier,'reason':'ambiguous lexical identity: all members withheld','path':path});continue
        index[identifier]=observation;state['observations'].append(observation)
    state['ambiguous']=sorted(ambiguous)


def equivalent_occurrence(first,second):
    # These claims only assert that one file contains literal syntax; multiple
    # identical occurrences support the same assertion, not distinct type owners.
    from .persistence_identity import POLICY
    keys=('id','project','category','statement','subject')
    if first['category']!='persistence' or first.get('identity_policy')!=POLICY or second.get('identity_policy')!=POLICY:keys+=('path',)
    return first['category']!='declaration' and not first.get('unsupported') and not second.get('unsupported') and all(first[k]==second[k] for k in keys)


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
        from .persistence_identity import canonical_match
        match=canonical_match(observation,records,{})
        if receipt['extractor']!=VERSION or (observation['id']!=claim['id'] and (match is None or match['id']!=claim['id'])) or observation['statement']!=claim['statement']:continue
        if not any(evidence[i]['provenance']=={'actor':'deterministic-discovery','method':VERSION} and evidence[i]['content_hash']==observation['content_hash'] and evidence[i]['source']==observation['path'] and evidence[i]['description']==observation['anchor'] and claim['id'] in evidence[i]['substantiates'] for i in claim['evidence']):continue
        for pid,plan_json in db.execute('SELECT plan,payload FROM receipts'):
            plan=loads(plan_json);candidate=plan['candidates'].get(receipt['candidate'])
            if candidate is None or digest(candidate)!=receipt['candidate']:continue
            candidate=plan.get('resolved',plan['candidates']).get(receipt['candidate'])
            if candidate is None:continue
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
    root = store.project.root
    paths = set(paths)
    snapshot = inventory(root)
    branch = _branch(root, snapshot)
    selected = {path: dict(snapshot['files'][path]) for path in paths & snapshot['files'].keys()
                if file_cache.code_file(path)}
    if not selected:
        removed = paths - snapshot['files'].keys()
        connection = store.discovery_completion_connection if record_ownership and removed else store.connection
        with connection() as db:
            require(life.enabled(db), 'upgrade-required')
            if record_ownership and removed and file_cache.exists(db):
                _verify_capture_snapshot(root, snapshot, branch)
                db.executemany('DELETE FROM discovery_file_cache WHERE path=?', ((path,) for path in sorted(removed)))
        return {'ok': True, 'source': snapshot['identity'], 'decisions': [], 'gaps': [],
                'reason': 'no changed source with a supported extractor'}
    from .persistence_identity import POLICY
    state = dict(snapshot=snapshot, coverage=selected, identity_policy=POLICY)
    by_file = {path: _extract_path(root, state, path) for path in sorted(selected)
               if selected[path]['status'] == 'not-analyzed'}
    state['complete'] = not snapshot.get('coverage_errors') and all(file_cache.verified(e) for e in selected.values())
    require(state['complete'], 'capture-source-analysis-incomplete', {
        'next_action': 'Inspect source policy and extraction diagnostics, then retry capture or review manually.'})
    receipts = []
    with (store.discovery_completion_connection() if record_ownership else store.connection()) as db:
        require(life.enabled(db), 'upgrade-required')
        scope = _cached_scope(db, store.project.identity, state, by_file, dependencies=True, root=root)
        missing = state['identity_verification']['missing_files']
        require(not missing, 'capture-observation-cache-incomplete', {
            'missing_file_count': len(missing), 'path_sample': missing[:20],
            'next_action': 'Run an explicit full knowledge-init or submit reviewed candidates, then retry capture.'})
        decisions = [{'observation': identifier, 'decision': 'manual-review',
                      'reason': 'ambiguous lexical identity against current source; withheld'}
                     for identifier, members in sorted(scope['ambiguous'].items())
                     if any(o['path'] in paths for o in members)]
        records=store._records(db);states=life.latest(db)
        current={c['id']:c for c in records['claims']}
        candidate_index = CandidateIndex(db, store._queue_rows(db))
        scope = identity_scope(scope, records)
        for obs in scope['observations']:
            if not any(location['path'] in paths for location in obs.get('occurrences',[obs])):continue
            legacy=[c['id'] for c in records['claims'] if c['provenance']['method'] in LEGACY_METHODS and c['id']==obs['legacy_id']]
            if legacy:
                decisions.append({'observation':obs['id'],'decision':'manual-review','legacy_ids':legacy});continue
            known=current.get(obs['id'])
            if known and (states[obs['id']]['lifecycle']=='superseded' or not discovery_owned(db,known,records,scope)):
                decisions.append({'observation':obs['id'],'decision':'manual-review','reason':'positive observation ownership or successor requires explicit review; no automatic overwrite/reactivation','current_revision':states[obs['id']]['revision']});continue
            value=proposal(store,db,obs,snapshot,captured_at or life.now(),records,states,scope)
            if value is None:continue
            equivalent=equivalent_candidate(db,value,candidate_index)
            if equivalent:decisions.append({'observation':obs['id'],'decision':'existing','candidate':equivalent[0],'status':equivalent[1]})
            else:
                decisions.append({'observation':obs['id'],'decision':'submit','payload':value})
                if record_ownership:
                    receipt=dict(version=1,extractor=VERSION,observation=obs,candidate=digest(value),source=snapshot['identity'])
                    receipts.append((CAPTURE_RECEIPT + digest(receipt), canonical_json(receipt)))
        cache_rows = None
        if record_ownership:
            cached = scope['cached_sources']
            dependencies = state['identity_verification']['dependency_files_extracted']
            updates = {p: cached[p] for p in dependencies if p in cached} if file_cache.exists(db) else cached
            cache_rows = file_cache.rows(db, store.project.identity, snapshot, scope['cache_context'],
                                        {**updates, **by_file})
        _verify_capture_snapshot(root, snapshot, branch)
        if record_ownership:
            file_cache.save(db, *cache_rows)
            db.executemany('INSERT OR IGNORE INTO metadata VALUES (?,?)', receipts)
    return {'ok':True,'source':snapshot['identity'],'decisions':decisions,'gaps':list(scope['ambiguous']),
            'reason':'eligible changed-source syntax or explicit review' if decisions else 'no new eligible supported source fact'}


def _verify_capture_snapshot(root, snapshot, branch):
    current = inventory(root)
    require(current['identity'] == snapshot['identity'] and _branch(root, current) == branch,
            'source-changed-during-preview')
