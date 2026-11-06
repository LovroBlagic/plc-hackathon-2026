// Team_Log: daily and monthly energy/cost tables (spec 4.2/4.3). Index = simulated day / month of interval k-1.
VAR_GLOBAL
	aDay : ARRAY[0..364] OF typeTeamAgg;    // day_of_year 0..364 (C_peak = 0, C_total = purchase - revenue + grid)
	aMonth : ARRAY[1..12] OF typeTeamAgg;   // month 1..12 incl. peak power P_peak and C_peak
	stYear : typeTeamAgg;                   // yearly totals (copied to Team_Results)
END_VAR
