"""Validate the dataset suite: baseline and v5 (strategies.st_config) on every dataset, both price modes.
  NPROC=3 python tools/datasets/eval_suite.py [names,comma,separated] [ctrl=baseline,v5]
Prints one line per run and a table; flags trips and EV < 100 %."""
import os, sys, time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))


def run(job):
    import twin, strategies
    from loader import load_dataset
    name, ctrl, mode = job
    d = load_dataset(name)
    strategies._DATA = d
    t = time.time()
    c = strategies.baseline() if ctrl == "baseline" else strategies.dp_strategy(**strategies.st_config(mode))
    r = twin.simulate(c, mode, data=d)
    return name, ctrl, mode, r["cost_total"], r["cost_peak"], r["ev_pct"], r["tripped"], time.time() - t


if __name__ == "__main__":
    from loader import list_datasets
    names = sys.argv[1].split(",") if len(sys.argv) > 1 and sys.argv[1] else ["practice"] + list_datasets()
    ctrls = sys.argv[2].split(",") if len(sys.argv) > 2 else ["baseline", "v5"]
    jobs = [(n, c, m) for c in ctrls for n in names for m in (0, 1)]
    res = {}
    with Pool(int(os.environ.get("NPROC", "3"))) as p:
        for (n, c, m, cost, pk, ev, tr, dt) in p.imap_unordered(run, jobs):
            flag = (" TRIP %s" % (tr,) if tr else "") + (" EV<100" if ev < 99.9999 else "")
            print("  %-15s %-8s m%d cost=%10.0f peak=%7.0f ev=%.3f %4.0fs%s" % (n, c, m, cost, pk, ev, dt, flag), flush=True)
            res[(n, c, m)] = (cost, pk, tr)
    print("\nTABLE  dataset | " + " | ".join("%s S%d" % (c, m + 1) for c in ctrls for m in (0, 1)))
    for n in names:
        cells = []
        for c in ctrls:
            for m in (0, 1):
                cost, pk, tr = res[(n, c, m)]
                cells.append("TRIP" if tr else "%.0f" % cost)
        print("  %-15s | %s" % (n, " | ".join(cells)))
