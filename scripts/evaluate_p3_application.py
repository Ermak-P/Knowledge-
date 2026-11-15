# Installed-product P3 entry; scenario generator is shared with accepted P2.
# Product imports resolve only from this interpreter's non-editable release install.
import argparse,importlib.util,os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    import harness,knowledge
    assert Path(harness.__file__).is_relative_to(Path(sys.prefix)) and Path(knowledge.__file__).is_relative_to(Path(sys.prefix))
    spec=importlib.util.spec_from_file_location('p3_application_scenarios',ROOT/'scripts/evaluate_p2.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    # The shared evaluator is Linux-specific historically. Execute a generated
    # P3 copy with native SDK discovery and actual installed product modules.
    text=(ROOT/'scripts/evaluate_p2.py').read_text(encoding='utf-8')
    text=text.replace("sdk=ROOT/'.local/dotnet/dotnet'", "sdk=Path(shutil.which('dotnet') or str(ROOT/'.local/dotnet/dotnet'))")
    text=text.replace(",dir=ROOT/'.local'",'')
    text=text.replace("ROOT=Path(__file__).resolve().parents[1]", 'ROOT=Path('+repr(str(ROOT))+')')
    namespace={'__name__':'__p3_scenarios__','__file__':str(ROOT/'scripts/evaluate_p3_application.py')}
    exec(compile(text,str(ROOT/'scripts/evaluate_p3_application.py'),'exec'),namespace)
    namespace['main']()
if __name__=='__main__':main()
