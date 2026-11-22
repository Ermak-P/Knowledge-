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
        if part:result.append(part)
    return result


def permission_clauses(text,aliases=()):
    """Unwrap only bounded topic/scope headers, never authorization prose.

    Denial checks use clauses() BEFORE this view. Unknown teaching headers
    invalidate the affirmative view of the entire message, including later
    sentences. Topic names are literal single-word catalog aliases, not regexes.
    """
    reserved={'no','not','never','only','unless','if','не','нет','нельзя','только','если'}
    labels=[re.escape(a.replace('ё','е').replace('Ё','Е')) for a in aliases
        if re.fullmatch(r'\w{1,64}',a) and a.casefold() not in reserved]
    topic='(?:'+'|'.join(labels)+')' if labels else r'(?!)'
    english=r'remember(?: '+topic+r'| for (?:(?:all|my|this) )?projects?(?: using (?:my )?(?:local )?'+topic+r'(?: environment)?)?)?'
    russian=r'запомни(?: '+topic+r'| для (?:(?:всех|моих) проектов|этого проекта|проектов)(?: (?:с|использующих) (?:(?:моей|этой) )?(?:локальной )?'+topic+r')?)?'
    result=[]
    for part in clauses(text):
        header,colon,body=part.partition(':')
        if colon and re.match(r'^(?:remember|запомни)\b',header,re.I):
            if not re.fullmatch('(?:'+english+'|'+russian+')',' '.join(header.split()),re.I):return []
            part=body.strip()
        if part:result.append(part)
    return result


# These recognize startup denials, not restart prohibitions. Unknown negatives
# can never pass the affirmative full-clause grammar below.
DENIAL=re.compile(r"(?:\b(?:you (?:may|must|can) not|you cannot|do not|don't|never) (?:automatically )?(?:start|launch)\b|"
    r'\b(?:starting (?:the )?containers?|container startup) (?:is|are) (?:forbidden|not (?:allowed|permitted|authorized))\b|'
    r'\bне (?:запускай|запускайте|запускать|разрешаю запуск)\b|'
    r'\b(?:запрещаю|запретить|запрещено) (?:запуск|запускать)\b|\bзапуск\b[^.;!?\n]{0,100}\b(?:запрещен|не разрешен|не допускается)\b)',re.I)
LIMITING=re.compile(r'\b(?:only|unless|until|provided|except|if|when|только|если|пока|лишь|кроме|после согласования)\b',re.I)
STOPPED_ONLY=re.compile(r'(?:only (?:if|when) (?:it is )?stopped|только если (?:он )?остановлен)$',re.I)
CONTEXT=re.compile(r'[`"“”«»]|(?:^|\n)\s*>|\b(?:example|quoted?|quotation|previous(?:ly)?|earlier|yesterday|said|reported|пример|цитата|ранее|вчера|сказал)\b',re.I)
EN_TARGET=r'(?:it|(?:that |the |this |specific |local |configured |stopped |existing )*container|container [a-z0-9][a-z0-9_.-]*)'
RU_TARGET=r'(?:(?:этого |указанного |настроенного |конкретного |локального |остановленного )*контейнера|контейнера [a-z0-9][a-z0-9_.-]*)'
EN_GRANT=re.compile(r'(?:you may start|i (?:allow|authorize) (?:you to start|starting)) (?P<target>'+EN_TARGET+r')'
    r'(?: (?:only )?(?:if|when) (?:it is )?stopped| for this purpose)?$',re.I)
RU_GRANT=re.compile(r'(?:разрешаю запуск|даю разрешение на запуск) (?P<target>'+RU_TARGET+r')'
    r'(?:,? (?:только )?если (?:он )?остановлен| для этой цели)?$',re.I)
CLEAR=re.compile(r'(?:you (?:may|can) start services again(?: for this (?:run|attempt))?|'
    r'разрешаю (?:снова )?запуск сервисов(?: в этом запуске)?)$',re.I)
