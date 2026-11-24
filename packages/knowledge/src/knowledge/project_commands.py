"""Installed slash-command backend. JSON stdin; explicit root only for CLI use.

The host supplies its active directory. Full scans run in durable workers; push
uses a separate provider/root/source-bound approval around the existing plan API.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys
from . import __version__, lifecycle, discovery, scan_jobs
from .auto_init import write_json, read_json
from .coordination import gate
from .execution_lock import ProjectExecutionLock
from .project import Project, safe_path
from .providers import shared
from .store import Store
from .util import KnowledgeError, require, digest, fingerprint, loads, emit_json

COMMANDS = ('knowledge-init', 'knowledge-candidates-update', 'knowledge-candidates-push')


def resolve_root(directory, roots=None):
    if roots is not None:
        require(isinstance(roots, list) and len(roots) == 1, 'ambiguous-or-missing-workspace-roots')
        directory = roots[0]
    candidate = Project(directory).root
    process = discovery.git_process(candidate,'rev-parse','--show-toplevel') if discovery.has_git(candidate) else None
    if process is not None:
        require(process.returncode == 0, 'invalid-git-workspace')
        candidate = Project(process.stdout.decode('utf-8').strip()).root
    return candidate


def installation_at(path):
    path = Path(path).absolute()
    safe_path(path)
    value = loads(safe_path(path / 'knowledge-machine-install.json').read_text(encoding='utf-8'))
    require(value.get('version') == 1 and value.get('product') == 'knowledge-machine' and value.get('root') == str(path) and value.get('state') == 'installed', 'machine-installation-not-ready')
    require(not (path / 'transaction.json').exists(), 'machine-installation-transaction-recovery-required')
    current = loads(safe_path(path / 'current.json').read_text(encoding='utf-8'))
    require(current == value.get('current') and current.get('product') == __version__, 'machine-runtime-identity-mismatch')
    runtime = Path(current.get('runtime', ''))
    require(not runtime.is_absolute() and '..' not in runtime.parts and runtime.parts and runtime.parts[0] == 'runtimes' and safe_path(path / runtime).is_dir(), 'invalid-machine-runtime-reference')
    return path


def machine_binding(installation, project):
    provider, reference = shared(installation / 'config/provider.json')
    current = loads(safe_path(installation / 'current.json').read_text(encoding='utf-8'))
    return {'root': project.describe(), 'provider_reference': reference, 'runtime_release': current['release_sha256']}, provider


def configure_project(installation, project):
    reference = str(installation / 'config/provider.json')
    runner = safe_path(project.root / '.harness/runner.json')
    lease = ProjectExecutionLock(project.root).acquire()
    try:
        with gate(project.root, exclusive=True):
            changed = False
            config_path = safe_path(project.base / 'machine.json')
            wanted = {'version': 1, 'project': project.identity, 'installation': str(installation), 'provider_ref': reference}
            if config_path.exists():
                require(loads(config_path.read_text(encoding='utf-8')) == wanted, 'project-machine-configuration-conflict')
            raw = None
            if runner.exists():
                raw = loads(runner.read_text(encoding='utf-8'))
                require(isinstance(raw, dict) and raw.get('version') in (1, 2), 'invalid-runner-config')
                require(not ('provider' in raw and 'provider_ref' in raw), 'ambiguous-provider-configuration')
                if 'provider_ref' in raw:
                    require(raw['provider_ref'] == reference, 'project-bound-to-another-provider')
                else:
                    require('provider' in raw and 'provider_reference' not in raw, 'invalid-runner-provider')
                    from .providers import validate
                    validate(raw['provider'])
                    raw = {k: v for k, v in raw.items() if k != 'provider'}
                    raw['provider_ref'] = reference
                    changed = True
            if changed:
                marker = safe_path(project.root / '.harness/companion.json')
                if marker.exists():
                    existing = loads(marker.read_text(encoding='utf-8'))
                    python = existing.get('python')
                    require(isinstance(python, str) and Path(python).is_absolute() and Path(python).is_file(), 'invalid-existing-harness-runtime')
                    check = subprocess.run([python, '-I', '-c', 'from harness.runtime import SHARED_PROVIDER_CONFIG; assert SHARED_PROVIDER_CONFIG == 1'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                    require(check.returncode == 0, 'installed-harness-provider-reference-upgrade-required', 'Update the existing Harness runtime with this kit before connecting its project; runner and enrollment were preserved.')
                _write(runner, raw)
            if not config_path.exists(): _write(config_path, wanted)
            return {'runner_transitioned': changed, 'provider_ref': reference, 'authority': 'Existing runs/enrollments must pass configuration drift checks; no authority was renewed.'}
    finally: lease.close()


def _write(path, value):
    safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, value)


def ready(store):
    require(store.path.exists(), 'project-not-initialized-run-knowledge-init')
    preview = lifecycle.upgrade_preview(store)
    require(preview['already_upgraded'], 'upgrade-required', preview)


def job_summary(folder, binding, provider):
    state = scan_jobs.status(folder)
    require(state['binding'] == binding, 'scan-provider-configuration-drift')
    result = {'ok': state['state'] not in ('BLOCKED', 'OUTCOME_UNKNOWN'), 'state': state['state'],
              'root': binding['root']['root'], 'version': __version__, 'provider_reference': binding['provider_reference'],
              'provider_evidence': provider['evidence'], 'job': state['job'], 'scan_id': state.get('scan_id'),
              'coverage_complete': state['state'] == 'COMPLETED' and state.get('coverage_complete', False), 'work': {k: v for k, v in (state.get('work') or {}).items() if k != 'paths_this_call'}, 'scope': state['scope'],
              'coverage':state.get('counters'), 'processing_complete':state.get('processing_complete',False),'phase':state.get('phase'),
              'source':state.get('source'),'checkpoint_error':state.get('checkpoint_error'),
              'candidates_in_scan': state.get('candidates', 0), 'queued_added': state.get('queued_added'), 'skipped_existing': state.get('skipped_existing'), 'reconciliation': state.get('reconciliation'), 'gaps': state.get('gaps', 0), 'diagnostics': str(folder),
              'semantic_status': 'BLOCKED_CAPABILITY' if state.get('identity_verification') and not state['identity_verification']['complete'] else 'PARTIAL', 'identity_verification': state.get('identity_verification'), 'semantic_coverage_complete': False,
              'limitations': ['Deterministic .NET lexical extraction and content inventory; no runtime/business understanding.',
                              'Unverifiable/dependent/conflicting assertions need semantic review. Absence does not establish retirement.',
                              'add/update are discovered; retire/supersede require reviewed positive evidence and supported v2 proposals.'],
              'next_action': 'Poll status until terminal; then /knowledge-candidates-push for separate plan review.'}
    if state['state'] == 'COMPLETED': result.update(state='PARTIAL', next_action='/knowledge-candidates-push; review semantic gaps before approval.')
    if 'error' in state: result.update(error=state['error'], next_action=state['next_action'])
    if state.get('checkpoint_error'):result['next_action']=state['next_action']
    return result


def execute(command, installation, directory, value):
    require(isinstance(value, dict) and set(value) <= {'roots', 'directory', 'action', 'approve', 'plan', 'upgrade_approval', 'migration_approval', 'base', 'head', 'max_files', 'candidates', 'resume', 'fresh', 'allow_test_double','observed_scan_id'}, 'invalid-command-input')
    require(all(key not in value or type(value[key]) is bool for key in ('resume', 'fresh','allow_test_double')), 'invalid-recovery-controls')
    require(value.get('observed_scan_id') is None or (value.get('resume') is True and not value.get('fresh') and value.get('action','start')=='start'),'observed-scan-requires-resume')
    installation = installation_at(installation)
    root = resolve_root(directory, value.get('roots'))
    require(not root.is_relative_to(installation) and not installation.is_relative_to(root), 'installation-and-project-must-be-separate')
    project = Project(root)
    store = Store(root)
    state_dir = safe_path(installation / 'state/projects' / project.identity)
    binding, provider = machine_binding(installation, project)
    action = value.get('action', 'start')
    if action=='capabilities':
        from .machine_mcp import TOOL_NAMES
        return {'ok':True,'contract':'knowledge-machine-v2','tools':sorted(TOOL_NAMES),'root':str(root),
                'scan_actions':['start','status','resume','fresh','cancel'],
                'provider':{'endpoint':provider['endpoint'],'model':provider['model'],'evidence':provider['evidence']},
                'provider_reference':binding['provider_reference'],'host_permission':'Not granted by backend discovery; actual MCP calls remain host-authorized.'}
    if action == 'cancel' and command == 'knowledge-init':
        state=scan_jobs.status(state_dir / 'full');require(state['binding']==binding,'scan-provider-configuration-drift')
        return scan_jobs.cancel(state_dir / 'full')
    if action == 'status' and command == 'knowledge-init':
        return job_summary(state_dir / 'full', binding, provider)
    if action=='start' and command=='knowledge-init' and (state_dir/'full/job.json').exists():
        active=scan_jobs.status(state_dir/'full')
        if active['state'] in ('STARTING','RUNNING'):
            require(not value.get('fresh',False),'scan-active-cancel-before-fresh')
            require(active['binding']==binding,'active-scan-configuration-drift')
            return job_summary(state_dir/'full',binding,provider)
    if action in ('status','cancel') and command == 'knowledge-candidates-update' and not value.get('base') and not value.get('head'):
        pointer = loads(safe_path(state_dir / 'last-incremental.json').read_text(encoding='utf-8'))
        require(isinstance(pointer.get('folder'), str) and pointer['folder'].startswith('incremental-') and len(pointer['folder']) == 76 and all(c in '0123456789abcdef' for c in pointer['folder'][12:]), 'invalid-incremental-pointer')
        if action=='cancel':
            state=scan_jobs.status(state_dir / pointer['folder']);require(state['binding']==binding,'scan-provider-configuration-drift')
            return scan_jobs.cancel(state_dir / pointer['folder'])
        return job_summary(state_dir / pointer['folder'], binding, provider)
    if command == 'knowledge-init':
        full_scope={'kind':'full'}
        if value.get('base') or value.get('head'):
            require(isinstance(value.get('base'),str) and isinstance(value.get('head'),str),'base-and-head-required')
            full_scope.update(base=discovery.git(root,'rev-parse','--verify',value['base']+'^{commit}',required=True),
                              head=discovery.git(root,'rev-parse','--verify',value['head']+'^{commit}',required=True))
        elif value.get('resume') and (state_dir/'full/job.json').exists():full_scope=scan_jobs.status(state_dir/'full')['scope']
        if not store.path.exists() and (root / '.ai').exists():
            from . import migration
            preview = migration.preview(root)
            require(value.get('migration_approval') == preview['fingerprint'], 'legacy-migration-approval-required', preview)
            migration.apply(root, value['migration_approval'])
        new = not store.path.exists()
        if new:
            store.init()
            lifecycle.upgrade(store, lifecycle.upgrade_preview(store)['fingerprint'])
        else:
            preview = lifecycle.upgrade_preview(store)
            if not preview['already_upgraded']:
                require(value.get('upgrade_approval') == preview['fingerprint'], 'upgrade-approval-required', preview)
                lifecycle.upgrade(store, value['upgrade_approval'])
        configured = configure_project(installation, project) if action == 'start' else {}
        folder = state_dir / 'full'
        if action == 'start':
            scan_jobs.start(folder, root, full_scope, binding, max_files=value.get('max_files', 100), resume=value.get('resume', False), fresh=value.get('fresh', False),observed_scan_id=value.get('observed_scan_id'))
        else:
            require(action == 'status', 'invalid-init-action')
        return {**job_summary(folder, binding, provider), **configured}
    ready(store)
    config = loads(safe_path(project.base / 'machine.json').read_text(encoding='utf-8'))
    require(config.get('installation') == str(installation) and config.get('project') == project.identity, 'project-machine-configuration-conflict')
    if command == 'knowledge-candidates-update':
        if 'candidates' in value:
            from .providers import semantic_preflight
            semantic_preflight(provider,value.get('allow_test_double',False),value['candidates'])
            semantic_binding={'version':1,'provider_ref':binding['provider_reference'],'model':provider['model'],
                              'evidence':provider['evidence'],'contract':'reviewed-v2-v1'}
            return submit_reviewed(store, root, value['candidates'],semantic_binding)
        base = value.get('base') or 'HEAD'
        head = value.get('head') or 'HEAD'
        if value.get('resume') and not value.get('base') and not value.get('head'):
            pointer=read_json(safe_path(state_dir/'last-incremental.json'));name=pointer.get('folder','')
            require(len(name)==76 and name.startswith('incremental-') and all(c in '0123456789abcdef' for c in name[12:]),'invalid-incremental-pointer')
            previous=scan_jobs.status(state_dir/name)
            base,head=previous['scope']['base'],previous['scope']['head']
        # Resolve refs once, so continuation remains bound to an exact range.
        b = discovery.git(root, 'rev-parse', '--verify', base + '^{commit}', required=True)
        h = discovery.git(root, 'rev-parse', '--verify', head + '^{commit}', required=True)
        scope = {'kind': 'incremental', 'base': b, 'head': h}
        folder = state_dir / ('incremental-' + digest(scope))
        if action == 'start':
            scan_jobs.start(folder, root, scope, binding, max_files=value.get('max_files', 100), resume=value.get('resume', False), fresh=value.get('fresh', False),observed_scan_id=value.get('observed_scan_id'))
            _write(state_dir / 'last-incremental.json', {'folder': folder.name})
        elif action=='cancel':
            state=scan_jobs.status(folder);require(state['binding']==binding,'scan-provider-configuration-drift')
            return scan_jobs.cancel(folder)
        else: require(action == 'status', 'invalid-update-action')
        return job_summary(folder, binding, provider)
    require(command == 'knowledge-candidates-push', 'unknown-command')
    from .coordination import gate
    lease = ProjectExecutionLock(root).acquire()
    try:
        with gate(root, exclusive=True):
            return push(store, root, state_dir, binding, value)
    finally: lease.close()


def diagnostics(installation,directory,scope='full',section='failures',cursor=0,limit=20):
    require(scope in ('full','incremental') and section in ('failures','coverage','reconciliation','impact','policy','identity','scans'), 'invalid-diagnostic-section')
    require(type(cursor) is int and cursor>=0 and type(limit) is int and 1<=limit<=100,'invalid-diagnostic-page')
    installation=installation_at(installation);root=resolve_root(directory);project=Project(root)
    require(not root.is_relative_to(installation) and not installation.is_relative_to(root),'installation-and-project-must-be-separate')
    base=safe_path(installation / 'state/projects' / project.identity)
    if scope=='full':folder=base/'full'
    else:
        pointer=read_json(safe_path(base/'last-incremental.json'));name=pointer.get('folder','')
        require(len(name)==76 and name.startswith('incremental-') and all(c in '0123456789abcdef' for c in name[12:]),'invalid-incremental-pointer')
        folder=base/name
    job=scan_jobs.status(folder);binding,provider=machine_binding(installation,project)
    require(job['binding']['root']==project.describe(),'scan-job-root-binding-mismatch')
    if section=='scans':
        scans=discovery.status(Store(root))['scans']
        rows=[{'scan_id':s['id'],'source_identity':s['snapshot']['identity'],'revision':s['snapshot']['revision'],
               'complete':s['complete'],'state':s.get('state'),'coverage':s.get('counters'),'incremental':s.get('incremental',False)} for s in scans]
        return {'ok':True,'state':job['state'],'rows':rows[cursor:cursor+limit],'total':len(rows),
                'next_cursor':cursor+limit if cursor+limit<len(rows) else None,'canonical_unchanged':True}
    require(job.get('scan_id'),'scan-checkpoint-not-yet-available',{'next_action':'Use diagnostics section=scans to observe the durable result before explicit resume with observed_scan_id, or choose fresh. Never start an unobserved retry.'})
    scans=discovery.status(Store(root),job['scan_id'])['scans'];require(len(scans)==1,'unknown-scan');state=scans[0]
    if section in ('failures','coverage'):
        rows=[{'path':path,**{k:v for k,v in entry.items() if k not in ('working_blob','git_blob','head_blob')}}
              for path,entry in sorted(state['coverage'].items())
              if section=='coverage' or entry['status'] in ('blocked','excluded') or entry.get('processing_status')=='partial']
        if section=='failures':rows.extend(state['snapshot']['exclusions']);rows.extend(state['snapshot'].get('coverage_errors',[]))
    elif section=='policy':rows=[state['snapshot']['policy']]
    elif section=='impact':rows=[state.get('impact',{})]
    elif section=='identity':
        identity=state.get('identity_verification') or {}
        rows=[{'path':path,'reason':'missing-compatible-cached-analysis'} for path in identity.get('missing_files',[])]+[{'id':identifier,'reason':'ambiguous-identity'} for identifier in identity.get('ambiguous_ids',[])]
    else:
        review=discovery.reconcile(Store(root),job['scan_id']);rows=review['claims']+review['negative_evidence_gaps']
    return {'ok':True,'section':section,'scan_id':state['id'],'state':job['state'],'coverage':state.get('counters'),
            'binding_matches_current':job['binding']==binding,'rows':rows[cursor:cursor+limit],
            'next_cursor':cursor+limit if cursor+limit<len(rows) else None,'total':len(rows),'canonical_unchanged':True}


def submit_reviewed(store, root, proposals, semantic_binding=None):
    """Validate a reviewed, source-bound v2 batch before normal queue submission."""
    from .coordination import gate
    require(isinstance(proposals, list) and len(proposals) <= 100, 'invalid-candidate-batch')
    lease = ProjectExecutionLock(root).acquire()
    try:
        with gate(root, exclusive=True):
            pending = {}; rows = []
            with store.connection() as db:
                for proposal in proposals:
                    lifecycle.envelope(proposal)
                    require(proposal['source'] is not None, 'source-bound-v2-proposal-required')
                    equivalent = discovery.equivalent_candidate(db, proposal)
                    if equivalent:
                        if equivalent[1]=='pending' and semantic_binding is not None:
                            from .providers import semantic_bindings
                            require(semantic_bindings(db).get(equivalent[0])==semantic_binding,'candidate-semantic-provider-reanalysis-required')
                        rows.append({'ok': True, 'result': 'duplicate', 'candidate': equivalent[0], 'status': equivalent[1]})
                    else:
                        pending[digest(proposal)] = proposal
                # Simulate the proposed batch against canonical revisions,
                # evidence and graph. Nothing canonical is written here.
                if pending: lifecycle.simulate(store, db, pending)
            for proposal in pending.values(): rows.append(store.submit(proposal,semantic_binding=semantic_binding))
            return {'ok': True, 'root': str(root), 'results': rows,
                    'added': sum(row['result'] == 'submitted' for row in rows),
                    'skipped': sum(row['result'] != 'submitted' for row in rows),
                    'blocked': 0, 'canonical_unchanged': True}
    finally: lease.close()


def push(store, root, state_dir, binding, value):
    action = value.get('action', 'start')
    plans = state_dir / 'plans'
    if value.get('approve') or action == 'recover':
        approval = value.get('approve') or value.get('plan')
        require(isinstance(approval, str) and approval.startswith('sha256:') and len(approval) == 71
                and all(c in '0123456789abcdef' for c in approval[7:]), 'exact-approval-required')
        path = safe_path(plans / (approval[7:] + '.json'))
        saved = loads(path.read_text(encoding='utf-8'))
        require(fingerprint(saved['binding']) == approval, 'corrupt-machine-plan')
        pid = saved['binding']['canonical_plan']
        states = {row['fingerprint']: row['state'] for row in store.status()['plans']}
        if action == 'recover':
            require(saved.get('approved') is True and states.get(pid) in ('COMMITTED', 'ACKNOWLEDGED'), 'no-approved-commit-to-recover')
        else:
            expected = {**binding, 'source_identity': discovery.inventory(root)['identity'], 'canonical_plan': pid}
            require(expected == saved['binding'], 'machine-plan-drift-prepare-again')
            # Durable intent allows acknowledgement recovery after an unknown
            # post-commit outcome; it never approves a replacement plan.
            saved['approved'] = True
            _write(path, saved)
            store.apply(pid, pid)
        store.acknowledge(pid)
        validation = store.validate()
        status = store.status()
        return {'ok': validation['ok'], 'state': 'ACKNOWLEDGED', 'fingerprint': approval, 'canonical_plan': pid,
                'validation': validation, 'queue': dict(Counter(row['status'] for row in status['queue']))}
    require(action in ('start', 'prepare'), 'invalid-push-action')
    before = discovery.inventory(root)['identity']
    prepared = store.prepare()
    require(discovery.inventory(root)['identity'] == before, 'source-drift-during-prepare')
    seal = {**binding, 'source_identity': before, 'canonical_plan': prepared['fingerprint']}
    approval = fingerprint(seal)
    if prepared['ok']:
        path = plans / (approval[7:] + '.json')
        if not path.exists(): _write(path, {'version': 1, 'binding': seal, 'approved': False})
    operations = Counter(op['action'] for candidate in prepared['candidates'].values() for op in candidate.get('operations', []))
    _write(state_dir / 'last-plan.json', prepared)
    return {'ok': prepared['ok'], 'state': 'AWAITING_EXACT_APPROVAL' if prepared['ok'] else 'BLOCKED', 'root': str(root),
            'fingerprint': approval, 'canonical_plan': prepared['fingerprint'], 'included': len(prepared['included']),
            'operations': dict(operations), 'skipped': len(prepared['skipped']), 'blocked': prepared['blocked'][:20],
            'canonical_unchanged': True, 'diagnostics': str(state_dir / 'last-plan.json'),
            'next_action': 'Separate explicit approval: /knowledge-candidates-push {"approve":"' + approval + '"}. On drift prepare and review a new fingerprint.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installation', required=True)
    parser.add_argument('--root')
    parser.add_argument('command', choices=COMMANDS)
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(1000001)
        require(len(raw) <= 1000000, 'command-input-too-large')
        value = loads(raw.decode('utf-8')) if raw.strip() else {}
        directory = args.root or value.get('directory') or os.getcwd()
        output = execute(args.command, args.installation, directory, value)
    except (KnowledgeError, OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        output = {'ok': False, 'error': getattr(error, 'code', 'command-or-filesystem-error'), 'details': getattr(error, 'details', None)}
    emit_json(output)
    return 0 if output['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
