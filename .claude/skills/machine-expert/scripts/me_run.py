# -*- coding: utf-8 -*-
"""Machine Expert one-shot runner (IronPython 2.7, run via LogicBuilderShell.exe / me.ps1).

  me_run.py --project P.project [--src DIR] [--tests T.json] [--create] [--device ID]

Steps (one engine start):
  1. open project (or create it with --create; device default TM241CE24T/U)
  2. apply every DIR/*.st file (POU / DUT / GVL, see SKILL.md for the file format)
  3. build; print messages; exit early if errors
  4. if --tests: simulator login, run test steps, print PASS/FAIL
Machine-readable summary lines:  BUILD_RESULT errors=N warnings=M   |   SIM_RESULT pass=N fail=M
"""
from __future__ import print_function
import sys, os, re, glob, time, json, argparse

DEVICES = {  # name: (type, id, version)   -- run probe_devices.py for more
    "TM241CE24T": (4096, "101a 0711", "5.3.12.51"),
    "TM241CEC24T": (4096, "101a 0706", "5.3.12.51"),
    "TM251MESE": (4096, "101a 0750", "5.3.12.51"),
    "TM262L20MESE8T": (4096, "101a 0810", "5.3.9.26"),
}
SEP = "// ---IMPL---"
POLL_S = 0.05            # simulator read poll interval; 50 ms is ~ 1 MAST cycle (default 20 ms) x 2-3
DEFAULT_TIMEOUT_MS = 1000  # how long an "expect" may take to become true unless the step says otherwise

ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True)
ap.add_argument("--src")
ap.add_argument("--tests")
ap.add_argument("--create", action="store_true")
ap.add_argument("--device", default="TM241CE24T")
ap.add_argument("--folder", help="create NEW objects inside this application folder (created if missing)")
ap.add_argument("--year", help="EESTEC energy sim: comma list of price modes to run full-year, e.g. 0,1")
ap.add_argument("--cycle-ms", type=int, default=10)
ap.add_argument("--timeout-min", type=float, default=25.0)
ap.add_argument("--save-archive", help="after a successful build/run save a .projectarchive here")
ap.add_argument("--extra", default="", help="comma list of extra expressions to print after each year run")
a = ap.parse_args()


def die(msg):
    print("FATAL:", msg)
    sys.exit(2)


# ---------- 1. open / create ----------
if a.create:
    if os.path.exists(a.project):
        die("project exists, refusing to overwrite: %s" % a.project)
    if a.device not in DEVICES:
        die("unknown device %s. Known: %s" % (a.device, ", ".join(sorted(DEVICES))))
    proj = projects.create(a.project, True)
    t, i, v = DEVICES[a.device]
    proj.add("MyController", t, i, v)
    print("CREATED", a.project, "with", a.device)
else:
    if not os.path.exists(a.project):
        die("project not found: %s (use --create)" % a.project)
    try:
        proj = projects.open(a.project, primary=True)
    except Exception as ex:
        die("cannot open project (is it open in the Logic Builder GUI? close it or use a copy): %s" % ex)
app = proj.active_application


def find_code_obj(name):
    """app.find also returns same-named non-code objects (e.g. MAST task call entry) -> keep textual ones."""
    return [o for o in app.find(name, True) if getattr(o, "has_textual_declaration", False)]


def read_src(path):
    raw = open(path, "rb").read()
    if raw.startswith("\xef\xbb\xbf"):  # UTF-8 BOM (PowerShell 5.1) breaks the ST parser
        raw = raw[3:]
    return raw.decode("utf-8").lstrip(u"﻿").replace(u"\r\n", u"\n")


def get_container():
    """Where new objects are created: the application, or app/<--folder> (created on demand)."""
    if not a.folder:
        return app
    for o in app.get_children(False):
        if getattr(o, "is_folder", False) and o.get_name() == a.folder:
            return o
    app.create_folder(a.folder)
    for o in app.get_children(False):
        if getattr(o, "is_folder", False) and o.get_name() == a.folder:
            print("CREATED folder", a.folder)
            return o
    die("could not create folder %s" % a.folder)


