"""r2_jury_imb_order.py - judge round 2 (jury): on a ship that STARTS unbalanced (|L0-R0| = d0 > 5),
is per-list order (CfgOrderMode 1) feasible under a relaxed but defensible balance rule?

Team rule (step rule): a lift/put may never increase |L-R| while it is > 5. On an unbalanced start this
can make list order "provably infeasible", and FB10 then falls back to FREE order (breaking elimination
criterion 2 "u skladu sa zadanom listom") to avoid e.g. a 9 -> 10 step on a ship that started at 10.

Relaxed rule R: |L-R| never exceeds max(5, d0) (never worse than the given data), and |L-R| <= 5 at the end
whenever the team plan also reaches that. Exact DP over (i unloads done, j loads done, L).

  python tools/judge_sets/r2_jury_imb_order.py [--random 400] [--seed 9]
"""
import json, os, random, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import crane_model as cm, crane_plan as cp

ALPHAS = [0, 100, 200, 300]


def relaxed_feasible(st, order, cap, end_lim):
    loc = cp.locate([st["bay0"], st["bay1"]], st["PU"], st["PL"])
    if loc is None:
        return False
    PU, PL = loc
    nu, nl = len(PU), len(PL)
    S0, Y0 = cp.cnt(st["bay0"]), cp.cnt(st["bay1"])
    usL = [1 if s.pos[0] <= 1 else 0 for s in PU]
    FT = [[0] * (nl + 1) for _ in range(nu + 1)]
    for i in range(nu, -1, -1):
        for j in range(nl, -1, -1):
            tot = S0 - i + j
            m = 0
            for L in range(25):
                R = tot - L
                if R < 0 or R > 24:
                    continue
                if i == nu and j == nl:
                    if abs(L - R) <= end_lim:
                        m |= 1 << L
                    continue
                ok = False
                if i < nu and Y0 + i - j < 48:
                    L2, R2 = (L - 1, R) if usL[i] else (L, R - 1)
                    if L2 >= 0 and R2 >= 0 and abs(L2 - R2) <= cap and (FT[i + 1][j] >> L2) & 1:
                        ok = True
                if not ok and j < nl and (order == 1 or i == nu):
                    for side in (0, 1):
                        L2, R2 = (L + 1, R) if side == 0 else (L, R + 1)
                        if L2 <= 24 and R2 <= 24 and abs(L2 - R2) <= cap and (FT[i][j + 1] >> L2) & 1:
                            ok = True
                            break
                if ok:
                    m |= 1 << L
            FT[i][j] = m
    L0, _ = cm.lr(st["bay0"])
    return bool((FT[0][0] >> L0) & 1)


def end_d(st, plan):
    g = [[c[:] for c in st["bay0"]], [c[:] for c in st["bay1"]]]
    for tr in plan:
        sx, sy, sb = tr["src"]; dx, dy, db = tr["dst"]
        g[db][dx][dy] = g[sb][sx][sy]; g[sb][sx][sy] = 0
    L, R = cm.lr(g[0])
    return abs(L - R)


def inversions(plan):
    inv = 0
    for kind in (1, 2):
        idx = [tr["list_idx"] for tr in plan if tr["kind"] == kind]
        inv += sum(1 for a in range(len(idx)) for b in range(a + 1, len(idx)) if idx[a] > idx[b])
    return inv


def gen(rng, name):
    """Unbalanced start: ship L-heavy by 7..12, random yard, random lists (random list order)."""
    d = rng.randint(7, 12)
    R = rng.randint(4, 24 - d)
    L = R + d
    yard = rng.randint(6, 30)
    ids = iter(rng.sample(range(100, 1000), 200))
    bay0 = [[0] * 12 for _ in range(4)]; bay1 = [[0] * 12 for _ in range(4)]
    lc = [(x, y) for x in (0, 1) for y in range(12)]; rc = [(x, y) for x in (2, 3) for y in range(12)]
    yc = [(x, y) for x in range(4) for y in range(12)]
    rng.shuffle(lc); rng.shuffle(rc); rng.shuffle(yc)
    for x, y in lc[:L]: bay0[x][y] = next(ids)
    for x, y in rc[:R]: bay0[x][y] = next(ids)
    for x, y in yc[:yard]: bay1[x][y] = next(ids)
    ship = [bay0[x][y] for x in range(4) for y in range(12) if bay0[x][y]]
    nu = rng.randint(2, min(16, len(ship)))
    nl = rng.randint(2, min(16, yard))
    ul = rng.sample(ship, nu)
    ll = rng.sample([bay1[x][y] for x, y in yc[:yard]], nl)
    if len(ship) - nu + nl > 48 or yard - nl + nu > 48:
        return None
    pad = lambda a: a + [0] * (48 - len(a))
    return {"name": name, "bay0": bay0, "bay1": bay1, "unload": pad(ul), "load": pad(ll),
            "note": "judge r2 jury: unbalanced start L=%d R=%d, %d unloads, %d loads" % (L, R, nu, nl)}


