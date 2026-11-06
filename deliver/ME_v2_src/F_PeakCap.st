FUNCTION F_PeakCap : REAL
// Lowest monthly import cap [kW] the battery can hold over the horizon for the given net-load
// forecast (bisection). The battery covers load above the cap and recharges below it.
// Never below rFloor (the peak already paid this month), never above rLimImp.
VAR_INPUT
	h : INT;                            // horizon length
	rE0 : REAL;                         // usable stored energy now [kWh]
	rFloor : REAL;                      // peak already reached this month [kW]
	rLimImp : REAL;                     // import limit [kW]
END_VAR
VAR_IN_OUT
	aLoad : ARRAY[0..191] OF REAL;      // net-load forecast [kW]
END_VAR
VAR
	n : INT;
	i : INT;
	rMid : REAL;
	rLo : REAL;
	rHi : REAL;
	rE : REAL;
	rG : REAL;
	rNeed : REAL;
	rEuse : REAL;
	xOk : BOOL;
END_VAR
// ---IMPL---
rEuse := (SimParam.BESS_SOC_MAX - SimParam.BESS_SOC_MIN) / 100.0 * SimParam.BESS_CAPACITY;
F_PeakCap := rFloor;
rLo := rFloor;
rHi := rLimImp;
FOR n := 0 TO 12 DO
	IF n = 0 THEN
		rMid := rFloor;
	ELSE
		rMid := 0.5 * (rLo + rHi);
	END_IF;
	xOk := TRUE;
	rE := rE0;
	FOR i := 0 TO h - 1 DO
		rG := aLoad[i];
		IF rG > rMid THEN
			rNeed := rG - rMid;
			rE := rE - rNeed * SimParam.TS_H / SimParam.BESS_ETA_DCH;
			IF rNeed > SimParam.BESS_MAX_DCH OR rE < 0.0 THEN
				xOk := FALSE;
				EXIT;
			END_IF;
		ELSE
			rE := rE + MIN(MIN(rMid - rG, SimParam.BESS_MAX_CHG), (rEuse - rE) / (SimParam.TS_H * SimParam.BESS_ETA_CHG))
				* SimParam.TS_H * SimParam.BESS_ETA_CHG;
		END_IF;
	END_FOR;
	IF n = 0 THEN
		IF xOk THEN
			RETURN;                     // the already-paid peak is enough
		END_IF;
	ELSIF xOk THEN
		rHi := rMid;
	ELSE
		rLo := rMid;
	END_IF;
END_FOR;
F_PeakCap := MAX(rFloor, MIN(rLimImp, rHi * Team_Cfg.PLAN_CAPM));
