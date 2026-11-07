"""r3 jury: on ships that START unbalanced, what does the v1.5 relaxed rule (World.BalCeil, R2-J1) do to the
balance trace, compared with the step rule in free order (the v1.4 fallback)?
Metrics per plan (|L-R| after every lift/put on the ship):
  up>5  = number of lift/put steps that INCREASE |L-R| while the result is > 5 (deliberately worsening an
          already unbalanced ship; the step rule forbids this)
  ops>5 = number of lift/put steps after which |L-R| > 5
  first = index of the first step after which |L-R| <= 5
  python tools/judge_sets/r3_jury_relaxed_trace.py [glob ...]"""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import crane_model as cm, crane_plan as cp

ALPHAS = [0, 100, 200, 300]

def trace(state, plan):
    g = [[c[:] for c in state["bay0"]], [c[:] for c in state["bay1"]]]
    L, R = cm.lr(g[0]); d = [abs(L - R)]
    for tr in plan:
        sx, sy, sb = tr["src"]; dx, dy, db = tr["dst"]
        v = g[sb][sx][sy]; g[sb][sx][sy] = 0
        L, R = cm.lr(g[0]); d.append(abs(L - R))
        g[db][dx][dy] = v
        L, R = cm.lr(g[0]); d.append(abs(L - R))
    up = sum(1 for a, b in zip(d, d[1:]) if b > a and b > 5)
    ops = sum(1 for b in d[1:] if b > 5)
    first = next((i for i, b in enumerate(d) if b <= 5), None)
    return up, ops, first, max(d), d[-1]

pats = sys.argv[1:] or ["tools/judge_sets/*.json", "tools/crane_data/*.json", "tools/crane_data_stress/*.json"]
files = sorted(set(f for p in pats for f in glob.glob(p)))
rows = []
for f in files:
    try:
        ds = cm.load_dataset(f)
    except Exception:
        continue
    L0, R0 = cm.lr(ds["bay0"])
    if abs(L0 - R0) <= 5:
        continue
    st = cp.build_state(ds)
    if st["init"]["blocking"]:
        continue
    cfg = {"mmode": 2, "order": 1, "balmode": 0, "lim": 5, "exact": True}
    r1 = cp.plan_fb(st, cfg, ALPHAS, imp_evals=3000)
    if r1["err"] != 0 or not r1["cfg"].get("ceil"):
        continue                       # only the sets where the relaxed rule is what the PLC runs
    r0 = cp.plan_fb(st, dict(cfg, order=0), ALPHAS, imp_evals=3000)
    t1 = trace(st, r1["plan"]); t0 = trace(st, r0["plan"]) if r0["err"] == 0 else None
    rows.append((os.path.basename(f), abs(L0 - R0), r1["J"], t1, r0["J"] if t0 else None, t0))
    print("%-44s d0=%2d | relaxed o1 J=%.4f up>5=%2d ops>5=%2d first=%s max=%d end=%d | free o0 J=%s up>5=%s ops>5=%s first=%s end=%s" % (
        os.path.basename(f), abs(L0 - R0), r1["J"], t1[0], t1[1], t1[2], t1[3], t1[4],
        "%.4f" % r0["J"] if t0 else "-", t0[0] if t0 else "-", t0[1] if t0 else "-", t0[2] if t0 else "-", t0[4] if t0 else "-"))
print("RELAXED_SETS", len(rows), " with up>5:", sum(1 for r in rows if r[3][0] > 0),
      " total up>5 steps:", sum(r[3][0] for r in rows),
      " ops>5 relaxed:", sum(r[3][1] for r in rows), " ops>5 free:", sum(r[5][1] for r in rows if r[5]))
