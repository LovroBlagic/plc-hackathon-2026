FUNCTION_BLOCK FB_Planner
// Rolling-horizon battery planner, re-solved every step (model predictive control).
//  1. Monthly peak cap T: the peak of the month so far is already paid, so T >= that peak.
//     A bisection finds the lowest cap the battery can hold over the forecast horizon
//     (PV de-rated for safety); T = max(peak so far, that cap * margin).
//  2. Dynamic programming over the stored battery energy (0..1200 kWh in PLAN_DE steps):
//     cost(i) = import*TS*(price+fee) - export*TS*0.9*price(>=0) + PEN*(import above T),
//     terminal value of stored energy = mean import price * PLAN_TVF.
//  3. The first interval is optimised with continuous candidates and the exact current values.
// Output rPb: requested BESS power for interval k (+ discharge / - charge); FB_GridGuard checks it.
VAR_INPUT
	iH : INT;                           // horizon length (1..192)
	rSoc : REAL;                        // [%]
	rBcMax : REAL;                      // feasible charge [kW]
	rBdMax : REAL;                      // feasible discharge [kW]
	rPeakSoFar : REAL;                  // import peak of the current month so far [kW]
END_VAR
VAR_IN_OUT
	aNet : ARRAY[0..191] OF REAL;       // forecast net load without battery [kW] (i = 0 is exact)
	aPvF : ARRAY[0..191] OF REAL;       // forecast PV [kW]
	aCi : ARRAY[0..191] OF REAL;        // import cost price + grid fee [EUR/kWh]
	aCe : ARRAY[0..191] OF REAL;        // export value 0.9*price, >= 0 [EUR/kWh]
END_VAR
VAR_OUTPUT
	rPb : REAL;                         // requested battery power, + discharge / - charge
	rT : REAL;                          // import cap used [kW]
END_VAR
VAR CONSTANT
	NS : INT := 60;                     // energy levels 0..NS (EUSE / PLAN_DE)
	AMIN : INT := -9;                   // max discharge levels per step (750*0.25/0.95/20 = 9.9)
	AMAX : INT := 8;                    // max charge levels per step (750*0.25*0.95/20 = 8.9)
	NCAND : INT := 21;                  // first-step candidates
END_VAR
VAR
	V : ARRAY[0..60] OF REAL;           // value function at i+1
	Vn : ARRAY[0..60] OF REAL;          // value function at i
	aBus : ARRAY[-9..8] OF REAL;        // bus power of each action, + discharge
	aCa : ARRAY[-9..8] OF REAL;         // stage cost of each action
	h : INT;
	i : INT;
	s : INT;
	a : INT;
	m : INT;
	n : INT;
	rDE : REAL;
	rEuse : REAL;
	rE0 : REAL;
	rE : REAL;
	rTv : REAL;
	rG : REAL;
	rC : REAL;
	rBest : REAL;
	rV : REAL;
	rLo : REAL;
	rHi : REAL;
	rMid : REAL;
	rTp : REAL;
	rB : REAL;
	rX : REAL;
	rFr : REAL;
	rNeed : REAL;
	xOk : BOOL;
	iS0 : INT;
	aCand : ARRAY[0..22] OF REAL;
	nCand : INT;
	ts : REAL;
	etaC : REAL;
	etaD : REAL;
	limImp : REAL;
	limExp : REAL;
END_VAR
// ---IMPL---
ts := SimParam.TS_H;
etaC := SimParam.BESS_ETA_CHG;
etaD := SimParam.BESS_ETA_DCH;
limImp := SimParam.EGC_MAX_IMPORT - Team_Cfg.GRID_MARGIN_IMP;
limExp := SimParam.EGC_MAX_EXPORT - Team_Cfg.GRID_MARGIN_EXP;
rEuse := (SimParam.BESS_SOC_MAX - SimParam.BESS_SOC_MIN) / 100.0 * SimParam.BESS_CAPACITY;
rDE := rEuse / INT_TO_REAL(NS);
h := LIMIT(1, iH, 192);
rE0 := (rSoc - SimParam.BESS_SOC_MIN) / 100.0 * SimParam.BESS_CAPACITY;

