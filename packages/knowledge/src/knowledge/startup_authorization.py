"""Bounded EN/RU startup grants, independent of the model's classification.

Only complete, unquoted permission clauses from the CURRENT trusted message
can issue a new grant. Grammar is intentionally small; unknown prose is not
permission. Resource/template selection and general teaching intent still use
local model proposals and the independent owner-approved catalog.
"""
import re


def clauses(text):
    # Docker names can contain dots: only split a sentence period at whitespace.
    parts=re.split(r'[;!?\n]+|\.(?=\s|$)',text.replace('ё','е').replace('Ё','Е'))
    result=[]
    for part in parts:
        part=part.strip(' \t.,')
        part=re.sub(r'^(?:remember|запомни)(?:\s+[^:]{0,180})?:\s*','',part,flags=re.I)
        if part:result.append(part)
    return result


# These recognize startup denials, not restart prohibitions. Unknown negatives
# can never pass the affirmative full-clause grammar below.
DENIAL=re.compile(r"(?:\b(?:you (?:may|must|can) not|you cannot|do not|don't|never) (?:start|launch)\b|"
    r'\bне (?:запускай|запускайте|запускать|разрешаю запуск)\b|'
    r'\b(?:запрещаю|запретить) запуск\b|\bзапуск\b[^.;!?\n]{0,100}\bзапрещен\b)',re.I)
CONTEXT=re.compile(r'[`"“”«»]|(?:^|\n)\s*>|\b(?:example|quoted?|quotation|previous(?:ly)?|earlier|yesterday|said|reported|пример|цитата|ранее|вчера|сказал)\b',re.I)
EN_TARGET=r'(?:it|(?:that |the |this |specific |local |configured |stopped |existing )*container|container [a-z0-9][a-z0-9_.-]*)'
RU_TARGET=r'(?:(?:этого |указанного |настроенного |конкретного |локального |остановленного )*контейнера|контейнера [a-z0-9][a-z0-9_.-]*)'
EN_GRANT=re.compile(r'(?:you may start|i (?:allow|authorize) (?:you to start|starting)) (?P<target>'+EN_TARGET+r')'
    r'(?: (?:only )?(?:if|when) (?:it is )?stopped| for this purpose)?$',re.I)
RU_GRANT=re.compile(r'(?:разрешаю запуск|даю разрешение на запуск) (?P<target>'+RU_TARGET+r')'
    r'(?:,? (?:только )?если (?:он )?остановлен| для этой цели)?$',re.I)
CLEAR=re.compile(r'(?:you (?:may|can) start services again(?: for this (?:run|attempt))?|'
    r'разрешаю (?:снова )?запуск сервисов(?: в этом запуске)?)$',re.I)


def restriction(text,proposed):
    """A model cannot clear a denial without a whole affirmative current clause."""
    parts=clauses(text)
    if any(DENIAL.search(c) for c in parts):return 'deny'
    if proposed=='clear-denial':
        return 'clear-denial' if not CONTEXT.search(text) and any(CLEAR.fullmatch(c) for c in parts) else 'unchanged'
    return proposed


def startup(text,binding,proposed,quote,resource_count=1):
    """Return current authorization evidence; does not inherit old source quotes.

    Deictic container/it is accepted only for the one selected Docker binding.
    Named targets must exactly equal its configured/materialized resource.
    No non-Docker command, service-wide or restart grant is manufactured.
    """
    parts=clauses(text)
    if any(DENIAL.search(c) for c in parts):
        return {'granted':False,'denied':True,'reason':'explicit-startup-denial','contract':'startup-en-ru-v1'}
    result={'granted':False,'denied':False,'reason':'no-validated-current-startup-grant','contract':'startup-en-ru-v1'}
    if not proposed or not quote or quote not in text or CONTEXT.search(text):return result
    if not binding or not (binding.get('template') or (binding.get('behavior') or {}).get('adapter')=='dependency'):return result
    docker=binding.get('behavior',{}).get('procedure',{}).get('docker',{})
    # An incomplete approved template may retain a deictic authorization intent;
    # execution still needs validated resource parameters and current allowlist.
    if not docker and not binding.get('template'):return result
    resource=docker.get('container') or docker.get('service')
    for clause in parts:
        match=EN_GRANT.fullmatch(clause) or RU_GRANT.fullmatch(clause)
        if not match:continue
        # Quote must identify this complete permission clause, not another sentence.
        if clause not in clauses(quote):continue
        target=match['target'];named=re.fullmatch(r'(?:container|контейнера) ([a-z0-9][a-z0-9_.-]*)',target,re.I)
        if named and (not resource or named[1]!=resource):continue
        if not named and resource_count!=1:continue
        return {**result,'granted':True,'reason':'validated-current-startup-clause'}
    return result
