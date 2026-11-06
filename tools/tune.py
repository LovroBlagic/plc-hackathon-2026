"""Parallel twin runs: python tools/tune.py '<json list of [label, kwargs, mode]>'"""
import sys, json, os
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run(job):
    import twin, strategies
    label, kw, mode = job[:3]
    vid = job[3] if len(job) > 3 else 0
    d = twin.variant(vid)
    import strategies as S
    S._DATA = d
    fn = kw.pop("_fn", "dp_strategy")
    r = twin.simulate(getattr(strategies, fn)(**kw), mode, data=d)
    return "%-22s v%d m%d %s peaks=%s" % (label, vid, mode, twin.fmt(r), [round(x) for x in r["mpeak"]])

if __name__ == "__main__":
    jobs = json.loads(open(sys.argv[1]).read()) if os.path.exists(sys.argv[1]) else json.loads(sys.argv[1])
    with Pool(min(len(jobs), int(sys.argv[2]) if len(sys.argv) > 2 else 6)) as p:
        for line in p.imap(run, jobs):
            print(line, flush=True)
