TYPE typeSimTime:
// ---------------------------------------------------------------------
// Simulirano vrijeme (izvedeno iz brojaca koraka k)
// ---------------------------------------------------------------------
	STRUCT
		k : DINT;   // indeks koraka 0..35039
		DT_YEAR : UINT;
		DT_MONTH : USINT;
		DT_DAY : USINT;
		DT_WEEKDAY : USINT;
		DT_HOUR : USINT;
		DT_MINUTE : USINT;
		DT_SECOND : USINT;
		DT_NANOSECOND : USINT;
		stamp : DT;   // simulirani datum/vrijeme POCETKA intervala
		qh_of_day : Int;   // 0..95
		day_of_year : Int;   // 0..364
		month : Int;   // 1..12
		weekday : Int;   // 1=pon .. 7=ned
		tariff_high : Bool;   // TRUE = visa tarifa (VT)
	END_STRUCT
END_TYPE