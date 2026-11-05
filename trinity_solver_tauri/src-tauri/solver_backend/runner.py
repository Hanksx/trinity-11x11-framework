#!/usr/bin/env python3
"""Only fixed, bundled solver code is importable by this GUI bridge."""
import json, os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trinity_solver_engine_v1 import TrinitySolverEngine

def main():
    try:
        line=sys.stdin.buffer.read(2_000_001)
        if len(line)>2_000_000:raise ValueError('JSON exceeds 2MB')
        req=json.loads(line)
        problem=req.get('problem')
        seed=req.get('seed',5711)
        if isinstance(seed,bool) or not isinstance(seed,int):raise ValueError('seed must be integer')
        result=TrinitySolverEngine(seed=seed).solve(problem)
        print(json.dumps({'ok':True,'result':result},allow_nan=False,ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'ok':False,'error':f'{type(exc).__name__}: {exc}'},ensure_ascii=False))

if __name__=='__main__':main()
