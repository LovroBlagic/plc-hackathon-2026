import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
def run(a):
    import lp_bound
    m, v = a
    r = lp_bound.solve(m, v, verbose=False)
    return m, v, r["cost"], r["peak"], r["simult"]
if __name__ == "__main__":
    jobs = [(m, v) for m in (0, 1) for v in (0, 1, 2, 3)]
    with Pool(4) as p:
        res = p.map(run, jobs)
    for m in (0, 1):
        xs = [r for r in res if r[0] == m]
        for r in xs: print("LP m%d v%d cost=%.0f peak=%.0f simult=%d" % r)
        print("LP m%d mean=%.0f" % (m, sum(r[2] for r in xs) / len(xs)))
