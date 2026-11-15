import unittest
from Feature import VALUE
class ExpectedBehavior(unittest.TestCase):
    def test_value_is_two(self):
        self.assertEqual(VALUE, 2)
if __name__ == '__main__':
    unittest.main()
