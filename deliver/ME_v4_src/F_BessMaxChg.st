FUNCTION F_BessMaxChg : REAL
// Largest bus-side charge power [kW] the simulator accepts at this SoC (same clamp as Sim_Core).
VAR_INPUT
	rSoc : REAL;            // [%] SoC at start of the interval
END_VAR
// ---IMPL---
F_BessMaxChg := LREAL_TO_REAL(MAX(0.0, MIN(REAL_TO_LREAL(SimParam.BESS_MAX_CHG),
	(REAL_TO_LREAL(SimParam.BESS_SOC_MAX) - REAL_TO_LREAL(rSoc)) / 100.0 * REAL_TO_LREAL(SimParam.BESS_CAPACITY)
	/ (REAL_TO_LREAL(SimParam.TS_H) * REAL_TO_LREAL(SimParam.BESS_ETA_CHG)))));
