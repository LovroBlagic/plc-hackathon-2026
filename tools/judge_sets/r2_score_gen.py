"""r2_score_gen.py - adversarial dataset families for the SCORE judge (round 2).
Writes tools/judge_sets/r2_score_<name>.json (same format as tools/crane_data).

  python tools/judge_sets/r2_score_gen.py [--seed 7]

Families:
  sm_*      small N (3..13) random, solvable EXACTLY by r2_score_opt.exact (true optimum)
  bal_*     small N, ship starts at |L-R| = 5 and lists push it further -> side choice binding
  corner_*  all sources in one corner, free target cells in the opposite corner
  far_*     ship nearly full, free cells only far from the yard (x=3) / far rows
  zig_*     list order alternates far rows y=0 / y=11 (adversarial for per-list order)
  uneq_*    very unequal list lengths (1 vs 30+)
  big_*     N 80..94 nearly full swaps
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import crane_model as cm  # noqa: E402

CELLS = [(x, y) for x in range(4) for y in range(12)]
LEFT = [c for c in CELLS if c[0] <= 1]
RIGHT = [c for c in CELLS if c[0] >= 2]


def blank():
    return [[0] * 12 for _ in range(4)]


def pad(lst):
    return list(lst) + [0] * (48 - len(lst))


def build(rng, name, ship_cells, yard_cells, u_cells, l_cells, shuffle=True, note=""):
    ids = rng.sample(range(100, 1000), len(ship_cells) + len(yard_cells))
    b0, b1 = blank(), blank()
    sid, yid = {}, {}
    for (x, y) in ship_cells:
        b0[x][y] = sid[(x, y)] = ids.pop()
    for (x, y) in yard_cells:
        b1[x][y] = yid[(x, y)] = ids.pop()
    u = [sid[c] for c in u_cells]
    l = [yid[c] for c in l_cells]
    if shuffle:
        rng.shuffle(u)
        rng.shuffle(l)
    L, R = cm.lr(b0)
    if abs(L - R) > 5:
        return None
    if len(ship_cells) - len(u) + len(l) > 48 or len(yard_cells) - len(l) + len(u) > 48:
        return None
    return {"name": "r2_score_" + name, "bay0": b0, "bay1": b1, "unload": pad(u), "load": pad(l), "note": note}


def ship_with(rng, nL, nR, Lpool=None, Rpool=None):
    Lpool = LEFT if Lpool is None else Lpool
    Rpool = RIGHT if Rpool is None else Rpool
    return rng.sample(Lpool, nL) + rng.sample(Rpool, nR)


def fam_small(rng, i):
    for _ in range(200):
        ns = rng.randint(8, 46)
        nL = rng.randint(max(0, ns - 24), min(24, ns))
        if abs(nL - (ns - nL)) > 5:
            continue
        ship = ship_with(rng, nL, ns - nL)
        ny = rng.randint(4, 46)
        yard = rng.sample(CELLS, ny)
        nu = rng.randint(0, 7)
        nl = rng.randint(0, 7)
        if nu + nl < 3 or nu > ns or nl > ny:
            continue
        d = build(rng, "sm_%02d" % i, ship, yard, rng.sample(ship, nu), rng.sample(yard, nl),
                  note="small random nu=%d nl=%d" % (nu, nl))
        if d:
            return d


def fam_bal(rng, i):
    # ship L = R + 5 ; unloads mostly from R (pushing imbalance), loads must go L/R carefully
    for _ in range(200):
        nR = rng.randint(6, 19)
        nL = nR + 5
        ship = ship_with(rng, nL, nR)
        ny = rng.randint(10, 40)
        yard = rng.sample(CELLS, ny)
        shipR = [c for c in ship if c[0] >= 2]
        shipL = [c for c in ship if c[0] <= 1]
        nu = rng.randint(2, 6)
        nuR = rng.randint(nu // 2, nu)
        us = rng.sample(shipR, min(nuR, len(shipR))) + rng.sample(shipL, nu - min(nuR, len(shipR)))
        nl = rng.randint(2, 7)
        ls = rng.sample(yard, nl)
        d = build(rng, "bal_%02d" % i, ship, yard, us, ls, note="ship L=R+5, unloads from R")
        if d:
            return d


def fam_corner(rng, i):
    # sources: ship rows 9..11 x=2,3 ; yard rows 9..11 x=0..1 ; free cells: ship rows 0..3 x=0,1, yard rows 0..2
    shipL = [c for c in LEFT if c[1] >= 4]
    shipR = [c for c in RIGHT if c[1] >= 2]
    nL = rng.randint(14, len(shipL))
    nR = rng.randint(max(0, nL - 5), min(len(shipR), nL + 5))
    ship = rng.sample(shipL, nL) + rng.sample(shipR, nR)
    yard = [c for c in CELLS if c[1] >= 3]
    yard = rng.sample(yard, rng.randint(20, len(yard)))
    usrc = [c for c in ship if c[0] >= 2 and c[1] >= 9]
    lsrc = [c for c in yard if c[0] <= 1 and c[1] >= 9]
    nu = min(len(usrc), rng.randint(2, 6))
    nl = min(len(lsrc), rng.randint(2, 6))
    return build(rng, "corner_%02d" % i, ship, yard, rng.sample(usrc, nu), rng.sample(lsrc, nl),
                 note="sources in one corner, free cells far away")


def fam_far(rng, i):
    # ship almost full; free cells only in x=3 high rows (far from the yard)
    free = [(3, y) for y in range(12 - rng.randint(4, 8), 12)] + [(2, 11)]
    ship = [c for c in CELLS if c not in free]
    L, R = sum(1 for c in ship if c[0] <= 1), sum(1 for c in ship if c[0] >= 2)
    # drop some left containers to keep |L-R|<=5
    lefts = [c for c in ship if c[0] <= 1]
    rng.shuffle(lefts)
    while L - R > 5:
        ship.remove(lefts.pop())
        L -= 1
    yard = rng.sample(CELLS, rng.randint(15, 40))
    nl = rng.randint(2, 5)
    nu = rng.randint(0, 4)
    us = rng.sample([c for c in ship if c[0] <= 1], nu)
    ls = rng.sample(yard, nl)
    return build(rng, "far_%02d" % i, ship, yard, us, ls, note="ship near full, free cells far (x=3)")


def fam_zig(rng, i):
    ns = rng.randint(24, 40)
    nL = ns // 2
    ship = ship_with(rng, nL, ns - nL)
    yard = rng.sample(CELLS, rng.randint(16, 36))
    u0 = [c for c in ship if c[1] <= 1]
    u1 = [c for c in ship if c[1] >= 10]
    l0 = [c for c in yard if c[1] <= 1]
    l1 = [c for c in yard if c[1] >= 10]
    k = min(len(u0), len(u1), 3)
    us = []
    for a, b in zip(rng.sample(u0, k), rng.sample(u1, k)):
        us += [a, b]
    kl = min(len(l0), len(l1), 3)
    ls = []
    for a, b in zip(rng.sample(l1, kl), rng.sample(l0, kl)):
        ls += [a, b]
    return build(rng, "zig_%02d" % i, ship, yard, us, ls, shuffle=False, note="zigzag rows in list order")


def fam_uneq(rng, i):
    if i % 2 == 0:
        ship = ship_with(rng, 20, 20)
        yard = rng.sample(CELLS, 6)
        us = rng.sample(ship, 34)
        ls = rng.sample(yard, 1)
        note = "34 U / 1 L"
    else:
        ship = ship_with(rng, 5, 5)
        yard = rng.sample(CELLS, 44)
        us = rng.sample(ship, 1)
        ls = rng.sample(yard, 34)
        note = "1 U / 34 L"
    return build(rng, "uneq_%02d" % i, ship, yard, us, ls, note=note)


def fam_big(rng, i):
    nfree_s = rng.randint(1, 6)
    nfree_y = rng.randint(0, 6)
    ship = rng.sample(CELLS, 48 - nfree_s)
    while abs(sum(1 for c in ship if c[0] <= 1) - sum(1 for c in ship if c[0] >= 2)) > 5:
        ship = rng.sample(CELLS, 48 - nfree_s)
    yard = rng.sample(CELLS, 48 - nfree_y)
    nu = rng.randint(35, len(ship))
    nl = rng.randint(35, len(yard))
    if len(ship) - nu + nl > 48:
        nl = 48 - len(ship) + nu
    if len(yard) - nl + nu > 48:
        nu = 48 - len(yard) + nl
    return build(rng, "big_%02d" % i, ship, yard, rng.sample(ship, nu), rng.sample(yard, nl),
                 note="near-full swap N=%d" % (nu + nl))


FAMS = [("sm", fam_small, 30), ("bal", fam_bal, 16), ("corner", fam_corner, 8), ("far", fam_far, 8),
        ("zig", fam_zig, 6), ("uneq", fam_uneq, 4), ("big", fam_big, 4)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    n = 0
    for nm, f, cnt in FAMS:
        for i in range(cnt):
            d = None
            for _ in range(50):
                d = f(rng, i)
                if d:
                    break
            if not d:
                print("skip", nm, i)
                continue
            with open(os.path.join(HERE, d["name"] + ".json"), "w") as fh:
                json.dump(d, fh)
            n += 1
    print("wrote", n)


if __name__ == "__main__":
    main()
