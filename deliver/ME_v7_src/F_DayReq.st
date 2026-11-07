FUNCTION F_DayReq : REAL
// R_d: lowest import cap [kW] that would have held one REALISED day (96 measured net-load values)
// starting with a full battery at 00:00. The battery covers load above the cap and recharges below it
// (same feasibility rule as F_PeakCap). Bisection over [0, rLimImp], 14 iterations (~0.06 kW).
VAR_INPUT
	rLimImp : REAL;                     // import limit [kW]
END_VAR
VAR_IN_OUT
	aDay : ARRAY[0..95] OF REAL;        // realised net load of the day: FEC - available PV + own EV draw [kW]
END_VAR
VAR
	n : INT;
	i : INT;
	rA : REAL;
	rB : REAL;
	rM : REAL;
	rE : REAL;
	rOver : REAL;
	rEuse : REAL;
	xOk : BOOL;
END_VAR
// ---IMPL---
rEuse := (SimParam.BESS_SOC_MAX - SimParam.BESS_SOC_MIN) / 100.0 * SimParam.BESS_CAPACITY;
rA := 0.0;
rB := rLimImp;
FOR n := 1 TO 14 DO
	rM := 0.5 * (rA + rB);
	xOk := TRUE;
	rE := rEuse;                        // full battery at 00:00
	FOR i := 0 TO 95 DO
		rOver := aDay[i] - rM;
		IF rOver > 0.0 THEN
			rE := rE - rOver * SimParam.TS_H / SimParam.BESS_ETA_DCH;
			IF rOver > SimParam.BESS_MAX_DCH OR rE < 0.0 THEN
				xOk := FALSE;
				EXIT;
			END_IF;
		ELSE
			rE := rE + MIN(MIN(-rOver, SimParam.BESS_MAX_CHG), (rEuse - rE) / (SimParam.TS_H * SimParam.BESS_ETA_CHG))
				* SimParam.TS_H * SimParam.BESS_ETA_CHG;
		END_IF;
	END_FOR;
	IF xOk THEN
		rB := rM;
	ELSE
		rA := rM;
	END_IF;
END_FOR;
F_DayReq := rB;
