"""r1_witness.py - judge round 1: build a concrete IN-ORDER plan (order 1 or 2) from the exact DP and
validate it command by command with the team's own FB1 emulator + CheckCmd (crane_plan.simulate).
Also prints how the PLC planner (plan_fb, default order 1 + fallback) breaks the list order.

  python tools/judge_sets/r1_witness.py <dataset.json> [--order 2|1]
"""
import os
import sys
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import crane_model as cm  # noqa: E402
import crane_plan as cp   # noqa: E402

LIM = 5


def ok(L, R, L2, R2):
    return abs(L2 - R2) <= LIM or abs(L2 - R2) <= abs(L - R)


def witness(ds, st, order):
    PU, PL = cp.locate([ds["bay0"], ds["bay1"]], st["PU"], st["PL"])
    us = [0 if s.pos[0] <= 1 else 1 for s in PU]
    nu, nl = len(PU), len(PL)
    L0, R0 = cm.lr(ds["bay0"])
    occ1 = sum(1 for x in range(4) for y in range(12) if ds["bay1"][x][y] != 0)
    sys.setrecursionlimit(10000)

    @lru_cache(maxsize=None)
    def f(i, j, L, R):
        if i == nu and j == nl:
            return ()
        if i < nu and occ1 + i - j < 48:
            L2, R2 = (L - 1, R) if us[i] == 0 else (L, R - 1)
            if ok(L, R, L2, R2):
                r = f(i + 1, j, L2, R2)
                if r is not None:
                    return (("U", i),) + r
        if j < nl and (order == 1 or i == nu):
            for side in (0, 1):
                L2, R2 = (L + 1, R) if side == 0 else (L, R + 1)
                if (L2 if side == 0 else R2) > 24 or not ok(L, R, L2, R2):
                    continue
                r = f(i, j + 1, L2, R2)
                if r is not None:
                    return (("L", j, side),) + r
        return None

    seq = f(0, 0, L0, R0)
    if seq is None:
        return None
    g = [[c[:] for c in ds["bay0"]], [c[:] for c in ds["bay1"]]]
    fb = cm.FB1(2)
    crane = (0, 0, 1)
    plan = []
    for step in seq:
        if step[0] == "U":
            s = PU[step[1]]
            cand = [(x, y, 1) for x in range(4) for y in range(12) if g[1][x][y] == 0]
        else:
            s = PL[step[1]]
            xs = (0, 1) if step[2] == 0 else (2, 3)
            cand = [(x, y, 0) for x in xs for y in range(12) if g[0][x][y] == 0]
        d = min(cand, key=lambda p: cm.W(s.pos, p, 2))
        if crane != s.pos:
            fb.command(3, *s.pos)
        fb.command(1)
        fb.command(3, *d)
        fb.command(2)
        sx, sy, sb = s.pos
        g[d[2]][d[0]][d[1]] = g[sb][sx][sy]
        g[sb][sx][sy] = 0
        crane = d
        plan.append({"kind": s.kind, "id": s.id, "list_idx": s.idx, "src": s.pos, "dst": d,
                     "cum_t": fb.T_ds, "cum_m": fb.M})
    return plan


def inversions(plan):
    out = []
    for k in (1, 2):
        seq = [tr["list_idx"] for tr in plan if tr["kind"] == k]
        inv = sum(1 for a in range(len(seq)) for b in range(a + 1, len(seq)) if seq[a] > seq[b])
        out.append((k, inv, seq))
    return out


def main():
    path = sys.argv[1]
    order = int(sys.argv[sys.argv.index("--order") + 1]) if "--order" in sys.argv else 2
    ds = cm.load_dataset(path)
    st = cp.build_state(ds)
    cfg = {"mmode": 2, "order": order, "balmode": 0, "lim": 5}
    w = witness(ds, st, order)
    if w is None:
        print("NO in-order plan exists for order", order)
    else:
        cp.simulate(st, w, cfg)   # raises on any CheckCmd / balance violation
        T, M = w[-1]["cum_t"], w[-1]["cum_m"]
        print("WITNESS order=%d transfers=%d  simulate OK (CheckCmd + |L-R|<=5 after every lift/put)  T=%.1fs M=%d J=%.4f"
              % (order, len(w), T / 10, M, cm.J(T, M, st["N"])))
        print("  order:", " ".join("%s%d" % ("U" if t["kind"] == 1 else "L", t["list_idx"]) for t in w))
    res = cp.plan_fb(st, {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}, [0, 100, 200, 300], imp_evals=3000)
    print("PLC plan_fb(order 1 pref): err=%d order_used=%s J=%s" % (res["err"], res.get("order"), res.get("J")))
    if res["err"] == 0:
        for k, inv, seq in inversions(res["plan"]):
            print("  list %s: %d inversions, executed order %s" % ("unload" if k == 1 else "load", inv, seq))


if __name__ == "__main__":
    main()
