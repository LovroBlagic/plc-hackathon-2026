FUNCTION F_StageCost : REAL
// Cost [EUR] of one 15-min interval, used by FB_Planner.
//   rG >= 0 (import): rG*TS*(price+fee);  rG < 0 (export): -min(-rG, limit)*TS*0.9*price (value >= 0,
//   at negative prices PV is curtailed instead of exporting)
//   + PLAN_PEN * (rGpen - cap) if the (pessimistic) import rGpen would exceed the monthly cap.
VAR_INPUT
	rG : REAL;                          // expected grid power [kW], + import
	rGpen : REAL;                       // pessimistic grid power for the peak penalty [kW]
	rCi : REAL;                         // import price + grid fee [EUR/kWh]
	rCe : REAL;                         // export value [EUR/kWh] (>= 0)
	rT : REAL;                          // import cap [kW]
	rLimExp : REAL;                     // export limit [kW]
END_VAR
// ---IMPL---
IF rG >= 0.0 THEN
	F_StageCost := rG * SimParam.TS_H * rCi;
ELSE
	F_StageCost := -MIN(-rG, rLimExp) * SimParam.TS_H * rCe;
END_IF;
IF rGpen > rT THEN
	F_StageCost := F_StageCost + Team_Cfg.PLAN_PEN * (rGpen - rT);
END_IF;
