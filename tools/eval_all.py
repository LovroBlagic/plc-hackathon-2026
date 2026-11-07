"""Evaluate v5 and every controller candidate on ALL accepted datasets, both price modes (twin).

  NPROC=12 python tools/eval_all.py            # run missing jobs, then write CSV + report
  python tools/eval_all.py --report             # only rebuild CSV + report from the run cache
  python tools/eval_all.py --only lh_s2,combo_s2  # restrict the controllers that are run

Run cache (resumable, one JSON per finished run): tools/eval_runs.jsonl
Outputs: tools/eval_results.csv (candidate, dataset, kind, mode, cost, peak_cost, tripped, ev_pct)
         work/TWIN_LEADERBOARD.md

Controllers (CTRL below):
  v5          strategies.dp_strategy(**strategies.st_config(mode))                    = ME_v5_k075
  longhorizon candidates.longhorizon.make(**config(mode))    S1 = v5 by construction (Hc=0)
  capmodel    candidates.capmodel.make(**config(mode))       S1 = v5 by construction (floor off)
  lprules     candidates.lprules.make(mode, **S?_KW)         S1 late_eps=0.005, S2 = v5 by construction
  lprules_e05 lprules with late_eps=0.05 (the value noted in strategies.st_config for the ST port)
  combo_s2    longhorizon S2 + capmodel S2 floor (floor injected through obs['mpeak'], see FloorWrap)
  capwrap_s2  v5 S2 + capmodel S2 floor via FloorWrap (fidelity check of the wrapper vs capmodel)
  combo_s1    lprules S1 (late_eps=0.005) + capmodel optional S1 floor (max R_d over 14 d) via FloorWrap
  combo_s1e05 lprules S1 (late_eps=0.05)  + capmodel optional S1 floor
A mode marked "same" for a controller is bit-identical to v5 by construction; the v5 run is reused and a
practice-data check run (dataset 'practice') is executed to confirm the identity.
WINNER (per mode): no trip, EV 100 % everywhere, strictly cheaper than v5 on every practice/variant/
synthetic/real dataset, stress datasets no trip and not worse than v5 by > 0.5 %, reviewer verdict pass/fixed.
"""
import json, os, sys, time
from multiprocessing import Pool

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "datasets"))

CACHE = os.path.join(TOOLS, "eval_runs.jsonl")
CSV = os.path.join(TOOLS, "eval_results.csv")
REPORT = os.path.join(ROOT, "work", "TWIN_LEADERBOARD.md")

ACCEPTED = ["syn_rot1", "syn_rot2", "syn_boot1", "syn_boot3", "syn_noise8", "syn_shift", "syn_cloudy",
            "real_pvgis2010", "real_pvgis2012", "real_pvgis2017", "real_pvgis2018", "real_pvgis2019",
            "real_pvgis2020", "real_pvgis2021", "real_pvgis2022", "syn_boot2", "syn_peaky", "syn_highload",
            "syn_mixed", "stress_load105", "stress_pv85", "stress_combo", "real_jplev", "real_ind9_pv2019",
            "real_ind13_pv2021_jpl"]
DATASETS = ["practice"] + ["variant%d" % i for i in range(1, 6)] + ACCEPTED
REJECTED = ["syn_sunny", "real_jplev_hiturn", "real_ind1_pv2010_jplhi", "real_ind7_pv2022"]

V5KW = {0: dict(realistic=True, cw=4, dE=40.0, hmax=96, coldmax=True, nacts=41, ksig=0.75, hi_in_dp=True, pvf=0.6),
        1: dict(realistic=True, cw=4, dE=40.0, hmax=96, coldmax=True, nacts=41, ksig=0.0, hi_in_dp=False, pvf=0.2)}

# capmodel floor settings (candidates/capmodel.py config(1) / config_s1floor(0))
FLOOR_S2 = dict(src="prevrd", f=0.95, nm=3, c=1.2, n=14, delay=14)
FLOOR_S1 = dict(src="rd", f=1.0, q=1.0, n=14, delay=14)

