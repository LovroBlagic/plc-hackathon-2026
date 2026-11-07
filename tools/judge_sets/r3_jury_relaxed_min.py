"""r3 jury: under per-list order (CfgOrderMode 1) and the team's own relaxed rule (step_ok with ceil=d0),
what is the MINIMUM number of imbalance-worsening ship operations (|L-R| increases while > 5) and the
minimum number of ship operations left at |L-R| > 5?  Exact DP over (i unloads, j loads, L); load side free.
Compares with the plan FB10/FB11 actually run (crane_plan.plan_fb, 3000 evals)."""
import glob, os, sys
from functools import lru_cache
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import crane_model as cm, crane_plan as cp
sys.path.insert(0, HERE)
from r3_jury_relaxed_trace import trace, ALPHAS

def dp_min(st, ceil, key):
    loc = cp.locate([st["bay0"], st["bay1"]], st["PU"], st["PL"])
    PU, PL = loc
    nu, nl = len(PU), len(PL)
    S0, Y0 = cp.cnt(st["bay0"]), cp.cnt(st["bay1"])
    usL = [s.pos[0] <= 1 for s in PU]
    L0, R0 = cm.lr(st["bay0"])
    INF = 10 ** 9
    def c(d, d2):
        if key == "up":
            return 1 if (d2 > d and d2 > 5) else 0
        return 1 if d2 > 5 else 0
    @lru_cache(None)
    def f(i, j, L):
        R = S0 - i + j - L
        if i == nu and j == nl:
            return 0 if abs(L - R) <= 5 else INF
        best = INF
        d = abs(L - R)
        if i < nu and Y0 + i - j < 48:
            L2, R2 = (L - 1, R) if usL[i] else (L, R - 1)
            d2 = abs(L2 - R2)
            if L2 >= 0 and R2 >= 0 and cm.step_ok(L, R, L2, R2, 5, ceil):
                best = min(best, c(d, d2) + f(i + 1, j, L2))
        if j < nl:
            for side in (0, 1):
                L2, R2 = (L + 1, R) if side == 0 else (L, R + 1)
                d2 = abs(L2 - R2)
                if L2 <= 24 and R2 <= 24 and cm.step_ok(L, R, L2, R2, 5, ceil):
                    best = min(best, c(d, d2) + f(i, j + 1, L2 if side == 0 else L))
        return best
    return f(0, 0, L0)

files = sys.argv[1:] or sorted(glob.glob("tools/judge_sets/*.json") + glob.glob("tools/crane_data/*.json"))
for fn in files:
    try:
        ds = cm.load_dataset(fn)
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
        continue
    t = trace(st, r1["plan"])
    d0 = abs(L0 - R0)
    print("%-36s d0=%2d  PLC plan: up>5=%d ops>5=%d   min possible in list order: up>5=%d ops>5=%d" % (
        os.path.basename(fn), d0, t[0], t[1], dp_min(st, d0, "up"), dp_min(st, d0, "ops")))
