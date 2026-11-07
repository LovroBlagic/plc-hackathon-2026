"""r2_jury_imbalance.py - judge round 2 (jury): datasets whose ship starts out of balance (|L-R| > 5).

Elimination criterion 1 says the unload/load must be done "tako da ne dođe do neuravnoteženosti".
When the given data starts unbalanced, the team's step rule only forbids making it WORSE, so the plan
may keep the ship unbalanced for many transfers. This script measures, per dataset and order mode:
  unbal_steps  = number of lift/put commands after which |L-R| > 5 (incl. the start state counted once)
  first_ok     = transfer index after which |L-R| <= 5 for the first time (-1 never)
  min_first_ok = lower bound: ceil((|L0-R0| - 5) / 1) ship-side events needed, each lift/put changes
                 |L-R| by at most 1 -> at least that many ship-side lift/puts, counted in transfers
                 (every transfer has exactly one ship-side event).
  J            = plan J (FB1 M rule)
  python tools/judge_sets/r2_jury_imbalance.py [glob ...]
"""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import crane_model as cm, crane_plan as cp

ALPHAS = [0, 100, 200, 300]


def trace(st, plan):
    g = [[c[:] for c in st["bay0"]], [c[:] for c in st["bay1"]]]
    L, R = cm.lr(g[0])
    d0 = abs(L - R)
    unbal = 0
    first_ok = 0 if d0 <= 5 else -1
    worst = d0
    for i, tr in enumerate(plan, 1):
        sx, sy, sb = tr["src"]; dx, dy, db = tr["dst"]
        cid = g[sb][sx][sy]; g[sb][sx][sy] = 0
        L, R = cm.lr(g[0])
        if abs(L - R) > 5:
            unbal += 1
        g[db][dx][dy] = cid
        L, R = cm.lr(g[0])
        if abs(L - R) > 5:
            unbal += 1
        elif first_ok < 0:
            first_ok = i
        worst = max(worst, abs(L - R))
    return d0, unbal, first_ok, worst, abs(L - R)


def main():
    pats = sys.argv[1:] or [os.path.join(HERE, "r2_jury_imb_*.json"),
                            os.path.join(HERE, "..", "crane_data", "edge_initial_imbalance.json")]
    files = sorted(set(f for p in pats for f in glob.glob(p)))
    print("%-34s %5s %3s | %-7s %5s %6s %6s %6s %7s" % ("set", "N", "d0", "order", "unbal", "1st_ok", "min", "d_end", "J"))
    for f in files:
        ds = json.load(open(f))
        st = cp.build_state(ds)
        L0, R0 = cm.lr(st["bay0"])
        d0 = abs(L0 - R0)
        mn = max(0, d0 - 5)
        for order in (1, 0):
            res = cp.plan_fb(st, {"mmode": 2, "order": order, "balmode": 0, "lim": 5}, ALPHAS, imp_evals=3000)
            if res["err"]:
                print("%-34s err=%d" % (os.path.basename(f)[:34], res["err"]))
                continue
            d0, unbal, fo, worst, dend = trace(st, res["plan"])
            print("%-34s %5d %3d | %d(used%d) %5d %6d %6d %6d %7.4f" % (
                os.path.basename(f)[:34], len(res["plan"]), d0, order, res["order"], unbal, fo, mn, dend, res["J"]))


if __name__ == "__main__":
    main()
