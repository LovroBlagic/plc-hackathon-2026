FUNCTION_BLOCK FB_Strategy
// Energy-management strategy: decides the REQUESTED setpoints for interval k.
// FB_GridGuard afterwards enforces the grid limits, so the strategy may ignore them.
//   iMode 0 = baseline from spec 2.6: no curtailment, EVs at max power,
//             BESS charges only from PV surplus and discharges on deficit.
VAR_INPUT
	iMode : INT;                        // strategy selector
	rFec : REAL;                        // fixed consumption interval k [kW]
	rFneAvail : REAL;                   // available PV interval k [kW]
	rSoc : REAL;                        // [%]
	rBcMax : REAL;                      // feasible BESS charge [kW]
	rBdMax : REAL;                      // feasible BESS discharge [kW]
	aEvMax : ARRAY[0..3] OF REAL;       // feasible EV power [kW]
END_VAR
VAR_OUTPUT
	rPbReq : REAL;                      // BESS request, + discharge / - charge [kW]
	aEvReq : ARRAY[0..3] OF REAL;       // EV requests [kW]
	xCurtReq : BOOL;                    // voluntary curtailment request
	rCurtReq : REAL;                    // PV limit [kW]
	rPeakTarget : REAL;                 // import cap aimed for (info for HMI) [kW]
END_VAR
VAR
	j : INT;
	sumEv : REAL;
END_VAR
// ---IMPL---
sumEv := 0.0;
FOR j := 0 TO 3 DO
	aEvReq[j] := aEvMax[j];             // charge every connected EV at maximum feasible power
	sumEv := sumEv + aEvReq[j];
END_FOR;
// net demand on the bus without the battery: + deficit -> discharge, - PV surplus -> charge
rPbReq := rFec + sumEv - rFneAvail;
xCurtReq := FALSE;
rCurtReq := 0.0;
rPeakTarget := SimParam.EGC_MAX_IMPORT;
