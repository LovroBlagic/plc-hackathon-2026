// Team_Cfg: team tuning constants (physics parameters are always read from SimParam).
VAR_GLOBAL CONSTANT
	N_STEPS : DINT := 35040;            // steps in the simulated year
	QH_PER_DAY : INT := 96;
	GRID_MARGIN_IMP : REAL := 1.0;      // [kW] safety margin below EGC_MAX_IMPORT for the predicted grid power
	GRID_MARGIN_EXP : REAL := 1.0;      // [kW] safety margin below EGC_MAX_EXPORT
	P_EPS : REAL := 0.001;              // [kW] below this a BESS setpoint is treated as zero
	ALARM_HIST : INT := 50;             // alarm history length (Team_HMI.aAlarmHist[0..ALARM_HIST-1])
END_VAR
