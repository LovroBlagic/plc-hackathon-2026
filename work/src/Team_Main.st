FUNCTION_BLOCK Team_Main
VAR_INPUT
      simOut : typeSimOut;
END_VAR
VAR_OUTPUT
      simCmd : typeSimCmd;
END_VAR
VAR_TEMP

END_VAR
VAR
	// ---- step sequencing (no timers: everything keyed on the simulated step k) ----
	xInit : BOOL;                       // first call done
	xNewStep : BOOL;                    // this call starts a new simulation step
	xResetStep : BOOL;                  // new step with k = 0 -> clear logs and state
	xLogNow : BOOL;                     // interval k-1 is logged in this step
	xHavePrev : BOOL;                   // values of interval k-1 are remembered
	kLast : DINT;                       // k of the previous new step
	dtLast : DT;                        // stamp of the previous new step
	k : DINT;
	j : INT;
	// ---- values of interval k-1 remembered for logging (spec 4.2) ----
	rFecPrev : REAL;                    // FEC_P_fix of interval k-1 (remembered for the next step)
	rFecLast : REAL;                    // FEC of the interval logged in this step (for HMI trend)
	iDayPrev : INT;                     // day_of_year of interval k-1
	iMonthPrev : INT;                   // month of interval k-1
	xHighPrev : BOOL;                   // VT of interval k-1
	aEvCmdPrev : ARRAY[0..3] OF REAL;   // feasible EV power commanded for interval k-1
	aEvConnPrev : ARRAY[0..3] OF BOOL;  // EV connected in interval k-1
	aEvDepKPrev : ARRAY[0..3] OF DINT;  // departure step of the EV connected in k-1
	aEvLast : ARRAY[0..3] OF REAL;      // actual EV power of interval k-1 (see note in body)
	rPrice : REAL;                      // energy price interval k
	rPricePrev : REAL;                  // energy price interval k-1
	// ---- per-step inputs for the control ----
	rBcMax : REAL;                      // feasible BESS charge [kW]
	rBdMax : REAL;                      // feasible BESS discharge [kW]
	aEvMax : ARRAY[0..3] OF REAL;       // feasible EV power [kW]
	aEvSteps : ARRAY[0..3] OF DINT;     // 15-min steps until departure
	aEvSlack : ARRAY[0..3] OF REAL;     // steps left minus steps needed at full power
	aEvRem : ARRAY[0..3] OF REAL;       // EV remaining energy [kWh] (0 if not connected)
	rPeakMonth : REAL;                  // import peak of the current month so far [kW]
	// ---- function blocks ----
	fbEnergyLog : FB_EnergyLogger;      // task 2
	fbCostLog : FB_CostLogger;          // task 3
	fbStrategy : FB_Strategy;           // task 1: what we would like to do
	fbGuard : FB_GridGuard;             // task 1: grid-limit protection (always last)
	fbHmi : FB_HmiUpdate;               // task 4 support data
	iStrategy : INT := 1;               // 0 = baseline (spec 2.6), 1 = forecast + planner
	// ---- command ----
	stCmd : typeSimCmd;                 // command for the current interval (held between steps)
	stCmdZero : typeSimCmd;             // never written -> all FALSE / 0
END_VAR

// ---IMPL---
// =====================================================================================
// Team_Main - energy manager. Called once per simulator step (SR_Main_Sim, phase 2 of 3).
// All state changes happen only when a NEW step is detected (k or stamp changed), so the
// result is independent of the SR_Main_Sim period. Order:
//   1. detect new step / reset   2. log interval k-1 (energy, cost)
//   3. control: strategy -> grid guard -> simCmd   4. remember values for the next step
//   5. HMI data. simCmd is written completely in every call.
// =====================================================================================
k := simOut.t_sim.k;
xNewStep := (NOT xInit) OR (k <> kLast) OR (simOut.t_sim.stamp <> dtLast);

