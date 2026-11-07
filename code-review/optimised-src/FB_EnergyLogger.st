FUNCTION_BLOCK FB_EnergyLogger
// Task 2 (spec 4.2): energy logging [kWh] per day / month / year + monthly import peak [kW].
// Called once per NEW simulation step k with the ACTUAL powers of interval k-1 (*_act, EGC_*),
// the fixed consumption remembered from the previous call and the day/month of interval k-1.
// E = P * TS_H, accumulated in LREAL into Team_Log (aDay, aMonth, stYear) and Team_Results.
VAR_INPUT
	xReset : BOOL;                      // k = 0: clear all tables
	xLog : BOOL;                        // log one interval
	iDay : INT;                         // day_of_year of interval k-1 (0..364)
	iMonth : INT;                       // month of interval k-1 (1..12)
	rFne : REAL;                        // FNE_P_act
	rFec : REAL;                        // FEC_P_fix of interval k-1 (remembered)
	rChg : REAL;                        // BESS_P_charge_act
	rDch : REAL;                        // BESS_P_discharge_act
	aEv : ARRAY[0..3] OF REAL;          // EV[j].P_charge_act
	rImp : REAL;                        // EGC_P_import
	rExp : REAL;                        // EGC_P_export
END_VAR
VAR
	stZero : typeTeamAgg;               // never written -> all zero
	ts : LREAL;
	d : INT;
	m : INT;
	j : INT;
	i : INT;
	eEv : LREAL;
END_VAR
// ---IMPL---
IF xReset THEN
	FOR i := 0 TO 364 DO
		Team_Log.aDay[i] := stZero;
	END_FOR;
	FOR i := 1 TO 12 DO
		Team_Log.aMonth[i] := stZero;
	END_FOR;
	Team_Log.stYear := stZero;
END_IF;

IF xLog THEN
	ts := REAL_TO_LREAL(SimParam.TS_H);
	d := LIMIT(0, iDay, 364);
	m := LIMIT(1, iMonth, 12);
	// day
	Team_Log.aDay[d].E_fne := Team_Log.aDay[d].E_fne + REAL_TO_LREAL(rFne) * ts;
	Team_Log.aDay[d].E_fec := Team_Log.aDay[d].E_fec + REAL_TO_LREAL(rFec) * ts;
	Team_Log.aDay[d].E_bess_chg := Team_Log.aDay[d].E_bess_chg + REAL_TO_LREAL(rChg) * ts;
	Team_Log.aDay[d].E_bess_dch := Team_Log.aDay[d].E_bess_dch + REAL_TO_LREAL(rDch) * ts;
	Team_Log.aDay[d].E_import := Team_Log.aDay[d].E_import + REAL_TO_LREAL(rImp) * ts;
	Team_Log.aDay[d].E_export := Team_Log.aDay[d].E_export + REAL_TO_LREAL(rExp) * ts;
	Team_Log.aDay[d].P_peak := MAX(Team_Log.aDay[d].P_peak, REAL_TO_LREAL(rImp));
	// month
	Team_Log.aMonth[m].E_fne := Team_Log.aMonth[m].E_fne + REAL_TO_LREAL(rFne) * ts;
	Team_Log.aMonth[m].E_fec := Team_Log.aMonth[m].E_fec + REAL_TO_LREAL(rFec) * ts;
	Team_Log.aMonth[m].E_bess_chg := Team_Log.aMonth[m].E_bess_chg + REAL_TO_LREAL(rChg) * ts;
	Team_Log.aMonth[m].E_bess_dch := Team_Log.aMonth[m].E_bess_dch + REAL_TO_LREAL(rDch) * ts;
	Team_Log.aMonth[m].E_import := Team_Log.aMonth[m].E_import + REAL_TO_LREAL(rImp) * ts;
	Team_Log.aMonth[m].E_export := Team_Log.aMonth[m].E_export + REAL_TO_LREAL(rExp) * ts;
	Team_Log.aMonth[m].P_peak := MAX(Team_Log.aMonth[m].P_peak, REAL_TO_LREAL(rImp));
	// year
	Team_Log.stYear.E_fne := Team_Log.stYear.E_fne + REAL_TO_LREAL(rFne) * ts;
	Team_Log.stYear.E_fec := Team_Log.stYear.E_fec + REAL_TO_LREAL(rFec) * ts;
	Team_Log.stYear.E_bess_chg := Team_Log.stYear.E_bess_chg + REAL_TO_LREAL(rChg) * ts;
	Team_Log.stYear.E_bess_dch := Team_Log.stYear.E_bess_dch + REAL_TO_LREAL(rDch) * ts;
	Team_Log.stYear.E_import := Team_Log.stYear.E_import + REAL_TO_LREAL(rImp) * ts;
	Team_Log.stYear.E_export := Team_Log.stYear.E_export + REAL_TO_LREAL(rExp) * ts;
	Team_Log.stYear.P_peak := MAX(Team_Log.stYear.P_peak, REAL_TO_LREAL(rImp));
	// EV per charger and total
	FOR j := 0 TO 3 DO
		eEv := REAL_TO_LREAL(aEv[j]) * ts;
		Team_Log.aDay[d].E_ev_ch[j] := Team_Log.aDay[d].E_ev_ch[j] + eEv;
		Team_Log.aDay[d].E_ev := Team_Log.aDay[d].E_ev + eEv;
		Team_Log.aMonth[m].E_ev_ch[j] := Team_Log.aMonth[m].E_ev_ch[j] + eEv;
		Team_Log.aMonth[m].E_ev := Team_Log.aMonth[m].E_ev + eEv;
		Team_Log.stYear.E_ev_ch[j] := Team_Log.stYear.E_ev_ch[j] + eEv;
		Team_Log.stYear.E_ev := Team_Log.stYear.E_ev + eEv;
	END_FOR;
END_IF;

IF xReset OR xLog THEN
	// publish yearly energies (names required by spec 4.2)
	Team_Results.E_fne := Team_Log.stYear.E_fne;
	Team_Results.E_fec := Team_Log.stYear.E_fec;
	Team_Results.E_bess_chg := Team_Log.stYear.E_bess_chg;
	Team_Results.E_bess_dch := Team_Log.stYear.E_bess_dch;
	Team_Results.E_ev := Team_Log.stYear.E_ev;
	Team_Results.E_import := Team_Log.stYear.E_import;
	Team_Results.E_export := Team_Log.stYear.E_export;
	Team_Results.E_ev_ch := Team_Log.stYear.E_ev_ch;
	Team_Results.P_peak := Team_Log.stYear.P_peak;
	IF xReset THEN
		Team_Results.nLogged := 0;
	END_IF;
	IF xLog THEN
		Team_Results.nLogged := Team_Results.nLogged + 1;
	END_IF;
END_IF;
