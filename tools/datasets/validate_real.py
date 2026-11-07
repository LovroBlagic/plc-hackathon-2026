"""Validate datasets (default: all kind=='real'): format/feasibility checks + twin runs of the baseline and the
v5 controller (strategies.st_config(mode)) in both price modes. Uses at most NPROC (default 3) processes.
Usage: python tools/datasets/validate_real.py [name,name,...]     -> prints table, writes real_validation.json"""
import json, os, sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
N = 35040
EV_PMAX = 22.0 * 0.9 * 0.25


def check(name):
    from loader import load_dataset
    d = load_dataset(name)
    errs = []
    if len(d["fne"]) != N or len(d["fec"]) != N:
        errs.append("length")
    if min(d["fne"]) < 0 or max(d["fne"]) > 750:
        errs.append("fne range")
    if max(d["fec"]) > 1000:
        errs.append("fec > 1000")
    tot = 0.0
    for j, ch in enumerate(d["ev"]):
        last = 0
        for (a, dp, e) in ch:
            tot += e
            if not (0 <= a < dp <= N):
                errs.append("ch%d bad window %s" % (j, (a, dp)))
            if a < last:
                errs.append("ch%d overlap at %d" % (j, a))
            if e > EV_PMAX * (dp - a) + 1e-9:
                errs.append("ch%d infeasible %s" % (j, (a, dp, e)))
            last = dp
    return dict(errors=errs[:5], n_err=len(errs), ev_MWh=round(tot / 1000, 3),
                fec_max=round(max(d["fec"]), 1), fne_MWh=round(sum(d["fne"]) * 0.25 / 1000, 1))


def run(job):
    import twin, strategies
    from loader import load_dataset
    name, ctl, mode = job
    d = load_dataset(name)
    strategies._DATA = d
    c = strategies.baseline() if ctl == "base" else strategies.dp_strategy(**strategies.st_config(mode))
    r = twin.simulate(c, mode, data=d)
    return name, ctl, mode, round(r["cost_total"], 1), round(r["cost_peak"], 1), r["ev_pct"], r["tripped"]


if __name__ == "__main__":
    from loader import list_datasets
    names = sys.argv[1].split(",") if len(sys.argv) > 1 else list_datasets("real")
    out = {n: dict(check=check(n)) for n in names}
    for n in names:
        print("%-26s %s" % (n, out[n]["check"]), flush=True)
    jobs = [(n, c, m) for n in names for m in (0, 1) for c in ("base", "v5")]
    with Pool(int(os.environ.get("NPROC", "3"))) as p:
        for (n, c, m, cost, peak, ev, tr) in p.imap_unordered(run, jobs):
            out[n]["%s_m%d" % (c, m)] = dict(cost=cost, peak=peak, ev_pct=ev, tripped=tr)
            print("  %-26s %-4s m%d cost=%10.0f peak=%7.0f ev=%.3f trip=%s" % (n, c, m, cost, peak, ev, tr), flush=True)
    path = os.path.join(HERE, "real_validation.json")
    old = {}
    if os.path.exists(path):
        with open(path) as f:
            old = json.load(f)
    old.update(out)
    with open(path, "w") as f:
        json.dump(old, f, indent=1)
    print("SUMMARY (cost EUR: base_m0 v5_m0 | base_m1 v5_m1 | trips)")
    for n in names:
        o = out[n]
        tr = [k for k in o if k != "check" and o[k]["tripped"]]
        print("  %-26s %9.0f %9.0f | %9.0f %9.0f | %s" % (n, o["base_m0"]["cost"], o["v5_m0"]["cost"],
                                                      o["base_m1"]["cost"], o["v5_m1"]["cost"], tr or "none"))