# ---------- 2. apply sources ----------
if a.src:
    cont = get_container()
    files = sorted(glob.glob(os.path.join(a.src, "*.st")))
    if not files:
        die("no .st files in %s" % a.src)
    # DUTs first, then GVLs, then POUs -> fewer transient errors
    def rank(f):
        head = read_src(f).lstrip().upper()
        return 0 if head.startswith("TYPE") or "{ATTRIBUTE" in head[:200] and "TYPE" in head[:300] else (1 if "VAR_GLOBAL" in head[:300] else 2)
    for f in sorted(files, key=rank):
        name = os.path.splitext(os.path.basename(f))[0]
        txt = read_src(f)
        decl, impl = (txt.split(SEP, 1) + [None])[:2] if SEP in txt else (txt, None)
        body = re.sub(r"\{[^}]*\}", "", decl)  # ignore pragmas when detecting kind
        found = find_code_obj(name)
        if found:
            obj, action = found[0], "updated"
        else:
            m_type = re.search(r"^\s*TYPE\s+\w+\s*:\s*(\(|STRUCT|UNION)?", body, re.M | re.I)
            m_pou = re.search(r"^\s*(PROGRAM|FUNCTION_BLOCK|FUNCTION)\b\s*\w+\s*(?::\s*(\w+))?", body, re.M | re.I)
            if m_type:
                k = (m_type.group(1) or "").upper()
                dt = DutType.Enumeration if k == "(" else DutType.Union if k == "UNION" else DutType.Structure if k == "STRUCT" else DutType.Alias
                base = None
                if dt == DutType.Alias:
                    mb = re.search(r"TYPE\s+\w+\s*:\s*([^;]+);", body, re.I)
                    base = mb.group(1).strip() if mb else "INT"
                obj = cont.create_dut(name, dt, base) if base else cont.create_dut(name, dt)
            elif re.search(r"\bVAR_GLOBAL\b", body, re.I):
                obj = cont.create_gvl(name)
            elif m_pou:
                kind = m_pou.group(1).upper()
                if kind == "PROGRAM":
                    obj = cont.create_pou(name=name, type=PouType.Program)
                elif kind == "FUNCTION":
                    if not m_pou.group(2):
                        die("%s: FUNCTION needs a return type (FUNCTION %s : INT)" % (f, name))
                    obj = cont.create_pou(name=name, type=PouType.Function, return_type=m_pou.group(2))
                else:
                    obj = cont.create_pou(name=name, type=PouType.FunctionBlock)
            else:
                die("%s: cannot detect object kind (expected TYPE / VAR_GLOBAL / PROGRAM / FUNCTION_BLOCK / FUNCTION)" % f)
            action = "created"
        obj.textual_declaration.replace(decl.strip("\n") + "\n")
        if impl is not None:
            if not getattr(obj, "has_textual_implementation", False):
                die("%s: has %s but %s has no implementation part (DUT/GVL?)" % (f, SEP, name))
            obj.textual_implementation.replace(impl.strip("\n") + "\n")
        print("APPLY %-24s %s" % (name, action))
    proj.save()

# ---------- 3. build ----------
for cat in system.get_message_categories(True):
    try:
        system.clear_messages(cat)
    except Exception:
        pass
app.build()
errs = warns = 0
seen = set()
for cat in system.get_message_categories(True):
    for msg in system.get_message_objects(cat):
        sev = str(msg.severity)
        if sev not in ("Error", "FatalError", "Warning"):
            continue
        obj = msg.object.get_name() if msg.object else "-"
        key = (sev, msg.text, obj, msg.position_text)
        if key in seen:
            continue
        seen.add(key)
        print("[%s] %s :: %s %s" % (sev.upper(), obj, msg.position_text, msg.text))
        if "Error" in sev:
            errs += 1
        else:
            warns += 1
print("BUILD_RESULT errors=%d warnings=%d" % (errs, warns))
sys.stdout.flush()


