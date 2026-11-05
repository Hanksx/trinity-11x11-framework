#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "results"
REPORTS = ROOT / "reports"
MATRIX_FILE = DATA / "postquantum_11x11_primary_core_matrix.json"


def load_matrix() -> np.ndarray:
    payload = json.loads(MATRIX_FILE.read_text(encoding="utf-8"))
    matrix = np.asarray(payload.get("E11", payload.get("matrix")), dtype=float)
    if matrix.shape != (11, 11):
        raise ValueError(f"expected 11x11 matrix, got {matrix.shape}")
    if not np.isfinite(matrix).all():
        raise ValueError("matrix contains non-finite values")
    return matrix


def matrix_fingerprint(matrix: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(matrix, dtype="<f8").tobytes()).hexdigest()


def encode(matrix: np.ndarray, bits, rng: np.random.Generator, noise: float = 0.035, orientation: str = "row") -> np.ndarray:
    bits = np.asarray(bits, dtype=np.int8)
    if len(bits) > 10:
        raise ValueError("11x11 core supports at most 10 channels")
    signs = np.sign(matrix + 1e-12)
    x = rng.normal(0.0, noise, matrix.shape)
    if orientation == "row":
        for i, bit in enumerate(bits):
            x[i, :] += signs[i, :] * (0.42 if bit else -0.42)
    elif orientation == "col":
        for i, bit in enumerate(bits):
            x[:, i] += signs[:, i] * (0.42 if bit else -0.42)
    else:
        raise ValueError("orientation must be row or col")
    return np.clip(x, -1.0, 1.0)


def decode(matrix: np.ndarray, encoded: np.ndarray, channels: int, orientation: str = "row"):
    signs = np.sign(matrix + 1e-12)
    if orientation == "row":
        values = np.asarray([np.mean(signs[i, :] * encoded[i, :]) for i in range(channels)])
    elif orientation == "col":
        values = np.asarray([np.mean(signs[:, i] * encoded[:, i]) for i in range(channels)])
    else:
        raise ValueError("orientation must be row or col")
    return (values > 0).astype(np.int8), values


def internal_roundtrip(trials: int = 200, noise: float = 0.20, seed: int = 20260625) -> dict:
    matrix = load_matrix()
    rng = np.random.default_rng(seed)
    rows = []
    for orientation in ("row", "col"):
        exact = []
        bit_accuracy = []
        for _ in range(trials):
            bits = rng.integers(0, 2, 10, dtype=np.int8)
            encoded = encode(matrix, bits, rng, noise=noise, orientation=orientation)
            predicted, _ = decode(matrix, encoded, 10, orientation=orientation)
            exact.append(bool(np.all(predicted == bits)))
            bit_accuracy.append(float(np.mean(predicted == bits)))
        rows.append({
            "orientation": orientation,
            "exact_rate": float(np.mean(exact)),
            "bit_accuracy": float(np.mean(bit_accuracy)),
        })
    return {
        "test": "INTERNAL_ROUNDTRIP_ONLY",
        "matrix_shape": list(matrix.shape),
        "matrix_rank": int(np.linalg.matrix_rank(matrix)),
        "condition_number": float(np.linalg.cond(matrix)),
        "fingerprint_sha256": matrix_fingerprint(matrix),
        "noise": noise,
        "trials": trials,
        "rows": rows,
        "warning": "This verifies encoder/decoder consistency only; it is not evidence of a unique 11x11 advantage.",
    }



def load_solver_engine(seed: int = 5711):
    """Return the bounded, independently verifiable classical solver registry."""
    try:
        from .trinity_solver_engine_v1 import TrinitySolverEngine
    except ImportError:
        from trinity_solver_engine_v1 import TrinitySolverEngine
    return TrinitySolverEngine(seed=seed)


def solve_problem(problem: dict, *, seed: int = 5711) -> dict:
    """Solve supported task kinds with reproducible numerical diagnostics."""
    return load_solver_engine(seed=seed).solve(problem)


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    report = internal_roundtrip()
    (RESULTS / "primary_core_internal_roundtrip.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (REPORTS / "primary_core_internal_roundtrip.md").write_text(
        "# Trinity 11x11 Internal Roundtrip\n\n```json\n" + json.dumps(report, indent=2) + "\n```\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
