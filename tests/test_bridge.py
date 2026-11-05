import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "trinity_solver_tauri/src-tauri/solver_backend/runner.py"
ENGINE = ROOT / "core/trinity_solver_engine_v1.py"


class TestDesktopPythonBridge(unittest.TestCase):
    """Execute the *packaged* runner from an isolated directory, without installed repo paths."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="trinity_bridge_")
        cls.dir = Path(cls.temp.name)
        shutil.copy2(RUNNER, cls.dir / "runner.py")
        shutil.copy2(ENGINE, cls.dir / "trinity_solver_engine_v1.py")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def invoke(self, payload):
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        process = subprocess.run(
            [sys.executable, "-B", str(self.dir / "runner.py")],
            input=data,
            capture_output=True,
            timeout=12,
            cwd=self.dir,
        )
        self.assertEqual(process.returncode, 0, process.stderr.decode(errors="replace"))
        return json.loads(process.stdout)

    def test_success_and_numerical_solution(self):
        out = self.invoke({"seed": 5711, "problem": {
            "kind": "linear_system", "A": [[3, 1], [1, 2]], "b": [9, 8],
        }})
        self.assertTrue(out["ok"])
        self.assertTrue(out["result"]["verified"])
        self.assertEqual(out["result"]["output"]["solution"], [2.0, 3.0])

    def test_reject_unknown_command(self):
        out = self.invoke({"problem": {"kind": "not_supported"}})
        self.assertFalse(out["ok"])
        self.assertIn("unknown problem kind", out["error"])

    def test_reject_invalid_seed(self):
        out = self.invoke({"seed": True, "problem": {"kind": "linear_system"}})
        self.assertFalse(out["ok"])
        self.assertIn("seed must be integer", out["error"])

    def test_reject_request_above_two_megabytes(self):
        out = self.invoke(b" " * 2_000_001)
        self.assertFalse(out["ok"])
        self.assertIn("JSON exceeds 2MB", out["error"])


if __name__ == "__main__":
    unittest.main()
