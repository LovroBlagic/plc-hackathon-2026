FUNCTION_BLOCK FB_Strategy
// Energy-management strategy: decides the REQUESTED setpoints for interval k.
// Called once per new step. FB_GridGuard afterwards enforces the grid limits.
//   iMode 0 = baseline from spec 2.6: no curtailment, EVs at max power,
//             BESS charges only from PV surplus and discharges on deficit.
//   iMode 1 = optimised: forecast (FB_Forecast) + rolling-horizon planner (FB_Planner) for the
//             battery: monthly peak shaving + tariff / day-ahead arbitrage + PV self-consumption;
//             PV curtailed when the day-ahead price is negative and we would export.
VAR_INPUT
	iMode : INT;                        // strategy selector
	xReset : BOOL;                      // k = 0
	k : DINT;                           // current step
	iQh : INT;                          // qh_of_day
	iWeekday : INT;                     // 1 = Mon .. 7 = Sun
	iMonth : INT;                       // 1..12
	xVt : BOOL;                         // high tariff in interval k
	iPriceMode : INT;                   // SimCtrl.price_mode
	rFec : REAL;                        // fixed consumption interval k [kW]
	rFneAvail : REAL;                   // available PV interval k [kW]
	rSoc : REAL;                        // [%]
	rBcMax : REAL;                      // feasible BESS charge [kW]
	rBdMax : REAL;                      // feasible BESS discharge [kW]
	aEvMax : ARRAY[0..3] OF REAL;       // feasible EV power [kW]
	aEvRem : ARRAY[0..3] OF REAL;       // EV remaining energy [kWh] (0 if not connected)
	aEvSteps : ARRAY[0..3] OF DINT;     // EV steps to departure
	rPeakSoFar : REAL;                  // import peak of this month so far [kW]
END_VAR
VAR_OUTPUT
	rPbReq : REAL;                      // BESS request, + discharge / - charge [kW]
	aEvReq : ARRAY[0..3] OF REAL;       // EV requests [kW]
	xCurtReq : BOOL;                    // voluntary curtailment request
	rCurtReq : REAL;                    // PV limit [kW]
	rPeakTarget : REAL;                 // import cap aimed for (info for HMI) [kW]
	iHorizon : INT;                     // planning horizon used [steps]
END_VAR
VAR
	fbForecast : FB_Forecast;
	fbPlanner : FB_Planner;
	aNet : ARRAY[0..191] OF REAL;       // forecast net load
	aNetHi : ARRAY[0..191] OF REAL;     // pessimistic net load
	aVtF : ARRAY[0..191] OF BOOL;       // forecast VT
	aCi : ARRAY[0..191] OF REAL;        // import price + fee
	aCe : ARRAY[0..191] OF REAL;        // export value
	j : INT;
	i : INT;
	kk : DINT;
	sumEv : REAL;
	rP : REAL;
	rP0 : REAL;
END_VAR
// ---IMPL---
sumEv := 0.0;
FOR j := 0 TO 3 DO
	aEvReq[j] := aEvMax[j];             // EVs: charge at maximum feasible power (EV energy has priority)
	sumEv := sumEv + aEvReq[j];
END_FOR;
xCurtReq := FALSE;
rCurtReq := 0.0;

IF iMode = 0 THEN
	// ---------------- baseline (spec 2.6) ----------------
	// net demand on the bus without the battery: + deficit -> discharge, - PV surplus -> charge
	rPbReq := rFec + sumEv - rFneAvail;
	rPeakTarget := SimParam.EGC_MAX_IMPORT;
	iHorizon := 0;
ELSE
	// ---------------- optimised ----------------
	// horizon: PLAN_H steps; with day-ahead prices optionally only as far as prices are published
	// (tomorrow's prices are known after 13:00 = qh 52)
	IF iPriceMode = 1 AND Team_Cfg.PLAN_DA_PUBLISHED THEN
		iHorizon := 96 - iQh;
		IF iQh >= 52 THEN
			iHorizon := iHorizon + 96;
		END_IF;
		iHorizon := MIN(iHorizon, Team_Cfg.PLAN_H);   // cap the computing load (no measurable gain beyond 24 h)
	ELSE
		iHorizon := Team_Cfg.PLAN_H;
	END_IF;
	iHorizon := DINT_TO_INT(MIN(INT_TO_DINT(iHorizon), Team_Cfg.N_STEPS - k));
	iHorizon := LIMIT(1, iHorizon, 192);

	fbForecast(xReset := xReset, xUpdate := TRUE, k := k, iQh := iQh, iWeekday := iWeekday,
		rFec := rFec, rPv := rFneAvail, xVt := xVt, aEvRem := aEvRem, aEvSteps := aEvSteps,
		iH := iHorizon, rKsig := SEL(iPriceMode = 1, Team_Cfg.FC_KSIG_TT, Team_Cfg.FC_KSIG_DA),
		aNet := aNet, aNetHi := aNetHi, aVtF := aVtF);

	// prices over the horizon (price lists from Team_Prices, grid fee from SimParam)
	FOR i := 0 TO iHorizon - 1 DO
		kk := k + i;
		IF i = 0 THEN
			rP := F_EnergyPrice(k := kk, iMonth := iMonth, xHigh := xVt, iMode := iPriceMode);
			rP0 := rP;
		ELSE
			rP := F_EnergyPrice(k := kk, iMonth := iMonth, xHigh := aVtF[i], iMode := iPriceMode);
		END_IF;
		IF aVtF[i] THEN
			aCi[i] := rP + SimParam.GRID_VT;
		ELSE
			aCi[i] := rP + SimParam.GRID_NT;
		END_IF;
		aCe[i] := MAX(0.0, rP * SimParam.EXPORT_FACTOR);
	END_FOR;

	fbPlanner(iH := iHorizon, rSoc := rSoc, rBcMax := rBcMax, rBdMax := rBdMax, rPeakSoFar := rPeakSoFar,
		xHiInDp := SEL(iPriceMode = 1, Team_Cfg.PLAN_HI_TT, Team_Cfg.PLAN_HI_DA),
		aNet := aNet, aNetHi := aNetHi, aCi := aCi, aCe := aCe);
	rPbReq := fbPlanner.rPb;
	rPeakTarget := fbPlanner.rT;

	// negative energy price: do not export (export would cost money) -> curtail PV to the bus demand
	IF rP0 < 0.0 AND (rFec + sumEv - rPbReq - rFneAvail) < 0.0 THEN
		xCurtReq := TRUE;
		rCurtReq := MAX(0.0, rFec + sumEv - rPbReq);
	END_IF;
END_IF;