def finish(code):
    if a.save_archive and code == 0:
        d = os.path.dirname(a.save_archive)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        proj.save_archive(a.save_archive)
        print("ARCHIVE_SAVED", a.save_archive)
    proj.save()
    proj.close()
    sys.exit(code)


if errs:
    finish(1)

# ---------- 3b. EESTEC energy-manager full-year runs (--year 0,1) ----------
YEAR_Q = ["E_fne", "E_fec", "E_bess_chg", "E_bess_dch", "E_ev", "E_import", "E_export",
          "cost_energy", "cost_grid", "cost_peak", "cost_total"]
YEAR_INFO = ["E_ev_required", "E_ev_unmet", "E_fne_curtailed", "P_peak"]


def num(v):
    s = unicode(v).strip()
    s = re.sub(r"^[A-Z_]+#", "", s)
    try:
        return float(s)
    except Exception:
        return s


def year_runs(oa, modes):
    rc = 0
    for mode in modes:
        t0 = time.time()
        oa.set_prepared_value("SimCtrl.run", "FALSE")
        oa.set_prepared_value("SimCtrl.change_cycle", "FALSE")
        oa.write_prepared_values()
        time.sleep(0.5)
        oa.set_prepared_value("SimCtrl.price_mode", str(mode))
        oa.set_prepared_value("SimCtrl.cycle_time_ms", str(a.cycle_ms))
        oa.set_prepared_value("SimCtrl.change_cycle", "TRUE")
        oa.set_prepared_value("SimCtrl.reset", "TRUE")
        oa.write_prepared_values()
        time.sleep(1.0)
        oa.set_prepared_value("SimCtrl.change_cycle", "FALSE")
        oa.write_prepared_values()
        time.sleep(0.3)
        print("YEAR mode=%s after reset: k=%s reset=%s" % (mode, oa.read_value("SimCtrl.k"), oa.read_value("SimCtrl.reset")))
        oa.set_prepared_value("SimCtrl.run", "TRUE")
        oa.write_prepared_values()
        deadline = time.time() + a.timeout_min * 60
        last_print = 0
        while True:
            time.sleep(5)
            k, fin, trip = oa.read_values(["SimCtrl.k", "SimCtrl.finished", "SimCtrl.tripped"])
            fin = unicode(fin).strip().upper() == "TRUE"
            trip = unicode(trip).strip().upper() == "TRUE"
            k = num(k)
            if time.time() - last_print > 60:
                print("  progress mode=%s k=%s t=%ds" % (mode, k, int(time.time() - t0)))
                sys.stdout.flush()
                last_print = time.time()
            if fin or trip or time.time() > deadline:
                break
        time.sleep(1.5)  # let the closing call (k=35040) run
        oa.set_prepared_value("SimCtrl.run", "FALSE")
        oa.write_prepared_values()
        time.sleep(0.3)
        sim = dict(zip(YEAR_Q + YEAR_INFO, [num(v) for v in oa.read_values(["SimScore.total." + q for q in YEAR_Q + YEAR_INFO])]))
        team = {}
        try:
            team = dict(zip(YEAR_Q, [num(v) for v in oa.read_values(["Team_Results." + q for q in YEAR_Q])]))
        except Exception as ex:
            print("  (Team_Results not readable: %s)" % ex)
        maxdev = 0.0
        for q in YEAR_Q:
            s, t = sim.get(q), team.get(q)
            dev_s = "-"
            if isinstance(s, float) and isinstance(t, float):
                d = abs(t - s) / max(abs(s), 1e-9) * 100.0
                maxdev = max(maxdev, d)
                dev_s = "%.5f%%" % d
            print("  %-12s sim=%-18s team=%-18s dev=%s" % (q, s, t, dev_s))
        for q in YEAR_INFO:
            print("  %-12s sim=%s" % (q, sim[q]))
        for e in [x for x in a.extra.split(",") if x.strip()]:
            try:
                print("  %s = %s" % (e, oa.read_value(e.strip())))
            except Exception as ex:
                print("  %s : %s" % (e, ex))
        ev_req = sim["E_ev_required"] if isinstance(sim["E_ev_required"], float) else 0.0
        print("YEAR_RESULT mode=%s finished=%s tripped=%s k=%s cost_total=%.2f E_ev=%.1f E_ev_unmet=%.2f ev_pct=%.3f maxdev=%.5f%% wall=%ds" % (
            mode, fin, trip, k, sim["cost_total"], sim["E_ev"], sim["E_ev_unmet"],
            (100.0 * (ev_req - sim["E_ev_unmet"]) / ev_req) if ev_req else 0.0, maxdev, int(time.time() - t0)))
        sys.stdout.flush()
        if trip or not fin:
            rc = 1
    return rc


