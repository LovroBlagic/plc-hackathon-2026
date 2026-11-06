FUNCTION F_StageCost : REAL
// Cost [EUR] of one 15-min interval with grid power rG (+ import / - export), used by FB_Planner.
//   import: rG*TS*(price+fee) + PLAN_PEN * (rG - cap)  (penalty for raising the monthly peak)
//   export: -min(-rG, export limit)*TS*0.9*price   (negative prices -> value 0: PV is curtailed)
VAR_INPUT
	rG : REAL;                          // grid power [kW]
	rCi : REAL;                         // import price + grid fee [EUR/kWh]
	rCe : REAL;                         // export value [EUR/kWh] (>= 0)
	rT : REAL;                          // import cap [kW]
	rLimExp : REAL;                     // export limit [kW]
END_VAR
// ---IMPL---
IF rG >= 0.0 THEN
	F_StageCost := rG * SimParam.TS_H * rCi + Team_Cfg.PLAN_PEN * MAX(rG - rT, 0.0);
ELSE
	F_StageCost := -MIN(-rG, rLimExp) * SimParam.TS_H * rCe;
END_IF;
