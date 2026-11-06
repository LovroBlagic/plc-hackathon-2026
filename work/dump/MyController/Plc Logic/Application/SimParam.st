// DATA_BLOCK "SimParam"
// NON_RETAIN
// ---------------------------------------------------------------------
// Globalni parametri
// ---------------------------------------------------------------------
   VAR_GLOBAL 
      TS_H : Real;
      SIM_YEAR : UInt;   // neprijestupna godina (365 d = 35040 koraka)
      START_WEEKDAY : Int;   // 1.1.2025. = srijeda (1=pon)
      FNE_MAX_POWER : Real;
      BESS_CAPACITY : Real;
      BESS_MAX_CHG : Real;
      BESS_MAX_DCH : Real;
      BESS_SOC_MIN : Real;   // (*) sigurnosna donja granica [%]
      BESS_SOC_MAX : Real;   // (*) sigurnosna gornja granica [%]
      BESS_SOC_INIT : Real;   // (*)
      BESS_ETA_CHG : Real;   // (*)
      BESS_ETA_DCH : Real;   // (*)
      EV_MAX_CHARGE : Real;
      EV_ETA : Real;   // (*)
      EGC_MAX_IMPORT : Real;
      EGC_MAX_EXPORT : Real;   // --- tarife (*) - uskladi s HEP Bijeli / srednji napon --- cijena ENERGIJE dolazi iz profila (Prof_PriceTT / Prof_PriceDA, EUR/kWh); VT/NT iz Prof_VT
      GRID_VT : Real;   // mrezarina VT [EUR/kWh]  (HEP ODS, Bijeli 2, SN, od 1.1.2025.)
      GRID_NT : Real;   // mrezarina NT [EUR/kWh]
      PEAK_PRICE : Real;   // vrsna snaga [EUR/kW po mjesecu]
      EXPORT_FACTOR : Real;   // (*) izvoz se placa cijena_energije * faktor
   END_VAR