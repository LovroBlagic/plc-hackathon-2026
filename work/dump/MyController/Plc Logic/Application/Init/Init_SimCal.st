FUNCTION_BLOCK Init_SimCal
VAR_INPUT
END_VAR
VAR_OUTPUT
END_VAR
VAR
END_VAR

// ---IMPL---
// Inicijalizacija GVL "SimCal"
   SimCal.CumDays[0] := 0;
   SimCal.CumDays[1] := 31;
   SimCal.CumDays[2] := 59;
   SimCal.CumDays[3] := 90;
   SimCal.CumDays[4] := 120;
   SimCal.CumDays[5] := 151;
   SimCal.CumDays[6] := 181;
   SimCal.CumDays[7] := 212;
   SimCal.CumDays[8] := 243;
   SimCal.CumDays[9] := 273;
   SimCal.CumDays[10] := 304;
   SimCal.CumDays[11] := 334;
   SimCal.CumDays[12] := 365;