def main():
    a = sys.argv[1:]
    n = int(a[a.index("--random") + 1]) if "--random" in a else 300
    seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 9
    save = "--save" in a
    rng = random.Random(seed)
    files = sorted(glob.glob(os.path.join(HERE, "r2_jury_imb_*.json")))
    sets = [json.load(open(f)) for f in files]
    k = 0
    while len(sets) < len(files) + n:
        ds = gen(rng, "r2_jury_imbrand_%03d" % k); k += 1
        if ds:
            sets.append(ds)
    tot = fb = fb_relaxed_ok = 0
    hits = []
    for ds in sets:
        st = cp.build_state(ds)
        if st["init"]["blocking"]:
            continue
        L0, R0 = cm.lr(st["bay0"])
        d0 = abs(L0 - R0)
        res = cp.plan_fb(st, {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}, ALPHAS, imp_evals=0)
        if res["err"]:
            continue
        tot += 1
        de = end_d(st, res["plan"])
        if res["order"] == 0:
            fb += 1
            ok = relaxed_feasible(st, 1, max(5, d0), 5 if de <= 5 else 99)
            if ok:
                fb_relaxed_ok += 1
                hits.append((ds["name"], d0, de, inversions(res["plan"]), len(res["plan"])))
                if save and len(hits) <= 3 and ds["name"].startswith("r2_jury_imbrand"):
                    ds = dict(ds, note=ds["note"] + "; order1 provably feasible never exceeding d0; PLC falls back to free order")
                    json.dump(ds, open(os.path.join(HERE, ds["name"] + ".json"), "w"))
    print("unbalanced-start sets planned=%d  order-1 fallback to FREE order=%d  of which in-order plan exists "
          "never exceeding the initial |L-R| (and ending balanced when ours does)=%d" % (tot, fb, fb_relaxed_ok))
    for h in hits[:12]:
        print("  %-26s d0=%2d d_end=%d inversions=%d transfers=%d" % h)


if __name__ == "__main__":
    main()


def relaxed_feasible_sticky(st, order, cap, end_lim):
    """Like relaxed_feasible, plus: once |L-R| <= 5 has been reached it must stay <= 5 (no re-imbalance).
    Exhaustive DFS with memo over (i, j, L, reached)."""
    loc = cp.locate([st["bay0"], st["bay1"]], st["PU"], st["PL"])
    if loc is None:
        return False
    PU, PL = loc
    nu, nl = len(PU), len(PL)
    S0, Y0 = cp.cnt(st["bay0"]), cp.cnt(st["bay1"])
    usL = [1 if s.pos[0] <= 1 else 0 for s in PU]
    memo = {}

    def ok_state(L2, R2, reached):
        d = abs(L2 - R2)
        return d <= (5 if reached else cap)

    def f(i, j, L, reached):
        key = (i, j, L, reached)
        if key in memo:
            return memo[key]
        tot = S0 - i + j
        R = tot - L
        if i == nu and j == nl:
            r = abs(L - R) <= end_lim
            memo[key] = r
            return r
        r = False
        if i < nu and Y0 + i - j < 48:
            L2, R2 = (L - 1, R) if usL[i] else (L, R - 1)
            if L2 >= 0 and R2 >= 0 and ok_state(L2, R2, reached):
                r = f(i + 1, j, L2, reached or abs(L2 - R2) <= 5)
        if not r and j < nl and (order == 1 or i == nu):
            for L2, R2 in ((L + 1, R), (L, R + 1)):
                if L2 <= 24 and R2 <= 24 and ok_state(L2, R2, reached) and f(i, j + 1, L2, reached or abs(L2 - R2) <= 5):
                    r = True
                    break
        memo[key] = r
        return r

    L0, R0 = cm.lr(st["bay0"])
    return f(0, 0, L0, abs(L0 - R0) <= 5)


def main2():
    files = sorted(glob.glob(os.path.join(HERE, "r2_jury_imb*.json")))
    for fpath in files:
        ds = json.load(open(fpath))
        st = cp.build_state(ds)
        L0, R0 = cm.lr(st["bay0"])
        d0 = abs(L0 - R0)
        res = cp.plan_fb(st, {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}, ALPHAS, imp_evals=0)
        print("%-24s d0=%2d used_order=%s  relaxed=%s  relaxed+sticky=%s" % (
            ds["name"], d0, res.get("order"), relaxed_feasible(st, 1, max(5, d0), 5),
            relaxed_feasible_sticky(st, 1, max(5, d0), 5)))


if __name__ == "__main__" and "--sticky" in sys.argv:
    main2()
