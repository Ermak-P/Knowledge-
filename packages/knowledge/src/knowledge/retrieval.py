"""Provided lexical ranking/assembly, refactored to consume an in-memory snapshot."""
import json
import math
import re
from . import legacy_validator as kb
from .util import canonical_json, digest, canonical_source

VERSION = 'context-engine-v2'
CONFIRMED = 'CONFIRMED'
DEFAULT_MAX_TOKENS = 2000
DEFAULT_MAX_ITEMS = 10
TOKEN_ESTIMATION = 'utf8-bytes/4'
# Weight of a camel-case fragment match relative to a full-token match.
# A compound identifier in the query (TargetId -> target/id) is a stronger
# signal in its full form than in its generic parts; fragments still match
# (retrieval is not lost), they are only down-weighted.
FRAGMENT_WEIGHT = 0.5

_WORD = re.compile(r'[^\W_]+', re.UNICODE)
_CAMEL = re.compile(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')

STOPWORDS = frozenset((
    # English
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'of', 'in', 'on', 'at',
    'to', 'for', 'from', 'by', 'with', 'and', 'or', 'but', 'if', 'then', 'else', 'when', 'where',
    'why', 'how', 'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'it', 'its',
    'as', 'do', 'does', 'did', 'can', 'could', 'should', 'would', 'may', 'might', 'will', 'shall',
    'there', 'here', 'not', 'no', 'about', 'into', 'over', 'under', 'between', 'out', 'up', 'down',
    'off', 'again', 'further', 'once', 'please', 'tell', 'explain', 'describe', 'list', 'show',
    'give', 'need', 'needs', 'know', 'understand', 'use', 'using', 'used', 'via', 'per',
    # Russian
    'и', 'в', 'на', 'по', 'с', 'из', 'о', 'об', 'а', 'но', 'или', 'если', 'то', 'что', 'кто',
    'где', 'когда', 'почему', 'как', 'который', 'которая', 'которые', 'это', 'тот', 'та', 'те',
    'этот', 'эта', 'эти', 'их', 'его', 'ее', 'мой', 'твой', 'наш', 'ваш', 'не', 'ни', 'же', 'бы',
    'ли', 'за', 'до', 'у', 'от', 'про', 'при', 'через', 'между', 'среди', 'очень', 'более',
    'меньше', 'чем', 'для', 'к', 'во', 'вне', 'внутри', 'около', 'там', 'здесь', 'тут', 'так',
    'тоже', 'также', 'лишь', 'только', 'даже', 'уже', 'ещё', 'еще', 'всегда', 'никогда', 'много',
    'мало', 'сколько', 'какой', 'какая', 'какие', 'чей', 'чья', 'чьи', 'пожалуйста', 'расскажи',
    'объясни', 'опиши', 'перечисли', 'покажи', 'дай', 'нужно', 'надо', 'знать', 'понять',
    'использовать', 'используется', 'есть', 'нет', 'да', 'был', 'была', 'было', 'были', 'будет',
    'будут',
))

# Curated v1 synonym table (deterministic, documented in docs/context-engine.md).
SYNONYMS = {
    'permission': {'permission', 'permissions', 'role', 'roles', 'right', 'rights', 'access',
                   'approve', 'approved', 'approval', 'approver'},
    'check': {'check', 'checks', 'validation', 'validate', 'validator', 'verified', 'verify'},
    'state': {'state', 'states', 'status', 'statuses'},
    'generate': {'generate', 'generates', 'generated', 'generation', 'create', 'creates',
                 'created', 'creation'},
    'database': {'database', 'databases', 'db', 'table', 'tables', 'persistence', 'persist',
                 'persisted'},
    'configuration': {'configuration', 'config', 'configs', 'configured'},
    'publish': {'publish', 'publishes', 'published', 'publishing', 'publication', 'publications',
                'republish', 'republished', 'republishing'},
}

# Cross-lingual (RU -> EN) alias stems for historical domain terms. Retrieval is
# lexical and the canonical claim statements are English, so a Russian prompt
# (e.g. the Stage 7.4 BSS scenario) otherwise matches only claims that happen to
# contain the literal Russian token (baseline: the exact BSS prompt retrieved just
# 4 high-level business_rule claims). A query token that STARTS WITH a RU stem is
# bridged to the EN canonical term so the English claim vocabulary becomes
# reachable. Curated v1, deterministic; documented in docs/context-engine.md.
CROSS_LINGUAL = {
    'контент': 'content',
    'статистик': 'statistics',
    'процесс': 'process',
    'создан': 'create',
    'отображ': 'display',
    'публикац': 'publish',
    'дистрибуц': 'distribution',
}


class ContextEngineError(ValueError):
    """Stable actionable error code, never a source-content or OS-path dump."""


def split_query(text):
    """Query tokens as (primary, fragments): full word runs vs camel-case parts.

    A fragment that is also an explicitly typed word stays primary
    ("TargetId and target" -> primary {targetid, target}, fragments {id})."""
    primary, fragments = set(), set()
    for run in _WORD.findall(text or ''):
        primary.add(run.lower())
        if any(character.isupper() for character in run):
            for part in _CAMEL.split(run):
                if part:
                    fragments.add(part.lower())
    fragments -= primary
    return primary, fragments


def tokenize(text):
    """Lowercase word tokens (Latin, digits, Cyrillic) plus camel-case identifier splits."""
    primary, fragments = split_query(text)
    return primary | fragments


def _canonical_form(token):
    """Naive English normalization (s/ed suffixes) applied to both sides.
    'ing' is not stripped: it over-stems (accounting -> account false positive)."""
    for suffix in ('s', 'ed'):
        if len(token) > len(suffix) + 2 and token.endswith(suffix):
            return token[:-len(suffix)]
    return token


_SYNONYM_LOOKUP = {}
for _key, _members in SYNONYMS.items():
    _group = {_key, *_members}
    for _member in _group:
        _SYNONYM_LOOKUP.setdefault(_canonical_form(_member), set()).update(_group)


def expand(tokens):
    """Stopword-free query tokens in canonical form, plus curated synonyms and a
    cross-lingual (RU->EN) bridge for core domain terms (see CROSS_LINGUAL)."""
    expanded = set()
    for token in tokens:
        expanded.add(_canonical_form(token))
        expanded.update(_canonical_form(synonym)
                        for synonym in _SYNONYM_LOOKUP.get(_canonical_form(token), ()))
        for ru_stem, en_term in CROSS_LINGUAL.items():
            if token.startswith(ru_stem):
                expanded.add(_canonical_form(en_term))
    return expanded


def estimated_tokens(text):
    """Deterministic token estimate: UTF-8 bytes / 4 (documented heuristic, not a tokenizer)."""
    return max(1, len(text.encode('utf-8')) // 4)


def conflict_note(partner_claim):
    """Stable note for one side of a conflict pair (shared by the engine and the MCP server)."""
    if partner_claim is None:
        return 'conflict partner record missing; canonical dataset must be revalidated'
    if partner_claim['status'] != CONFIRMED:
        return 'partner is not CONFIRMED; historical/uncertain assertion, not an active rule'
    return 'both sides CONFIRMED; unresolved conflict requires human decision'


class ContextEngine:
    """Read-only retrieval and context assembly over validated canonical records."""

    def assemble(self, records, task, scope=(), max_tokens=DEFAULT_MAX_TOKENS,
                 include_unconfirmed=False, max_items=DEFAULT_MAX_ITEMS, compact=False):
        claims = records['claims']
        evidence = {item['id']: item for item in records['evidence']}
        task_lower = task.lower()
        primary_raw, fragment_raw = split_query(task)
        query_primary = expand(primary_raw - STOPWORDS)
        query_fragments = expand(fragment_raw - STOPWORDS) - query_primary
        query = query_primary | query_fragments

        docs = []
        for claim in claims:
            evidence_items = [evidence[i] for i in claim['evidence'] if i in evidence]
            evidence_text = ' '.join(
                ' '.join(part for part in (canonical_source(item), _reference(item.get('location')),
                                           item.get('description', '')) if part)
                for item in evidence_items)
            docs.append({
                'claim': claim,
                'id_tokens': tokenize(claim['id']),
                'statement_tokens': tokenize(claim['statement']),
                'evidence_tokens': tokenize(evidence_text),
                'evidence_items': evidence_items,
                'category': claim['id'].split('.', 1)[0],
                'scope_text': (claim['id'] + ' ' + claim['statement'] + ' ' + evidence_text).lower(),
            })
        total = len(docs)
        doc_frequency = {}
        for doc in docs:
            for token in {_canonical_form(t) for t in
                          doc['id_tokens'] | doc['statement_tokens'] | doc['evidence_tokens']}:
                doc_frequency[token] = doc_frequency.get(token, 0) + 1

        def idf(token):
            # doc_frequency is keyed by canonical form; look up the canonical form
            # or suffixed tokens (targets, created, states) would read df=0 and get
            # the maximum possible IDF, inflating generic plural/ed matches.
            return math.log(1.0 + (total + 1) / (1.0 + doc_frequency.get(_canonical_form(token), 0)))

        def hits(doc_tokens):
            """(primary_hits, fragment_hits): doc tokens matching the query, split by strength."""
            primary = {token for token in doc_tokens if _canonical_form(token) in query_primary}
            fragment = {token for token in doc_tokens if _canonical_form(token) in query_fragments}
            return primary, fragment

        def weighted_sum(hit):
            primary, fragment = hit
            return sum(idf(t) for t in primary) + FRAGMENT_WEIGHT * sum(idf(t) for t in fragment)

        candidates = []
        for doc in docs:
            claim = doc['claim']
            if claim['status'] != CONFIRMED and not include_unconfirmed:
                continue
            if scope and not any(value.lower() in doc['scope_text']
                                 for value in scope if value.strip()):
                continue
            breakdown, reasons = {}, []
            if claim['id'].lower() in task_lower:
                breakdown['id_exact'] = 100.0
                reasons.append('claim id appears verbatim in the task')
            id_hits = hits(doc['id_tokens'])
            if id_hits[0] or id_hits[1]:
                breakdown['id_tokens'] = round(min(15.0, 3.0 * weighted_sum(id_hits)), 6)
                reasons.append('claim id tokens: ' + ', '.join(sorted(id_hits[0] | id_hits[1])))
            statement_hits = hits(doc['statement_tokens'])
            if statement_hits[0] or statement_hits[1]:
                breakdown['statement'] = round(weighted_sum(statement_hits), 6)
                reasons.append('statement tokens: ' + ', '.join(sorted(statement_hits[0] | statement_hits[1])))
            if doc['category'] in query:
                breakdown['category'] = 1.5
                reasons.append('claim category ' + doc['category'])
            if claim['type'] in task_lower or claim['type'].replace('_', ' ') in task_lower:
                breakdown['type'] = 2.0
                reasons.append('claim type ' + claim['type'])
            evidence_hits = hits(doc['evidence_tokens'])
            if evidence_hits[0] or evidence_hits[1]:
                breakdown['evidence'] = round(min(5.0, 0.5 * weighted_sum(evidence_hits)), 6)
                reasons.append('evidence tokens: ' + ', '.join(sorted(evidence_hits[0] | evidence_hits[1])))
            if not breakdown:
                continue
            quality = sum(1 for item in doc['evidence_items']
                          if item['status'] == 'active'
                          and item['type'] in ('direct-authoritative', 'direct-technical')
                          and item.get('location'))
            if quality:
                breakdown['evidence_quality'] = round(0.25 * min(4, quality), 6)
                reasons.append(str(quality) + ' active direct evidence reference(s) with location')
            if claim['status'] == CONFIRMED:
                breakdown['status_confirmed'] = 0.5
                reasons.append('status CONFIRMED')
            if claim['last_verified'] is not None:
                breakdown['freshness'] = 0.25
                reasons.append('last_verified ' + claim['last_verified'])
            doc['breakdown'] = breakdown
            doc['reasons'] = reasons
            candidates.append((round(sum(breakdown.values()), 6), claim['id'], doc))
        candidates.sort(key=lambda item: (-item[0], item[1]))
        self.candidate_ids=frozenset(item[1] for item in candidates)

        fingerprint = 'sha256:' + digest({
            'claims': sorted(claims, key=canonical_json),
            'evidence': sorted(records['evidence'], key=canonical_json),
            'relationships': sorted(records['relationships'], key=canonical_json)})
        result = {
            'command': 'context',
            'ok': True,
            'engine_version': VERSION,
            'result': 'matches',
            'message': None,
            'claims': [],
            'evidence': [],
            'conflicts': [],
            'truncation': {'candidates': len(candidates), 'returned': 0, 'dropped': 0, 'reason': None},
            'budget': {'max_tokens': max_tokens, 'estimated_tokens': 0, 'estimation': TOKEN_ESTIMATION},
        }
        if compact:
            # LLM-consumption view: no query echo, no diagnostic ranking internals.
            # The budget below is enforced against THIS representation.
            result['view'] = 'compact'
            result['knowledge_base'] = {'fingerprint': fingerprint}
        else:
            result['query'] = {'task': task, 'scope': sorted(set(scope)), 'max_tokens': max_tokens,
                               'include_unconfirmed': include_unconfirmed, 'max_items': max_items}
            result['knowledge_base'] = {'fingerprint': fingerprint, 'claim_count': len(claims),
                                        'evidence_count': len(records['evidence']),
                                        'schema_versions': dict(kb.MANIFEST['schema_versions'])}

        def size(payload):
            return estimated_tokens(json.dumps(payload, sort_keys=True, ensure_ascii=False))

        def evidence_ref(evidence_id):
            item = evidence[evidence_id]
            ref = {'id': evidence_id, 'provenance': item['provenance'], 'status': item['status'],
                   'source': canonical_source(item), 'location': _reference(item.get('location'))}
            if not compact:
                ref['type'] = item['type']
                ref['captured_at'] = item['captured_at']
            return ref

        selected_evidence = []
        conflict_pairs = set()
        reason = None
        for score, claim_id, doc in candidates:
            if len(result['claims']) >= max_items:
                reason = 'max-items'
                break
            claim = doc['claim']
            entry = {'id': claim['id'], 'status': claim['status'],
                     'confirmed': claim['status'] == CONFIRMED, 'type': claim['type'],
                     'statement': claim['statement'], 'last_verified': claim['last_verified'],
                     'depends_on':list(claim['depends_on']), 'revision':claim.get('_p1',{}).get('revision'),
                     'provenance': claim['provenance'], 'evidence_ids': claim['evidence'], 'conflicts_with': claim['conflicts_with']}
            if '_p1' in claim:entry['current']=claim['_p1']
            if not compact:
                entry['score'] = score
                entry['score_breakdown'] = doc['breakdown']
                entry['reasons'] = doc['reasons']
            new_evidence = [i for i in claim['evidence'] if i in evidence and i not in selected_evidence]
            new_conflicts = []
            for partner in claim['conflicts_with']:
                pair = tuple(sorted((claim['id'], partner)))
                if pair in conflict_pairs:
                    continue
                conflict_pairs.add(pair)
                partner_claim = next((c for c in claims if c['id'] == partner), None)
                note = conflict_note(partner_claim)
                conflict = {
                    'claim_id': claim['id'], 'partner_id': partner,
                    'partner_status': partner_claim['status'] if partner_claim else None,
                    'partner_statement': partner_claim['statement'] if partner_claim else None,
                    'partner_confirmed': bool(partner_claim and partner_claim['status'] == CONFIRMED),
                    'note': note}
                if not compact:
                    conflict['partner_type'] = partner_claim['type'] if partner_claim else None
                new_conflicts.append(conflict)
            trial = dict(result)
            trial['claims'] = result['claims'] + [entry]
            trial['evidence'] = result['evidence'] + [evidence_ref(i) for i in new_evidence]
            trial['conflicts'] = result['conflicts'] + new_conflicts
            if size(trial) > max_tokens:
                reason = 'budget-exhausted-by-envelope' if not result['claims'] else 'token-budget'
                break
            result = trial
            selected_evidence.extend(new_evidence)
        result['truncation'].update(returned=len(result['claims']),
                                    dropped=len(candidates) - len(result['claims']),
                                    reason=reason)
        if not candidates and not result['claims']:
            result['result'] = 'insufficient-evidence'
            result['message'] = ('No canonical claim matches the query under the status policy, scope '
                                 'and lexical retrieval; no architecture knowledge is asserted for this question.')
        result['budget']['estimated_tokens'] = size(result)
        return result


def _reference(value):
    if isinstance(value, dict):
        return value.get('reference')
    return value
