import unittest
from calc import core

class Check(unittest.TestCase):
    def test_power(self):
        self.assertEqual(core.power(2, 10), 1024)
        self.assertEqual(core.power(5, 0), 1)
        self.assertAlmostEqual(core.power(9, 0.5), 3.0)
