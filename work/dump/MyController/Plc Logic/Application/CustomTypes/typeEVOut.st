TYPE typeEVOut:
// VERSION : 0.1
// ---------------------------------------------------------------------
// Sucelje: izlazi simulatora (cita regulator)
// ---------------------------------------------------------------------
   STRUCT
      connected : Bool;
      planned_departure : DT;   // (odlazak iza kraja godine je ogranicen na zadnji korak)
      PD_DT_YEAR : UINT;
	  PD_DT_MONTH : USINT;
	  PD_DT_DAY : USINT;
	  PD_DT_WEEKDAY : USINT;
	  PD_DT_HOUR : USINT;
	  PD_DT_MINUTE : USINT;
	  PD_DT_SECOND : USINT;
	  PD_DT_NANOSECOND : USINT;
	  energy_required : REAL;   // [kWh] jos treba dostaviti (E* - E)
      energy_delivered : Real;   // [kWh] dostavljeno u sesiji
      P_charge_act : Real;   // [kW] ostvarena snaga u PROSLOM koraku
   END_STRUCT
END_TYPE