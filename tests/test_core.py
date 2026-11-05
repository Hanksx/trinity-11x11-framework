import sys, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.primary_core import load_matrix,internal_roundtrip,solve_problem,matrix_fingerprint
class TestTrinityCore(unittest.TestCase):
    def test_matrix(self):
        a=load_matrix()
        self.assertEqual(a.shape,(11,11))
        self.assertTrue(np.isfinite(a).all())
        self.assertEqual(len(matrix_fingerprint(a)),64)
    def test_roundtrip(self):
        v=internal_roundtrip(trials=20,noise=.08,seed=101)
        self.assertEqual(v['matrix_shape'],[11,11])
        self.assertEqual(len(v['rows']),2)
    def test_linear(self):
        r=solve_problem({'kind':'linear_system','A':[[3,1],[1,2]],'b':[9,8]})
        self.assertTrue(r['verified'])
        self.assertTrue(np.allclose(r['output']['solution'],[2,3]))
    def test_anomaly(self):
        r=solve_problem({'kind':'anomaly_scan','values':[1.0]*30+[20.0]})
        self.assertEqual(r['output']['candidate_indices'],[30])
    def test_reject_unknown(self):
        with self.assertRaises(ValueError):solve_problem({'kind':'unsupported'})
if __name__=='__main__':unittest.main()