# name -> dict(modes={mode: "run"|"same"}, review=verdict, ops=per-step estimate, desc)
CTRL = {
    "v5":          dict(modes={0: "run", 1: "run"}, review="baseline", ops=33500,
                        desc="strategies.dp_strategy(**strategies.st_config(mode))"),
    "longhorizon": dict(modes={0: "same", 1: "run"}, review="fixed (fix round; S1 = v5)", ops=39504,
                        desc="candidates.longhorizon.make(**longhorizon.config(mode))"),
    "capmodel":    dict(modes={0: "same", 1: "run"}, review="fixed (fix round; S1 = v5)", ops=28000,
                        desc="candidates.capmodel.make(**capmodel.config(mode))"),
    "lprules":     dict(modes={0: "run", 1: "same"}, review="pass", ops=27100,
                        desc="candidates.lprules.make(mode, late_eps=0.005 if mode == 0 else 0.0)"),
    "lprules_e05": dict(modes={0: "run", 1: "same"}, review="pass (eps variant suggested by reviewer)", ops=27100,
                        desc="candidates.lprules.make(mode, late_eps=0.05 if mode == 0 else 0.0)"),
    "combo_s2":    dict(modes={0: "same", 1: "run"}, review="combination of fixed candidates (not reviewed)",
                        ops=40000, desc="FloorWrap(longhorizon.make(**config(1)), FLOOR_S2)"),
    "capwrap_s2":  dict(modes={1: "run"}, review="wrapper fidelity check", ops=28000,
                        desc="FloorWrap(dp_strategy(**st_config(1)), FLOOR_S2)"),
    "combo_s1":    dict(modes={0: "run", 1: "same"}, review="combination incl. capmodel S1 floor, which failed review rule",
                        ops=28100, desc="FloorWrap(lprules.make(0, late_eps=0.005), FLOOR_S1)"),
    "combo_s1e05": dict(modes={0: "run", 1: "same"}, review="combination incl. capmodel S1 floor, which failed review rule",
                        ops=28100, desc="FloorWrap(lprules.make(0, late_eps=0.05), FLOOR_S1)"),
}
CHECK_DS = ["practice"]           # datasets on which "same" modes are actually run as an identity check
WRAP_DS = ["practice", "variant2", "syn_peaky", "real_pvgis2010", "real_ind13_pv2021_jpl"]   # capwrap_s2 only


class FloorWrap:
    """capmodel's learned monthly cap floor, applied around ANY v5-style controller by raising the
    observed monthly peak: obs['mpeak'] := max(mpeak, floor).  The inner controller sets its cap
    T := max(T, mpeak) and bisects from there, so T >= floor (capmodel: T := max(T_v5, floor)).
    R_d = lowest cap holding a realised day (FEC - PV + own EV command) from a full battery; the new
    R_d becomes usable at qh >= delay (ST: bisection spread over the first 14 steps of the day).
    Only own measurements, own commands and own realised monthly peaks are used."""

    def __init__(self, inner, src="prevrd", f=0.95, nm=3, c=1.2, n=14, q=1.0, delay=14):
        import numpy as np
        from candidates.capmodel import _req_full
        self.np, self.req = np, _req_full
        self.inner, self.src, self.f, self.nm, self.c, self.n, self.q, self.delay = inner, src, f, nm, c, n, q, delay
        self.base = np.zeros(96); self.ev = np.zeros(96); self.day = -1
        self.Rd, self.pend, self.prevpk = [], [], []
        self.month, self.T, self.evlast = 0, 0.0, 0.0

    def __call__(self, o):
        np = self.np
        t = o["t"]; k = o["k"]; q = t["qh"]; day = t["day"]
        if k > 0:
            self.ev[(k - 1) % 96] = self.evlast
        if day != self.day:
            if self.day >= 0:
                self.pend.append(self.req(self.base + self.ev))
            self.day = day; self.base[:] = 0.0; self.ev[:] = 0.0
        if self.pend and q >= self.delay:
            self.Rd.extend(self.pend); self.pend.clear()
            del self.Rd[:-max(28, self.n)]
        self.base[q] = o["fec"] - o["fne"]
        if t["month"] != self.month:
            if self.month > 0:
                self.prevpk.append(self.T)
            self.month = t["month"]; self.T = 0.0
        self.T = max(self.T, o["mpeak"])
        fl = 0.0
        if len(self.Rd) >= 5:
            if self.src == "rd":
                fl = min(1000.0, self.f * float(np.quantile(self.Rd[-self.n:], self.q)))
            elif self.src == "prevrd" and self.prevpk:
                pp = self.prevpk[-self.nm:]
                fl = min(1000.0, self.f * sum(pp) / len(pp), self.c * max(self.Rd[-self.n:]))
        if fl > o["mpeak"]:
            o = dict(o); o["mpeak"] = fl
        out = self.inner(o)
        self.evlast = sum(out["ev"])
        return out


