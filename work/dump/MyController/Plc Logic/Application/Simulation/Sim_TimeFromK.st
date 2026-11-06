FUNCTION Sim_TimeFromK : BOOL
VAR_INPUT
      k : DINT;
END_VAR
VAR_OUTPUT
      t : typeSimTime;
END_VAR
VAR
	day : INT;
	qh : Int;
	m : Int;
	hour : Int;
	wd : INT;	
	DT_Set_DB : Datum_Vrijeme_Set;
END_VAR
// ---IMPL---
// FUNCTION "Sim_TimeFromK"
// =====================================================================
// ---------------------------------------------------------------------
// k -> simulirano vrijeme, tarifni sat, DTL
// ---------------------------------------------------------------------
	day := DINT_TO_INT(k / 96);
	qh := DINT_TO_INT(k MOD 96);
	hour := qh / 4;
	
	// mjesec: CumDays[m-1] <= day < CumDays[m]
	m := 1;
	WHILE m < 12 AND day >= SimCal.CumDays[m] DO
	    m := m + 1;
	END_WHILE;
	
	// 1=pon .. 7=ned
	wd := (((SimParam.START_WEEKDAY - 1) + day) MOD 7) + 1;
	
	t.k := k;
	t.qh_of_day := qh;
	t.day_of_year := day;
	t.month := m;
	t.weekday := wd;
	t.tariff_high := FALSE;                   // postavlja Sim_Core iz profila Prof_VT
	
	// DT
	t.DT_YEAR := SimParam.SIM_YEAR;
	t.DT_MONTH := INT_TO_USINT(m);
	t.DT_DAY := INT_TO_USINT(day - SimCal.CumDays[m - 1] + 1);
	t.DT_WEEKDAY := INT_TO_USINT((wd MOD 7) + 1);
	t.DT_HOUR := INT_TO_USINT(hour);
	t.DT_MINUTE := INT_TO_USINT((qh MOD 4) * 15);
	t.DT_SECOND := 0;
	t.DT_NANOSECOND := 0;
	DT_Set_DB (IN_Year := UINT_TO_INT(t.DT_YEAR),
				IN_Month := t.DT_MONTH,
				IN_Day := t.DT_DAY,
				IN_Hour := t.DT_HOUR,
				IN_Minute := t.DT_MINUTE,
				IN_Second := t.DT_SECOND,
				OUT_Date_Time => t.stamp);