NEVER_RESTART=re.compile(r'(?:never restart a running (?:container|service)|никогда не перезапускай работающий (?:контейнер|сервис))$',re.I)
READINESS=re.compile(r'check readiness(?: before required (?:integration )?tests)?$',re.I)
AUTHORIZATION_TOPIC=re.compile(r'\b(?:start\w*|launch\w*|permission\w*|approv\w*|authoriz\w*|запуск\w*|разреш\w*|соглас\w*|утвержд\w*)\b',re.I)
CONTRACT='startup-en-ru-v2'


def represented_clauses(text,mode,aliases=(),resource=None):
    """Closed whole-message grammar, shared by grants and denial clearing.

    Unknown clauses are never silently dropped when changing authorization.
    Supporting grant clauses describe only guards the executor already enforces;
    a universal session clear admits no conditional/supporting clause at all.
    """
    parts=permission_clauses(text,aliases)
    if not parts:return None
    for part in parts:
        if mode=='clear':
            if not CLEAR.fullmatch(part):return None
            continue
        if EN_GRANT.fullmatch(part) or RU_GRANT.fullmatch(part) or STOPPED_ONLY.fullmatch(part) or NEVER_RESTART.fullmatch(part) or READINESS.fullmatch(part):continue
        # Existing explicit resource teaching: data, not free-form prose.
        # Names are matched literally and must equal the selected resource.
        metadata=re.fullmatch(r'remember (\w{1,64}) container ([a-z0-9][a-z0-9_.-]*) and port ([0-9]{1,5})',part,re.I)
        if metadata and metadata[1].casefold() in {a.casefold() for a in aliases} and metadata[2]==resource and 1<=int(metadata[3])<=65535:continue
        return None
    return parts


def restriction(text,proposed):
    """A model cannot clear a denial without a whole affirmative current clause."""
    parts=clauses(text)
    if any(DENIAL.search(c) for c in parts):return 'deny'
    if proposed=='clear-denial':
        return 'clear-denial' if not CONTEXT.search(text) and represented_clauses(text,'clear') else 'unchanged'
    return proposed


def startup(text,binding,proposed,quote,resource_count=1):
    """Return current authorization evidence; does not inherit old source quotes.

    Deictic container/it is accepted only for the one selected Docker binding.
    Named targets must exactly equal its configured/materialized resource.
    No non-Docker command, service-wide or restart grant is manufactured.
    """
    parts=clauses(text)
    if any(DENIAL.search(c) for c in parts):
        return {'granted':False,'denied':True,'reason':'explicit-startup-denial','contract':CONTRACT}
    result={'granted':False,'denied':False,'reason':'no-validated-current-startup-grant','contract':CONTRACT}
    if not binding or not (binding.get('template') or (binding.get('behavior') or {}).get('adapter')=='dependency'):return result
    docker=binding.get('behavior',{}).get('procedure',{}).get('docker',{})
    # An incomplete approved template may retain a deictic authorization intent;
    # execution still needs validated resource parameters and current allowlist.
    if not docker and not binding.get('template'):return result
    resource=docker.get('container') or docker.get('service')
    aliases=binding.get('aliases',[])
    permitted=represented_clauses(text,'grant',aliases,resource)
    # Ordinary same-resource clarification may preserve a prior grant. An
    # authorization-related source needs complete representation even when the
    # model declines a new grant (including historical replay).
    if permitted is None and (AUTHORIZATION_TOPIC.search(text) or LIMITING.search(text)):
        return {**result,'uncertain':True,'reason':'unrepresented-startup-condition'}
    if permitted is None:return result
    if not proposed or not quote or quote not in text or CONTEXT.search(text):return result
    for clause in permitted:
        match=EN_GRANT.fullmatch(clause) or RU_GRANT.fullmatch(clause)
        if not match:continue
        # Quote must identify this complete permission clause, not another sentence.
        if clause not in permission_clauses(quote,binding.get('aliases',[])):continue
        target=match['target'];named=re.fullmatch(r'(?:container|контейнера) ([a-z0-9][a-z0-9_.-]*)',target,re.I)
        if named and (not resource or named[1]!=resource):continue
        if not named and resource_count!=1:continue
        return {**result,'granted':True,'reason':'validated-current-startup-clause'}
    return result
