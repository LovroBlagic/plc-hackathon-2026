"""r1_jury_rival.py - how a plausible rival team (simple free-order double cycling, no lookahead,
no local search) compares with our PLC default (order 1 + fallback) and our free order (0).
Rival: at each step pick the pending transfer and free destination cell minimising
W(crane->src) + W(src->dst) (T + 190*M, mmode 2), subject to the balance step rule and the same end-state reachability test (cm.reachable). Counts real FB1 M (1 per move).
  python tools/judge_sets/r1_jury_rival.py [glob ...]
"""
import glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import crane_model as cm, crane_plan as cp

def rival(st, mm=2, lim=5):
    g = [[c[:] for c in st["bay0"]], [c[:] for c in st["bay1"]]]
    loc = cp.locate(g, st["PU"], st["PL"])
    if loc is None:
        return None
    pend = [(s.kind, s.pos) for s in loc[0] + loc[1]]
    crane = tuple(st["crane"]); T = M = 0
    while pend:
        L, R = cm.lr(g[0]); best = None
        for k, (kind, src) in enumerate(pend):
            db = 1 - src[2]
            for x in range(4):
                for y in range(12):
                    if g[db][x][y]:
                        continue
                    if kind == 1: L2, R2 = (L - 1, R) if src[0] <= 1 else (L, R - 1)
                    else:         L2, R2 = (L + 1, R) if x <= 1 else (L, R + 1)
                    if not cm.step_ok(L, R, L2, R2, lim):
                        continue
                    rest = [q for j, q in enumerate(pend) if j != k]
                    uL = sum(1 for q in rest if q[0] == 1 and q[1][0] <= 1)
                    uR = sum(1 for q in rest if q[0] == 1 and q[1][0] >= 2)
                    nl = sum(1 for q in rest if q[0] == 2)
                    if not cm.reachable(L2, R2, uL, uR, nl, lim):
                        continue
                    w = cp.wcost(crane, src, mm)[2] + cp.wcost(src, (x, y, db), mm)[2]
                    if best is None or w < best[0]:
                        best = (w, k, (x, y, db))
        if best is None:
            return None
        _, k, d = best; kind, src = pend.pop(k)
        et, em, _ = cp.wcost(crane, src, mm); lt, lm, _ = cp.wcost(src, d, mm)
        T += et + 400 + lt; M += em + 2 + lm
        g[d[2]][d[0]][d[1]] = g[src[2]][src[0]][src[1]]; g[src[2]][src[0]][src[1]] = 0
        crane = d
    return cm.J(T, M, st["N"])

def ours(st, order):
    r = cp.plan_fb(st, {"mmode": 2, "order": order, "balmode": 0, "lim": 5}, [0, 100, 200, 300], imp_evals=3000)
    return r["J"] if r["err"] == 0 else None

pats = sys.argv[1:] or [os.path.join(HERE, "..", "crane_data", "rand_*.json"), os.path.join(HERE, "r1_jury_fig1_*.json")]
rows = []
for pat in pats:
    for p in sorted(glob.glob(pat)):
        st = cp.build_state(cm.load_dataset(p), 5)
        if st["init"]["blocking"]:
            continue
        a, b, c = ours(st, 1), ours(st, 0), rival(st)
        if None in (a, b, c):
            print(os.path.basename(p), "skip", a, b, c); continue
        rows.append((os.path.basename(p), a, b, c))
        print("%-34s default=%.4f free=%.4f rival=%.4f  default-vs-rival %+.2f%%" % (rows[-1][0], a, b, c, 100 * (a / c - 1)))
n = len(rows)
if n:
    md = sum(r[1] for r in rows) / n; mf = sum(r[2] for r in rows) / n; mr = sum(r[3] for r in rows) / n
    lose = sum(1 for r in rows if r[1] > r[3])
    print("SETS=%d mean default=%.4f free=%.4f rival=%.4f ; rival beats our default on %d/%d sets" % (n, md, mf, mr, lose, n))
