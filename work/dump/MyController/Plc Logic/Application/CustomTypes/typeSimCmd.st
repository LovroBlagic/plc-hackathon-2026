TYPE typeSimCmd:
// VERSION : 0.1
   STRUCT
      FNE_enable_curtail : BOOL;
      FNE_curtail_value : REAL;   // [kW]
      BESS_enable_charge : BOOL;
      BESS_P_charge : REAL;   // [kW]
      BESS_enable_discharge : BOOL;
      BESS_P_discharge : REAL;   // [kW]
      EV : Array[0..3] of typeEVCmd;
   END_STRUCT
END_TYPE