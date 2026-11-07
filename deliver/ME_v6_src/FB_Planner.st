FUNCTION_BLOCK FB_Planner
// Rolling-horizon battery planner, re-solved every step (model predictive control).
//  1. Monthly peak cap T: the peak of the month so far is already paid, so T >= that peak.
//     A bisection finds the lowest cap the battery can hold over the PESSIMISTIC forecast
//     (aNetHi); T = max(peak so far, that cap * margin).
//  2. Dynamic programming over the stored battery energy (0..1200 kWh in 40 kWh levels):
//     cost(i) = import*TS*(price+fee) - export*TS*0.9*price(>=0) + PEN*(pessimistic import above T),
//     terminal value of stored energy = mean import price * PLAN_TVF.
//     Tie-breaker (two-tariff only, rLateEps > 0): the import price of horizon step i is scaled by
//     (1 + rLateEps*i/96), so within one tariff block the battery discharges as late as possible and
//     import is held flat at the paid peak (like the full-year LP). The terminal value uses unscaled prices.
//  3. The first interval is optimised with continuous candidates and the exact current values.
// Output rPb: requested BESS power for interval k (+ discharge / - charge); FB_GridGuard checks it.
VAR_INPUT
	iH : INT;                           // horizon length (1..192)
	rSoc : REAL;                        // [%]
	rBcMax : REAL;                      // feasible charge [kW]
	rBdMax : REAL;                      // feasible discharge [kW]
	rPeakSoFar : REAL;                  // import peak of the current month so far [kW]
	xHiInDp : BOOL;                     // TRUE: peak penalty uses the pessimistic net load
	rLateEps : REAL;                    // late-discharge tie-breaker: import price of step i x (1 + rLateEps*i/96)
END_VAR
VAR_IN_OUT
	aNet : ARRAY[0..191] OF REAL;       // forecast net load without battery [kW] (i = 0 is exact)
	aNetHi : ARRAY[0..191] OF REAL;     // pessimistic net load for the peak cap [kW]
	aCi : ARRAY[0..191] OF REAL;        // import cost price + grid fee [EUR/kWh]
	aCe : ARRAY[0..191] OF REAL;        // export value 0.9*price, >= 0 [EUR/kWh]
END_VAR
VAR_OUTPUT
	rPb : REAL;                         // requested battery power, + discharge / - charge
	rT : REAL;                          // free import level (cap) used [kW]
	rTh : REAL;                         // cap under the pessimistic forecast [kW]
END_VAR
VAR CONSTANT
	NS : INT := 30;                     // energy levels 0..NS: 1200 kWh / 30 = 40 kWh per level
	AMIN : INT := -4;                   // max discharge levels per step (750*0.25/0.95/40 = 4.9)
	AMAX : INT := 4;                    // max charge levels per step (750*0.25*0.95/40 = 4.5)
	N_FIRST : INT := 41;                  // first-step candidates
END_VAR
VAR
	V : ARRAY[0..30] OF REAL;           // value function at i+1
	Vn : ARRAY[0..30] OF REAL;          // value function at i
	aBus : ARRAY[-4..4] OF REAL;        // bus power of each action, + discharge
	aCa : ARRAY[-4..4] OF REAL;         // stage cost of each action
	h : INT;
	i : INT;
	iE : INT;
	a : INT;
	m : INT;
	rDE : REAL;
	rEuse : REAL;
	rE0 : REAL;
	rE : REAL;
	rTv : REAL;
	rCiS : REAL;                        // scaled import price of the current DP stage
	rG : REAL;
	rC : REAL;
	rBest : REAL;
	rV : REAL;
	rB : REAL;
	rX : REAL;
	rFr : REAL;
	iS0 : INT;
	aCand : ARRAY[0..42] OF REAL;
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

// ---------------- 1. monthly import caps ----------------
// rTh: cap the battery can hold under the PESSIMISTIC forecast (reserve)
// rT : free import level. Without PLAN_TSPLIT rT = rTh; with it rT is the cap needed under the
//      EXPECTED forecast, so the DP never plans grid charging above what the load needs anyway.
rTh := F_PeakCap(h := h, rE0 := rE0, rFloor := rPeakSoFar, rLimImp := limImp, aLoad := aNetHi);
IF Team_Cfg.PLAN_TSPLIT THEN
	rT := F_PeakCap(h := h, rE0 := rE0, rFloor := rPeakSoFar, rLimImp := limImp, aLoad := aNet);
ELSE
	rT := rTh;
END_IF;

// ---------------- 2. DP backward over stored energy ----------------
rTv := 0.0;
FOR i := 0 TO h - 1 DO
	rTv := rTv + aCi[i];
END_FOR;
rTv := rTv / INT_TO_REAL(h) * Team_Cfg.PLAN_TVF;
FOR iE := 0 TO NS DO
	V[iE] := -INT_TO_REAL(iE) * rDE * rTv;
END_FOR;
FOR a := AMIN TO AMAX DO
	IF a > 0 THEN
		aBus[a] := -INT_TO_REAL(a) * rDE / (ts * etaC);
	ELSE
		aBus[a] := -INT_TO_REAL(a) * rDE * etaD / ts;
	END_IF;
END_FOR;
FOR i := h - 1 TO 1 BY -1 DO
	rCiS := aCi[i] * (1.0 + rLateEps * INT_TO_REAL(i) / 96.0);   // tie-breaker scaled import price
	FOR a := AMIN TO AMAX DO
		IF NOT Team_Cfg.PLAN_TSPLIT THEN
			IF xHiInDp THEN
				rG := aNetHi[i] - aBus[a];
			ELSE
				rG := aNet[i] - aBus[a];
			END_IF;
			aCa[a] := F_StageCost(aNet[i] - aBus[a], rG, rCiS, aCe[i], rT, limExp);
		ELSE
			aCa[a] := F_StageCost(aNet[i] - aBus[a], aNet[i] - aBus[a], rCiS, aCe[i], rT, limExp);
			IF xHiInDp AND aNetHi[i] - aBus[a] > rTh THEN
				aCa[a] := aCa[a] + Team_Cfg.PLAN_PEN * (aNetHi[i] - aBus[a] - rTh);
			END_IF;
		END_IF;
	END_FOR;
	FOR iE := 0 TO NS DO
		rBest := 3.0E38;
		FOR a := MAX(AMIN, -iE) TO MIN(AMAX, NS - iE) DO
			rV := aCa[a] + V[iE + a];
			IF rV < rBest THEN
				rBest := rV;
			END_IF;
		END_FOR;
		Vn[iE] := rBest;
	END_FOR;
	V := Vn;
END_FOR;

// ---------------- 3. first interval: continuous candidates ----------------
nCand := 0;
FOR m := 0 TO N_FIRST - 1 DO
	aCand[nCand] := -rBcMax + (rBcMax + rBdMax) * INT_TO_REAL(m) / INT_TO_REAL(N_FIRST - 1);
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
	rC := F_StageCost(aNet[0] - rB, aNet[0] - rB, aCi[0], aCe[0], rT, limExp) + rV;
	IF rC < rBest THEN
		rBest := rC;
		rPb := rB;
	END_IF;
END_FOR;
// never plan an import above the cap if the battery can avoid it
IF aNet[0] - rPb > rT THEN
	rPb := MIN(rBdMax, aNet[0] - rT);
END_IF;
