"""Project presence identity, independent of file names; old evidence stays data."""
from pathlib import Path
import re
from .util import digest,loads,require

POLICY='project-presence-v1'
LEGACY='legacy-file-presence-v0'
METHOD='dotnet-lexical-v3'


def identifier(project,method,argument):
    return 'scan.'+digest(['identity-v3',project,'persistence',method+':'+str(argument)])[:32]


def describe(observation):
    if observation.get('category')!='persistence' or observation.get('method')!=METHOD:return None
    project=observation['project'];label=Path(project).stem+' ['+project+']' if project!='.' else 'root [.]'
    prefix=label+' contains ';suffix=' persistence/configuration syntax.';text=observation['statement']
    if not text.startswith(prefix) or not text.endswith(suffix):return None
    match=re.fullmatch(r'(AddDbContext|UseSqlServer|UseSqlite|GetConnectionString)(?:<(.+)>)?',text[len(prefix):-len(suffix)])
    if not match:return None
    method,argument=match.groups();return project,method,argument


def compatible_ids(observation,paths=None):
    data=describe(observation)
    if data is None:return {observation['id']}
    project,method,argument=data
    paths=paths or [o['path'] for o in observation.get('occurrences',[observation])]
    return {identifier(project,method,argument)}|{
        'scan.'+digest(['identity-v3',project,'persistence',Path(path).stem+':'+method+':'+str(argument)])[:32] for path in paths}


def canonical_match(observation,records,states):
    if describe(observation) is None:return None
    evidence={e['id']:e for e in records['evidence']}
    matches=[]
    for claim in records['claims']:
        if claim['statement']!=observation['statement'] or claim['provenance']!={'actor':'deterministic-discovery','method':METHOD}:continue
        # Approved historical proofs retain the old file-stem identity even when
        # that file has disappeared and current supporting evidence moved.
        paths=[e['source'] for e in evidence.values() if claim['id'] in e['substantiates']
               and isinstance(e['source'],str) and e['provenance']==claim['provenance']]
        if claim['id'] in compatible_ids(observation,paths):matches.append(claim)
    require(len(matches)<=1,'ambiguous-canonical-persistence-identity')
    return matches[0] if matches else None


