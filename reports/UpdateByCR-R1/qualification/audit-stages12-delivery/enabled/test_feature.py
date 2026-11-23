import unittest
from Feature import price
class ApprovedBehavior(unittest.TestCase):
 def test_price(self): self.assertEqual(price(),37)
if __name__=="__main__":unittest.main()
