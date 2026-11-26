"""Fast installed machine/host feedback; full P4 qualification remains required."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from verify_p4 import source, ROOT, py_at


def main():
    rid = uuid.uuid4().hex
    output = ROOT / 'reports/AutomaticInstaller-fast/runs' / rid
    output.mkdir(parents=True)
    inputs = source(); identity = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    ledger = {'version': 2, 'id': rid, 'qualification': 'machine-fast', 'source': inputs, 'source_identity': identity,
              'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'status': 'RUNNING', 'started': time.time(), 'checks': {}, 'commands': [], 'platform': {'os': platform.system(), 'python': sys.version}}
    def save():
        (output / 'run.json').write_text(json.dumps(ledger, indent=2) + '\n', encoding='utf-8')
    def command(name, argv, required=True):
        before = time.time()
        with (output / (name + '.log')).open('wb') as stream:
            process = subprocess.run([str(value) for value in argv], cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        ledger['commands'].append({'name': name, 'returncode': process.returncode, 'seconds': time.time() - before,
                                   'log': name + '.log', 'sha256': hashlib.sha256((output / (name + '.log')).read_bytes()).hexdigest()})
        ledger['checks'][name] = 'PASS' if process.returncode == 0 else 'FAIL'; save()
        if process.returncode and required: raise RuntimeError('Machine qualification failed: ' + name)
    save()
    try:
        command('distribution', [sys.executable, '-B', ROOT / 'scripts/build_p4.py', '--output', output / 'distribution', '--source-id', identity])
        kit = output / 'distribution/knowledge-harness-0.5.0rc1'
        with tempfile.TemporaryDirectory(prefix='machine-fast-') as tmp:
            base = Path(tmp); runtime = base / 'runtime'; python = py_at(runtime)
            command('install', [sys.executable, kit / 'install.py', 'install', '--env', runtime])
            command('test-dependencies', [python, '-I', '-m', 'pip', 'install', '-r', ROOT / 'requirements-dev.lock'])
            driver = base / 'test-driver.py'
            driver.write_text('import sys,unittest,json,traceback\nfrom pathlib import Path\nsys.path.insert(0,' + repr(str(ROOT / 'tests')) + ')\nsuite=unittest.TestSuite(unittest.defaultTestLoader.discover(' + repr(str(ROOT / 'tests')) + ',pattern=pattern) for pattern in ("test_machine_commands.py","test_discovery_r2.py","test_discovery_optimization.py","test_core_bootstrap.py","test_core_reliability.py","test_plan_deduplication.py","test_persistence_recovery.py","test_plan_recovery_diagnostics.py","test_confluence_source.py","test_confluence_sync.py","test_confluence_command.py","test_confluence_r2*.py","test_confluence_resume.py","test_confluence_progress.py","test_confluence_static.py","test_ci_artifacts.py"))\nissues={};passed=[]\nclass Result(unittest.TextTestResult):\n def addSuccess(self,t):passed.append(t.id());super().addSuccess(t)\n def addError(self,t,e):issues[t.id()]=dict(exception_type=e[0].__name__,errno=getattr(e[1],"errno",None),winerror=getattr(e[1],"winerror",None),filename=getattr(e[1],"filename",None),frames=[dict(file=Path(f.filename).name,line=f.lineno,function=f.name) for f in traceback.extract_tb(e[2])]);super().addError(t,e)\nr=unittest.TextTestRunner(verbosity=2,resultclass=Result).run(suite)\nPath(' + repr(str(output / 'machine-tests.json')) + ').write_text(json.dumps(dict(tests=r.testsRun,passed=len(passed),failed=len(r.failures),errors=len(r.errors),skipped=len(r.skipped),success=r.wasSuccessful(),skip_reasons=[dict(test=t.id(),reason=reason) for t,reason in r.skipped],results=[dict(test=t.id(),status=status,**issues.get(t.id(),{})) for status,items in (("FAIL",r.failures),("ERROR",r.errors)) for t,error in items]),indent=2),encoding="utf-8")\nraise SystemExit(not r.wasSuccessful())\n', encoding='utf-8')
            command('machine-unit-tests', [python, '-I', '-B', '-X', 'utf8', driver], required=False)
            command('machine-installer', [python, '-I', '-B', '-X', 'utf8', ROOT / 'scripts/machine_installer_trial.py', kit, output / 'machine-installer'])
            command('machine-native-host-setup', [python, '-I', '-B', '-X', 'utf8', ROOT / 'scripts/setup_machine_host.py', '--output', base / 'host', '--evidence', output / 'machine-native/host'])
            command('machine-native-commands', [python, '-I', '-B', '-X', 'utf8', ROOT / 'scripts/machine_native_trial.py', '--kit', kit, '--host', base / ('host/opencode.exe' if os.name == 'nt' else 'host/opencode'), '--output', output / 'machine-native'])
        ledger['unchanged'] = inputs == source()
        if not ledger['unchanged']: raise RuntimeError('Qualification inputs changed')
        failed=[name for name,result in ledger['checks'].items() if result!='PASS']
        if failed:raise RuntimeError('Machine qualification failed: '+', '.join(failed))
        ledger['status'] = 'PASS_NATIVE' if os.name == 'nt' else 'PASS_PORTABLE'
    except BaseException as error:
        ledger.update(status='FAILED', error=str(error), unchanged=inputs == source())
        raise
    finally:
        diagnostics = ROOT / 'reports/AutomaticInstaller-diagnostics'
        if diagnostics.exists(): shutil.copytree(diagnostics, output / 'job-diagnostics', dirs_exist_ok=True)
        ledger['finished'] = time.time(); save()
        write = ROOT / 'reports/AutomaticInstaller-fast/latest.json'
        write.write_text(json.dumps({'run': rid, 'status': ledger['status']}) + '\n', encoding='utf-8')
        print(json.dumps({'run': rid, 'status': ledger['status']}))


if __name__ == '__main__': main()