// ---------------- 1. monthly import cap ----------------
// feasibility of cap rMid: battery covers net load above the cap, recharges below it
rTp := rPeakSoFar;
FOR n := 0 TO 13 DO
	IF n = 0 THEN
		rMid := rPeakSoFar;
	ELSE
		rMid := 0.5 * (rLo + rHi);
	END_IF;
	xOk := TRUE;
	rE := rE0;
	FOR i := 0 TO h - 1 DO
		rG := aNet[i];
		IF i > 0 THEN
			rG := rG + (1.0 - Team_Cfg.PLAN_PVF) * aPvF[i];   // pessimistic PV for the peak check
		END_IF;
		IF rG > rMid THEN
			rNeed := rG - rMid;
			rE := rE - rNeed * ts / etaD;
			IF rNeed > SimParam.BESS_MAX_DCH OR rE < 0.0 THEN
				xOk := FALSE;
				EXIT;
			END_IF;
		ELSE
			rE := rE + MIN(MIN(rMid - rG, SimParam.BESS_MAX_CHG), (rEuse - rE) / (ts * etaC)) * ts * etaC;
		END_IF;
	END_FOR;
	IF n = 0 THEN
		IF xOk THEN
			EXIT;                       // the already-paid peak is enough
		END_IF;
		rLo := rPeakSoFar;
		rHi := limImp;
	ELSIF xOk THEN
		rHi := rMid;
	ELSE
		rLo := rMid;
	END_IF;
	IF n = 13 THEN
		rTp := MIN(limImp, rHi * Team_Cfg.PLAN_CAPM);
	END_IF;
END_FOR;
rT := MAX(rPeakSoFar, rTp);

// ---------------- 2. DP backward over stored energy ----------------
rTv := 0.0;
FOR i := 0 TO h - 1 DO
	rTv := rTv + aCi[i];
END_FOR;
rTv := rTv / INT_TO_REAL(h) * Team_Cfg.PLAN_TVF;
FOR s := 0 TO NS DO
	V[s] := -INT_TO_REAL(s) * rDE * rTv;
END_FOR;
FOR a := AMIN TO AMAX DO
	IF a > 0 THEN
		aBus[a] := -INT_TO_REAL(a) * rDE / (ts * etaC);
	ELSE
		aBus[a] := -INT_TO_REAL(a) * rDE * etaD / ts;
	END_IF;
END_FOR;
FOR i := h - 1 TO 1 BY -1 DO
	FOR a := AMIN TO AMAX DO
		aCa[a] := F_StageCost(aNet[i] - aBus[a], aCi[i], aCe[i], rT, limExp);
	END_FOR;
	FOR s := 0 TO NS DO
		rBest := 3.0E38;
		FOR a := MAX(AMIN, -s) TO MIN(AMAX, NS - s) DO
			rV := aCa[a] + V[s + a];
			IF rV < rBest THEN
				rBest := rV;
			END_IF;
		END_FOR;
		Vn[s] := rBest;
	END_FOR;
	V := Vn;
END_FOR;

// ---------------- 3. first interval: continuous candidates ----------------
nCand := 0;
FOR m := 0 TO NCAND - 1 DO
	aCand[nCand] := -rBcMax + (rBcMax + rBdMax) * INT_TO_REAL(m) / INT_TO_REAL(NCAND - 1);
	nCand := nCand + 1;
END_FOR;
IF aNet[0] > -rBcMax AND aNet[0] < rBdMax THEN
	aCand[nCand] := aNet[0];            // exact self-consumption (grid = 0)
	nCand := nCand + 1;
END_IF;
IF aNet[0] - rT > -rBcMax AND aNet[0] - rT < rBdMax THEN
	aCand[nCand] := aNet[0] - rT;       // import exactly at the cap
	nCand := nCand + 1;
END_IF;
rBest := 3.0E38;
rPb := 0.0;
FOR m := 0 TO nCand - 1 DO
	rB := aCand[m];
	IF rB < 0.0 THEN
		rE := rE0 - rB * ts * etaC;
	ELSE
		rE := rE0 - rB * ts / etaD;
	END_IF;
	IF h > 1 THEN
		rX := LIMIT(0.0, rE / rDE, INT_TO_REAL(NS));
		iS0 := REAL_TO_INT(rX);             // REAL_TO_INT rounds -> make it floor
		IF INT_TO_REAL(iS0) > rX THEN
			iS0 := iS0 - 1;
		END_IF;
		iS0 := LIMIT(0, iS0, NS - 1);
		rFr := rX - INT_TO_REAL(iS0);
		rV := V[iS0] * (1.0 - rFr) + V[iS0 + 1] * rFr;
	ELSE
		rV := -rE * rTv;
	END_IF;
	rC := F_StageCost(aNet[0] - rB, aCi[0], aCe[0], rT, limExp) + rV;
	IF rC < rBest THEN
		rBest := rC;
		rPb := rB;
	END_IF;
END_FOR;
// never plan an import above the cap if the battery can avoid it
IF aNet[0] - rPb > rT THEN
	rPb := MIN(rBdMax, aNet[0] - rT);
END_IF;
