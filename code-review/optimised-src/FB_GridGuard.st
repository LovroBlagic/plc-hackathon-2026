FUNCTION_BLOCK FB_GridGuard
// Grid-connection protection (spec 2.5 / 4.1, mandatory). Always the LAST stage before simCmd.
// Predicts the grid power of the CURRENT interval from the bus balance
//     P_grid = P_fec - P_fne + sum(P_ev) - P_bess      (P_bess: + discharge, - charge)
// using the values the simulator will actually realise (same clamps as Sim_Core: SoC limits,
// EV remaining energy, PV availability), and corrects the requested setpoints so that
//     P_grid <= EGC_MAX_IMPORT - margin   and   -P_grid <= EGC_MAX_EXPORT - margin.
// Import side: 1) drop voluntary curtailment, 2) more BESS discharge, 3) shed EV power (most slack first).
// Export side: 1) less discharge / more BESS charge, 2) curtail PV (safer than relying on the battery).
VAR_INPUT
	rFec : REAL;                        // fixed consumption of interval k [kW]
	rFneAvail : REAL;                   // available PV of interval k [kW]
	rBcMax : REAL;                      // feasible BESS charge [kW] (F_BessMaxChg)
	rBdMax : REAL;                      // feasible BESS discharge [kW] (F_BessMaxDch)
	aEvMax : ARRAY[0..3] OF REAL;       // feasible EV power per charger [kW] (0 if not connected)
	aEvSlack : ARRAY[0..3] OF REAL;     // EV scheduling slack [steps], bigger = shed first
	rPbReq : REAL;                      // requested BESS power, + discharge / - charge
	aEvReq : ARRAY[0..3] OF REAL;       // requested EV powers
	xCurtReq : BOOL;                    // strategy wants curtailment (e.g. negative price)
	rCurtReq : REAL;                    // requested PV limit [kW]
END_VAR
VAR_OUTPUT
	rPb : REAL;                         // final BESS power, + discharge / - charge
	aEv : ARRAY[0..3] OF REAL;          // final EV powers
	xCurt : BOOL;                       // final curtailment enable
	rCurt : REAL;                       // final PV limit [kW]
	rFne : REAL;                        // expected PV after curtailment
	rGridPred : REAL;                   // predicted grid power, + import / - export
	xEvShed : BOOL;                     // EV power reduced by the guard
	xExpCurt : BOOL;                    // PV curtailed by the guard for export protection
	xImpFail : BOOL;                    // import limit cannot be held (should never happen)
END_VAR
VAR
	limImp : REAL;
	limExp : REAL;
	sumEv : REAL;
	pg : REAL;
	d : REAL;
	j : INT;
	jSel : INT;
	n : INT;
	rBest : REAL;
END_VAR
// ---IMPL---
limImp := SimParam.EGC_MAX_IMPORT - Team_Cfg.GRID_MARGIN_IMP;
limExp := SimParam.EGC_MAX_EXPORT - Team_Cfg.GRID_MARGIN_EXP;
xEvShed := FALSE;
xExpCurt := FALSE;
xImpFail := FALSE;

// 1. clamp requests to what the simulator will realise
rPb := LIMIT(-rBcMax, rPbReq, rBdMax);
sumEv := 0.0;
FOR j := 0 TO 3 DO
	aEv[j] := LIMIT(0.0, aEvReq[j], aEvMax[j]);
	sumEv := sumEv + aEv[j];
END_FOR;
IF xCurtReq THEN
	rFne := MIN(rFneAvail, MAX(0.0, rCurtReq));
ELSE
	rFne := rFneAvail;
END_IF;
pg := rFec - rFne + sumEv - rPb;

// 2. import protection
IF pg > limImp THEN
	// 2a. give back voluntarily curtailed PV
	d := MIN(pg - limImp, rFneAvail - rFne);
	IF d > 0.0 THEN
		rFne := rFne + d;
		pg := pg - d;
	END_IF;
	// 2b. more discharge
	d := MIN(pg - limImp, rBdMax - rPb);
	IF d > 0.0 THEN
		rPb := rPb + d;
		pg := pg - d;
	END_IF;
	// 2c. shed EV power, charger with the largest slack first
	n := 0;
	WHILE pg > limImp AND n < 4 DO
		jSel := -1;
		rBest := -1.0E30;
		FOR j := 0 TO 3 DO
			IF aEv[j] > 0.0 AND aEvSlack[j] > rBest THEN
				rBest := aEvSlack[j];
				jSel := j;
			END_IF;
		END_FOR;
		IF jSel < 0 THEN
			EXIT;
		END_IF;
		d := MIN(pg - limImp, aEv[jSel]);
		aEv[jSel] := aEv[jSel] - d;
		sumEv := sumEv - d;
		pg := pg - d;
		xEvShed := TRUE;
		n := n + 1;
	END_WHILE;
	xImpFail := pg > limImp;
END_IF;

// 3. export protection
IF pg < -limExp THEN
	// 3a. less discharge / more charge
	d := MIN(-limExp - pg, rPb + rBcMax);
	IF d > 0.0 THEN
		rPb := rPb - d;
		pg := pg + d;
	END_IF;
	// 3b. curtail PV
	IF pg < -limExp THEN
		rFne := MAX(0.0, rFne - (-limExp - pg));
		xExpCurt := TRUE;
	END_IF;
END_IF;

// 4. outputs
xCurt := rFne < rFneAvail - 0.0001;
IF xCurt THEN
	rCurt := rFne;
ELSE
	rCurt := 0.0;
	rFne := rFneAvail;
END_IF;
sumEv := 0.0;
FOR j := 0 TO 3 DO
	sumEv := sumEv + aEv[j];
END_FOR;
rGridPred := rFec - rFne + sumEv - rPb;
