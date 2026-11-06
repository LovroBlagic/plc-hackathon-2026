FUNCTION_BLOCK FB_CostLogger
// Task 3 (spec 4.3): cost logging [EUR] per day / month / year, from the energy of interval k-1
// and the energy price + grid-fee tariff of that same interval.
//   purchase = E_imp * c_en,  revenue = E_exp * 0.9 * c_en,  grid = E_imp * fee(VT/NT)
//   peak (month) = PEAK_PRICE * monthly import peak, year peak = sum of the 12 months
//   day total = purchase - revenue + grid ; month/year total also + peak
// Must be called AFTER FB_EnergyLogger in the same step (uses Team_Log.aMonth[m].P_peak).
VAR_INPUT
	xReset : BOOL;                      // k = 0 (tables are cleared by FB_EnergyLogger)
	xLog : BOOL;                        // log one interval
	iDay : INT;                         // day_of_year of interval k-1
	iMonth : INT;                       // month of interval k-1
	rImp : REAL;                        // EGC_P_import of interval k-1 [kW]
	rExp : REAL;                        // EGC_P_export of interval k-1 [kW]
	rPrice : REAL;                      // energy price of interval k-1 [EUR/kWh]
	xHigh : BOOL;                       // VT tariff of interval k-1 (grid fee)
END_VAR
VAR
	ts : LREAL;
	d : INT;
	m : INT;
	i : INT;
	cBuy : LREAL;
	cRev : LREAL;
	cGrid : LREAL;
	fee : LREAL;
	cPeakYear : LREAL;
END_VAR
// ---IMPL---
IF xLog THEN
	ts := REAL_TO_LREAL(SimParam.TS_H);
	d := LIMIT(0, iDay, 364);
	m := LIMIT(1, iMonth, 12);
	IF xHigh THEN
		fee := REAL_TO_LREAL(SimParam.GRID_VT);
	ELSE
		fee := REAL_TO_LREAL(SimParam.GRID_NT);
	END_IF;
	cBuy := REAL_TO_LREAL(rImp) * ts * REAL_TO_LREAL(rPrice);
	cRev := REAL_TO_LREAL(rExp) * ts * REAL_TO_LREAL(rPrice) * REAL_TO_LREAL(SimParam.EXPORT_FACTOR);
	cGrid := REAL_TO_LREAL(rImp) * ts * fee;

	// day (no peak component)
	Team_Log.aDay[d].C_purchase := Team_Log.aDay[d].C_purchase + cBuy;
	Team_Log.aDay[d].C_revenue := Team_Log.aDay[d].C_revenue + cRev;
	Team_Log.aDay[d].C_grid := Team_Log.aDay[d].C_grid + cGrid;
	Team_Log.aDay[d].C_total := Team_Log.aDay[d].C_purchase - Team_Log.aDay[d].C_revenue + Team_Log.aDay[d].C_grid;
	// month (peak known so far in this month)
	Team_Log.aMonth[m].C_purchase := Team_Log.aMonth[m].C_purchase + cBuy;
	Team_Log.aMonth[m].C_revenue := Team_Log.aMonth[m].C_revenue + cRev;
	Team_Log.aMonth[m].C_grid := Team_Log.aMonth[m].C_grid + cGrid;
	Team_Log.aMonth[m].C_peak := Team_Log.aMonth[m].P_peak * REAL_TO_LREAL(SimParam.PEAK_PRICE);
	Team_Log.aMonth[m].C_total := Team_Log.aMonth[m].C_purchase - Team_Log.aMonth[m].C_revenue
		+ Team_Log.aMonth[m].C_grid + Team_Log.aMonth[m].C_peak;
	// year
	Team_Log.stYear.C_purchase := Team_Log.stYear.C_purchase + cBuy;
	Team_Log.stYear.C_revenue := Team_Log.stYear.C_revenue + cRev;
	Team_Log.stYear.C_grid := Team_Log.stYear.C_grid + cGrid;
	cPeakYear := 0.0;
	FOR i := 1 TO 12 DO
		cPeakYear := cPeakYear + Team_Log.aMonth[i].C_peak;
	END_FOR;
	Team_Log.stYear.C_peak := cPeakYear;
	Team_Log.stYear.C_total := Team_Log.stYear.C_purchase - Team_Log.stYear.C_revenue
		+ Team_Log.stYear.C_grid + Team_Log.stYear.C_peak;
END_IF;

IF xReset OR xLog THEN
	Team_Results.C_purchase := Team_Log.stYear.C_purchase;
	Team_Results.C_revenue := Team_Log.stYear.C_revenue;
	Team_Results.C_grid := Team_Log.stYear.C_grid;
	Team_Results.C_peak := Team_Log.stYear.C_peak;
	Team_Results.C_total := Team_Log.stYear.C_total;
	// simulator (SimScore.total) naming
	Team_Results.cost_energy := Team_Log.stYear.C_purchase - Team_Log.stYear.C_revenue;
	Team_Results.cost_grid := Team_Log.stYear.C_grid;
	Team_Results.cost_peak := Team_Log.stYear.C_peak;
	Team_Results.cost_total := Team_Log.stYear.C_total;
END_IF;
