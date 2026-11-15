# Installed-product P3 entry; scenario generator is shared with accepted P2.
# Product imports resolve only from this interpreter's non-editable release install.
import argparse,importlib.util,json,os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def save_utf8(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    import harness,knowledge
    assert Path(harness.__file__).is_relative_to(Path(sys.prefix)) and Path(knowledge.__file__).is_relative_to(Path(sys.prefix))
    spec=importlib.util.spec_from_file_location('p3_application_scenarios',ROOT/'scripts/evaluate_p2.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    # The shared evaluator is Linux-specific historically. Execute a generated
    # P3 copy with native SDK discovery and actual installed product modules.
    text=(ROOT/'scripts/evaluate_p2.py').read_text(encoding='utf-8')
    text=text.replace("sdk=ROOT/'.local/dotnet/dotnet'", "sdk=Path(shutil.which('dotnet') or str(ROOT/'.local/dotnet/dotnet'))")
    text=text.replace(",dir=ROOT/'.local'",'')
    text=text.replace("sdkversion=subprocess.check_output([str(sdk),'--version'],env=env,text=True).strip()","sdkversion=subprocess.check_output([str(sdk),'--version'],cwd=root,env=env,text=True).strip()")
    text=text.replace("(synthetic/'Checks').mkdir()","(synthetic/'Checks').mkdir();(synthetic/'global.json').write_text('{\"sdk\":{\"version\":\"10.0.404\",\"rollForward\":\"disable\"}}',encoding='utf-8')")
    text=text.replace("ROOT=Path(__file__).resolve().parents[1]", 'ROOT=Path('+repr(str(ROOT))+')')
    namespace={'__name__':'__p3_scenarios__','__file__':str(ROOT/'scripts/evaluate_p3_application.py')}
    exec(compile(text,str(ROOT/'scripts/evaluate_p3_application.py'),'exec'),namespace)
    namespace['save']=save_utf8
    namespace['main']()
if __name__=='__main__':main()