def build(name, mode):
    import strategies
    if name == "v5" or CTRL[name]["modes"].get(mode) == "same":
        return strategies.dp_strategy(**strategies.st_config(mode))
    if name == "longhorizon":
        from candidates import longhorizon as L
        return L.make(**L.config(mode))
    if name == "capmodel":
        from candidates import capmodel as C
        return C.make(**C.config(mode))
    if name in ("lprules", "lprules_e05"):
        from candidates import lprules as R
        return R.make(mode, late_eps=(0.005 if name == "lprules" else 0.05) if mode == 0 else 0.0)
    if name == "combo_s2":
        from candidates import longhorizon as L
        return FloorWrap(L.make(**L.config(1)), **FLOOR_S2)
    if name == "capwrap_s2":
        return FloorWrap(strategies.dp_strategy(**strategies.st_config(1)), **FLOOR_S2)
    if name in ("combo_s1", "combo_s1e05"):
        from candidates import lprules as R
        return FloorWrap(R.make(0, late_eps=0.005 if name == "combo_s1" else 0.05), **FLOOR_S1)
    raise KeyError(name)


def kind_of(ds):
    if ds == "practice":
        return "practice"
    if ds.startswith("variant"):
        return "variant"
    from loader import meta
    return meta(ds).get("kind", "synthetic")


def run(job):
    import twin, strategies
    from loader import load_dataset
    name, ds, mode = job
    d = load_dataset(ds)
    strategies._DATA = d
    t0 = time.time()
    ctrl = build(name, mode)
    r = twin.simulate(ctrl, mode, data=d)
    tr = r["tripped"]
    return dict(ctrl=name, ds=ds, mode=mode, cost=r["cost_total"], peak=r["cost_peak"], ev=r["ev_pct"],
                tripped=bool(tr), trip=list(tr) if tr else None, mpeak=r["mpeak"], secs=time.time() - t0)


def load_cache():
    res = {}
    if os.path.isfile(CACHE):
        with open(CACHE) as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    res[(r["ctrl"], r["ds"], r["mode"])] = r
    return res


def jobs_needed(cache, only=None):
    jobs = []
    for name, cfg in CTRL.items():
        if only and name not in only:
            continue
        for mode, how in cfg["modes"].items():
            dss = WRAP_DS if name == "capwrap_s2" else (DATASETS if how == "run" else CHECK_DS)
            for ds in dss:
                if (name, ds, mode) not in cache:
                    jobs.append((name, ds, mode))
    slow = {"longhorizon": 0, "combo_s2": 0}
    jobs.sort(key=lambda j: (j[0] not in slow, j[2] == 0))
    return jobs


def result(cache, name, ds, mode):
    """Run result for a controller, falling back to v5 for modes that are identical by construction."""
    r = cache.get((name, ds, mode))
    if r is None and CTRL[name]["modes"].get(mode) == "same":
        r = cache.get(("v5", ds, mode))
    return r


def evaluate(cache):
    """Per controller and mode: stats + winner check.  Returns dict."""
    kinds = {ds: kind_of(ds) for ds in DATASETS}
    out = {}
    for name, cfg in CTRL.items():
        for mode in (0, 1):
            if mode not in cfg["modes"]:
                continue
            dss = WRAP_DS if name == "capwrap_s2" else DATASETS
            rows = []
            for ds in dss:
                r = result(cache, name, ds, mode); b = cache.get(("v5", ds, mode))
                if r is None or b is None:
                    continue
                rows.append((ds, kinds[ds], r, b))
            if not rows:
                continue
            complete = len(rows) == len(dss)
            deltas = [(ds, kd, r["cost"] - b["cost"], 100.0 * (r["cost"] - b["cost"]) / b["cost"]) for ds, kd, r, b in rows]
            trips = sum(1 for _, _, r, _ in rows if r["tripped"])
            min_ev = min(r["ev"] for _, _, r, _ in rows)
            fails = []
            for (ds, kd, r, b), (_, _, dd, dp) in zip(rows, deltas):
                if r["tripped"]:
                    fails.append("%s trip" % ds)
                elif r["ev"] < 99.9999:
                    fails.append("%s EV %.3f %%" % (ds, r["ev"]))
                elif kd == "stress":
                    if dp > 0.5:
                        fails.append("%s +%.2f %%" % (ds, dp))
                elif dd >= 0 and cfg["modes"].get(mode) != "same":
                    fails.append("%s %+.0f" % (ds, dd))
            same = cfg["modes"].get(mode) == "same"
            ident_ok = None
            if same:
                ident_ok = all(abs(cache[(name, ds, mode)]["cost"] - cache[("v5", ds, mode)]["cost"]) < 1e-6
                               for ds in CHECK_DS if (name, ds, mode) in cache and ("v5", ds, mode) in cache)
            out[(name, mode)] = dict(
                n=len(rows), complete=complete, same=same, ident_ok=ident_ok,
                mean=sum(r["cost"] for _, _, r, _ in rows) / len(rows),
                mean_v5=sum(b["cost"] for _, _, _, b in rows) / len(rows),
                mean_d=sum(d for _, _, d, _ in deltas) / len(deltas),
                mean_d_nonstress=(lambda xs: sum(xs) / len(xs) if xs else 0.0)([d for _, kd, d, _ in deltas if kd != "stress"]),
                worst=max(deltas, key=lambda x: x[2]), best=min(deltas, key=lambda x: x[2]),
                nbetter=sum(1 for _, _, d, _ in deltas if d < 0), trips=trips, min_ev=min_ev,
                deltas=deltas, fails=fails,
                passes=(not same) and complete and not fails and name != "v5" and name != "capwrap_s2",
                rule200=all(d <= 200 for _, kd, d, dp in deltas if kd != "stress") and
                all(dp <= 0.5 for _, kd, d, dp in deltas if kd == "stress"))
    return out


