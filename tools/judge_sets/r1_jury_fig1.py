"""r1_jury_fig1.py - jury check on datasets shaped like spec Figure 1 (p.2).
Writes r1_jury_fig1_*.json and prints J for: PLC default (order 1 + fallback), free order (0),
strict (2), naive (crane_eval.naive), lower bound; mmode 2 (FB1) and 0 (spec rule).
  python tools/judge_sets/r1_jury_fig1.py
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import crane_model as cm, crane_plan as cp, crane_eval as ce

def grid():
    return [[0]*12 for _ in range(4)]

def mk(name, bay0, bay1, unload, load, note):
    ds = {"name": name, "bay0": bay0, "bay1": bay1,
          "unload": unload + [0]*(48-len(unload)), "load": load + [0]*(48-len(load)), "note": note}
    p = os.path.join(HERE, "r1_jury_%s.json" % name)
    json.dump(ds, open(p, "w"), separators=(",", ":"))
    return p

# Figure 1 as read from the spec drawing: yard (Bay1) red, ship (Bay0) cyan.
b1 = grid()
for x, i in enumerate([104, 105, 106, 107]): b1[x][0] = i
b1[1][5] = 145; b1[2][6] = 126; b1[0][7] = 127
for x, i in enumerate([101, 142, 123, 144]): b1[x][11] = i
b0 = grid()
rows = {3: (160, 164), 4: (162, 163), 5: (165, 192), 6: (167, 168), 7: (180, 169), 8: (171, 170)}
for y, (a, b) in rows.items(): b0[1][y] = a; b0[2][y] = b
ship = [b0[x][y] for y in range(12) for x in range(4) if b0[x][y]]
yard = [b1[x][y] for y in range(12) for x in range(4) if b1[x][y]]
paths = []
paths.append(mk("fig1_full_swap", b0, b1, sorted(ship), sorted(yard),
                "Fig.1: unload all 12 cyan, load all 11 red, lists in ID order"))
paths.append(mk("fig1_half", b0, b1, sorted(ship)[:6], sorted(yard)[:6],
                "Fig.1: unload 6 lowest IDs, load 6 lowest IDs"))
paths.append(mk("fig1_unload_only", b0, b1, sorted(ship), [],
                "Fig.1: unload all, no load"))
paths.append(mk("fig1_reverse_lists", b0, b1, sorted(ship, reverse=True), sorted(yard, reverse=True),
                "Fig.1: full swap, lists in descending ID order"))

def run(path, mmode):
    ds = cm.load_dataset(path)
    st = cp.build_state(ds, 5)
    out = {}
    for lab, order in (("default_o1", 1), ("free_o0", 0), ("strict_o2", 2)):
        cfg = {"mmode": mmode, "order": order, "balmode": 0, "lim": 5}
        r = cp.plan_fb(st, cfg, [0, 100, 200, 300], imp_evals=3000)
        if r["err"] == 0:
            cp.simulate(st, r["plan"], r["cfg"])
            out[lab] = "%.4f (o%d)" % (r["J"], r.get("order", r["cfg"]["order"]))
        else:
            out[lab] = "err%d" % r["err"]
    nv = ce.naive(st, {"mmode": mmode, "lim": 5})
    out["naive"] = ("%.4f" % cm.J(nv[0], nv[1], st["N"])) if nv else "infeasible"
    out["LB"] = "%.4f" % cp.lower_bound(st)[2]
    return out

for p in paths:
    for mm in (2, 0):
        print(os.path.basename(p), "mmode", mm, run(p, mm))
