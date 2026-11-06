// Team_HMI: everything the HMI needs that is not directly in SimIO/SimParam/SimCtrl.
// Written by FB_HmiUpdate (called from Team_Main). Only iSelDay / iSelMonth are written by the HMI.
// All times are SIMULATED time (derived from simOut.t_sim), never the PLC clock.
VAR_GLOBAL
	// ---- status / header (show on every screen) ----
	sDateTime : STRING(20);             // "DD.MM.YYYY HH:MM" start of current interval k
	k : DINT;                           // current step
	rProgressPct : REAL;                // 0..100 % of the year
	xTariffHigh : BOOL;                 // TRUE = VT (high tariff) in current interval
	sTariff : STRING(2);                // 'VT' / 'NT'
	sPriceMode : STRING(20);            // 'Dvotarifni (HEP)' / 'Dan-unaprijed'
	rPrice : REAL;                      // [EUR/kWh] energy price of the current interval
	rGridFee : REAL;                    // [EUR/kWh] grid fee of the current interval
	// ---- power flows: requested (simCmd, interval k) vs actual (*_act, interval k-1) [kW] ----
	rFneAvail : REAL;                   // available PV in interval k (before curtailment)
	rFneExpected : REAL;                // PV expected after our curtailment, interval k
	xCurtActive : BOOL;                 // curtailment enabled in interval k
	rCurtValue : REAL;                  // curtailment limit [kW]
	rFneAct : REAL;                     // actual PV, interval k-1
	rFec : REAL;                        // fixed consumption, interval k
	rFecPrev : REAL;                    // fixed consumption, interval k-1
	rBessReq : REAL;                    // requested battery power, + = discharge, - = charge
	rBessChgReq : REAL;                 // requested charge [kW] (0 if not charging)
	rBessDchReq : REAL;                 // requested discharge [kW]
	rBessAct : REAL;                    // actual battery power interval k-1, + = discharge
	rBessChgAct : REAL;
	rBessDchAct : REAL;
	aEvReq : ARRAY[0..3] OF REAL;       // requested EV power, interval k
	aEvAct : ARRAY[0..3] OF REAL;       // actual EV power, interval k-1
	rEvReqSum : REAL;
	rEvActSum : REAL;
	rGridPred : REAL;                   // predicted grid power interval k, + = import, - = export
	rImportAct : REAL;                  // measured import interval k-1
	rExportAct : REAL;                  // measured export interval k-1
	rGridPredErr : REAL;                // |prediction(k-1) - measurement(k-1)| [kW]
	rGridPredErrMax : REAL;             // max of the above since reset
	// ---- battery ----
	rSoc : REAL;                        // [%]
	rSocMin : REAL;                     // [%] safety limits (SimParam)
	rSocMax : REAL;
	sBessDir : STRING(12);              // 'PUNJENJE' / 'PRAZNJENJE' / 'MIROVANJE'
	// ---- EV chargers ----
	aEvConnected : ARRAY[0..3] OF BOOL;
	aEvDeparture : ARRAY[0..3] OF STRING(20);   // planned departure "DD.MM.YYYY HH:MM" ('' if not connected)
	aEvRemaining : ARRAY[0..3] OF REAL;         // [kWh] energy still required
	aEvDelivered : ARRAY[0..3] OF REAL;         // [kWh] delivered this session
	aEvStepsLeft : ARRAY[0..3] OF DINT;         // 15-min intervals until departure
	// ---- peak power ----
	rPeakMonth : REAL;                  // [kW] monthly import peak so far (current month)
	rPeakTarget : REAL;                 // [kW] import cap the controller currently aims for
	// ---- energy/cost tables: selection written by the HMI ----
	iSelDay : INT := 0;                 // 0..364 -> stSelDay
	iSelMonth : INT := 1;               // 1..12  -> stSelMonth, aSelMonthDays
	stSelDay : typeTeamAgg;
	stSelMonth : typeTeamAgg;
	aSelMonthDays : ARRAY[1..31] OF typeTeamAgg;   // days of the selected month (unused days = 0)
	iSelMonthDays : INT;                // number of days in the selected month
	// ---- 24 h trends: index 95 = newest interval (k-1), 0 = oldest ----
	aTrFne : ARRAY[0..95] OF REAL;      // PV actual [kW]
	aTrFec : ARRAY[0..95] OF REAL;      // fixed consumption [kW]
	aTrGrid : ARRAY[0..95] OF REAL;     // grid, + import / - export [kW]
	aTrBess : ARRAY[0..95] OF REAL;     // battery, + discharge / - charge [kW]
	aTrEv : ARRAY[0..95] OF REAL;       // EV total [kW]
	aTrSoc : ARRAY[0..95] OF REAL;      // SoC [%]
	aTrPrice : ARRAY[0..95] OF REAL;    // energy price [EUR/kWh]
	// ---- alarms ----
	xAlmImport : BOOL;                  // EGC_overload_import (previous step)
	xAlmExport : BOOL;                  // EGC_overload_export
	xAlmTripped : BOOL;                 // plant disconnected
	xAlmFinished : BOOL;                // year finished (message)
	xAlmEvUnmet : BOOL;                 // an EV left with undelivered energy (latched until reset)
	xAlmGuardEv : BOOL;                 // guard reduced EV charging to hold import limit (this step)
	xAlmGuardCurt : BOOL;               // guard curtailed PV to hold export limit (this step)
	xAlmGuardFail : BOOL;               // predicted import above limit even after all measures
	aAlarmHist : ARRAY[0..49] OF typeTeamAlarm;   // newest at index 0
	nAlarms : DINT;                     // number of messages since reset
	sLastAlarm : STRING(80);
	// ---- diagnostics ----
	nCalls : DINT;                      // Team_Main calls since PLC start
	nSteps : DINT;                      // new steps processed since reset
	nGuardEv : DINT;                    // steps with EV shedding
	nGuardCurt : DINT;                  // steps with export curtailment by the guard
	nGuardFail : DINT;                  // steps where the guard could not hold the import limit
	nBothEnables : DINT;                // must stay 0
	rEvUnmetSum : REAL;                 // [kWh] energy not delivered at departures (own estimate)
END_VAR
