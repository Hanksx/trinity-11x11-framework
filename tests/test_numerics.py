import unittest

import numpy as np

from core.primary_core import solve_problem


class TestNumericalEdgeCases(unittest.TestCase):
    def test_singular_system_uses_least_squares(self):
        a = [[1.0, 2.0], [2.0, 4.0]]
        b = [3.0, 6.0]
        result = solve_problem({"kind": "linear_system", "A": a, "b": b})
        self.assertEqual(result["method"], "numpy.linalg.lstsq")
        self.assertEqual(result["diagnostics"]["rank"], 1)
        self.assertTrue(result["verified"])
        self.assertTrue(np.allclose(np.array(a) @ result["output"]["solution"], b))

    def test_overdetermined_normal_residual(self):
        a = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
        b = np.array([1.0, 2.0, 2.8])
        result = solve_problem({"kind": "linear_system", "A": a.tolist(), "b": b.tolist()})
        self.assertEqual(result["method"], "numpy.linalg.lstsq")
        self.assertTrue(result["verified"])
        expected = np.linalg.lstsq(a, b, rcond=None)[0]
        self.assertTrue(np.allclose(result["output"]["solution"], expected))
        self.assertLessEqual(result["diagnostics"]["normal_equation_residual"], 1e-9)


if __name__ == "__main__":
    unittest.main()
