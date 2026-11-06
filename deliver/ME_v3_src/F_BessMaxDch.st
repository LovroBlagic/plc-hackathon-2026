FUNCTION F_BessMaxDch : REAL
// Largest bus-side discharge power [kW] the simulator accepts at this SoC (same clamp as Sim_Core).
VAR_INPUT
	rSoc : REAL;            // [%] SoC at start of the interval
END_VAR
// ---IMPL---
F_BessMaxDch := LREAL_TO_REAL(MAX(0.0, MIN(REAL_TO_LREAL(SimParam.BESS_MAX_DCH),
	(REAL_TO_LREAL(rSoc) - REAL_TO_LREAL(SimParam.BESS_SOC_MIN)) / 100.0 * REAL_TO_LREAL(SimParam.BESS_CAPACITY)
	* REAL_TO_LREAL(SimParam.BESS_ETA_DCH) / REAL_TO_LREAL(SimParam.TS_H))));
