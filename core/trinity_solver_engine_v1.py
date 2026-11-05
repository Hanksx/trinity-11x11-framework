#!/usr/bin/env python3
"""Trinity Solver Engine v1: verifiable numerical problems and scientific leads.

This is a classical numerical baseline attached to the 11x11 framework.
A detected anomaly or fitted relation is a hypothesis, NOT a physical discovery.
No E11 superiority or post-quantum speedup is claimed by this module.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Callable
import time
import numpy as np


@dataclass(frozen=True)
class SolverResult:
    kind: str
    status: str
    method: str
    verified: bool
    output: dict[str, Any]
    diagnostics: dict[str, Any]
    caveat: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class TrinitySolverEngine:
    """Bounded solver registry with independently checked numerical outcomes."""

    def __init__(self, seed: int = 5711):
        self.seed = int(seed)
        self._registry: dict[str, Callable[[dict], SolverResult]] = {}
        self.register('linear_system', self._linear_system)
        self.register('anomaly_scan', self._anomaly_scan)
        self.register('relation_search', self._relation_search)

    def register(self, kind: str, fn: Callable[[dict], SolverResult]):
        if not kind or not isinstance(kind, str) or not callable(fn):
            raise ValueError('invalid solver registration')
        if kind in self._registry:
            raise ValueError(f'duplicate solver registration: {kind}')
        self._registry[kind] = fn

    def capabilities(self) -> list[str]:
        return sorted(self._registry)

    def solve(self, problem: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(problem, dict):
            raise TypeError('problem must be a dictionary')
        kind = problem.get('kind')
        if kind not in self._registry:
            raise ValueError(f'unknown problem kind: {kind!r}; supported={self.capabilities()}')
        started = time.perf_counter()
        result = self._registry[kind](problem)
        if not isinstance(result, SolverResult):
            raise TypeError('solver plugin must return SolverResult')
        result_dict = result.as_dict()
        result_dict['seed'] = self.seed
        result_dict['elapsed_ms'] = round(1000 * (time.perf_counter()-started), 3)
        result_dict['selector'] = 'explicit_capability_registry_v1'
        result_dict['e11_decision_policy_active'] = False
        return result_dict

    @staticmethod
    def _array(values: Any, ndim: int, name: str, maximum: int = 10000):
        arr = np.asarray(values, dtype=np.float64)
        if arr.ndim != ndim or arr.size == 0 or arr.size > maximum:
            raise ValueError(f'{name} must have {ndim} dimensions and 1..{maximum} values')
        if not np.isfinite(arr).all():
            raise ValueError(f'{name} contains non-finite values')
        return arr

    def _linear_system(self, p: dict) -> SolverResult:
        a = self._array(p.get('A'), 2, 'A', 10000)
        b = self._array(p.get('b'), 1, 'b', 200)
        if a.shape[0] != b.size or a.shape[1] > 100:
            raise ValueError('A columns <=100 and A rows equal b length required')
        # Reuse one SVD for both rank determination and spectral norm.
        singular_values = np.linalg.svd(a, compute_uv=False)
        rank_tolerance = singular_values[0] * max(a.shape) * np.finfo(a.dtype).eps
        rank = int(np.count_nonzero(singular_values > rank_tolerance))
        if a.shape[0] == a.shape[1] and rank == a.shape[1]:
            x = np.linalg.solve(a, b)
            method = 'numpy.linalg.solve'
        else:
            x = np.linalg.lstsq(a, b, rcond=None)[0]
            method = 'numpy.linalg.lstsq'
        residual = a @ x-b
        abs_residual = float(np.linalg.norm(residual))
        normal_residual = float(np.linalg.norm(a.T @ residual))
        # Preserve the previous exact spectral-norm verification threshold.
        scale = 1+float(singular_values[0])*float(np.linalg.norm(x))+float(np.linalg.norm(b))
        verified = bool(np.isfinite(x).all() and
                        normal_residual <= 1e-8*scale and
                        (method == 'numpy.linalg.lstsq' or abs_residual <= 1e-8*scale))
        exact = bool(abs_residual <= 1e-8*scale)
        return SolverResult('linear_system', 'solved' if exact and verified else 'approximate' if verified else 'failed', method,
            verified, {'solution':x.tolist()},
            {'rank':rank,'equations':a.shape[0],'unknowns':a.shape[1],
             'residual_norm':abs_residual,'normal_equation_residual':normal_residual},
            'Numerical linear algebra; verify condition number and input-model validity separately.')

    def _anomaly_scan(self, p: dict) -> SolverResult:
        x = self._array(p.get('values'), 1, 'values', 10000)
        if x.size < 12: raise ValueError('at least 12 samples required')
        threshold = float(p.get('threshold', 3.5))
        if not np.isfinite(threshold) or not 2.0 <= threshold <= 10.0:
            raise ValueError('threshold must be finite in [2,10]')
        median = float(np.median(x))
        mad = float(np.median(np.abs(x-median)))
        robust_scale = 1.4826*mad
        if robust_scale <= 1e-12:
            # Constant baseline: report deviations but don't manufacture a z-score.
            outliers = np.flatnonzero(np.abs(x-median) > 1e-12).tolist()
            scores = [None if i in outliers else 0.0 for i in range(len(x))]
            method = 'constant_baseline_change_points'
        else:
            z = np.abs((x-median)/robust_scale)
            outliers = np.flatnonzero(z > threshold).tolist()
            scores = z.tolist()
            method = 'median_MAD_robust_zscore'
        verified = bool(all(0 <= i < len(x) for i in outliers))
        return SolverResult('anomaly_scan', 'candidate' if outliers else 'no_candidate', method, verified,
            {'candidate_indices':outliers,'candidate_values':[float(x[i]) for i in outliers],
             'scores':scores},
            {'n_samples':len(x),'median':median,'MAD':mad,'threshold':threshold},
            'A statistical anomaly is not evidence of a new physical phenomenon; check sensors and independent datasets.')

    def _relation_search(self, p: dict) -> SolverResult:
        x = self._array(p.get('x'),1,'x',5000)
        y = self._array(p.get('y'),1,'y',5000)
        if x.size != y.size or x.size < 30: raise ValueError('x and y must have equal length >=30')
        n_perm = p.get('permutations',99)
        if isinstance(n_perm,bool) or not isinstance(n_perm,int) or not 19 <= n_perm <= 499:
            raise ValueError('permutations must be an integer in [19,499]')
        if np.std(x) < 1e-12 or np.std(y) < 1e-12:
            return SolverResult('relation_search','inconclusive','constant_data_guard',True,{},
                {'reason':'no meaningful variance'},'No relationship can be inferred from constant data.')
        rng = np.random.default_rng(self.seed)
        ids = rng.permutation(len(x))
        split = max(16,int(round(len(x)*.75)))
        train,test = ids[:split],ids[split:]
        xm = float(np.mean(x[train])); xs = float(np.std(x[train]))
        if xs < 1e-12: raise ValueError('training x has no variance')
        z = (x-xm)/xs
        design = (np.ones((len(x),1)),np.column_stack((np.ones(len(x)),z)),
                  np.column_stack((np.ones(len(x)),z,z*z)))
        labels = ('constant','linear','quadratic')
        def compare(target):
            errors=[]; coefs=[]
            for d in design:
                coef=np.linalg.lstsq(d[train],target[train],rcond=None)[0]
                errors.append(float(np.sqrt(np.mean((d[test]@coef-target[test])**2))))
                coefs.append(coef)
            baseline = errors[0]
            best = min((1,2),key=lambda i:(errors[i],i))
            # Require substantive lift to prevent a barely better complex model.
            lift = max(0.0,(baseline-errors[best])/max(baseline,1e-12))
            return errors,coefs,best,lift
        errors,coefs,best,lift=compare(y)
        null_lifts=np.empty(n_perm,dtype=float)
        for j in range(n_perm):
            perm=rng.permutation(len(y))
            null_lifts[j]=compare(y[perm])[3]
        p_value=float((1+np.count_nonzero(null_lifts >= lift-1e-12))/(n_perm+1))
        selected = best if lift >= .10 and p_value <= .05 else 0
        status='candidate' if selected else 'inconclusive'
        predictions=design[selected][test] @ coefs[selected]
        verified=bool(np.isfinite(predictions).all() and np.isfinite(errors).all())
        return SolverResult('relation_search',status,'holdout_polynomial_selection_with_permutation_null',verified,
            {'model':labels[selected], 'coefficients_scaled_x':coefs[selected].tolist(),
             'x_center':xm,'x_scale':xs},
            {'n_samples':len(x),'n_train':len(train),'n_holdout':len(test),
             'holdout_rmse':errors[selected],'baseline_rmse':errors[0],
             'candidate_model':labels[best],'candidate_lift':lift,
             'selection_adjusted_permutation_p':p_value,'permutations':n_perm},
            'Exploratory statistical lead only. Holdout was used for model selection; external replication and controls are still required.')
