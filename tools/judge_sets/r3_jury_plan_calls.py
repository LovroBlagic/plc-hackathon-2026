"""r3 jury: how many OB1 calls does one planning job take with the PLC defaults
(CfgStepsPerCall 1, CfgImproveEvals 3000, CfgImprovePerCall 1, CfgSlotSweeps 10)?
Uses the team's line-by-line mirror tia-src/13_improve_mirror.py (IMPROVE+SLOT part only; the greedy
part adds about 4 variants x N transfers calls).  python tools/judge_sets/r3_jury_plan_calls.py <json...>"""
import importlib.util, os, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location("m13", os.path.join(REPO, "tia-src", "13_improve_mirror.py"))
m13 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m13)
for f in sys.argv[1:]:
    r = m13.check(f, {"mmode": 2, "order": 1, "balmode": 0, "lim": 5}, 3000, 0, 1, [0, 100, 200, 300])
    if r:
        ok, calls, ops, ev, acc = r
        print("%-40s parity=%s improve+slot OB1 calls=%d evals=%d accepts=%d max inner iterations/eval=%d" % (os.path.basename(f), ok, calls, ev, acc, ops))
