import json
import select
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "trinity_solver_tauri/src-tauri/solver_backend/runner.py"


class TestPersistentWorker(unittest.TestCase):
    def test_multiple_requests_and_error_recovery(self):
        with subprocess.Popen(
            [sys.executable, "-B", "-u", str(RUNNER), "--serve"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ) as proc:
            def call(request):
                proc.stdin.write((json.dumps(request) + "\n").encode())
                proc.stdin.flush()
                ready, _, _ = select.select([proc.stdout], [], [], 12)
                self.assertTrue(ready, "worker did not respond in 12 seconds")
                response = proc.stdout.readline()
                self.assertTrue(response, "worker terminated without response")
                return json.loads(response)

            first = call({"problem": {"kind": "linear_system", "A": [[2]], "b": [6]}})
            self.assertTrue(first["ok"])
            self.assertEqual(first["result"]["output"]["solution"], [3.0])
            pid = proc.pid

            second = call({"problem": {"kind": "linear_system", "A": [[3]], "b": [12]}})
            self.assertTrue(second["ok"])
            self.assertEqual(second["result"]["output"]["solution"], [4.0])
            self.assertEqual(proc.pid, pid)
            self.assertIsNone(proc.poll())

            error = call({"problem": {"kind": "unknown"}})
            self.assertFalse(error["ok"])
            self.assertIn("unknown problem kind", error["error"])
            self.assertIsNone(proc.poll())

            proc.stdin.close()
            proc.wait(timeout=12)
            self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
