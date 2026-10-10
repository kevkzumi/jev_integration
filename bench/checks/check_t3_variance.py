import unittest
from calc import stats

class Check(unittest.TestCase):
    def test_variance_population(self):
        self.assertAlmostEqual(stats.variance([2, 4, 4, 4, 5, 5, 7, 9]), 4.0)

    def test_stdev(self):
        self.assertAlmostEqual(stats.stdev([2, 4, 4, 4, 5, 5, 7, 9]), 2.0)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            stats.variance([])

    def test_docstrings(self):
        self.assertTrue(stats.variance.__doc__ and stats.stdev.__doc__)
