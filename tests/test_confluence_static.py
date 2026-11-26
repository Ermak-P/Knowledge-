import ast,unittest
from pathlib import Path

class StaticDefinitions(unittest.TestCase):
    def test_duplicate_module_functions_static(self):
        from knowledge import confluence_command
        for path in Path(confluence_command.__file__).parent.glob('confluence*.py'):
            with self.subTest(module=path.name):
                tree=ast.parse(path.read_text());names=[n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
                self.assertEqual(len(names),len(set(names)))

