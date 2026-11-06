FUNCTION_BLOCK FB_HmiUpdate
// Fills Team_HMI for the HMI: simulated date/time, progress, requested vs actual flows, SoC, EVs,
// table selections, 24 h trends (96 samples, simulated time) and the alarm/message history.
// Trends and alarms advance only on a NEW simulation step -> independent of the PLC cycle time.
VAR_INPUT
	xNewStep : BOOL;                    // first call of a new step k
	xReset : BOOL;                      // k = 0 after reset
	stOut : typeSimOut;                 // simulator outputs (copy of simOut)
	stCmd : typeSimCmd;                 // commands issued for interval k
	rPbCmd : REAL;                      // final BESS setpoint, + discharge / - charge
	rFneExp : REAL;                     // expected PV after curtailment
	rGridPred : REAL;                   // predicted grid power interval k
	rFecPrev : REAL;                    // fixed consumption interval k-1
	rPrice : REAL;                      // energy price interval k
	rPricePrev : REAL;                  // energy price interval k-1
	aEvSteps : ARRAY[0..3] OF DINT;     // steps to departure
	rPeakMonth : REAL;                  // running monthly import peak
	rPeakTarget : REAL;                 // controller import cap
	xEvShed : BOOL;                     // guard flags of this step
	xExpCurt : BOOL;
	xImpFail : BOOL;
