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

COMMANDS = ('knowledge-init', 'knowledge-candidates-update', 'knowledge-candidates-push','knowledge-confluence','knowledge-update')


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


def scan_binding(installation, project):
    """Provider telemetry is optional for deterministic lexical jobs."""
    path = safe_path(installation / 'current.json')
    current = loads(path.read_text(encoding='utf-8'))
    binding = {'root': project.describe(), 'runtime_release': current['release_sha256']}
    try:
        provider, reference = shared(installation / 'config/provider.json')
    except FileNotFoundError:
        return {**binding, 'provider_state': 'missing'}, {}
    except OSError:
        return {**binding, 'provider_state': 'unavailable'}, {}
    except ValueError:
        return {**binding, 'provider_state': 'invalid'}, {}
    binding['provider_reference'] = reference
    binding['provider_fields'] = {key: digest(provider.get(key)) for key in ('endpoint', 'model', 'evidence', 'key_env')}
    return binding, provider


def configure_project(installation, project, connect_runner=True):
    reference = str(installation / 'config/provider.json')
    runner = safe_path(project.root / '.harness/runner.json')
    lease = ProjectExecutionLock(project.root).acquire() if connect_runner else None
    try:
        with gate(project.root, exclusive=True):
            changed = False
            config_path = safe_path(project.base / 'machine.json')
            wanted = {'version': 1, 'project': project.identity, 'installation': str(installation), 'provider_ref': reference}
            if config_path.exists():
                require(loads(config_path.read_text(encoding='utf-8')) == wanted, 'project-machine-configuration-conflict')
            raw = None
            if connect_runner and runner.exists():
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
    finally:
        if lease:lease.close()


def _write(path, value):
    safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, value)


def ready(store):
    require(store.path.exists(), 'project-not-initialized-run-knowledge-init')
    if not store.upgraded():
        raise KnowledgeError('upgrade-required', lifecycle.upgrade_preview(store))


def no_scan(root):
    store=Store(root)
    present = store.path.exists()
    return {'ok':True,'state':'NOT_STARTED','worker_state':'NOT_STARTED','phase':'PRE_SCAN','scan_id':None,'job':None,
            'database':str(store.path),'database_present':present,'existing_counts':store.scan_counts() if present else {},
            'next_action':'No job was created for this invocation. Existing database data is separate from scan progress. Identity mismatch requires explicit SQLite identity migration; fresh/restart cannot repair it.'}


def job_summary(folder, binding, provider):
    if not (Path(folder)/'job.json').exists():return no_scan(binding['root']['root'])
    state = scan_jobs.status(folder, binding['root'])
    compatibility = scan_jobs.compatibility(state, binding)
    result = {'ok': state['state'] not in ('BLOCKED', 'OUTCOME_UNKNOWN'), 'state': state['state'],
              'root': binding['root']['root'], 'version': __version__, 'provider_reference': binding.get('provider_reference'),
              'provider_evidence': provider.get('evidence'), 'worker_state': state['state'], 'compatibility': compatibility, 'job': state['job'], 'scan_id': state.get('scan_id'),
              'coverage_complete': state['state'] == 'COMPLETED' and state.get('coverage_complete', False), 'work': {k: v for k, v in (state.get('work') or {}).items() if k != 'paths_this_call'}, 'scope': state['scope'],
              'coverage':state.get('counters'), 'processing_complete':state.get('processing_complete',False),'phase':state.get('phase'),
              'source':state.get('source'),'source_verified':state['state'] in ('COMPLETED','COMPLETED_WITH_GAPS') and state.get('source_verified',False),'checkpoint_error':state.get('checkpoint_error'),
              'candidates_in_scan': state.get('candidates', 0), 'queued_added': state.get('queued_added'), 'skipped_existing': state.get('skipped_existing'), 'reconciliation': state.get('reconciliation'), 'gaps': state.get('gaps', 0), 'diagnostics': str(folder),
              'semantic_status': 'BLOCKED_CAPABILITY' if state.get('identity_verification') and not state['identity_verification']['complete'] else 'PARTIAL', 'identity_verification': state.get('identity_verification'), 'semantic_coverage_complete': False,
              'limitations': ['Deterministic .NET lexical extraction and content inventory; no runtime/business understanding.',
                              'Unverifiable/dependent/conflicting assertions need semantic review. Absence does not establish retirement.',
                              'add/update are discovered; retire/supersede require reviewed positive evidence and supported v2 proposals.'],
              'next_action': 'Poll status until terminal; then /knowledge-candidates-push for separate plan review.'}
    if state['state'] == 'COMPLETED': result.update(state='PARTIAL', next_action='/knowledge-candidates-push; review semantic gaps before approval.')
    if result['semantic_status'] == 'BLOCKED_CAPABILITY':
        result['next_action'] = 'Inspect identity diagnostics, then explicitly run full knowledge-init or submit reviewed candidates.'
    if 'error' in state: result.update(error=state['error'], next_action=state['next_action'])
    if state['state'] in ('CANCELLED', 'OUTCOME_UNKNOWN') or state.get('checkpoint_error'):
        result['next_action'] = compatibility['next_action']
    if state.get('resume_failure'):
        result.update(ok=False, error='resume-scan-configuration-drift', details=state['resume_failure'],
                      next_action=compatibility['next_action'])
    if state.get('recovery_of'):
        result['recovery_of'] = state['recovery_of']
    if state.get('recovery_failure'):
        result['details'] = state['recovery_failure']
    return result


