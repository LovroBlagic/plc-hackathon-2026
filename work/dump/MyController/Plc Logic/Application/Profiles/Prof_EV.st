// DATA_BLOCK "Prof_EV"
// NON_RETAIN
// EV sesije; indeks = punjac*300 + redni broj; Count = broj sesija po punjacu
   VAR_GLOBAL 
      Count : Array[0..3] of Int;
      Arr : Array[0..1199] of DInt;
      Dep : Array[0..1199] of DInt;
      Energy : Array[0..1199] of Real;
   END_VAR