if a.year:
    dev = [o for o in proj.get_children() if o.is_device][0]
    dev.set_simulation_mode(True)
    oa = online.create_online_application(app)
    rc = 1
    try:
        oa.login(OnlineChangeOption.Never, True)
        if str(oa.application_state).lower() != "run":
            oa.start()
        time.sleep(1.0)
        rc = year_runs(oa, [int(x) for x in a.year.split(",")])
    finally:
        try:
            oa.logout()
        except Exception:
            pass
        dev.set_simulation_mode(False)
    finish(rc)

if not a.tests:
    finish(0)

# ---------- 4. simulator tests ----------
steps = json.load(open(a.tests))
dev = [o for o in proj.get_children() if o.is_device][0]
dev.set_simulation_mode(True)
oa = online.create_online_application(app)
passed = failed = 0


def lit(v):
    if v is True: return "TRUE"
    if v is False: return "FALSE"
    return unicode(v)


def norm(v):
    s = unicode(v).strip().upper().replace(" ", "")
    s = re.sub(r"^\w+\.(?=\w+$)", "", s)        # E_STATE.FILLING -> FILLING
    s = re.sub(r"\(\d+\)$", "", s)              # FILLING(2) -> FILLING
    s = re.sub(r"^(SINT|INT|DINT|LINT|USINT|UINT|UDINT|ULINT|BYTE|WORD|DWORD|LWORD|REAL|LREAL)#", "", s)  # INT#2 -> 2
    return s


try:
    oa.login(OnlineChangeOption.Never, True)
    if str(oa.application_state).lower() != "run":
        oa.start()
    time.sleep(0.5)
    for st in steps:
        name = st.get("name", "?")
        try:
            for k, v in st.get("set", {}).items():
                oa.set_prepared_value(k, lit(v))
            if st.get("set"):
                oa.write_prepared_values()
            if st.get("wait_ms"):
                time.sleep(st["wait_ms"] / 1000.0)
            exp = st.get("expect", {})
            keys = list(exp.keys())
            t0 = time.time()
            deadline = t0 + st.get("timeout_ms", DEFAULT_TIMEOUT_MS) / 1000.0
            reads = 0
            while True:
                vals = oa.read_values(keys) if keys else []  # one batched read = consistent snapshot
                got = dict(zip(keys, vals))
                reads += 1
                bad = [k for k in keys if norm(got[k]) != norm(lit(exp[k]))]
                if not bad or time.time() > deadline:
                    break
                time.sleep(POLL_S)
            ms = int((time.time() - t0) * 1000)
            for k in keys:
                ok = k not in bad
                passed += ok
                failed += (not ok)
                print("%s %-28s %s = %s (expected %s) [%dms, %d reads]" % ("PASS" if ok else "FAIL", name, k, got[k], lit(exp[k]), ms, reads))
        except Exception as ex:
            failed += 1
            print("FAIL %-28s EXCEPTION %s  (expressions are POU.var, e.g. SR_Main.x or GVL.x)" % (name, ex))
finally:
    try:
        oa.logout()
    except Exception:
        pass
    dev.set_simulation_mode(False)
    proj.save()
    proj.close()
print("SIM_RESULT pass=%d fail=%d" % (passed, failed))
sys.exit(1 if failed else 0)
