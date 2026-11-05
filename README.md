# Trinity 11x11 Framework

Software-only version. Contains the numerical matrix core, a bounded classical solver,
the Trinity Solver 5.0.1 desktop application (Tauri, Rust, TypeScript, Python),
and tests. The 11x11 matrix is bundled solely as a required engine configuration.

This repository deliberately excludes all research projects, Kaggle entries,
notebooks, experiments, reports, generated results and private data.

Quick test:
    python3 -m pip install -r requirements.txt
    python3 -m unittest discover -s tests -v
    python3 core/primary_core.py

Desktop app:
    cd trinity_solver_tauri
    npm ci
    npm run build
    npm run tauri:dev

Features: numerical matrix encode/decode, linear systems, anomaly scanning,
candidate relationship search, plus trusted local Target scripts.

Security: Target scripts run with the current operating system user permissions.
Never run untrusted scripts. This code does not establish physical discoveries or quantum advantage.

License has not yet been selected. Publishing source code by itself does not
grant permissions beyond those already applicable to any third-party dependencies.

For trusted Target scripts importing the core, set TRINITY_WORKSPACE to your clone directory before launching the desktop application.

## Continuous integration

GitHub Actions runs the Python core + packaged Python bridge tests on Python 3.11–3.13,
the TypeScript/Vite frontend build on Node.js 22, and a native macOS Intel job
that compiles Rust, runs Rust tests and builds a Tauri `.app` bundle.

The macOS CI is a build verification, **not** a notarized application release or
an end-to-end GUI test. The packaged app needs a local Python installation with
NumPy available; it does not currently bundle a Python runtime or NumPy wheels.
Configure `TRINITY_PYTHON` with the Python interpreter path when necessary.

**Target Scripts are privileged local code**, not a sandbox. Only run scripts
whose source you have reviewed and trust. They execute with your operating-system
user's permissions and can access your filesystem. JavaScript Targets require
dynamic code evaluation in the app's webview, so this mode carries additional risk.

The linear-system capability delegates its numerical solve to NumPy.
Automated tests check correctness and regressions; they do not prove a new
algorithm, scientific discovery, or competitive performance.

### Persistent solver bridge

The desktop app now uses a single long-lived Python process for normal
\`solver_run\` calls (newline-delimited JSON over local stdin/stdout). Repeated
queries reuse the NumPy import and the Python interpreter; no socket or
network server is exposed. The worker restarts after an I/O error or timeout
(35 seconds), and responses are limited to 2 MB.

\`run_python_script\` Target scripts remain separate, privileged one-shot
processes; they are **not** a security sandbox. The worker startup cost is
paid on the first call. The persistent protocol is covered by Python and Rust
tests. Performance benchmarks are stored privately outside this repository.
