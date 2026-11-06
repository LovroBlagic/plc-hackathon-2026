// DATA_BLOCK "SimCtrl"
// { S7_Optimized_Access := 'TRUE' }
// VERSION : 0.1
// NON_RETAIN
// ---------------------------------------------------------------------
// Upravljanje simulacijom (HMI/organizator)
// ---------------------------------------------------------------------
   VAR_GLOBAL 
      run : Bool;   // TRUE = simulacija radi (pauza = FALSE)
      reset : Bool;   // 1 = reinicijalizacija (obradi se u OB30, sam se vraca na FALSE)
      price_mode : Int;   // 0 = dvotarifno, 1 = dan-unaprijed
      k : DInt;   // trenutni korak
      finished : BOOL;   // { ExternalWritable := 'False'}
      tripped : BOOL;   // { ExternalWritable := 'False'}
      stepActive : Bool;   // postavlja Sim_Core faza 1 --- promjena cycle timea (tvoja mreza SET_CINT) ---
      cycle_time_ms : UDInt;
      cycle_time_us : UDINT;   // { ExternalAccessible := 'False'; ExternalVisible := 'False'; ExternalWritable := 'False'}
      change_cycle : Bool;   // HMI: 1 -> primijeni cycle_time_ms
      change_cycle_P1 : BOOL;   // { ExternalAccessible := 'False'; ExternalVisible := 'False'; ExternalWritable := 'False'} memorijski bit za P_TRIG
      ret_val_cint : UDInt;   // { ExternalAccessible := 'False'; ExternalVisible := 'False'; ExternalWritable := 'False'}
   END_VAR