"""Packaged operational help, independent of project and shared instructions."""
from .diagnostic_contract import contracts

SUBMISSION = {
    'proposals': [{
        'version': 2, 'operation': 'batch', 'reason': 'Reviewed source supports retiring this claim',
        'source': {'identity': '0' * 64, 'revision': None, 'kind': 'filesystem-no-history'},
        'operations': [{'action': 'retire', 'kind': 'claims', 'id': 'example.claim', 'expected': 1,
                        'payload': None, 'successor': None}],
    }],
}
HELP = {
    'knowledge_context': ('Find bounded relevant claims and evidence for a task.', {'task': 'Find persistence configuration'}),
    'knowledge_get_claim': ('Use an ID from context. Set history=true to read revisions.', {'identifier': 'example.claim'}),
    'knowledge_get_evidence': ('Use an evidence ID from a claim.', {'identifier': 'example.evidence'}),
    'knowledge_instructions': ('Omit the tool to list available help. Omit the name for a tool overview. Specify a project instruction name to query stored instructions.', {}),
    'knowledge_capabilities': ('Discover the current backend mode and supported tools.', {}),
    'knowledge_scan': ('Start a durable scan, poll status, then inspect failures. Use resume for a compatible checkpoint and recover with scan_id for changed structured source or dialect policy.', {'action': 'status'}),
    'knowledge_scan_diagnostics': ('Discover candidate IDs with candidates, then pass candidate to inspect one. Request sections for all argument contracts.', {'section': 'candidates'}),
    'knowledge_source_read': ('Use an included relative file path. Continue at next_line and next_column when supplied.', {'path': 'appsettings.json'}),
    'knowledge_submit_candidates': ('Submit up to 100 reviewed, source-bound v2 batch proposals. Replace the example source with the source identity from knowledge_source_read or a registered Confluence binding. Use current claim revisions and add linked evidence when adding claims. Submission never approves a plan. After an unknown outcome, inspect the queue before retrying.', SUBMISSION),
    'knowledge_semantic_preflight': ('Check semantic provider readiness and explicit test authorization before reviewing Git proposals.', {}),
    'knowledge_plan': ('Prepare, observe the job until terminal, and review dispositions. Apply only after explicit user authorization of the exact fingerprint. Observe status after an unknown outcome.', {'action': 'status'}),
    'knowledge_confluence': ('Observe scoped synchronization before advancing. Source snapshots require the configured Confluence integration.', {'action': 'status', 'request': {}}),
    'knowledge_change_review': ('Use the installed /update-by-CR workflow to establish its native session and reviewed source.', None),
}


def names(tool):
    return ['overview', 'sections'] if tool == 'knowledge_scan_diagnostics' else ['overview']


def builtin(tool, name, available):
    if tool is None or name == 'list':
        return {'ok': True, 'state': 'discovery', 'source': 'builtin',
                'instructions': {key: names(key) for key in sorted(available)}}
    if tool not in available:
        return None
    if name == 'sections' and tool == 'knowledge_scan_diagnostics':
        return {'ok': True, 'state': 'matched', 'source': 'builtin', 'tool': tool, 'name': name,
                'sections': contracts()}
    if name in (None, 'overview', tool):
        guidance, example = HELP[tool]
        return {'ok': True, 'state': 'matched', 'source': 'builtin', 'tool': tool, 'name': 'overview',
                'guidance': guidance, 'example': example, 'available_names': names(tool)}
    return None


def discovery_hint(value, tool, available):
    if value.get('state') == 'no-match':
        value['available_names'] = names(tool) if tool in available else []
        value['next_invocation'] = {'tool': tool} if tool in available else {}
    return value