def preferences(db,pending,observations=None):
    """Index validated persisted producer identities, not statement guesses."""
    wanted={}
    for cid,item in pending.items():
        if item.get('source') is None or item['source'].get('kind')=='confluence':continue
        for op in item.get('operations',[]):
            if op['kind']=='claims' and op['action']=='add' and op['payload']['provenance']=={'actor':'deterministic-discovery','method':METHOD}:
                wanted[op['id']]=(op['payload']['statement'],item['source']['identity'])
    if not wanted:return {}
    result={}
    def accept(o,source,files=None):
        if o.get('id') not in wanted or wanted[o['id']]!=(o.get('statement'),source):return
        data=describe(o)
        if data is None:return
        require(o['id'] in compatible_ids(o),'incompatible-persistence-observation-identity')
        if files is not None:
            for location in o.get('occurrences',[o]):
                require(location['path'] in files and location['content_hash']==files[location['path']]['hash'],'corrupt-persistence-observation')
        preferred=identifier(*data)
        require(o['id'] not in result or result[o['id']]==preferred,'ambiguous-persistence-identity')
        result[o['id']]=preferred
        if observations is not None:observations.setdefault(o['id'],[]).append(o)
    sources={source for _,source in wanted.values()}
    for payload, in db.execute('SELECT payload FROM scans'):
        state=loads(payload);snap=state.get('snapshot',{})
        if snap.get('identity') not in sources or state.get('extractor')!=METHOD:continue
        core={k:v for k,v in snap.items() if k not in ('identity','delta','snapshot_kind')}
        core['files']={p:{k:v for k,v in item.items() if k!='status'} for p,item in snap['files'].items()}
        require(digest(core)==snap['identity'],'corrupt-persistence-scan-snapshot')
        for o in state['observations']:accept(o,snap['identity'],snap['files'])
    for payload, in db.execute("SELECT value FROM metadata WHERE key LIKE 'capture-observation-v1:%'"):
        receipt=loads(payload)
        if receipt['source'] in sources:accept(receipt['observation'],receipt['source'])
    # Queue-only fallback: prove the exact old/new producer hash from the scoped
    # statement and ALL typed source proofs. Never invent missing occurrences.
    # Store prepare/apply separately verifies the original source/provider binding.
    for item in pending.values():
        if item.get('version')!=2 or item.get('source') is None:continue
        proofs={o['id']:o['payload'] for o in item['operations'] if o['kind']=='evidence' and o['payload']}
        for op in item['operations']:
            if op['kind']!='claims' or op['action']!='add' or op['id'] not in wanted or op['id'] in result:continue
            c=op['payload'];match=re.fullmatch(r'(.+) \[([^\[\]]+)\] contains .+ persistence/configuration syntax\.',c['statement'])
            if not match:continue
            label,project=match.groups()
            if Path(project).is_absolute() or '..' in Path(project).parts or '\\' in project or (label!=('root' if project=='.' else Path(project).stem)):continue
            locations=[]
            for eid in c['evidence']:
                e=proofs.get(eid,{})
                path=e.get('source');location=e.get('location')
                if not (isinstance(path,str) and not Path(path).is_absolute() and '..' not in Path(path).parts and '\\' not in path
                        and isinstance(location,str) and re.fullmatch(re.escape(path)+r'#L[1-9][0-9]*',location)
                        and re.fullmatch(r'sha256:[a-f0-9]{64}',e.get('content_hash',''))
                        and e.get('provenance')==c['provenance'] and op['id'] in e.get('substantiates',[])):break
                locations.append(dict(path=path,line=int(location.rsplit('#L',1)[1]),anchor=e['description'],content_hash=e['content_hash']))
            else:
                if not locations:continue
                observation=dict(id=c['id'],category='persistence',project=project,method=METHOD,statement=c['statement'],occurrences=locations,**locations[0])
                if describe(observation) is not None and c['id'] in compatible_ids(observation):accept(observation,item['source']['identity'])
    return result


def recovery_projection(db,pending):
    """Restore omitted occurrences in derived payloads, preserving original CIDs."""
    from copy import deepcopy
    from . import lifecycle as life
    observations={};preferred=preferences(db,pending,observations);derived=dict(pending)
    for cid,item in pending.items():
        if item.get('version')!=2 or (item.get('source') or {}).get('kind')=='confluence':continue
        changes=[];additions=[]
        proofs={o['id']:o['payload'] for o in item['operations'] if o['kind']=='evidence' and o['payload']}
        for index,op in enumerate(item['operations']):
            if op['kind']!='claims' or op['action']!='add' or op['id'] not in observations:continue
            claim=op['payload'];locations={}
            for observation in observations[op['id']]:
                for location in observation.get('occurrences',[observation]):
                    locations[(location['path'],location['line'],location['content_hash'],location['anchor'])]=location
            existing={(e['source'],e['location'],e.get('content_hash'),e['description']) for i,e in proofs.items() if i in claim['evidence']}
            new=[]
            for _,location in sorted(locations.items()):
                path=location['path'];line=path+'#L'+str(location['line']);raw=location['content_hash'];anchor=location['anchor']
                if (path,line,raw,anchor) in existing:continue
                eid='evidence.'+digest(['occurrence-v1',op['id'],path,raw,line,anchor])
                # A recovered proof inherits its original reviewed trust/provenance.
                originals=[proofs[i] for i in claim['evidence'] if i in proofs]
                require(bool(originals),'missing-persistence-source-proof')
                proof=deepcopy(originals[0]);proof.update(id=eid,source=path,location=line,content_hash=raw,description=anchor,substantiates=[op['id']])
                new.append(eid);additions.append(life.op('add','evidence',eid,0,proof))
            if new:changes.append((index,new))
        if changes:
            value=deepcopy(item)
            for index,new in changes:value['operations'][index]['payload']['evidence'].extend(new)
            value['operations'].extend(additions);derived[cid]=value
    return derived,preferred
