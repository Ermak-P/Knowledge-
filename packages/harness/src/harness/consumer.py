"""Compatible read-only context facade. Execution is explicit through harness-run."""
from knowledge.project import Project, safe_path
from knowledge.store import Store
from knowledge.util import KnowledgeError, loads, require, canonical_json, read_text


def context(root,task,max_bytes=None,include_unconfirmed=False):
    project=Project(root)
    config=project.root/'.harness/config.json'
    safe_path(config)
    settings=loads(read_text(config)) if config.exists() else {}
    require(isinstance(settings,dict) and set(settings)<= {'response_max_bytes'},'invalid-harness-config')
    budget=max_bytes if max_bytes is not None else settings.get('response_max_bytes',16000)
    require(type(budget) is int and 512<=budget<=1000000,'invalid-harness-budget')
    try:
        result=Store(project.root).context(task,budget-256,include_unconfirmed=include_unconfirmed)
    except KnowledgeError as e:
        if e.code in ('knowledge-absent','store-busy-retry','database-unavailable-or-corrupt'):
            # Corruption is an explicit unavailable/error result, never empty knowledge success.
            return {'ok':True,'mode':'degraded','knowledge_available':False,'reason':e.code,
                    'runner':'not-invoked','claims':[]}
        raise
    response={'ok':True,'mode':'knowledge','runner':'not-invoked','context':result}
    require(len(canonical_json(response).encode())<=budget,'harness-response-budget-exceeded')
    return response
