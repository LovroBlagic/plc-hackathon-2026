TYPE typeTeamAgg :
// Team energy [kWh] and cost [EUR] aggregate for one day, one month or the year.
// Names follow spec tables 12 (energies) and 4.3 (cost components). LREAL accumulators.
STRUCT
	E_fne : LREAL;                      // PV production after curtailment (FNE_P_act)
	E_fec : LREAL;                      // fixed consumption (FEC_P_fix remembered from k-1)
	E_bess_chg : LREAL;                 // battery charging, bus side
	E_bess_dch : LREAL;                 // battery discharging, bus side
	E_ev : LREAL;                       // all EV chargers, bus side
	E_ev_ch : ARRAY[0..3] OF LREAL;     // per EV charger, bus side
	E_import : LREAL;                   // grid import
	E_export : LREAL;                   // grid export
	P_peak : LREAL;                     // [kW] max 15-min import (monthly value; also kept per day for info)
	C_purchase : LREAL;                 // energy purchase = import * c_en
	C_revenue : LREAL;                  // export revenue = export * 0.9 * c_en
	C_grid : LREAL;                     // grid fee on import (VT/NT)
	C_peak : LREAL;                     // peak power cost (month/year only; 0 for days)
	C_total : LREAL;                    // purchase - revenue + grid (+ peak for month/year)
END_STRUCT
END_TYPE
