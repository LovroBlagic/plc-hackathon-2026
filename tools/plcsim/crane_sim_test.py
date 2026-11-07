"""crane_sim_test.py - run a crane dataset on the PLCSIM instance (via SimHost.exe) and compare with the Python model.

  python tools/plcsim/crane_sim_test.py <dataset.json> [--port 50123] [--timeout 900] [--out <dir>] [--noload]

Steps: SwOn -> write DB10/DB11/DB20/DB21 (all 192 values) -> POCETNO STANJE -> wait READY -> AUTO -> START
-> sample every 100 ms until DONE (State 6) or ALARM/timeout. Every OB30 tick (HMI_IF.OB30Ticks change) logs
the crane position, M (MD107), T (MD112), BalL/BalR, Carried. Commands are reconstructed from FB1's position
and M/T changes and compared with crane_plan.commands() of the model plan (same default config as the PLC).
Prints SIM_RESULT pass=0/1 and writes <out>/<name>.ticks.csv + <name>.result.json.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, TOOLS)
from simclient import Sim  # noqa: E402
import crane_model as cm  # noqa: E402
import crane_plan as cp  # noqa: E402

B0 = "Current_state_of_Bay0.Bay0[%d,%d]"
B1 = "Current_state_of_Bay1.Bay1[%d,%d]"
UL = "From_Bay0_to_Bay1.IDs_of_the_containers[%d]"
LL = "From_Bay1_to_Bay0.Bay1_IDs_of_the_containers[%d]"
TICK = ["HMI_IF.OB30Ticks", "HMI_IF.State", "x_position", "y_position", "bay_ID", "number_of_manipulations", "time",
        "HMI_IF.BalL", "HMI_IF.BalR", "HMI_IF.Carried", "HMI_IF.AlarmWord", "HMI_IF.TrDone", "HMI_IF.TrTotal",
        "HMI_IF.CurCmd", "HMI_IF.CurId", "HMI_IF.MSpec", "HMI_IF.Planning",
        "Crane_Control_DB.Planner.DiagMaxCallMs", "Crane_Control_DB.Planner.DiagJobMs", "Crane_Control_DB.Planner.DiagCalls"]
STATE_NAMES = {0: "OFF", 1: "INIT", 2: "READY", 3: "RUNNING", 4: "PAUSED", 5: "ALARM", 6: "DONE", 7: "PLANNING"}


def model(path):
    a = cp.parse_args([path])
    ds = cm.load_dataset(path)
    cfg = {"mmode": a.mmode, "order": a.order, "balmode": a.balmode, "lim": a.lim, "exact": True}
    alphas = [int(v) for v in a.alpha.split(",")]
    st = cp.build_state(ds, a.lim)
    if st["init"]["blocking"]:
        return {"err": "blocking", "commands": [], "T_ds": 0, "M": 0}
    res = cp.plan_fb(st, cfg, alphas, None, a.algo, imp_evals=a.improve, imp_dist=a.dist, slot_sweeps=a.slot)
    if res["err"] != 0:
        return {"err": res["err"], "commands": [], "T_ds": 0, "M": 0}
    out = cp.simulate(st, res["plan"], res["cfg"])
    g = [[list(c) for c in ds["bay0"]], [list(c) for c in ds["bay1"]]]
    for tr in res["plan"]:
        sx, sy, sb = tr["src"]
        dx, dy, db = tr["dst"]
        g[db][dx][dy] = g[sb][sx][sy]
        g[sb][sx][sy] = 0
    fb0 = cm.FB1(0)
    fb0.x, fb0.y, fb0.bay = st["crane"]
    for o in out:
        fb0.command(o["cmd"], o["x"], o["y"], o["bay"])
    mspec = fb0.M
    N = sum(1 for v in ds["unload"] if v) + sum(1 for v in ds["load"] if v)
    return {"err": 0, "commands": [(o["cmd"], o["x"], o["y"], o["bay"]) for o in out],
            "T_ds": out[-1]["t_ds"] if out else 0, "M": out[-1]["m"] if out else 0, "MSpec": mspec, "J": res["J"],
            "order_used": res["cfg"]["order"], "plan": [(tr["id"], tuple(tr["src"]), tuple(tr["dst"])) for tr in res["plan"]], "bay0": g[0], "bay1": g[1], "N": N, "transfers": len(res["plan"])}


def wait_for(s, cond, timeout, period=0.2):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = cond()
        if v:
            return v
        time.sleep(period)
    return None


def load_data(s, ds):
    pairs = []
    for x in range(4):
        for y in range(12):
            pairs.append((B0 % (x, y), ds["bay0"][x][y]))
            pairs.append((B1 % (x, y), ds["bay1"][x][y]))
    for i in range(48):
        pairs.append((UL % (i + 1), ds["unload"][i]))
        pairs.append((LL % (i + 1), ds["load"][i]))
    s.wb(pairs)


def read_bays(s):
    names = [B0 % (x, y) for x in range(4) for y in range(12)] + [B1 % (x, y) for x in range(4) for y in range(12)]
    v = [int(z) for z in s.rb(names)]
    b0 = [v[x * 12:(x + 1) * 12] for x in range(4)]
    b1 = [v[48 + x * 12:48 + (x + 1) * 12] for x in range(4)]
    return b0, b1


def press(s, btn):
    s.w("HMI_IF." + btn, 1)


def state(s):
    return int(s.r("HMI_IF.State"))


def run(path, port=50123, timeout=900, outdir=None, noload=False):
    name = os.path.splitext(os.path.basename(path))[0]
    outdir = outdir or os.path.join(HERE, "results")
    os.makedirs(outdir, exist_ok=True)
    ds = cm.load_dataset(path)
    mod = model(path)
    s = Sim(port)
    res = {"dataset": path, "model": {k: mod[k] for k in ("err", "T_ds", "M") if k in mod}}
    res["model"].update({k: mod.get(k) for k in ("J", "order_used", "N", "transfers", "MSpec")})
    # ON, data, INIT
    if state(s) in (3, 7):
        press(s, "BtnStop")
        time.sleep(1.5)
    s.w("HMI_IF.SwOn", 1)
    time.sleep(1.2)
    if not noload:
        load_data(s, ds)
        time.sleep(1.2)
    press(s, "BtnInit")
    wait_for(s, lambda: state(s) in (1, 7), 5, 0.05)          # leave the previous DONE/READY first
    st = wait_for(s, lambda: state(s) in (2, 5) and state(s), 180)
    time.sleep(1.5)
    st = state(s)
    res["after_init_state"] = STATE_NAMES.get(st, st)
    res["after_init_alarm"] = int(s.r("HMI_IF.AlarmWord"))
    res["after_init_N"] = int(s.r("HMI_IF.N"))
    res["after_init_M"], res["after_init_T"] = int(s.r("number_of_manipulations")), float(s.r("time"))
    press(s, "BtnAuto")
    time.sleep(0.5)
    press(s, "BtnStart")
    t0 = time.time()
    ticks = []
    last_tick = None
    maxbal = 0
    done_state = None
    while time.time() - t0 < timeout:
        v = s.rb(TICK)
        tick = int(v[0])
        if tick != last_tick:
            last_tick = tick
            row = [round(time.time() - t0, 2)] + v
            ticks.append(row)
            L, R = int(v[7]), int(v[8])
            maxbal = max(maxbal, abs(L - R))
            stv = int(v[1])
            if stv in (5, 6) or (stv == 2 and len(ticks) > 5 and int(v[11]) == int(v[12])):
                # settle a little and stop
                if stv == 6 or stv == 5:
                    done_state = stv
                    break
        time.sleep(0.1)
    wall = time.time() - t0
    with open(os.path.join(outdir, name + ".ticks.csv"), "w", encoding="utf-8") as f:
        f.write("wall_s|" + "|".join(TICK) + "\n")
        for r in ticks:
            f.write("|".join(str(z) for z in r) + "\n")
    # reconstruct commands from successive (x,y,bay,M,T,Carried) samples
    cmds = []
    prev = None
    carrying = False
    for r in ticks:
        x, y, b, m = int(r[3]), int(r[4]), int(r[5]), int(r[6])
        if prev is not None:
            px, py, pb, pm = prev
            dm = m - pm
            if dm == 1:
                if (x, y, b) != (px, py, pb):
                    cmds.append((3, x, y, b))
                else:
                    cmds.append((2 if carrying else 1, x, y, b))
                    carrying = not carrying
            elif dm != 0:
                cmds.append((-dm, x, y, b))   # missed sample / reset
        prev = (x, y, b, m)
    fin_M, fin_T = int(s.r("number_of_manipulations")), float(s.r("time"))
    b0, b1 = read_bays(s)
    res.update({
        "plc_final_state": STATE_NAMES.get(done_state, done_state), "plc_M": fin_M, "plc_T": fin_T,
        "plc_T_ds": int(round(fin_T * 10)), "plc_MSpec": int(s.r("HMI_IF.MSpec")), "plc_J": float(s.r("HMI_IF.J")),
        "plc_PredJ": float(s.r("HMI_IF.PredJ")), "plc_OrderModeAct": int(s.r("HMI_IF.OrderModeAct")),
        "plc_TrDone": int(s.r("HMI_IF.TrDone")), "plc_TrTotal": int(s.r("HMI_IF.TrTotal")),
        "plc_AlarmWord": int(s.r("HMI_IF.AlarmWord")), "plc_AlarmWord2": int(s.r("HMI_IF.AlarmWord2")),
        "max_abs_balance": maxbal, "wall_s": round(wall, 1), "ticks": len(ticks),
        "planner_max_call_ms": float(s.r("Crane_Control_DB.Planner.DiagMaxCallMs")),
        "planner_job_ms": float(s.r("Crane_Control_DB.Planner.DiagJobMs")),
        "planner_calls": int(s.r("Crane_Control_DB.Planner.DiagCalls")),
        "cpu_state": s.cmd("STATE"),
        "plc_cmds_reconstructed": len(cmds), "model_cmds": len(mod["commands"]),
    })
    mc = [tuple(c) for c in mod["commands"]]
    pc = [tuple(c) for c in cmds]
    res["cmds_match"] = (mc == pc)
    if mc != pc:
        k = next((i for i in range(min(len(mc), len(pc))) if mc[i] != pc[i]), min(len(mc), len(pc)))
        res["first_cmd_diff"] = {"index": k, "model": mc[k:k + 3], "plc": pc[k:k + 3]}
    if mod["err"] == 0:
        res["bay0_match"] = (b0 == mod["bay0"])
        res["bay1_match"] = (b1 == mod["bay1"])
    res["M_match"] = fin_M == mod["M"]
    res["MSpec_match"] = res["plc_MSpec"] == mod.get("MSpec")
    res["T_match"] = int(round(fin_T * 10)) == mod["T_ds"]
    res["plc_bay0"], res["plc_bay1"] = b0, b1
    ok = (done_state == 6 and res["M_match"] and res["T_match"] and res.get("bay0_match", True)
          and res.get("bay1_match", True) and res.get("MSpec_match", True))
    res["cmds_or_sampling_ok"] = res["cmds_match"] or res.get("first_cmd_diff", {}).get("plc", [[0]])[0][0] < 0
    res["balance_ok"] = maxbal <= 5
    res["pass"] = ok
    with open(os.path.join(outdir, name + ".result.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    s.close()
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--port", type=int, default=50123)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--out")
    ap.add_argument("--noload", action="store_true")
    a = ap.parse_args()
    r = run(a.dataset, a.port, a.timeout, a.out, a.noload)
    short = {k: v for k, v in r.items() if k not in ("plc_bay0", "plc_bay1")}
    print(json.dumps(short, indent=1))
    print("SIM_RESULT pass=%d" % (1 if r["pass"] else 0))
