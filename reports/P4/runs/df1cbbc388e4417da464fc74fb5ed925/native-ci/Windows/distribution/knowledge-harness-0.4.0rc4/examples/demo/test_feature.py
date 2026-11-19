"""Independent regression executes the compiled C# application."""
import subprocess,sys,unittest
from pathlib import Path
DOTNET=sys.argv.pop(1)
class CompiledFeature(unittest.TestCase):
    def test_compiled_behavior(self):
        p=subprocess.run([DOTNET,str(Path('bin/Debug/net10.0/Project.dll'))],capture_output=True,text=True,timeout=30)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(p.stdout.strip(),'fixed')
if __name__=='__main__':unittest.main()
