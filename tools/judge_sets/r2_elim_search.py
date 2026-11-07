"""r2_elim_search.py - judge round 2 (elimination): adversarial dataset families that the team's
generators (crane_gen.random_set / stress_one) do NOT produce, checked against an exact DP.

Families: imbal (|L-R| 6..12 at start), obst (invalid-ID obstacles in both bays), holes (zeros, invalid,
duplicate, missing IDs interleaved in the lists), yardfull (yard 46..48), oneside (all unloads from one
half, ship at |L-R| = 5), full48 (both lists 48 long / near-full bays), cranemid (replan from a random
crane position and a random mid-run state, as after MANUAL moves).

Checks per set (PLC default: order 1 + fallback, bal 0, mmode 2):
  F  planner error although the exact free-order DP finds a plan          (false bit 8)
  O  order fallback although the exact order-1 DP finds a plan            (needless list-order break)
  B/L/S  crane_stress.check_plan (CheckCmd replay, balance trace, list membership + order)
  R  replans from 3 mid-run states (same checks)

  python tools/judge_sets/r2_elim_search.py [--n 800] [--seed 9] [--evals 200]
"""
import json
import os
import random
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import crane_model as cm      # noqa: E402
import crane_plan as cp       # noqa: E402
import crane_gen as cg        # noqa: E402
import crane_stress as cs     # noqa: E402
import r1_feas as rf          # noqa: E402

AL = [0, 100, 200, 300]
FAMS = ("imbal", "obst", "holes", "yardfull", "oneside", "full48", "cranemid")
EVALS = 200
CELLS = cg.CELLS
LEFT = [c for c in CELLS if c[0] <= 1]
RIGHT = [c for c in CELLS if c[0] >= 2]


def put(g, cells, ids):
    for (x, y) in cells:
        g[x][y] = ids.pop()


def occ(g):
    return [g[x][y] for x in range(4) for y in range(12) if g[x][y] != 0]


def make(rng, fam, name):
    ids = rng.sample(range(100, 1000), 200)
    b0, b1 = cg.blank(), cg.blank()
    if fam == "imbal":
        d0 = rng.randint(6, 12) * rng.choice((-1, 1))
        n = rng.randint(max(abs(d0), 10), 40)
        if (n + d0) % 2:
            n += 1
        L = (n + d0) // 2
        R = n - L
        if not (0 <= L <= 24 and 0 <= R <= 24):
            raise ValueError
        put(b0, rng.sample(LEFT, L) + rng.sample(RIGHT, R), ids)
        put(b1, rng.sample(CELLS, rng.randint(5, 40)), ids)
    elif fam == "obst":
        n0 = rng.randint(16, 40)
        Ls = rng.randint(max(0, n0 - 24), min(24, n0))
        if abs(2 * Ls - n0) > 5:
            Ls = n0 // 2
        put(b0, rng.sample(LEFT, Ls) + rng.sample(RIGHT, n0 - Ls), ids)
        put(b1, rng.sample(CELLS, rng.randint(10, 40)), ids)
        for g in (b0, b1):
            for _ in range(rng.randint(1, 4)):
                x, y = rng.choice([c for c in CELLS if g[c[0]][c[1]] != 0])
                g[x][y] = rng.choice((1, 42, 99, 1000, 4711, 65535))
    elif fam in ("holes", "yardfull", "oneside", "full48", "cranemid"):
        if fam == "yardfull":
            d = cg.random_set(rng, name, ship=rng.randint(20, 46), yard=rng.randint(46, 48),
                              nu=rng.randint(10, 40), nl=rng.randint(0, 20))
        elif fam == "full48":
            d = cg.random_set(rng, name, ship=48, yard=rng.randint(46, 47), nu=48, nl=rng.randint(46, 47))
        elif fam == "oneside":
            n0 = rng.randint(20, 43)
            Ls = (n0 + 5) // 2 if rng.random() < 0.5 else (n0 - 5 + 1) // 2
            Ls = max(0, min(24, Ls))
            if abs(2 * Ls - n0) > 5 or n0 - Ls > 24:
                raise ValueError
            put(b0, rng.sample(LEFT, Ls) + rng.sample(RIGHT, n0 - Ls), ids)
            put(b1, rng.sample(CELLS, rng.randint(10, 44)), ids)
            side = 0 if Ls * 2 > n0 else 1     # unload from the heavy side first, then the light side
            heavy = [b0[x][y] for (x, y) in (LEFT if side == 0 else RIGHT) if b0[x][y]]
            light = [b0[x][y] for (x, y) in (RIGHT if side == 0 else LEFT) if b0[x][y]]
            rng.shuffle(heavy)
            rng.shuffle(light)
            un = light[:rng.randint(3, len(light))] + heavy[:rng.randint(0, len(heavy))]
            if rng.random() < 0.5:
                un = list(reversed(un))
            yard_ids = occ(b1)
            cap = 48 - n0 + len(un)
            ld = rng.sample(yard_ids, rng.randint(0, min(len(yard_ids), cap, 30)))
            if 48 - len(yard_ids) + len(ld) < len(un) - 0:
                raise ValueError
            return cg.ds_dict(name, b0, b1, un[:48], ld[:48])
        else:
            d = cg.random_set(rng, name)
        if fam == "holes":
            un = [c for c in d["unload"] if c]
            ld = [c for c in d["load"] if c]
            junk = [0, 0, 7, 1000, rng.randint(100, 999)]
            for lst in (un, ld):
                for _ in range(rng.randint(1, 4)):
                    if len(lst) < 48:
                        lst.insert(rng.randint(0, len(lst)), rng.choice(junk + (lst[:1] if lst else [])))
            d = cg.ds_dict(name, d["bay0"], d["bay1"], un[:48], ld[:48])
        d["name"] = name
        return d
    nu = rng.randint(0, len(occ(b0)))
    un = rng.sample([v for v in occ(b0) if cm.valid_id(v)], min(nu, len([v for v in occ(b0) if cm.valid_id(v)])))
    yv = [v for v in occ(b1) if cm.valid_id(v)]
    ld = rng.sample(yv, rng.randint(0, len(yv)))
    return cg.ds_dict(name, b0, b1, un[:48], ld[:48])


