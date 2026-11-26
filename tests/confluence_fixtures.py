"""Explicit client coverage/review declarations for synthetic integration tests."""
import hashlib,inspect
from knowledge import confluence as cf,confluence_sync as cs,lifecycle as life


def coverage(store,source,starts=None):
    with store.connection() as db:data=cf.snapshot(db,source['snapshot'])
    text=data['content'];starts=range(0,len(text),2000) if starts is None else starts
    return dict(source=source,content_hash=data['content_hash'],representation=data['representation'],chunks=[dict(start=start,end=min(start+2000,len(text)),hash='sha256:'+hashlib.sha256(text[start:start+2000].encode()).hexdigest()) for start in starts])


def targeted_reviews(store,source,findings):
    by_statement={f['statement']:f for f in findings};reviews=[]
    with store.connection() as db:
        records=store._records(db);claims={c['id']:c for c in records['claims']};states=life.latest(db)
        for e in records['evidence']:
            if e['status']!='active' or not cf.is_binding(e['source']) or e['source']['identity']!=source['identity'] or e['source']['snapshot']==source['snapshot']:continue
            f=next((by_statement[claims[i]['statement']] for i in e['substantiates'] if claims[i]['statement'] in by_statement),None)
            if f:reviews.append(dict(evidence=e['id'],expected=states[e['id']]['revision'],verdict='superseded',quote=f['quote'],reason='Synthetic client explicitly reviewed this historical proof against the current statement and quote.'))
    return reviews


def analyze_page(store,source,findings,**kw):
    if 'coverage' in inspect.signature(cs.analyze).parameters:
        kw.setdefault('coverage',coverage(store,source));kw.setdefault('revalidations',targeted_reviews(store,source,findings) if kw.get('complete',True) else [])
    return cs.analyze(store,source,findings,**kw)


def work_result(store,work,result):
    if work['kind']!='analysis' or 'findings' not in result:return result
    with store.connection() as db:source=cs.source_now(cf.page(db,work['target']))
    value=dict(result);value.setdefault('coverage',coverage(store,source));value.setdefault('revalidations',targeted_reviews(store,source,value['findings']) if value.get('complete',True) else [])
    return value
