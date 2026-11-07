"""r3_feas_free.py - independent count-level feasibility check for FREE order (any interleaving, any
unload order) under the step rule: state (unloads done from L, from R, loads put L, loads put R).
Capacities: ship side free cells, yard free cells (loads free yard cells, unloads fill them).
  python tools/judge_sets/r3_feas_free.py <set.json> ...
"""
import json, sys, os
from functools import lru_cache
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import crane_model as cm

def check(path, lim=5):
    d = cm.load_dataset(path)
    b0, b1 = d["bay0"], d["bay1"]
    pos0 = {b0[x][y]: x for x in range(4) for y in range(12) if b0[x][y]}
    pos1 = {b1[x][y] for x in range(4) for y in range(12) if b1[x][y]}
    U = [i for i in d["unload"] if i in pos0]
    Lo = [i for i in d["load"] if i in pos1]
    uL = sum(1 for i in U if pos0[i] <= 1); uR = len(U) - uL; nl = len(Lo)
    L0, R0 = cm.lr(b0); Y0 = sum(1 for x in range(4) for y in range(12) if b1[x][y])
    @lru_cache(None)
    def f(a, b, c, e):
        L, R = L0 - a + c, R0 - b + e
        if a == uL and b == uR and c + e == nl:
            return True
        Y = Y0 + a + b - c - e
        nxt = []
        if a < uL and Y < 48: nxt.append((a + 1, b, c, e, L - 1, R))
        if b < uR and Y < 48: nxt.append((a, b + 1, c, e, L, R - 1))
        if c + e < nl:
            if L < 24: nxt.append((a, b, c + 1, e, L + 1, R))
            if R < 24: nxt.append((a, b, c, e + 1, L, R + 1))
        for (a2, b2, c2, e2, L2, R2) in nxt:
            if cm.step_ok(L, R, L2, R2, lim) and f(a2, b2, c2, e2):
                return True
        return False
    return f(0, 0, 0, 0), dict(L0=L0, R0=R0, uL=uL, uR=uR, nl=nl, Y0=Y0)

if __name__ == "__main__":
    for p in sys.argv[1:]:
        ok, info = check(p)
        print(os.path.basename(p), "FREE_FEASIBLE" if ok else "INFEASIBLE", info)