def gen(i, seed):
    rng = random.Random(seed * 1000003 + i)
    fam = FAMS[i % len(FAMS)]
    for _ in range(300):
        try:
            return fam, make(rng, fam, "r2_%s_%d_%04d" % (fam, seed, i))
        except (ValueError, RuntimeError, IndexError):
            continue
    return fam, None


def random_mid(rng, st, res):
    """cranemid: start a replan from a random point of the plan with the crane parked anywhere."""
    n = len(res["plan"])
    if n < 2:
        return None
    k = rng.randint(1, n - 1)
    ms = cs.mid_state(st, res["plan"], k)
    ms["crane"] = (rng.randint(0, 3), rng.randint(0, 11), rng.randint(0, 1))
    return ms


def one(args):
    i, seed = args
    fam, ds = gen(i, seed)
    if ds is None:
        return None
    st = cp.build_state(ds)
    if st["init"]["blocking"]:
        return {"fam": fam, "blocked": True}
    cfg = {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}
    f1 = rf.feasible(ds, st, 1)
    f0 = rf.feasible(ds, st, 0)
    res = cp.plan_fb(st, cfg, AL, imp_evals=EVALS)
    issues = []
    if res["err"] != 0 and f0:
        issues.append("F false infeasible err=%d (free order exact-feasible)" % res["err"])
    if res["err"] == 0:
        if res["order"] != 1 and f1:
            issues.append("O needless fallback to order %d" % res["order"])
        issues += cs.check_plan(st, res, "init")
        rng = random.Random(i)
        n = len(res["plan"])
        mids = [cs.mid_state(st, res["plan"], k) for k in sorted({n // 4, n // 2, (3 * n) // 4}) if 1 <= k < n]
        if fam == "cranemid":
            m = random_mid(rng, st, res)
            if m:
                mids.append(m)
        for ms in mids:
            r3 = cp.plan_fb(ms, cfg, AL, imp_evals=EVALS)
            if r3["err"] != 0:
                # a mid state of a valid plan is always completable in the mode that plan used
                issues.append("R replan failed err=%d" % r3["err"])
                continue
            if r3["order"] != 1 and cp.order_feasible(ms, 1, 5):
                issues.append("R needless fallback in replan")
            issues += ["R " + e for e in cs.check_plan(ms, r3, "mid")]
    return {"fam": fam, "issues": issues, "ds": ds if issues else None, "err": res["err"], "f0": f0, "f1": f1,
            "used": res.get("order")}


def main():
    a = sys.argv[1:]
    n = int(a[a.index("--n") + 1]) if "--n" in a else 700
    seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 9
    global EVALS
    EVALS = int(a[a.index("--evals") + 1]) if "--evals" in a else 200
    with Pool() as p:
        rs = [r for r in p.map(one, [(i, seed) for i in range(n)], chunksize=4) if r]
    by = {}
    for r in rs:
        s = by.setdefault(r["fam"], {"sets": 0, "blocked": 0, "infeas_exact": 0, "fallback_forced": 0, "issues": 0})
        s["sets"] += 1
        if r.get("blocked"):
            s["blocked"] += 1
            continue
        s["infeas_exact"] += 0 if r["f0"] else 1
        s["fallback_forced"] += 1 if (r["err"] == 0 and r["used"] == 0) else 0
        s["issues"] += 1 if r["issues"] else 0
    for k, v in sorted(by.items()):
        print("%-9s %s" % (k, v))
    bad = [r for r in rs if r.get("issues")]
    for r in bad[:10]:
        print("ISSUE", r["ds"]["name"], r["issues"][:3])
    for r in bad[:3]:
        p = os.path.join(HERE, "r2_elimination_%s.json" % r["ds"]["name"])
        with open(p, "w", encoding="utf-8") as f:
            json.dump(r["ds"], f)
        print("saved", p)
    print("R2_SEARCH_RESULT sets=%d issues=%d" % (len(rs), len(bad)))


if __name__ == "__main__":
    main()
