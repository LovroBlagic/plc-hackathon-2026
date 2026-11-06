FUNCTION_BLOCK FB_Forecast
// Forecast of the next h intervals (allowed by spec 4.1: estimates from PAST data only).
//   FEC: exponential moving average per day type (Mon-Fri / Sat / Sun) and quarter-hour,
//        plus the mean absolute deviation (sigma) per day type and quarter-hour.
//   PV : exponential moving average per quarter-hour (all days).
//   Intraday correction: ratio actual / profile over the last FC_CORR_W intervals scales the
//        profile forecast, fading out with time constant FC_CORR_TAU (cloudy day, busy day ...).
//   VT : tariff window learned from the last observed day.
//   EV : connected vehicles charged as soon as possible with their remaining energy.
// Interval i = 0 is the current interval k and uses the ACTUAL simOut values.
// Outputs: aNet = expected net load, aNetHi = pessimistic net load (for the peak cap):
//          + rKsig * sigma(FEC) + (1 - PLAN_PVF) * PV forecast.
// Learned profiles live in this FB only (built online from simOut, nothing is embedded).
VAR_INPUT
	xReset : BOOL;                      // k = 0: forget all learned profiles
	xUpdate : BOOL;                     // new step: learn from the current interval
	k : DINT;                           // current step
	iQh : INT;                          // qh_of_day of k
	iWeekday : INT;                     // 1 = Mon .. 7 = Sun of k
	rFec : REAL;                        // FEC_P_fix of k
	rPv : REAL;                         // FNE_output_power of k
	xVt : BOOL;                         // tariff_high of k
	aEvRem : ARRAY[0..3] OF REAL;       // EV remaining energy [kWh] (0 if not connected)
	aEvSteps : ARRAY[0..3] OF DINT;     // EV steps to departure
	iH : INT;                           // horizon length (1..192)
	rKsig : REAL;                       // pessimistic load = expected + rKsig * sigma
END_VAR
VAR_IN_OUT
	aNet : ARRAY[0..191] OF REAL;       // expected net load fec + ev - pv [kW]
	aNetHi : ARRAY[0..191] OF REAL;     // pessimistic net load [kW]
	aVtF : ARRAY[0..191] OF BOOL;       // forecast VT
END_VAR
VAR
	aFec : ARRAY[0..2, 0..95] OF REAL;  // learned FEC profile per day type
	aSig : ARRAY[0..2, 0..95] OF REAL;  // learned mean abs deviation of FEC
	aFecOk : ARRAY[0..2, 0..95] OF BOOL;
	aPv : ARRAY[0..95] OF REAL;         // learned PV profile
	aPvOk : ARRAY[0..95] OF BOOL;
	aVt : ARRAY[0..95] OF BOOL;         // last observed VT window
	aHf : ARRAY[0..15] OF REAL;         // recent actual FEC
	aHfP : ARRAY[0..15] OF REAL;        // profile value for it (before update)
	aHp : ARRAY[0..15] OF REAL;         // recent actual PV
	aHpP : ARRAY[0..15] OF REAL;        // profile value for it
	nHist : INT;                        // valid entries in the ring
	iHead : INT;                        // next write index
	rCorrF : REAL := 1.0;               // FEC intraday ratio
	rCorrP : REAL := 1.0;               // PV intraday ratio
	rFecMax : REAL;                     // highest FEC seen since reset (cold-start fallback)
	aEvR : ARRAY[0..3] OF REAL;
	i : INT;
	j : INT;
	q : INT;
	dtp : INT;
	wd : INT;
	kk : DINT;
	rF : REAL;
	rP : REAL;
	rS : REAL;
	rEv : REAL;
	pe : REAL;
	rA : REAL;
	rB : REAL;
	rA2 : REAL;
	rB2 : REAL;
	rDecay : REAL;
	rPrevF : REAL;
	rPrevP : REAL;
END_VAR
// ---IMPL---
IF xReset THEN
	FOR q := 0 TO 95 DO
		FOR dtp := 0 TO 2 DO
			aFec[dtp, q] := 0.0;
			aSig[dtp, q] := 0.0;
			aFecOk[dtp, q] := FALSE;
		END_FOR;
		aPv[q] := 0.0;
		aPvOk[q] := FALSE;
		aVt[q] := FALSE;
	END_FOR;
	nHist := 0;
	iHead := 0;
	rFecMax := 0.0;
	rCorrF := 1.0;
	rCorrP := 1.0;
END_IF;

