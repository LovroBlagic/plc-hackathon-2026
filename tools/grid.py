"""Robust evaluation: python tools/grid.py '<json {label: kwargs}>' [variants=0,1,2,3] [modes=0,1]
Prints per-run lines and a summary with mean cost per config and mode over the dataset variants."""
import sys, json, os
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run(job):
    import twin, strategies
    label, kw, mode, vid = job
    kw = dict(kw)
    d = twin.variant(vid)
    strategies._DATA = d
    fn = kw.pop("_fn", "dp_strategy")
    r = twin.simulate(getattr(strategies, fn)(**kw), mode, data=d)
    return label, mode, vid, r["cost_total"], r["cost_peak"], r["ev_pct"], r["tripped"]

if __name__ == "__main__":
    cfg = json.loads(sys.argv[1])
    vids = [int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else "0,1,2,3").split(",")]
    modes = [int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else "0,1").split(",")]
    jobs = [(l, kw, m, v) for l, kw in cfg.items() for m in modes for v in vids]
    res = {}
    with Pool(min(len(jobs), int(os.environ.get("NPROC", "15")))) as p:
        for (l, m, v, c, pk, ev, tr) in p.imap_unordered(run, jobs):
            print("  %-24s m%d v%d cost=%10.0f peak=%7.0f ev=%.3f trip=%s" % (l, m, v, c, pk, ev, tr), flush=True)
            res.setdefault((l, m), []).append(c if tr is None else 1e9)
    print("SUMMARY (mean over variants %s)" % vids)
    for l in cfg:
        row = ["%-24s" % l]
        for m in modes:
            xs = res.get((l, m), [])
            row.append("m%d=%10.0f" % (m, sum(xs) / len(xs)))
        print("  " + "  ".join(row))
