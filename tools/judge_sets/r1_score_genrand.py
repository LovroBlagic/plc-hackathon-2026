"""r1_score_genrand.py - fresh random sets from the team's own generator (crane_gen.random_set),
new seed, so the order-1 gap statistic is not measured on the sets the planner was tuned on.
  python tools/judge_sets/r1_score_genrand.py [--n 24] [--seed 4242]
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import crane_gen as cg  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=24)
ap.add_argument("--seed", type=int, default=4242)
a = ap.parse_args()
rng = random.Random(a.seed)
for i in range(1, a.n + 1):
    d = cg.random_set(rng, "r1_score_rnd_%02d" % i)
    with open(os.path.join(HERE, "r1_score_rnd_%02d.json" % i), "w") as f:
        json.dump(d, f)
print("ok")