// ---- learn from the current interval ----
IF xUpdate THEN
	q := LIMIT(0, iQh, 95);
	dtp := F_DayType(iWeekday);
	rFecMax := MAX(rFecMax, rFec);
	// profile values before the update (for the intraday ratio)
	IF aFecOk[dtp, q] THEN rPrevF := aFec[dtp, q]; ELSE rPrevF := rFec; END_IF;
	IF aPvOk[q] THEN rPrevP := aPv[q]; ELSE rPrevP := rPv; END_IF;
	IF aFecOk[dtp, q] THEN
		aSig[dtp, q] := aSig[dtp, q] + Team_Cfg.FC_ALPHA_SIG * (ABS(rFec - aFec[dtp, q]) - aSig[dtp, q]);
		aFec[dtp, q] := aFec[dtp, q] + Team_Cfg.FC_ALPHA_FEC * (rFec - aFec[dtp, q]);
	ELSE
		aFec[dtp, q] := rFec;
		aFecOk[dtp, q] := TRUE;
	END_IF;
	IF aPvOk[q] THEN
		aPv[q] := aPv[q] + Team_Cfg.FC_ALPHA_PV * (rPv - aPv[q]);
	ELSE
		aPv[q] := rPv;
		aPvOk[q] := TRUE;
	END_IF;
	aVt[q] := xVt;
	// intraday correction ratios over the last FC_CORR_W intervals
	IF Team_Cfg.FC_CORR_W > 0 THEN
		aHf[iHead] := rFec;
		aHfP[iHead] := rPrevF;
		aHp[iHead] := rPv;
		aHpP[iHead] := rPrevP;
		iHead := (iHead + 1) MOD 16;
		nHist := MIN(nHist + 1, LIMIT(1, Team_Cfg.FC_CORR_W, 16));
		rA := 0.0; rB := 0.0; rA2 := 0.0; rB2 := 0.0;
		FOR j := 1 TO nHist DO
			i := (iHead - j + 16) MOD 16;
			rA := rA + aHf[i];
			rB := rB + aHfP[i];
			rA2 := rA2 + aHp[i];
			rB2 := rB2 + aHpP[i];
		END_FOR;
		IF Team_Cfg.FC_CORR_FEC AND rB > 10.0 THEN
			rCorrF := LIMIT(0.5, rA / rB, 1.5);
		ELSE
			rCorrF := 1.0;
		END_IF;
		IF Team_Cfg.FC_CORR_PV AND rB2 > 20.0 THEN
			rCorrP := LIMIT(0.2, rA2 / rB2, 1.5);
		ELSE
			rCorrP := 1.0;
		END_IF;
	END_IF;
END_IF;

// ---- horizon ----
FOR j := 0 TO 3 DO
	aEvR[j] := aEvRem[j];
END_FOR;
FOR i := 0 TO LIMIT(1, iH, 192) - 1 DO
	kk := k + i;
	q := DINT_TO_INT(kk MOD 96);
	rS := 0.0;
	IF i = 0 THEN
		rF := rFec;
		rP := rPv;
		aVtF[i] := xVt;
	ELSE
		wd := DINT_TO_INT((INT_TO_DINT(iWeekday) - 1 + (kk / 96) - (k / 96)) MOD 7) + 1;
		dtp := F_DayType(wd);
		IF aFecOk[dtp, q] THEN
			rF := aFec[dtp, q];
			rS := aSig[dtp, q];
		ELSIF aFecOk[0, q] THEN
			rF := aFec[0, q];
		ELSE
			rF := rFec;                 // nothing learned yet: persistence
		END_IF;
		rP := aPv[q];
		IF Team_Cfg.FC_CORR_W > 0 THEN
			rDecay := EXP(-INT_TO_REAL(i) / Team_Cfg.FC_CORR_TAU);
			rF := rF * (1.0 + (rCorrF - 1.0) * rDecay);
			rP := rP * (1.0 + (rCorrP - 1.0) * rDecay);
		END_IF;
		aVtF[i] := aVt[q];
	END_IF;
	rEv := 0.0;
	FOR j := 0 TO 3 DO
		IF aEvR[j] > 0.000001 AND i < aEvSteps[j] THEN
			pe := MIN(SimParam.EV_MAX_CHARGE, aEvR[j] / (SimParam.TS_H * SimParam.EV_ETA));
			aEvR[j] := aEvR[j] - pe * SimParam.TS_H * SimParam.EV_ETA;
			rEv := rEv + pe;
		END_IF;
	END_FOR;
	aNet[i] := rF + rEv - rP;
	IF i = 0 THEN
		aNetHi[i] := aNet[i];
	ELSE
		aNetHi[i] := aNet[i] + rKsig * rS + (1.0 - Team_Cfg.PLAN_PVF) * rP;
	END_IF;
END_FOR;
