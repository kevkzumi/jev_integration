import unittest
from decimal import Decimal
from calc import core

class Check(unittest.TestCase):
    def test_decimal_preserved(self):
        r = core.add(Decimal("0.1"), Decimal("0.2"))
        self.assertIsInstance(r, Decimal)
        self.assertEqual(r, Decimal("0.3"))

    def test_mixed_float_and_decimal(self):
        r = core.multiply(0.5, Decimal("0.2"))
        self.assertIsInstance(r, Decimal)
        self.assertEqual(r, Decimal("0.1"))

    def test_divide_precision(self):
        r = core.divide(Decimal("1"), Decimal("3"))
        self.assertIsInstance(r, Decimal)
        self.assertTrue(str(r).startswith("0.3333333333"))

    def test_ints_and_floats_unchanged(self):
        self.assertEqual(core.add(2, 3), 5)
        self.assertIsInstance(core.add(2, 3), int)
        self.assertAlmostEqual(core.divide(1.0, 4), 0.25)
        self.assertIsInstance(core.divide(1.0, 4), float)

    def test_zero_message_kept(self):
        with self.assertRaises(ZeroDivisionError):
            core.divide(Decimal("1"), Decimal("0"))