def last_incremental(state_dir):
    path = safe_path(state_dir / 'last-incremental.json')
    if not path.exists():
        return None
    name = read_json(path, max_bytes=8192).get('folder')
    require(isinstance(name, str) and len(name) == 76 and name.startswith('incremental-')
            and all(c in '0123456789abcdef' for c in name[12:]), 'invalid-incremental-pointer')
    return safe_path(state_dir / name)


def project_configuration(installation, project):
    config = loads(safe_path(project.base / 'machine.json').read_text(encoding='utf-8'))
    require(config.get('installation') == str(installation) and config.get('project') == project.identity,
            'project-machine-configuration-conflict')


def lexical_scan(installation, project, store, state_dir, kind, action, value):
    root = project.root
    owner = project.describe()
    require(action in ('start', 'status', 'cancel', 'recover'), 'invalid-scan-action')
    recovery_of = value.get('recovery_of')
    import re
    require((action == 'recover') == (recovery_of is not None) and
            (recovery_of is None or isinstance(recovery_of, str) and re.fullmatch('[0-9a-f]{64}', recovery_of)),
            'invalid-recovery-scan-id', {'example': {'action': 'recover', 'scan_id': '<id from section=scans>'}})
    resume, fresh = value.get('resume', False), value.get('fresh', False)
    require(not (resume and fresh) and (action == 'start' or not (resume or fresh)), 'invalid-recovery-controls')
    base, head = value.get('base'), value.get('head')
    scope = {'kind': kind}
    if kind == 'full':
        folder = state_dir / 'full'
    elif not (base or head) and (action != 'start' or resume):
        folder = last_incremental(state_dir)
    else:
        folder = None
    if not (base or head) and folder is not None and not fresh:
        if safe_path(folder / 'job.json').exists():
            scope = scan_jobs.owned_job(folder, owner)['scope']
    elif base or head or kind == 'incremental':
        if kind == 'full':
            require(isinstance(base, str) and isinstance(head, str), 'base-and-head-required')
        scope.update(base=discovery.git(root, 'rev-parse', '--verify', (base or 'HEAD') + '^{commit}', required=True),
                     head=discovery.git(root, 'rev-parse', '--verify', (head or 'HEAD') + '^{commit}', required=True))
        if kind == 'incremental':
            folder = state_dir / ('incremental-' + digest(scope))
    if folder is None:
        if resume:
            missing = {'binding': {'root': owner}, 'state': 'NOT_STARTED'}
            binding, _ = scan_binding(installation, project)
            raise KnowledgeError('resume-scan-configuration-drift',
                                 scan_jobs.resume_details(missing, binding, 'scan-outcome-observation-required'))
        return no_scan(root)

    metadata = safe_path(folder / 'job.json')
    if action == 'cancel':
        return scan_jobs.cancel(folder, owner, scope) if metadata.exists() else no_scan(root)
    binding, provider = scan_binding(installation, project)
    if action == 'status':
        if metadata.exists() and (base or head):
            require(scan_jobs.owned_job(folder, owner)['scope'] == scope, 'scan-job-scope-binding-mismatch')
        return job_summary(folder, binding, provider)

    configured = {}
    if metadata.exists():
        active = scan_jobs.status(folder, owner)
        if active['state'] in scan_jobs.ACTIVE:
            if resume or recovery_of:
                raise KnowledgeError('scan-worker-active', scan_jobs.resume_details(active, binding, 'scan-worker-active'))
            require(not fresh, 'scan-active-cancel-before-fresh')
            require(active['scope'] == scope, 'active-scan-scope-mismatch')
            return job_summary(folder, binding, provider)
    if recovery_of:
        ready(store)
    elif not resume and kind == 'full':
        if not store.path.exists() and (root / '.ai').exists():
            from . import migration
            preview = migration.preview(root)
            require(value.get('migration_approval') == preview['fingerprint'], 'legacy-migration-approval-required', preview)
            migration.apply(root, value['migration_approval'])
        if not store.path.exists():
            store.init()
            lifecycle.upgrade(store, lifecycle.upgrade_preview(store)['fingerprint'])
        else:
            preview = lifecycle.upgrade_preview(store)
            if not preview['already_upgraded']:
                require(value.get('upgrade_approval') == preview['fingerprint'], 'upgrade-approval-required', preview)
                lifecycle.upgrade(store, value['upgrade_approval'])
        configured = configure_project(installation, project, connect_runner=bool(provider))
    elif kind == 'incremental' and not resume:
        ready(store)
        project_configuration(installation, project)
    if resume and safe_path(project.base / 'machine.json').exists():
        project_configuration(installation, project)

    launched = scan_jobs.start(folder, root, scope, binding, max_files=value.get('max_files', 100),
                               resume=resume, fresh=fresh, observed_scan_id=value.get('observed_scan_id'),
                               recovery_of=recovery_of)
    if failure := launched.get('resume_failure'):
        raise KnowledgeError('resume-scan-configuration-drift', failure)
    return {**job_summary(folder, binding, provider), **configured}


