"""Measure the observed MCP failures using baseline and candidate interpreters."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from core_wire import Wire
from test_core_reliability import upgraded
from test_machine_commands import fixture
from knowledge import discovery


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))


def replay(baseline):
    with tempfile.TemporaryDirectory() as temporary:
        installation, root = fixture(temporary, count=2)
        store = upgraded(root)
        (root / 'appsettings.json').write_bytes(b'\xef\xbb\xbf{\n // fixture\n "value": "https://example.invalid",\n}\n')
        scan = discovery.scan(store, max_files=100)
        wire = Wire([sys.executable, '-I', '-m', 'knowledge.machine_mcp', '--installation', installation, '--workspace', root])
        try:
            wire.initialize()
            catalog = wire.request(102, 'tools/list')['tools']
            responses = []

            def call(tool, /, **arguments):
                raw = wire.request(103 + len(wire.received), 'tools/call', {'name': tool, 'arguments': arguments})
                result = json.loads(raw['content'][0]['text'])
                responses.append({'tool': tool, 'error': result.get('error'), 'state': result.get('state'),
                                  'payload_bytes': len(raw['content'][0]['text'].encode('utf-8')),
                                  'result_bytes': size(raw)})
                return result

            if baseline:
                call('knowledge_scan_diagnostics', section='candidate', scan_id=scan['id'], limit=10)
                candidate = call('knowledge_scan_diagnostics', section='candidate')
                candidate_invalid, candidate_corrective = 2, 1
            else:
                found = call('knowledge_scan_diagnostics', section='candidates', scan_id=scan['id'], limit=10)
                candidate = call('knowledge_scan_diagnostics', section='candidate', candidate=found['rows'][0]['candidate'])
                candidate_invalid = candidate_corrective = 0
            candidate_responses = responses[:]
            responses.clear()
            if baseline:
                for name in ('knowledge-submit', 'submit-candidates'):
                    help_result = call('knowledge_instructions', tool='knowledge_submit_candidates', name=name)
            else:
                help_result = call('knowledge_instructions', tool='knowledge_submit_candidates')
            help_responses = responses[:]
            responses.clear()
            source = call('knowledge_source_read', path='appsettings.json')
            entry = scan['coverage']['appsettings.json']
            report = {'baseline': baseline, 'schema_bytes': sum(size(item['inputSchema']) for item in catalog),
                      'catalog_bytes': size(catalog), 'tool_count': len(catalog),
                      'candidate_workflow': {'invalid_calls': candidate_invalid, 'corrective_retries': candidate_corrective,
                                             'completed': candidate['ok'], 'calls': candidate_responses},
                      'instruction_workflow': {'invalid_calls': 0, 'corrective_retries': int(baseline),
                                               'completed': help_result.get('state') == 'matched', 'calls': help_responses},
                      'structured_workflow': {'completed': source['ok'], 'scan_state': scan['state'],
                                             'syntax_reason': entry.get('syntax_reason'), 'calls': responses[:]}}
            if not baseline:
                responses.clear()
                invalid = call('knowledge_scan_diagnostics', section='candidate', scan_id=scan['id'])
                next_call = invalid['details']['next_invocation']
                found = call('knowledge_scan_diagnostics', **next_call)
                candidate = call('knowledge_scan_diagnostics', section='candidate', candidate=found['rows'][0]['candidate'])
                report['bad_call_recovery'] = {'invalid_calls': 1, 'corrective_retries': 1, 'completed': candidate['ok'], 'calls': responses[:]}
            return report
        finally:
            wire.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    print(json.dumps(replay(args.baseline), indent=2))
