import unittest
from calc import core

class Check(unittest.TestCase):
    def test_message_fixed(self):
        with self.assertRaises(ZeroDivisionError) as cm:
            core.divide(1, 0)
        self.assertIn("Cannot divide by zero", str(cm.exception))
        self.assertNotIn("devide", str(cm.exception))