def execute(command, installation, directory, value):
    if command=='knowledge-update':command='knowledge-candidates-push'
    extra={'scope','operations','extra_operations','capabilities','request'} if command=='knowledge-confluence' else {'recovery_of'} if command in ('knowledge-init','knowledge-candidates-update') else set()
    if command == 'knowledge-candidates-push':
        extra = {'job_id', 'wait_seconds', 'execution_seconds'}
    require(isinstance(value, dict) and set(value) <= {'roots', 'directory', 'action', 'approve', 'plan', 'upgrade_approval', 'migration_approval', 'base', 'head', 'max_files', 'candidates', 'resume', 'fresh', 'allow_test_double','observed_scan_id','rebuild_scan_id'}|extra, 'invalid-command-input')
    require(all(key not in value or type(value[key]) is bool for key in ('resume', 'fresh','allow_test_double')), 'invalid-recovery-controls')
    require(value.get('observed_scan_id') is None or (value.get('resume') is True and not value.get('fresh') and value.get('action','start')=='start'),'observed-scan-requires-resume')
    installation = installation_at(installation)
    from .access import readonly, require_maintainer
    if readonly(installation):
        if value.get('action') == 'capabilities':
            from .machine_mcp import READ_TOOLS
            return {'ok': True, 'contract': 'knowledge-machine-v2', 'mode': 'readonly', 'tools': sorted(READ_TOOLS)}
        require_maintainer(installation)
    root = resolve_root(directory, value.get('roots'))
    require(not root.is_relative_to(installation) and not installation.is_relative_to(root), 'installation-and-project-must-be-separate')
    project = Project(root)
    store = Store(root)
    state_dir = safe_path(installation / 'state/projects' / project.identity)
    action = value.get('action', 'start')
    if action != 'capabilities' and (command == 'knowledge-init' or
            (command == 'knowledge-candidates-update' and 'candidates' not in value)):
        kind = 'full' if command == 'knowledge-init' else 'incremental'
        return lexical_scan(installation, project, store, state_dir, kind, action, value)
    if command == 'knowledge-candidates-push' and action != 'capabilities':
        from . import plan_jobs
        if action in ('status', 'cancel', 'resume', 'prepare') or action == 'start' and 'approve' not in value:
            require('approve' not in value and 'plan' not in value, 'prepare-is-not-approval')
            require('rebuild_scan_id' not in value or action in ('start', 'prepare'), 'rebuild-requires-prepare')
            project_configuration(installation, project)
            plan_binding = machine_binding(installation, project)[0] if action not in ('status', 'cancel') else None
            return plan_jobs.dispatch(state_dir / 'plan', project, 'prepare' if action == 'start' else action, value, plan_binding)
        require(action in ('start', 'apply', 'recover'), 'invalid-push-action')
        require(not ({'job_id', 'wait_seconds', 'execution_seconds'} & value.keys()), 'invalid-plan-job-control')
    binding, provider = machine_binding(installation, project)
    if action=='capabilities':
        from .machine_mcp import TOOL_NAMES
        return {'ok':True,'contract':'knowledge-machine-v2','tools':sorted(TOOL_NAMES),'root':str(root),
                'scan_actions':['start','status','resume','fresh','cancel','recover'],
                'plan_actions':['prepare','rebuild','status','cancel','resume','apply','recover'],
                'provider':{'endpoint':provider['endpoint'],'model':provider['model'],'evidence':provider['evidence']},
                'provider_reference':binding['provider_reference'],'host_permission':'Not granted by backend discovery; actual MCP calls remain host-authorized.'}
    if command=='knowledge-confluence':
        from .confluence import dispatch
        if not store.path.exists() and (root/'.ai').exists():
            from . import migration
            preview=migration.preview(root);require(value.get('migration_approval')==preview['fingerprint'],'legacy-migration-approval-required',preview)
            migration.apply(root,value['migration_approval'])
        if not store.path.exists():
            store.init();lifecycle.upgrade(store,lifecycle.upgrade_preview(store)['fingerprint'])
        else:
            preview=lifecycle.upgrade_preview(store)
            if not preview['already_upgraded']:
                require(value.get('upgrade_approval')==preview['fingerprint'],'upgrade-approval-required',preview);lifecycle.upgrade(store,value['upgrade_approval'])
        configure_project(installation,project,connect_runner=False)
        if 'scope' in value:dispatch(store,'scope',{'scope':value['scope']})
        state=dispatch(store,'status',{})
        if state['state']=='SCOPE_REQUIRED':return state
        requested=value.get('action','start')
        request=value.get('request',{k:v for k,v in value.items() if k in ('operations','extra_operations','capabilities','resume','fresh')})
        return dispatch(store,requested,request)
    ready(store)
    project_configuration(installation, project)
    if command == 'knowledge-candidates-update':
        from .confluence import is_binding
        require(isinstance(value['candidates'], list) and all(isinstance(p, dict) for p in value['candidates']),
                'invalid-candidate-batch')
        if all(is_binding(p.get('source')) for p in value['candidates']):
            return submit_reviewed(store, root, value['candidates'])
        from .providers import semantic_preflight
        semantic_preflight(provider, value.get('allow_test_double', False), value['candidates'])
        semantic_binding = {'version': 1, 'provider_ref': binding['provider_reference'], 'model': provider['model'],
                            'evidence': provider['evidence'], 'contract': 'reviewed-v2-v1'}
        return submit_reviewed(store, root, value['candidates'], semantic_binding)
    require(command == 'knowledge-candidates-push', 'unknown-command')
    from .coordination import gate
    lease = ProjectExecutionLock(root).acquire()
    try:
        with gate(root, exclusive=True):
            return push(store, root, state_dir, binding, value)
    finally: lease.close()


