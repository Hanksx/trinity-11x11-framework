import json
import select
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "trinity_solver_tauri/src-tauri/solver_backend/runner.py"
ENGINE = ROOT / "core/trinity_solver_engine_v1.py"


class TestPersistentWorker(unittest.TestCase):
    def test_multiple_requests_and_error_recovery(self):
        # In a fresh GitHub checkout the adjacent engine is not present until
        # the packaging sync step. Assemble the real bundle in a clean folder.
        with tempfile.TemporaryDirectory(prefix="trinity_worker_") as folder:
            target = Path(folder)
            shutil.copy2(RUNNER, target / "runner.py")
            shutil.copy2(ENGINE, target / "trinity_solver_engine_v1.py")

            with subprocess.Popen(
                [sys.executable, "-B", "-u", str(target / "runner.py"), "--serve"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=target,
            ) as proc:
                def call(request):
                    proc.stdin.write((json.dumps(request) + "\n").encode())
                    proc.stdin.flush()
                    ready, _, _ = select.select([proc.stdout], [], [], 12)
                    self.assertTrue(ready, "worker did not respond in 12 seconds")
                    response = proc.stdout.readline()
                    if not response:
                        stderr = proc.stderr.read().decode(errors="replace") if proc.poll() is not None else ""
                        self.fail("worker terminated without response; stderr: " + stderr[:1500])
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