END_VAR
VAR
	i : INT;
	j : INT;
	iSel : INT;
	iFirst : INT;
	rGridPredLast : REAL;               // prediction made for the previous interval
	xHavePred : BOOL;
	aPrevConn : ARRAY[0..3] OF BOOL;
	aPrevRemain : ARRAY[0..3] OF REAL;
	aPrevDepK : ARRAY[0..3] OF DINT;
	xPrevImpOv : BOOL;
	xPrevExpOv : BOOL;
	xPrevTrip : BOOL;
	xPrevFin : BOOL;
	xPrevShed : BOOL;
	xPrevCurt : BOOL;
	xPrevFail : BOOL;
	rUnmet : REAL;
	aDim : ARRAY[1..12] OF INT := [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
	stZero : typeTeamAgg;
	kNow : DINT;
END_VAR
// ---IMPL---
kNow := stOut.t_sim.k;
Team_HMI.nCalls := Team_HMI.nCalls + 1;

// ---------------- reset (k = 0) ----------------
IF xReset THEN
	FOR i := 0 TO 95 DO
		Team_HMI.aTrFne[i] := 0.0;
		Team_HMI.aTrFec[i] := 0.0;
		Team_HMI.aTrGrid[i] := 0.0;
		Team_HMI.aTrBess[i] := 0.0;
		Team_HMI.aTrEv[i] := 0.0;
		Team_HMI.aTrSoc[i] := 0.0;
		Team_HMI.aTrPrice[i] := 0.0;
	END_FOR;
	FOR i := 0 TO 49 DO
		Team_HMI.aAlarmHist[i].k := 0;
		Team_HMI.aAlarmHist[i].sStamp := '';
		Team_HMI.aAlarmHist[i].iCode := 0;
		Team_HMI.aAlarmHist[i].sText := '';
	END_FOR;
	Team_HMI.nAlarms := 0;
	Team_HMI.sLastAlarm := '';
	Team_HMI.nSteps := 0;
	Team_HMI.nGuardEv := 0;
	Team_HMI.nGuardCurt := 0;
	Team_HMI.nGuardFail := 0;
	Team_HMI.nBothEnables := 0;
	Team_HMI.rEvUnmetSum := 0.0;
	Team_HMI.rGridPredErr := 0.0;
	Team_HMI.rGridPredErrMax := 0.0;
	Team_HMI.xAlmEvUnmet := FALSE;
	xHavePred := FALSE;
	xPrevImpOv := FALSE;
	xPrevExpOv := FALSE;
	xPrevTrip := FALSE;
	xPrevFin := FALSE;
	xPrevShed := FALSE;
	xPrevCurt := FALSE;
	xPrevFail := FALSE;
	FOR j := 0 TO 3 DO
		aPrevConn[j] := FALSE;
	END_FOR;
END_IF;

// ---------------- status / header (every call) ----------------
Team_HMI.sDateTime := F_DtString(stOut.t_sim.stamp);
Team_HMI.k := kNow;
Team_HMI.rProgressPct := DINT_TO_REAL(kNow) * 100.0 / DINT_TO_REAL(Team_Cfg.N_STEPS);
Team_HMI.xTariffHigh := stOut.t_sim.tariff_high;
IF stOut.t_sim.tariff_high THEN
	Team_HMI.sTariff := 'VT';
	Team_HMI.rGridFee := SimParam.GRID_VT;
ELSE
	Team_HMI.sTariff := 'NT';
	Team_HMI.rGridFee := SimParam.GRID_NT;
END_IF;
IF SimCtrl.price_mode = 1 THEN
	Team_HMI.sPriceMode := 'Dan-unaprijed';
ELSE
	Team_HMI.sPriceMode := 'Dvotarifni (HEP)';
END_IF;
Team_HMI.rPrice := rPrice;

// requested (interval k)
Team_HMI.rFneAvail := stOut.FNE_output_power;
Team_HMI.rFneExpected := rFneExp;
Team_HMI.xCurtActive := stCmd.FNE_enable_curtail;
Team_HMI.rCurtValue := stCmd.FNE_curtail_value;
Team_HMI.rFec := stOut.FEC_P_fix;
Team_HMI.rFecPrev := rFecPrev;
Team_HMI.rBessReq := rPbCmd;
Team_HMI.rBessChgReq := SEL(stCmd.BESS_enable_charge, 0.0, stCmd.BESS_P_charge);
Team_HMI.rBessDchReq := SEL(stCmd.BESS_enable_discharge, 0.0, stCmd.BESS_P_discharge);
Team_HMI.rGridPred := rGridPred;
Team_HMI.rEvReqSum := 0.0;
Team_HMI.rEvActSum := 0.0;
FOR j := 0 TO 3 DO
	Team_HMI.aEvReq[j] := stCmd.EV[j].P_charge;
	Team_HMI.aEvAct[j] := stOut.EV[j].P_charge_act;
	Team_HMI.rEvReqSum := Team_HMI.rEvReqSum + stCmd.EV[j].P_charge;
	Team_HMI.rEvActSum := Team_HMI.rEvActSum + stOut.EV[j].P_charge_act;
	Team_HMI.aEvConnected[j] := stOut.EV[j].connected;
	IF stOut.EV[j].connected THEN
		Team_HMI.aEvDeparture[j] := F_DtString(stOut.EV[j].planned_departure);
	ELSE
		Team_HMI.aEvDeparture[j] := '';
	END_IF;
	Team_HMI.aEvRemaining[j] := stOut.EV[j].energy_required;
	Team_HMI.aEvDelivered[j] := stOut.EV[j].energy_delivered;
	Team_HMI.aEvStepsLeft[j] := aEvSteps[j];
END_FOR;
// actual (interval k-1)
Team_HMI.rFneAct := stOut.FNE_P_act;
Team_HMI.rBessChgAct := stOut.BESS_P_charge_act;
Team_HMI.rBessDchAct := stOut.BESS_P_discharge_act;
Team_HMI.rBessAct := stOut.BESS_P_discharge_act - stOut.BESS_P_charge_act;
Team_HMI.rImportAct := stOut.EGC_P_import;
Team_HMI.rExportAct := stOut.EGC_P_export;
// battery
Team_HMI.rSoc := stOut.BESS_SoC;
Team_HMI.rSocMin := SimParam.BESS_SOC_MIN;
Team_HMI.rSocMax := SimParam.BESS_SOC_MAX;
IF rPbCmd > Team_Cfg.P_EPS THEN
	Team_HMI.sBessDir := 'PRAZNJENJE';
ELSIF rPbCmd < -Team_Cfg.P_EPS THEN
	Team_HMI.sBessDir := 'PUNJENJE';
ELSE
	Team_HMI.sBessDir := 'MIROVANJE';
END_IF;
Team_HMI.rPeakMonth := rPeakMonth;
Team_HMI.rPeakTarget := rPeakTarget;
IF stCmd.BESS_enable_charge AND stCmd.BESS_enable_discharge THEN
	Team_HMI.nBothEnables := Team_HMI.nBothEnables + 1;
END_IF;

// ---------------- table selection (HMI writes iSelDay / iSelMonth) ----------------
iSel := LIMIT(0, Team_HMI.iSelDay, 364);
Team_HMI.stSelDay := Team_Log.aDay[iSel];
iSel := LIMIT(1, Team_HMI.iSelMonth, 12);
Team_HMI.stSelMonth := Team_Log.aMonth[iSel];
Team_HMI.iSelMonthDays := aDim[iSel];
iFirst := 0;
FOR i := 1 TO iSel - 1 DO
	iFirst := iFirst + aDim[i];
END_FOR;
FOR i := 1 TO 31 DO
	IF i <= aDim[iSel] THEN
		Team_HMI.aSelMonthDays[i] := Team_Log.aDay[iFirst + i - 1];
	ELSE
		Team_HMI.aSelMonthDays[i] := stZero;
	END_IF;
END_FOR;

// ---------------- once per new step: trends, prediction check, alarms ----------------
IF xNewStep THEN
	Team_HMI.nSteps := Team_HMI.nSteps + 1;
	IF kNow > 0 THEN
		// trends: shift left, newest (interval k-1) at index 95
		FOR i := 0 TO 94 DO
			Team_HMI.aTrFne[i] := Team_HMI.aTrFne[i + 1];
			Team_HMI.aTrFec[i] := Team_HMI.aTrFec[i + 1];
			Team_HMI.aTrGrid[i] := Team_HMI.aTrGrid[i + 1];
			Team_HMI.aTrBess[i] := Team_HMI.aTrBess[i + 1];
			Team_HMI.aTrEv[i] := Team_HMI.aTrEv[i + 1];
			Team_HMI.aTrSoc[i] := Team_HMI.aTrSoc[i + 1];
			Team_HMI.aTrPrice[i] := Team_HMI.aTrPrice[i + 1];
		END_FOR;
		Team_HMI.aTrFne[95] := stOut.FNE_P_act;
		Team_HMI.aTrFec[95] := rFecPrev;
		Team_HMI.aTrGrid[95] := stOut.EGC_P_import - stOut.EGC_P_export;
		Team_HMI.aTrBess[95] := stOut.BESS_P_discharge_act - stOut.BESS_P_charge_act;
		Team_HMI.aTrEv[95] := Team_HMI.rEvActSum;
		Team_HMI.aTrSoc[95] := stOut.BESS_SoC;
		Team_HMI.aTrPrice[95] := rPricePrev;
		// grid prediction quality (prediction for k-1 vs measurement of k-1)
		IF xHavePred THEN
			Team_HMI.rGridPredErr := ABS(rGridPredLast - (stOut.EGC_P_import - stOut.EGC_P_export));
			Team_HMI.rGridPredErrMax := MAX(Team_HMI.rGridPredErrMax, Team_HMI.rGridPredErr);
		END_IF;
		// EV departures with undelivered energy
		FOR j := 0 TO 3 DO
			IF aPrevConn[j] AND kNow >= aPrevDepK[j] THEN
				rUnmet := aPrevRemain[j] - stOut.EV[j].P_charge_act * SimParam.TS_H * SimParam.EV_ETA;
				IF rUnmet > 0.01 THEN
					Team_HMI.xAlmEvUnmet := TRUE;
					Team_HMI.rEvUnmetSum := Team_HMI.rEvUnmetSum + rUnmet;
					F_AlarmPush(k := kNow, sStamp := Team_HMI.sDateTime, iCode := 5,
						sText := CONCAT(CONCAT('EV punjac ', INT_TO_STRING(j + 1)),
							CONCAT(': vozilo otislo, nepredano kWh = ', REAL_TO_STRING(rUnmet))));
				END_IF;
			END_IF;
		END_FOR;
	END_IF;
	// overload flags of the previous interval (also show as active alarms)
	Team_HMI.xAlmImport := stOut.EGC_overload_import;
	Team_HMI.xAlmExport := stOut.EGC_overload_export;
	IF stOut.EGC_overload_import AND NOT xPrevImpOv THEN
		F_AlarmPush(k := kNow, sStamp := Team_HMI.sDateTime, iCode := 1, sText := 'Prekoracenje uvoza iz mreze (EGC overload import)');
	END_IF;
	IF stOut.EGC_overload_export AND NOT xPrevExpOv THEN
		F_AlarmPush(k := kNow, sStamp := Team_HMI.sDateTime, iCode := 2, sText := 'Prekoracenje izvoza u mrezu (EGC overload export)');
	END_IF;
	xPrevImpOv := stOut.EGC_overload_import;
	xPrevExpOv := stOut.EGC_overload_export;
	// guard interventions (rising edge -> message)
	Team_HMI.xAlmGuardEv := xEvShed;
	Team_HMI.xAlmGuardCurt := xExpCurt;
	Team_HMI.xAlmGuardFail := xImpFail;
	IF xEvShed THEN Team_HMI.nGuardEv := Team_HMI.nGuardEv + 1; END_IF;
	IF xExpCurt THEN Team_HMI.nGuardCurt := Team_HMI.nGuardCurt + 1; END_IF;
	IF xImpFail THEN Team_HMI.nGuardFail := Team_HMI.nGuardFail + 1; END_IF;
	IF xEvShed AND NOT xPrevShed THEN
		F_AlarmPush(k := kNow, sStamp := Team_HMI.sDateTime, iCode := 6, sText := 'Zastita prikljucka: smanjeno punjenje EV (limit uvoza)');
	END_IF;
	IF xExpCurt AND NOT xPrevCurt THEN
		F_AlarmPush(k := kNow, sStamp := Team_HMI.sDateTime, iCode := 7, sText := 'Zastita prikljucka: ogranicena FNE (limit izvoza)');
	END_IF;
	IF xImpFail AND NOT xPrevFail THEN
		F_AlarmPush(k := kNow, sStamp := Team_HMI.sDateTime, iCode := 8, sText := 'UPOZORENJE: predvideni uvoz iznad limita');
	END_IF;
	xPrevShed := xEvShed;
	xPrevCurt := xExpCurt;
	xPrevFail := xImpFail;
	// remember for next step
	rGridPredLast := rGridPred;
	xHavePred := kNow < Team_Cfg.N_STEPS;
	FOR j := 0 TO 3 DO
		aPrevConn[j] := stOut.EV[j].connected AND kNow < Team_Cfg.N_STEPS;
		aPrevRemain[j] := stOut.EV[j].energy_required;
		aPrevDepK[j] := kNow + aEvSteps[j];
	END_FOR;
END_IF;

// ---------------- simulation state messages (every call, edge detected) ----------------
Team_HMI.xAlmTripped := stOut.sim_tripped OR SimCtrl.tripped;
Team_HMI.xAlmFinished := stOut.sim_finished OR SimCtrl.finished;
IF Team_HMI.xAlmTripped AND NOT xPrevTrip THEN
	F_AlarmPush(k := kNow, sStamp := Team_HMI.sDateTime, iCode := 3, sText := 'ODSPAJANJE od mreze (tripped) - simulacija zaustavljena');
END_IF;
IF Team_HMI.xAlmFinished AND NOT xPrevFin THEN
	F_AlarmPush(k := kNow, sStamp := Team_HMI.sDateTime, iCode := 4, sText := 'Simulacija godine zavrsena (finished)');
END_IF;
xPrevTrip := Team_HMI.xAlmTripped;
xPrevFin := Team_HMI.xAlmFinished;