def diagnostics(installation,directory,scope='full',section='failures',cursor=0,limit=20,max_bytes=16000,group=None,candidate=None,operation=None,plan=None,collection=None,scan_id=None):
    from .diagnostic_contract import validate
    validate(scope, section, cursor, limit, max_bytes, group=group, candidate=candidate,
             operation=operation, plan=plan, collection=collection, scan_id=scan_id)
    installation=installation_at(installation);root=resolve_root(directory);project=Project(root)
    require(not root.is_relative_to(installation) and not installation.is_relative_to(root),'installation-and-project-must-be-separate')
    from .diagnostic_pages import page
    if section == 'candidates':
        store = Store(root)
        if scan_id is not None:
            scans = discovery.status(store, scan_id)['scans']
            require(len(scans) == 1, 'unknown-scan', {'next_invocation': {'section': 'scans'}})
            require(bool(scans[0].get('incremental')) == (scope == 'incremental'), 'scan-job-scope-binding-mismatch')
            rows = [{'candidate': cid} for cid in scans[0]['candidates']]
        elif plan is not None:
            rows = store.plan_dispositions(plan)
        else:
            with store._telemetry_connection({'queue'}) as db:
                rows = [{'candidate': cid, 'status': status} for cid, status in
                        db.execute('SELECT id,status FROM queue ORDER BY id')]
        return page(rows, {'ok': True, 'section': section, 'scan_id': scan_id, 'plan': plan}, cursor, limit, max_bytes)
    if section in ('plan-progress', 'plan-dispositions'):
        from . import plan_jobs
        base = safe_path(installation / 'state/projects' / project.identity)
        job = plan_jobs.summary(plan_jobs.read_state(base / 'plan', project.describe()))
        if section == 'plan-progress':
            path = safe_path(base / 'plan-progress.json')
            progress = job.get('progress')
            if progress:
                progress = {**progress, 'job_id': job['job_id'], 'worker_state': job['worker_state']}
            elif path.exists():
                progress = read_json(path, max_bytes=65536)
            return page([progress] if progress else [], {'ok':True, 'section':section}, cursor, limit, max_bytes)
        pid = plan or job.get('canonical_plan')
        require(pid is not None, 'plan-dispositions-require-prepared-plan')
        return page(Store(root).plan_dispositions(pid), {'ok':True, 'section':section, 'plan':pid},
                    cursor, limit, max_bytes)
    if section=='candidate':
        from .util import canonical_json
        import hashlib
        require(type(max_bytes) is int and 256<=max_bytes<=1000000,'invalid-byte-budget')
        if max_bytes<1024:return {'ok':False,'error':'diagnostic-budget-too-small','minimum_budget':1024}
        text=Store(root).candidate_text(candidate,operation,plan);require(cursor<=len(text),'invalid-diagnostic-offset')
        end=min(len(text),cursor+max(1,min(2048,(max_bytes-768)//8)))
        result={'ok':True,'section':section,'candidate':candidate,'operation':operation,'plan':plan,'cursor':cursor,
                'next_cursor':end if end<len(text) else None,'total_chars':len(text),'text':text[cursor:end],
                'record_hash':hashlib.sha256(text.encode()).hexdigest(),'canonical_unchanged':True}
        require(len(canonical_json(result).encode())<=max_bytes,'diagnostic-budget-too-small');return result
    if section=='duplicates':
        counts,rows=Store(root).duplicate_diagnostics(group)
        return page(rows,{'ok':True,'section':section,'counts':counts,'group':group,'canonical_unchanged':True},cursor,limit,max_bytes)
    if section=='scans':
        scans=discovery.status(Store(root),scan_id,summaries=True)['scans']
        rows=[{'scan_id':s['id'],'source_identity':s['snapshot']['identity'],'revision':s['snapshot']['revision'],
               'complete':s['complete'],'state':s.get('state'),'coverage':s.get('counters'),'incremental':s.get('incremental',False),
               **({'recovery_of': s['recovery_of']} if s.get('recovery_of') else {})} for s in scans]
        return page(rows,{'ok':True,'section':section,'canonical_unchanged':True},cursor,limit,max_bytes)
    base=safe_path(installation / 'state/projects' / project.identity)
    job = None
    compatibility = None
    if scan_id is None:
        folder = base / 'full' if scope == 'full' else last_incremental(base)
        if folder is None or not safe_path(folder / 'job.json').exists():
            return no_scan(root)
        binding, _ = scan_binding(installation, project)
        job = scan_jobs.status(folder, binding['root'])
        compatibility = scan_jobs.compatibility(job, binding)
        scan_id = job.get('scan_id')
    if section == 'checkpoint':
        rows = [{'scan_id': scan_id, 'job_id': job['job'], 'worker_state': job['state'],
                 'scope': job['scope'], **compatibility}]
        return page(rows, {'ok':True,'section':section,'canonical_unchanged':True}, cursor, limit, max_bytes)
    require(scan_id, 'scan-checkpoint-not-yet-available', compatibility)
    scans=discovery.status(Store(root),scan_id)['scans']
    require(len(scans)==1,'unknown-scan')
    state=scans[0]
    require(bool(state.get('incremental')) == (scope == 'incremental'), 'scan-job-scope-binding-mismatch')
    if section in ('failures','coverage'):
        rows=[{'path':path,**{k:v for k,v in entry.items() if k not in ('working_blob','git_blob','head_blob')}}
              for path,entry in sorted(state['coverage'].items())
              if section=='coverage' or entry['status'] in ('blocked','excluded') or entry.get('processing_status')=='partial']
        if section=='failures':rows.extend(state['snapshot']['exclusions']);rows.extend(state['snapshot'].get('coverage_errors',[]))
    elif section=='policy':rows=[state['snapshot']['policy']]
    elif section=='impact':
        impact=state.get('impact',{});require(collection is None or collection in impact,'unknown-impact-collection')
        rows=[{'category':kind,'value':item} for kind,items in sorted(impact.items()) if collection is None or kind==collection for item in (items if isinstance(items,list) else [items])]
    elif section=='identity':
        identity=state.get('identity_verification') or {}
        rows=[{'path':path,'reason':'missing-compatible-cached-analysis'} for path in identity.get('missing_files',[])]+[{'id':identifier,'reason':'ambiguous-identity'} for identifier in identity.get('ambiguous_ids',[])]
    else:
        review=discovery.reconcile(Store(root),state['id']);rows=review['claims']+review['negative_evidence_gaps']
    return page(rows,{'ok':True,'section':section,'scan_id':state['id'],'state':job['state'] if job else state.get('state'),'coverage':state.get('counters'),
            **({'impact_summary':{k:len(v) for k,v in state.get('impact',{}).items() if isinstance(v,list)},'collection':collection} if section=='impact' else {}),
            **({'binding_matches_current':compatibility['configuration'] == 'unchanged', 'compatibility':compatibility} if job else {}),
            'canonical_unchanged':True},cursor,limit,max_bytes)


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
                if pending:
                    from .plan_deduplication import reconcile
                    resolved,report,conflicts=reconcile(store._records(db),pending,lifecycle.latest(db),
                        {cid:semantic_binding for cid in pending} if semantic_binding else {})
                    require(not conflicts,'duplicate-conflict',{'groups':[g['group'] for g in report['groups'] if g['resolution']=='blocked']})
                    lifecycle.verify_source_bindings(store,pending.values(),db)
                    lifecycle.simulate(store,db,{cid:v for cid,v in resolved.items() if v is not None},check_source=False)
            for proposal in pending.values(): rows.append(store.submit(proposal,semantic_binding=semantic_binding))
            return {'ok': True, 'root': str(root), 'results': rows,
                    'added': sum(row['result'] == 'submitted' for row in rows),
                    'skipped': sum(row['result'] != 'submitted' for row in rows),
                    'blocked': 0, 'canonical_unchanged': True}
    finally: lease.close()


def push(store, root, state_dir, binding, value, observe_progress=None):
    action = value.get('action', 'start')
    plans = state_dir / 'plans'
    if 'approve' in value or action in ('recover', 'apply'):
        approval = value.get('approve') or value.get('plan')
        require(isinstance(approval, str) and approval.startswith('sha256:') and len(approval) == 71
                and all(c in '0123456789abcdef' for c in approval[7:]), 'exact-approval-required')
        path = safe_path(plans / (approval[7:] + '.json'))
        saved = loads(path.read_text(encoding='utf-8'))
        require(fingerprint(saved['binding']) == approval, 'corrupt-machine-plan')
        pid = saved['binding']['canonical_plan']
        if action == 'recover':
            states = {row['fingerprint']: row['state'] for row in store.status()['plans']}
            require(saved.get('approved') is True and states.get(pid) in ('COMMITTED', 'ACKNOWLEDGED'), 'no-approved-commit-to-recover')
        else:
            snapshot = discovery.inventory(root) if saved['binding']['source_identity'] is not None else None
            expected = {**binding, 'source_identity': snapshot['identity'] if snapshot else None, 'canonical_plan': pid}
            incremental_validation = saved['binding'].get('source_validation') == 'incremental-git-v1'
            if incremental_validation:
                expected['source_validation'] = 'incremental-git-v1'
            require(expected == saved['binding'], 'machine-plan-drift-prepare-again')
            # Durable intent allows acknowledgement recovery after an unknown
            # post-commit outcome; it never approves a replacement plan.
            saved['approved'] = True
            _write(path, saved)
            store.apply(pid, pid, source_snapshot=snapshot, reconcile_git=incremental_validation)
        store.acknowledge(pid)
        validation = store.validate()
        status = store.status()
        return {'ok': validation['ok'], 'state': 'ACKNOWLEDGED', 'fingerprint': approval, 'canonical_plan': pid,
                'validation': validation, 'queue': dict(Counter(row['status'] for row in status['queue']))}
    require(action in ('start', 'prepare'), 'invalid-push-action')
    import time
    started=time.monotonic();progress_state={}
    def progress(stage,**counts):
        if observe_progress:
            observe_progress(stage, **counts)
        else:
            progress_state.update(stage=stage,elapsed_seconds=round(time.monotonic()-started,3),**counts)
            _write(state_dir/'plan-progress.json',progress_state)
    source_identity = None

    def observe_source(snapshot):
        nonlocal source_identity
        source_identity = snapshot['identity']

    try:
        progress('loading-completed-scan-artifacts')
        recovered=discovery.completed_artifact(store,value['rebuild_scan_id']) if value.get('rebuild_scan_id') else None
        snapshot = None
        if recovered:
            progress('verifying-current-source-inventory')
            snapshot = discovery.inventory(root)
            require(recovered['source_identity']==snapshot['identity'],'scan-artifact-source-or-policy-drift',
                    {'next_action':'Preserve the scan. Inspect source/policy changes before selecting explicit recovery.'})
        prepared = store.prepare(progress=progress, source_snapshot=snapshot, reconcile_git=True, observe_source=observe_source)
        progress('blocked' if prepared['blocked'] else 'awaiting-exact-approval',
                 processed_candidates=len(prepared['candidates']) + len(prepared['skipped']),
                 total_candidates=len(prepared['candidates']) + len(prepared['skipped']))
    except Exception as error:
        progress('failed',error=getattr(error,'code',type(error).__name__));raise
    seal = {**binding, 'source_identity': source_identity, 'canonical_plan': prepared['fingerprint'],
            'source_validation': 'incremental-git-v1'}
    approval = fingerprint(seal)
    if prepared['ok']:
        path = plans / (approval[7:] + '.json')
        if not path.exists(): _write(path, {'version': 1, 'binding': seal, 'approved': False})
    from .diagnostic_pages import compact
    from .git_reconciliation import local
    resolved = prepared.get('resolved', prepared['candidates'])
    included = prepared['included']
    deferred = prepared['skipped']
    operations = Counter(op['action'] for cid in included if resolved[cid] for op in resolved[cid].get('operations', []))
    counts = {'pending': len(prepared['candidates']) + len(deferred), 'included': len(included),
              'skipped': len(deferred), 'blocked_by_plan': len(prepared['candidates']) - len(included),
              'coalesced_within_included': sum(resolved[cid] is None for cid in included)}
    dispositions = Counter(row['reason'] for row in deferred)
    next_action = ('Separate explicit approval: /knowledge-candidates-push {"approve":"' + approval
                   + '"}. On drift prepare and review a new fingerprint.' if prepared['ok'] else
                   'Inspect plan-dispositions and resolve the reported blockers before preparing again.')
    path = state_dir / 'last-plan.json'
    summary = {'ok': prepared['ok'], 'state': 'AWAITING_EXACT_APPROVAL' if prepared['ok'] else 'BLOCKED',
               'root': str(root), 'fingerprint': approval, 'canonical_plan': prepared['fingerprint'],
               'included': len(included), 'operations': dict(operations), 'candidate_counts': counts,
               'source_revalidated_git': sum(local(item) and item['source']['identity'] != source_identity
                                             for item in prepared['candidates'].values()),
               'skipped_by_reason': dict(dispositions), 'deduplication': prepared.get('deduplication', {}).get('counts'),
               'recovered_scan': recovered, 'skipped': len(deferred), 'blocked': [compact(row) for row in prepared['blocked'][:8]],
               'canonical_unchanged': True, 'skipped_details': [compact(row) for row in deferred[:8]],
               'diagnostics': str(path), 'next_action': next_action}
    _write(path, {'version': 2, 'diagnostic_projection': True, **summary})
    return summary


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
