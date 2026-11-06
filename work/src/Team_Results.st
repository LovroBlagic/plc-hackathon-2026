// Team_Results: YEARLY totals checked by the jury against SimScore.total (tolerance 0.1 %).
// Energies [kWh] and costs [EUR], all LREAL. Updated every simulation step (interval k-1).
VAR_GLOBAL
	E_fne : LREAL;                      // PV production after curtailment
	E_fec : LREAL;                      // fixed consumption
	E_bess_chg : LREAL;                 // battery charge, bus side
	E_bess_dch : LREAL;                 // battery discharge, bus side
	E_ev : LREAL;                       // EV chargers total, bus side
	E_import : LREAL;                   // grid import
	E_export : LREAL;                   // grid export
	E_ev_ch : ARRAY[0..3] OF LREAL;     // per EV charger, bus side
	P_peak : LREAL;                     // [kW] highest monthly peak of the year (info)
	// cost components (spec 4.3)
	C_purchase : LREAL;                 // energy purchase
	C_revenue : LREAL;                  // export revenue (0.9 * price)
	C_grid : LREAL;                     // grid fee
	C_peak : LREAL;                     // peak power cost = sum of 12 monthly values
	C_total : LREAL;                    // purchase - revenue + grid + peak
	// same quantities with the simulator's SimScore.total names
	cost_energy : LREAL;                // purchase - revenue
	cost_grid : LREAL;
	cost_peak : LREAL;
	cost_total : LREAL;
	nLogged : DINT;                     // number of 15-min intervals logged (35040 after the final call)
END_VAR
