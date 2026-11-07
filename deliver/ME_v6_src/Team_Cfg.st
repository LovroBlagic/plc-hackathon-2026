// Team_Cfg: team tuning constants (physics parameters are always read from SimParam).
VAR_GLOBAL CONSTANT
	N_STEPS : DINT := 35040;            // steps in the simulated year
	GRID_MARGIN_IMP : REAL := 1.0;      // [kW] safety margin below EGC_MAX_IMPORT for the predicted grid power
	GRID_MARGIN_EXP : REAL := 1.0;      // [kW] safety margin below EGC_MAX_EXPORT
	P_EPS : REAL := 0.001;              // [kW] below this a BESS setpoint is treated as zero
	// ---- forecast (FB_Forecast) ----
	FC_ALPHA_FEC : REAL := 0.5;         // EMA weight of the newest day for the load profile
	FC_ALPHA_PV : REAL := 0.3;          // EMA weight of the newest day for the PV profile
	FC_ALPHA_SIG : REAL := 0.3;         // EMA weight for the FEC deviation (sigma)
	FC_KSIG_TT : REAL := 0.75;          // two-tariff: pessimistic load = expected + FC_KSIG_TT * sigma
	FC_KSIG_DA : REAL := 0.0;           // day-ahead: same (arbitrage is worth more than the reserve)
	FC_CORR_W : INT := 4;               // intraday correction window [steps], 0 = off (max 16)
	FC_CORR_TAU : REAL := 16.0;         // fade-out of the intraday correction [steps]
	FC_CORR_FEC : BOOL := TRUE;         // apply intraday correction to FEC
	FC_CORR_PV : BOOL := TRUE;          // apply intraday correction to PV
	// ---- planner (FB_Planner) ----
	PLAN_H : INT := 96;                 // planning horizon [steps] (24 h)
	PLAN_DA_PUBLISHED : BOOL := TRUE;   // TRUE: day-ahead horizon limited to published prices (13:00 rule)
	PLAN_PEN : REAL := 20.0;            // [EUR/kW per step] penalty for planned import above the cap
	PLAN_LATE_EPS_TT : REAL := 0.05;    // two-tariff: late-discharge tie-breaker in the DP (0 = off); day-ahead: off
	PLAN_TVF : REAL := 0.9;             // terminal value of stored energy = mean import price * PLAN_TVF
	PLAN_PVF_TT : REAL := 0.6;          // two-tariff: PV share trusted in the pessimistic load (peak cap)
	PLAN_PVF_DA : REAL := 0.2;          // day-ahead: lower -> higher cap -> more room for cheap grid charging
	PLAN_HI_TT : BOOL := TRUE;          // two-tariff: DP peak penalty uses the pessimistic net load
	PLAN_HI_DA : BOOL := FALSE;         // day-ahead: DP peak penalty uses the expected net load
	PLAN_TSPLIT : BOOL := FALSE;        // TRUE: free import level from the expected forecast (see FB_Planner)
	PLAN_CAPM : REAL := 1.02;           // safety factor on the computed peak cap
END_VAR
