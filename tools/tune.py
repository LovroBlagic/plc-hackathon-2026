"""Parallel twin runs: python tools/tune.py '<json list of [label, kwargs, mode]>'"""
import sys, json, os
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run(job):
    import twin, strategies
    label, kw, mode = job
    r = twin.simulate(strategies.dp_strategy(**kw), mode)
    return "%-28s m%d %s peaks=%s" % (label, mode, twin.fmt(r), [round(x) for x in r["mpeak"]])

if __name__ == "__main__":
    jobs = json.loads(open(sys.argv[1]).read()) if os.path.exists(sys.argv[1]) else json.loads(sys.argv[1])
    with Pool(min(len(jobs), int(sys.argv[2]) if len(sys.argv) > 2 else 6)) as p:
        for line in p.imap(run, jobs):
            print(line, flush=True)
