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
