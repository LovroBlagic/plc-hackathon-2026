FUNCTION_BLOCK Init_SimParam
VAR_INPUT
END_VAR
VAR_OUTPUT
END_VAR
VAR
END_VAR

// ---IMPL---
// Inicijalizacija GVL "SimParam"
   SimParam.TS_H := 0.25;
   SimParam.SIM_YEAR := 2025;
   SimParam.START_WEEKDAY := 3;
   SimParam.FNE_MAX_POWER := 750.0;
   SimParam.BESS_CAPACITY := 1500.0;
   SimParam.BESS_MAX_CHG := 750.0;
   SimParam.BESS_MAX_DCH := 750.0;
   SimParam.BESS_SOC_MIN := 10.0;
   SimParam.BESS_SOC_MAX := 90.0;
   SimParam.BESS_SOC_INIT := 50.0;
   SimParam.BESS_ETA_CHG := 0.95;
   SimParam.BESS_ETA_DCH := 0.95;
   SimParam.EV_MAX_CHARGE := 22.0;
   SimParam.EV_ETA := 0.9;
   SimParam.EGC_MAX_IMPORT := 1000.0;
   SimParam.EGC_MAX_EXPORT := 499.0;
   SimParam.GRID_VT := 0.020811;
   SimParam.GRID_NT := 0.010404;
   SimParam.PEAK_PRICE := 3.865;
   SimParam.EXPORT_FACTOR := 0.9;