def write_csv(cache):
    with open(CSV, "w") as f:
        f.write("candidate,dataset,kind,mode,cost,peak_cost,tripped,ev_pct,source\n")
        for name, cfg in CTRL.items():
            for mode in (0, 1):
                if mode not in cfg["modes"]:
                    continue
                for ds in (WRAP_DS if name == "capwrap_s2" else DATASETS):
                    r = result(cache, name, ds, mode)
                    if r is None:
                        continue
                    src = "run" if (name, ds, mode) in cache else "v5 (identical by construction)"
                    f.write("%s,%s,%s,%d,%.2f,%.2f,%d,%.4f,%s\n" % (name, ds, kind_of(ds), mode, r["cost"], r["peak"],
                                                                 int(r["tripped"]), r["ev"], src))


def write_report(cache, ev):
    L = []
    L.append("# Twin leaderboard (all accepted datasets)\n")
    L.append("Generated by `tools/eval_all.py` on %s. Twin runs only (tools/twin.py); the twin matches real ME within "
             "about 200 EUR in S1 and 7 EUR in S2. Raw runs: `tools/eval_runs.jsonl`, table: `tools/eval_results.csv`.\n"
             % time.strftime("%Y-%m-%d %H:%M"))
    L.append("Datasets (%d): practice, variant1..5 (week/day rotations of practice), and the %d accepted suite sets. "
             "Rejected and not used: %s.\n" % (len(DATASETS), len(ACCEPTED), ", ".join(REJECTED)))
    L.append("WINNER rule per mode: no trip, EV 100 %, strictly cheaper than v5 on every practice/variant/synthetic/real "
             "dataset, stress sets no trip and at most 0.5 % worse, reviewer verdict pass or fixed. "
             "\"=v5\" means the mode is identical to v5 by construction (v5 runs reused, identity checked on practice).\n")
    L.append("## Summary\n")
    L.append("| Controller | Mode | Datasets | Mean cost | Mean vs v5 | Better on | Worst delta | Best delta | Trips | Min EV % | Winner rule | <=200 EUR rule | Review | ops/step |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for name, cfg in CTRL.items():
        for mode in (0, 1):
            s = ev.get((name, mode))
            if not s:
                continue
            if s["same"]:
                win = "=v5" + ("" if s["ident_ok"] else " (identity check FAILED)" if s["ident_ok"] is False else "")
            elif name == "v5":
                win = "baseline"
            else:
                win = ("PASS" if s["passes"] else "fail") + ("" if s["complete"] else " (incomplete)")
            L.append("| %s | S%d | %d | %.0f | %+.0f | %d/%d | %s %+.0f | %s %+.0f | %d | %.2f | %s | %s | %s | %s |" % (
                name, mode + 1, s["n"], s["mean"], s["mean_d"], s["nbetter"], s["n"], s["worst"][0], s["worst"][2],
                s["best"][0], s["best"][2], s["trips"], s["min_ev"], win, "yes" if s["rule200"] else "no",
                cfg["review"], cfg["ops"]))
    L.append("")
    L.append("## Winners (strict rule) and user rule (mean better, no dataset > +200 EUR)\n")
    for mode in (0, 1):
        w = [n for n in CTRL if (n, mode) in ev and ev[(n, mode)]["passes"] and "not reviewed" not in CTRL[n]["review"]
             and "failed review" not in CTRL[n]["review"]]
        u = [n for n in CTRL if (n, mode) in ev and not ev[(n, mode)]["same"] and n not in ("v5", "capwrap_s2")
             and ev[(n, mode)]["complete"] and ev[(n, mode)]["rule200"] and ev[(n, mode)]["mean_d"] < 0 and ev[(n, mode)]["trips"] == 0
             and ev[(n, mode)]["min_ev"] >= 99.9999]
        w.sort(key=lambda n: ev[(n, mode)]["mean_d"]); u.sort(key=lambda n: ev[(n, mode)]["mean_d"])
        L.append("- **S%d strict winners**: %s" % (mode + 1, ", ".join("%s (mean %+.0f)" % (n, ev[(n, mode)]["mean_d"]) for n in w) or "none"))
        L.append("- **S%d user-rule qualifiers**: %s" % (mode + 1, ", ".join("%s (mean %+.0f, worst %+.0f)" % (
            n, ev[(n, mode)]["mean_d"], ev[(n, mode)]["worst"][2]) for n in u) or "none"))
    L.append("")
    L.append("## Failures of the winner rule\n")
    for name, cfg in CTRL.items():
        for mode in (0, 1):
            s = ev.get((name, mode))
            if s and not s["same"] and name != "v5":
                L.append("- **%s S%d**: %s" % (name, mode + 1, ", ".join(s["fails"]) if s["fails"] else "none"))
    L.append("")
    L.append("## Delta vs v5 per dataset (EUR, negative = cheaper)\n")
    cols = [(n, m) for n, cfg in CTRL.items() for m in (0, 1) if (n, m) in ev and n != "v5" and not ev[(n, m)]["same"]]
    L.append("| Dataset | Kind | v5 S1 | v5 S2 | " + " | ".join("%s S%d" % (n, m + 1) for n, m in cols) + " |")
    L.append("|---|---|---|---|" + "---|" * len(cols))
    for ds in DATASETS:
        b0 = cache.get(("v5", ds, 0)); b1 = cache.get(("v5", ds, 1))
        cells = []
        for n, m in cols:
            r = result(cache, n, ds, m); b = cache.get(("v5", ds, m))
            if r is None or b is None:
                cells.append("")
            elif r["tripped"]:
                cells.append("TRIP")
            else:
                cells.append("%+.0f" % (r["cost"] - b["cost"]) + ("" if r["ev"] >= 99.9999 else " EV!"))
        L.append("| %s | %s | %s | %s | %s |" % (ds, kind_of(ds), "%.0f" % b0["cost"] if b0 else "", "%.0f" % b1["cost"] if b1 else "",
                                             " | ".join(cells)))
    L.append("")
    L.append("## Controller definitions\n")
    for name, cfg in CTRL.items():
        L.append("- **%s**: `%s`; modes: %s" % (name, cfg["desc"], ", ".join("S%d %s" % (m + 1, h) for m, h in cfg["modes"].items())))
    L.append("- FLOOR_S2 = `%s`; FLOOR_S1 = `%s` (FloorWrap in tools/eval_all.py)" % (FLOOR_S2, FLOOR_S1))
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def main():
    args = sys.argv[1:]
    only = None
    if "--only" in args:
        only = set(args[args.index("--only") + 1].split(","))
    cache = load_cache()
    if "--report" not in args:
        jobs = jobs_needed(cache, only)
        print("%d jobs to run, NPROC=%s" % (len(jobs), os.environ.get("NPROC", "12")), flush=True)
        if jobs:
            with Pool(int(os.environ.get("NPROC", "12"))) as p, open(CACHE, "a") as f:
                for r in p.imap_unordered(run, jobs):
                    f.write(json.dumps(r) + "\n"); f.flush()
                    cache[(r["ctrl"], r["ds"], r["mode"])] = r
                    print("  %-12s %-22s S%d cost=%10.1f peak=%8.1f ev=%.3f %s %4.0fs" % (
                        r["ctrl"], r["ds"], r["mode"] + 1, r["cost"], r["peak"], r["ev"],
                        "TRIP" if r["tripped"] else "", r["secs"]), flush=True)
    write_csv(cache)
    ev = evaluate(cache)
    write_report(cache, ev)
    print("wrote", CSV, "and", REPORT)


if __name__ == "__main__":
    main()
