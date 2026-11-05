#!/usr/bin/env python3
"""Only fixed, bundled solver code is importable by this GUI bridge."""
import json, os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trinity_solver_engine_v1 import TrinitySolverEngine

def handle_request(line):
    try:
        if len(line)>2_000_000:raise ValueError("JSON exceeds 2MB")
        req=json.loads(line)
        problem=req.get("problem")
        seed=req.get("seed",5711)
        if isinstance(seed,bool) or not isinstance(seed,int):raise ValueError("seed must be integer")
        result=TrinitySolverEngine(seed=seed).solve(problem)
        return {"ok":True,"result":result}
    except Exception as exc:
        return {"ok":False,"error":f"{type(exc).__name__}: {exc}"}


def main():
    line=sys.stdin.buffer.read(2_000_001)
    print(json.dumps(handle_request(line),allow_nan=False,ensure_ascii=False))


def serve():
    """Newline-delimited JSON local worker. Sequential requests share one NumPy import."""
    while True:
        line=sys.stdin.buffer.readline(2_000_002)
        if not line:
            break
        answer=handle_request(line)
        print(json.dumps(answer,allow_nan=False,ensure_ascii=False),flush=True)
        if len(line)>2_000_000:
            # Oversized frame may leave unread bytes: stop rather than desynchronize.
            break


if __name__=="__main__":
    if "--serve" in sys.argv[1:]:
        serve()
    else:
        main()
