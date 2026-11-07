FUNCTION F_EnergyPrice : REAL
// Energy price [EUR/kWh] of interval k for the selected price model (same series the simulator uses).
//   iMode 0 = two-tariff Elektra (per calendar quarter, VT/NT), 1 = day-ahead (Team_Prices.aDA)
VAR_INPUT
	k : DINT;               // interval 0..35039
	iMonth : INT;           // 1..12 of interval k
	xHigh : BOOL;           // VT of interval k (t_sim.tariff_high)
	iMode : INT;            // SimCtrl.price_mode
END_VAR
VAR
	iQ : INT;
END_VAR
// ---IMPL---
IF iMode = 1 THEN
	F_EnergyPrice := Team_Prices.aDA[LIMIT(0, k, 35039)];
ELSE
	iQ := LIMIT(1, (iMonth - 1) / 3 + 1, 4);
	IF xHigh THEN
		F_EnergyPrice := Team_Prices.TT_VT[iQ];
	ELSE
		F_EnergyPrice := Team_Prices.TT_NT[iQ];
	END_IF;
END_IF;