IF xNewStep THEN
	xInit := TRUE;
	xResetStep := (k = 0);
	IF xResetStep THEN
		xHavePrev := FALSE;
	END_IF;

	// ---------------- 2. logging of interval k-1 ----------------
	xLogNow := xHavePrev AND (k = kLast + 1);
	FOR j := 0 TO 3 DO
		// The simulator publishes P_charge_act = 0 for an EV that departs at step k although it
		// was charged in interval k-1 (Sim_Core clears evPact on departure). For that interval we
		// use our own command, which was already clamped to the simulator's feasible value.
		IF xLogNow AND aEvConnPrev[j] AND (k >= aEvDepKPrev[j]) THEN
			aEvLast[j] := aEvCmdPrev[j];
		ELSE
			aEvLast[j] := simOut.EV[j].P_charge_act;
		END_IF;
	END_FOR;
	rFecLast := rFecPrev;
	IF xLogNow THEN
		rPricePrev := F_EnergyPrice(k := k - 1, iMonth := iMonthPrev, xHigh := xHighPrev, iMode := SimCtrl.price_mode);
	END_IF;
	fbEnergyLog(xReset := xResetStep, xLog := xLogNow, iDay := iDayPrev, iMonth := iMonthPrev,
		rFne := simOut.FNE_P_act, rFec := rFecPrev,
		rChg := simOut.BESS_P_charge_act, rDch := simOut.BESS_P_discharge_act,
		aEv := aEvLast, rImp := simOut.EGC_P_import, rExp := simOut.EGC_P_export);
	fbCostLog(xReset := xResetStep, xLog := xLogNow, iDay := iDayPrev, iMonth := iMonthPrev,
		rImp := simOut.EGC_P_import, rExp := simOut.EGC_P_export, rPrice := rPricePrev, xHigh := xHighPrev);

	// ---------------- 3. control ----------------
	IF (k >= Team_Cfg.N_STEPS) OR simOut.sim_finished THEN
		// final call (k = 35040): only logging, commands are ignored -> all zero
		stCmd := stCmdZero;
		xHavePrev := FALSE;
		FOR j := 0 TO 3 DO
			aEvCmdPrev[j] := 0.0;
			aEvConnPrev[j] := FALSE;
		END_FOR;
	ELSE
		rPrice := F_EnergyPrice(k := k, iMonth := simOut.t_sim.month, xHigh := simOut.t_sim.tariff_high, iMode := SimCtrl.price_mode);
		rPeakMonth := LREAL_TO_REAL(Team_Log.aMonth[LIMIT(1, simOut.t_sim.month, 12)].P_peak);
		// feasible limits (same clamps as the simulator)
		rBcMax := F_BessMaxChg(simOut.BESS_SoC);
		rBdMax := F_BessMaxDch(simOut.BESS_SoC);
		FOR j := 0 TO 3 DO
			IF simOut.EV[j].connected THEN
				aEvMax[j] := MAX(0.0, MIN(SimParam.EV_MAX_CHARGE,
					simOut.EV[j].energy_required / (SimParam.TS_H * SimParam.EV_ETA)));
				// planned departure is on a 15-min boundary: steps left = (departure - start of k) / 900 s
				aEvSteps[j] := MAX(1, (UDINT_TO_DINT(DT_TO_UDINT(simOut.EV[j].planned_departure))
					- UDINT_TO_DINT(DT_TO_UDINT(simOut.t_sim.stamp))) / 900);
				aEvSlack[j] := DINT_TO_REAL(aEvSteps[j])
					- simOut.EV[j].energy_required / (SimParam.EV_MAX_CHARGE * SimParam.TS_H * SimParam.EV_ETA);
				aEvRem[j] := simOut.EV[j].energy_required;
			ELSE
				aEvMax[j] := 0.0;
				aEvSteps[j] := 0;
				aEvSlack[j] := 0.0;
				aEvRem[j] := 0.0;
			END_IF;
		END_FOR;

		// 3a. strategy: requested setpoints
		fbStrategy(iMode := iStrategy, xReset := xResetStep, k := k, iQh := simOut.t_sim.qh_of_day,
			iWeekday := simOut.t_sim.weekday, iMonth := simOut.t_sim.month, xVt := simOut.t_sim.tariff_high,
			iPriceMode := SimCtrl.price_mode, rFec := simOut.FEC_P_fix, rFneAvail := simOut.FNE_output_power,
			rSoc := simOut.BESS_SoC, rBcMax := rBcMax, rBdMax := rBdMax, aEvMax := aEvMax,
			aEvRem := aEvRem, aEvSteps := aEvSteps, rPeakSoFar := rPeakMonth,
			iDay := simOut.t_sim.day_of_year, rEvPrevSum := aEvLast[0] + aEvLast[1] + aEvLast[2] + aEvLast[3]);

		// 3b. grid guard: predicted P_grid within EGC limits
		fbGuard(rFec := simOut.FEC_P_fix, rFneAvail := simOut.FNE_output_power,
			rBcMax := rBcMax, rBdMax := rBdMax, aEvMax := aEvMax, aEvSlack := aEvSlack,
			rPbReq := fbStrategy.rPbReq, aEvReq := fbStrategy.aEvReq,
			xCurtReq := fbStrategy.xCurtReq, rCurtReq := fbStrategy.rCurtReq);

		// 3c. complete command (all members, BESS enables mutually exclusive by construction)
		stCmd := stCmdZero;
		stCmd.FNE_enable_curtail := fbGuard.xCurt;
		stCmd.FNE_curtail_value := fbGuard.rCurt;
		IF fbGuard.rPb > Team_Cfg.P_EPS THEN
			stCmd.BESS_enable_discharge := TRUE;
			stCmd.BESS_P_discharge := fbGuard.rPb;
		ELSIF fbGuard.rPb < -Team_Cfg.P_EPS THEN
			stCmd.BESS_enable_charge := TRUE;
			stCmd.BESS_P_charge := -fbGuard.rPb;
		END_IF;
		FOR j := 0 TO 3 DO
			stCmd.EV[j].P_charge := fbGuard.aEv[j];
		END_FOR;

		// ---------------- 4. remember interval k for logging in step k+1 ----------------
		rFecPrev := simOut.FEC_P_fix;
		iDayPrev := simOut.t_sim.day_of_year;
		iMonthPrev := simOut.t_sim.month;
		xHighPrev := simOut.t_sim.tariff_high;
		FOR j := 0 TO 3 DO
			aEvCmdPrev[j] := fbGuard.aEv[j];
			aEvConnPrev[j] := simOut.EV[j].connected;
			aEvDepKPrev[j] := k + aEvSteps[j];
		END_FOR;
		xHavePrev := TRUE;
	END_IF;
	kLast := k;
	dtLast := simOut.t_sim.stamp;
END_IF;

// ---------------- 5. HMI data ----------------
fbHmi(xNewStep := xNewStep, xReset := xNewStep AND xResetStep, stOut := simOut, stCmd := stCmd,
	rPbCmd := fbGuard.rPb, rFneExp := fbGuard.rFne, rGridPred := fbGuard.rGridPred, rFecPrev := rFecLast,
	rPrice := rPrice, rPricePrev := rPricePrev, aEvSteps := aEvSteps, aEvLast := aEvLast,
	rPeakMonth := rPeakMonth, rPeakTarget := fbStrategy.rPeakTarget,
	xEvShed := fbGuard.xEvShed, xExpCurt := fbGuard.xExpCurt, xImpFail := fbGuard.xImpFail);

simCmd := stCmd;
