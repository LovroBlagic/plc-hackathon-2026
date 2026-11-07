FUNCTION_BLOCK FB_CapFloor
// Learned monthly import-cap FLOOR (day-ahead mode, twin candidate "capmodel", config(1)).
// Import up to the floor is treated as free from the first day of a month, instead of ratcheting the
// cap up day by day while the battery is short early in the month.
//   R_d   = lowest cap that would have held one realised day starting with a full battery (F_DayReq),
//           computed from our own measurements (FEC - available PV + own EV draw) of the previous day;
//           usable from qh = CAPF_DELAY of the next day.
//   floor = MIN(CAPF_F * mean(last CAPF_NM paid monthly peaks), CAPF_C * max(R_d of the last CAPF_N days))
//           (the R_d bound keeps one high month from being carried into later lower-load months).
// Active only when xEnable, at least one previous month and >= 5 R_d values exist. Past data only.
// Called once per new step, before FB_Planner.
VAR_INPUT
	xReset : BOOL;                      // k = 0: forget everything
	xEnable : BOOL;                     // output a floor (day-ahead mode)
	k : DINT;                           // current step
	iQh : INT;                          // qh_of_day of k
	iDay : INT;                         // day_of_year of k
	iMonth : INT;                       // month of k
	rFec : REAL;                        // FEC_P_fix of k
	rPv : REAL;                         // FNE_output_power (available) of k
	rEvPrev : REAL;                     // actual total EV power of interval k-1
	rPeakSoFar : REAL;                  // import peak of the current month so far (logged up to k-1)
	rLimImp : REAL;                     // import limit used by the planner
END_VAR
VAR_OUTPUT
	rFloor : REAL;                      // cap floor [kW], 0 = inactive
	rRdLast : REAL;                     // newest R_d [kW] (diagnostics)
	nRd : INT;                          // number of R_d values available (max 28, diagnostics)
END_VAR
VAR
	aDayBase : ARRAY[0..95] OF REAL;    // current day: FEC - available PV per quarter-hour
	aDayEv : ARRAY[0..95] OF REAL;      // current day: own EV draw per quarter-hour
	aDayDone : ARRAY[0..95] OF REAL;    // finished previous day (net load incl. EV)
	iDayCur : INT := -1;
	xPend : BOOL;                       // R_d of aDayDone still to be computed
	aRd : ARRAY[0..13] OF REAL;         // ring of the last CAPF_N (= 14) R_d values
	iRdHead : INT;
	aPk : ARRAY[0..2] OF REAL;          // ring of the last CAPF_NM (= 3) paid monthly peaks
	iPkHead : INT;
	nPk : INT;
	iMonthCur : INT;
	rTPaid : REAL;                      // paid peak of the current month (max of rPeakSoFar)
	i : INT;
	n : INT;
	rSum : REAL;
	rMaxRd : REAL;
END_VAR
// ---IMPL---
IF xReset THEN
	FOR i := 0 TO 95 DO
		aDayBase[i] := 0.0;
		aDayEv[i] := 0.0;
		aDayDone[i] := 0.0;
	END_FOR;
	FOR i := 0 TO 13 DO
		aRd[i] := 0.0;
	END_FOR;
	FOR i := 0 TO 2 DO
		aPk[i] := 0.0;
	END_FOR;
	iDayCur := -1;
	xPend := FALSE;
	iRdHead := 0;
	nRd := 0;
	iPkHead := 0;
	nPk := 0;
	iMonthCur := 0;
	rTPaid := 0.0;
	rRdLast := 0.0;
END_IF;

// ---- day record (EV draw of interval k-1 is known now) ----
IF k > 0 THEN
	aDayEv[DINT_TO_INT((k - 1) MOD 96)] := rEvPrev;
END_IF;
IF iDay <> iDayCur THEN
	IF iDayCur >= 0 THEN
		FOR i := 0 TO 95 DO
			aDayDone[i] := aDayBase[i] + aDayEv[i];
		END_FOR;
		xPend := TRUE;
	END_IF;
	iDayCur := iDay;
	FOR i := 0 TO 95 DO
		aDayBase[i] := 0.0;
		aDayEv[i] := 0.0;
	END_FOR;
END_IF;
IF xPend AND iQh >= Team_Cfg.CAPF_DELAY THEN
	rRdLast := F_DayReq(rLimImp := rLimImp, aDay := aDayDone);
	aRd[iRdHead] := rRdLast;
	iRdHead := (iRdHead + 1) MOD 14;
	nRd := MIN(nRd + 1, 28);
	xPend := FALSE;
END_IF;
aDayBase[LIMIT(0, iQh, 95)] := rFec - rPv;

// ---- paid monthly peaks ----
IF iMonth <> iMonthCur THEN
	IF iMonthCur > 0 THEN
		aPk[iPkHead] := rTPaid;
		iPkHead := (iPkHead + 1) MOD 3;
		nPk := MIN(nPk + 1, 3);
	END_IF;
	iMonthCur := iMonth;
	rTPaid := 0.0;
END_IF;
rTPaid := MAX(rTPaid, rPeakSoFar);

// ---- floor ----
rFloor := 0.0;
IF xEnable AND nPk > 0 AND nRd >= 5 THEN
	rSum := 0.0;
	FOR i := 0 TO nPk - 1 DO
		rSum := rSum + aPk[i];
	END_FOR;
	rMaxRd := 0.0;
	n := MIN(nRd, 14);
	FOR i := 1 TO n DO
		rMaxRd := MAX(rMaxRd, aRd[(iRdHead - i + 14) MOD 14]);
	END_FOR;
	rFloor := MIN(rLimImp, MIN(Team_Cfg.CAPF_F * rSum / INT_TO_REAL(nPk), Team_Cfg.CAPF_C * rMaxRd));
END_IF;
