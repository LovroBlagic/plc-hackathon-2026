FUNCTION_BLOCK FB_Forecast
// Forecast of the next h intervals (allowed by spec 4.1: estimates from PAST data only).
//   FEC: exponential moving average per day type (Mon-Fri / Sat / Sun) and quarter-hour.
//   PV : exponential moving average per quarter-hour (all days).
//   VT : tariff window learned from the last observed day.
//   EV : connected vehicles charged as soon as possible with their remaining energy.
// Interval i = 0 is the current interval k and uses the ACTUAL simOut values.
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
	iH : INT;                           // horizon length (1..TEAM_H_MAX)
	rAlphaFec : REAL := 0.5;
	rAlphaPv : REAL := 0.3;
END_VAR
VAR_IN_OUT
	aNet : ARRAY[0..191] OF REAL;       // forecast net load fec + ev - pv [kW]
	aPvF : ARRAY[0..191] OF REAL;       // forecast PV [kW]
	aVtF : ARRAY[0..191] OF BOOL;       // forecast VT
END_VAR
VAR
	aFec : ARRAY[0..2, 0..95] OF REAL;  // learned FEC profile per day type
	aFecOk : ARRAY[0..2, 0..95] OF BOOL;
	aPv : ARRAY[0..95] OF REAL;         // learned PV profile
	aPvOk : ARRAY[0..95] OF BOOL;
	aVt : ARRAY[0..95] OF BOOL;         // last observed VT window
	aEvR : ARRAY[0..3] OF REAL;
	i : INT;
	j : INT;
	q : INT;
	dtp : INT;
	wd : INT;
	kk : DINT;
	rF : REAL;
	rP : REAL;
	rEv : REAL;
	pe : REAL;
END_VAR
// ---IMPL---
IF xReset THEN
	FOR q := 0 TO 95 DO
		FOR dtp := 0 TO 2 DO
			aFec[dtp, q] := 0.0;
			aFecOk[dtp, q] := FALSE;
		END_FOR;
		aPv[q] := 0.0;
		aPvOk[q] := FALSE;
		aVt[q] := FALSE;
	END_FOR;
END_IF;

// ---- learn from the current interval ----
IF xUpdate THEN
	q := LIMIT(0, iQh, 95);
	dtp := F_DayType(iWeekday);
	IF aFecOk[dtp, q] THEN
		aFec[dtp, q] := aFec[dtp, q] + rAlphaFec * (rFec - aFec[dtp, q]);
	ELSE
		aFec[dtp, q] := rFec;
		aFecOk[dtp, q] := TRUE;
	END_IF;
	IF aPvOk[q] THEN
		aPv[q] := aPv[q] + rAlphaPv * (rPv - aPv[q]);
	ELSE
		aPv[q] := rPv;
		aPvOk[q] := TRUE;
	END_IF;
	aVt[q] := xVt;
END_IF;

// ---- horizon ----
FOR j := 0 TO 3 DO
	aEvR[j] := aEvRem[j];
END_FOR;
FOR i := 0 TO LIMIT(1, iH, 192) - 1 DO
	kk := k + i;
	q := DINT_TO_INT(kk MOD 96);
	IF i = 0 THEN
		rF := rFec;
		rP := rPv;
		aVtF[i] := xVt;
	ELSE
		wd := DINT_TO_INT((INT_TO_DINT(iWeekday) - 1 + (kk / 96) - (k / 96)) MOD 7) + 1;
		dtp := F_DayType(wd);
		IF aFecOk[dtp, q] THEN
			rF := aFec[dtp, q];
		ELSIF aFecOk[0, q] THEN
			rF := aFec[0, q];
		ELSE
			rF := rFec;                 // nothing learned yet: persistence
		END_IF;
		rP := aPv[q];
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
	aPvF[i] := rP;
END_FOR;
