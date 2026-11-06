TYPE typeSimOut:
// VERSION : 0.1
   STRUCT
      t_sim : typeSimTime;
      FNE_output_power : Real;   // [kW] RASPOLOZIVA snaga u intervalu k (prije curtailmenta)
      FNE_P_act : Real;   // [kW] ostvarena snaga u proslom koraku
      FEC_P_fix : Real;   // [kW] fiksna potrosnja u intervalu k
      BESS_SoC : Real;   // [%] na pocetku intervala k
      BESS_P_charge_act : Real;   // [kW] ostvareno u proslom koraku
      BESS_P_discharge_act : Real;   // [kW] ostvareno u proslom koraku
      EV : ARRAY[0..3] OF typeEVOut;
      EGC_P_import : Real;   // [kW] izmjereno u PROSLOM koraku (k-1)
      EGC_P_export : Real;   // [kW] izmjereno u PROSLOM koraku (k-1)
      EGC_overload_import : Bool;
      EGC_overload_export : Bool;
      sim_finished : Bool;
      sim_tripped : Bool;   // postrojenje odspojeno (overload) - latch
   END_STRUCT
END_TYPE