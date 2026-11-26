"""Deterministic content coverage, not proof of semantic model correctness."""
import hashlib
from . import confluence as cf
from .util import require,digest
CHARS=2000


def chunk(text,start):
    end=min(start+CHARS,len(text))
    return dict(start=start,end=end,hash='sha256:'+hashlib.sha256(text[start:end].encode('utf-8')).hexdigest())


def binding(source,data):return dict(source=source,content_hash=data['content_hash'],representation=data['representation'])


def merge(source,data,value,prior=None):
    require(isinstance(value,dict) and set(value)=={'source','content_hash','representation','chunks'},'confluence-analysis-coverage-required',{'next_action':'Read deterministic snapshot chunks and submit their descriptors; analyzed_until is not coverage.'})
    require({k:value[k] for k in ('source','content_hash','representation')}==binding(source,data),'confluence-coverage-binding-mismatch')
    require(isinstance(value['chunks'],list) and len(value['chunks'])<=128,'invalid-confluence-coverage-chunks')
    entries=dict(prior or {})
    for item in value['chunks']:
        require(isinstance(item,dict) and set(item)=={'start','end','hash'} and type(item['start']) is int and type(item['end']) is int,'invalid-confluence-coverage-chunk')
        start=item['start'];require(0<=start<len(data['content']) and start%CHARS==0,'invalid-confluence-coverage-chunk-offset')
        require(item==chunk(data['content'],start),'confluence-coverage-chunk-hash-or-range-mismatch')
        key=str(start);require(key not in entries or entries[key]==item,'confluence-coverage-chunk-conflict');entries[key]=item
    return entries


def progress(data,entries):
    length=len(data['content']);expected=list(range(0,length,CHARS));prefix=0
    for start in expected:
        if str(start) not in entries:break
        prefix=min(start+CHARS,length)
    missing=[start for start in expected if str(start) not in entries]
    return dict(total_characters=length,covered_characters=sum(v['end']-v['start'] for v in entries.values()),continuous_until=prefix,verified_chunks=len(entries),expected_chunks=len(expected),missing_chunk_starts=missing[:64],missing_chunks=len(missing),complete=not missing,
                semantic_correctness='agent-reported; content coverage does not establish semantic truth')


def certificate(source,data,entries):
    state=progress(data,entries);require(state['complete'],'incomplete-confluence-analysis-coverage',state)
    return dict(version=1,**binding(source,data),characters=len(data['content']),chunk_characters=CHARS,chunks=state['expected_chunks'],coverage_hash=digest([entries[str(i)] for i in range(0,len(data['content']),CHARS)]),semantic_correctness='agent-reported, not independently verified')


def verify(db,source,value):
    require(isinstance(value,dict),'confluence-analysis-coverage-revalidation-required')
    data=cf.verify_binding(db,source,False)
    expected={str(i):chunk(data['content'],i) for i in range(0,len(data['content']),CHARS)}
    require(value==certificate(source,data,expected),'corrupt-confluence-coverage-certificate')
    return value
