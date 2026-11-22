"""Experiment C adapter: no simulator source edits, one real solver call per round."""
import dataclasses
import hashlib
import json
import math
import sys
from pathlib import Path

from ugvkit import runner


def alpha_for(mode, k, r):
    return float(mode == 'on' or (mode == 'pulse' and r == k) or
                 (mode == 'prefix' and r <= k))


def canonical(x):
    if x is None or isinstance(x, (str, bool, int, float)):
        return x
    if isinstance(x, (list, tuple)):
        return [canonical(v) for v in x]
    if isinstance(x, dict):
        return {str(k): canonical(v) for k, v in sorted(x.items(), key=lambda p: str(p[0]))}
    if isinstance(x, (set, frozenset)):
        return sorted((canonical(v) for v in x), key=lambda v: json.dumps(v, sort_keys=True))
    if dataclasses.is_dataclass(x):
        return canonical(dataclasses.asdict(x))
    if hasattr(x, 'item'):
        return canonical(x.item())
    if hasattr(x, '__dict__'):
        return canonical(vars(x))
    raise TypeError(f'Unsupported action/state type: {type(x)}')


def digest(x):
    return hashlib.sha256(json.dumps(canonical(x), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class Trace:
    def __init__(self, mode, k):
        self.mode, self.k = mode, k
        self.pending, self.rounds = [], []

    def result(self):
        if any(math.isfinite(p[0]) for p in self.pending):
            raise RuntimeError('Feasible pair evaluations did not end in a solver call; adapter cannot identify rounds safely')
        return {'schema': 1, 'mode': self.mode, 'k': self.k, 'rounds': self.rounds}


def install(app, np, mode, k, algorithm):
    t = Trace(mode, k)
    original = app.SharedRideEngine.pair_cost

    def pair_cost(self, m, request, alpha, beta):
        r = len(t.rounds) + 1
        active = alpha_for(mode, k, r)
        # Fingerprint the ordered candidate identities, pre-existing plan and scalar vehicle state.
        # This is not a snapshot of the complete simulator state.
        mid = getattr(m, 'id', getattr(m, 'vehicle_id', None))
        if mid is None:
            raise RuntimeError('Cannot identify vehicle in frozen simulator')
        scalars = {key: val for key, val in vars(m).items()
                   if isinstance(val, (str, int, float, bool, type(None)))}
        state = digest([mid, request.id, getattr(m, 'planned_stops', None), scalars])
        cost, meta = original(self, m, request, active, beta)
        t.pending.append((float(cost), meta, canonical(mid), canonical(request.id), state))
        return cost, meta

    app.SharedRideEngine.pair_cost = pair_cost
    fn = app.ALGO_FUNCS[algorithm]

    def solver(C, *args, **kwargs):
        matrix = np.asarray(C, dtype=float)
        n = matrix.size
        if matrix.ndim != 2 or n == 0 or len(t.pending) < n:
            raise RuntimeError(f'Unexpected matrix/round boundary: {matrix.shape}, {len(t.pending)} pair calls')
        # Some all-infeasible matrices are not solved at all. The preceding discarded evaluations
        # must be individually infeasible; otherwise the hook has missed a real eligible round.
        if any(math.isfinite(p[0]) for p in t.pending[:-n]):
            raise RuntimeError('Unmatched feasible pair evaluations before solver matrix')
        t.pending=t.pending[-n:]
        costs = np.array([p[0] for p in t.pending]).reshape(matrix.shape)
        if not np.allclose(matrix, costs, rtol=1e-12, atol=1e-12, equal_nan=True):
            raise RuntimeError('Pair evaluation order does not match solver matrix')
        pairs = fn(C, *args, **kwargs)
        if not np.isfinite(matrix).any():
            if len(pairs): raise RuntimeError('All-infeasible matrix returned assignments')
            t.pending.clear()
            return pairs
        actions = []
        for i, j in sorted(set(map(tuple, pairs))):
            _, meta, mid, rid, _ = t.pending[int(i)*matrix.shape[1]+int(j)]
            if not meta or not math.isfinite(float(meta['delta_energy'])):
                raise RuntimeError('Selected pair lacks finite route increment')
            actions.append({'vehicle': mid, 'request': rid, 'stops': digest(meta['stops']),
                            'energy_Wh': float(meta['delta_energy']), 'time_s': float(meta['delta_time'])})
        r = len(t.rounds)+1
        t.rounds.append({'round': r, 'alpha': alpha_for(mode, k, r), 'shape': list(matrix.shape),
                         'state': digest([p[4] for p in t.pending]),
                         'feasibility': digest(np.isfinite(matrix).tolist()), 'matrix': digest(matrix.tolist()),
                         'actions': actions})
        t.pending.clear()
        return pairs

    solver.__name__ = fn.__name__
    app.ALGO_FUNCS[algorithm] = solver
    return t


def main():
    rd = Path(sys.argv[sys.argv.index('--run-dir')+1])
    spec = json.loads((rd/'run_spec.json').read_text())
    if spec['probe']['enabled']:
        runner.install_probe = lambda app, np, ignored: install(app, np, spec['mode'], spec['k'], spec['algorithm'])
    runner.main()


if __name__ == '__main__':
    main()
