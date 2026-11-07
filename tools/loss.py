"""Loss breakdown: twin (ST config) vs LP bound per month, practice data."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import twin, strategies as S, lp_bound
import numpy as np
for mode in (0, 1):
    r = twin.simulate(S.dp_strategy(**S.st_config(mode)), mode)
    L = lp_bound.solve(mode, 0, verbose=False)
    print("MODE %d  twin %.0f  LP %.0f  gap %.0f (%.2f%%)" % (mode, r["cost_total"], L["cost"], r["cost_total"] - L["cost"], 100 * (r["cost_total"] - L["cost"]) / L["cost"]))
    print("  m |   buy twin/LP   |  rev twin/LP  | grid twin/LP | peak kW twin/LP | d_energy d_grid d_peak")
    tb = tg = tp = 0
    for m in range(12):
        b, rv, g = r["mon"][m]; pk = r["mpeak"][m]
        _, lb, lr, lg, lpk = L["monthly"][m]
        de = (b - rv) - (lb - lr); dg = g - lg; dp = (pk * 3.865) - lpk
        tb += de; tg += dg; tp += dp
        print(" %2d | %7.0f/%7.0f | %6.0f/%6.0f | %5.0f/%5.0f | %5.0f/%5.0f | %7.0f %6.0f %6.0f" % (m + 1, b, lb, rv, lr, g, lg, pk, lpk / 3.865, de, dg, dp))
    print("  TOTAL loss: energy(net) %.0f  grid %.0f  peak %.0f" % (tb, tg, tp))
