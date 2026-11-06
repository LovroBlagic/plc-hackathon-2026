# -*- coding: utf-8 -*-
# Usage: LogicBuilderShell.exe sim_test.py <project.project>
# Builds, logs into the Machine Expert SIMULATOR, starts the PLC, drives inputs and asserts outputs.
# Edit TESTS below for your task. Each step: (dict of writes, wait_ms, dict of expected reads)
from __future__ import print_function
import sys, time
P = "SR_Main."   # expressions are relative to the application: POU.var
TESTS = [
    ("idle",          {P+"xStartPB": False, P+"xStopPB": True, P+"xOverload": False}, 300,  {P+"fbConveyor.xMotor": False, P+"fbConveyor.xHorn": False}),
    ("press start",   {P+"xStartPB": True},  300,  {P+"fbConveyor.xHorn": True,  P+"fbConveyor.xMotor": False}),
    ("release start", {P+"xStartPB": False}, 2500, {P+"fbConveyor.xHorn": False, P+"fbConveyor.xMotor": True}),
    ("press stop",    {P+"xStopPB": False},  300,  {P+"fbConveyor.xMotor": False}),
    ("fault",         {P+"xStopPB": True, P+"xOverload": True, P+"xStartPB": True}, 300, {P+"fbConveyor.xMotor": False, P+"fbConveyor.xFaultLamp": True}),
]
proj = projects.open(sys.argv[1], primary=True)
app = proj.active_application
dev = [o for o in proj.get_children() if o.is_device][0]
dev.set_simulation_mode(True)
app.build()
oa = online.create_online_application(app)
oa.login(OnlineChangeOption.Never, True)
print("logged in:", oa.is_logged_in)
if str(oa.application_state) != "run":
    oa.start()
time.sleep(1)
print("state:", oa.application_state)
fails = 0
def lit(v): return "TRUE" if v is True else "FALSE" if v is False else str(v)
for name, writes, wait_ms, expect in TESTS:
    for k, v in writes.items(): oa.set_prepared_value(k, lit(v))
    oa.write_prepared_values()
    time.sleep(wait_ms / 1000.0)
    for k, v in expect.items():
        got = oa.read_value(k)
        ok = str(got).upper() == lit(v)
        if not ok: fails += 1
        print("%-5s %-14s %s = %s (expected %s)" % ("PASS" if ok else "FAIL", name, k.replace(P, ""), got, lit(v)))
oa.logout()
dev.set_simulation_mode(False)
proj.close()
print("SIM_RESULT fails=%d" % fails)
