// Team_Cfg: team tuning constants (physics parameters are always read from SimParam).
VAR_GLOBAL CONSTANT
	N_STEPS : DINT := 35040;            // steps in the simulated year
	GRID_MARGIN_IMP : REAL := 1.0;      // [kW] safety margin below EGC_MAX_IMPORT for the predicted grid power
	GRID_MARGIN_EXP : REAL := 1.0;      // [kW] safety margin below EGC_MAX_EXPORT
	P_EPS : REAL := 0.001;              // [kW] below this a BESS setpoint is treated as zero
	// ---- forecast (FB_Forecast) ----
	FC_ALPHA_FEC : REAL := 0.5;         // EMA weight of the newest day for the load profile
	FC_ALPHA_PV : REAL := 0.3;          // EMA weight of the newest day for the PV profile
	// ---- planner (FB_Planner) ----
	PLAN_H : INT := 96;                 // planning horizon [steps] (24 h)
	PLAN_DA_PUBLISHED : BOOL := FALSE;  // TRUE: day-ahead horizon limited to published prices (13:00 rule)
	PLAN_PEN : REAL := 20.0;            // [EUR/kW per step] penalty for planned import above the cap
	PLAN_TVF : REAL := 0.9;             // terminal value of stored energy = mean import price * PLAN_TVF
	PLAN_PVF : REAL := 0.6;             // PV share trusted when computing the peak cap
	PLAN_CAPM : REAL := 1.02;           // safety factor on the computed peak cap
END_VAR
