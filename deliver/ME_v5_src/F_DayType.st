FUNCTION F_DayType : INT
// Day type for load forecasting: 0 = Monday..Friday, 1 = Saturday, 2 = Sunday.
VAR_INPUT
	iWeekday : INT;                     // 1 = Monday .. 7 = Sunday
END_VAR
// ---IMPL---
IF iWeekday = 6 THEN
	F_DayType := 1;
ELSIF iWeekday = 7 THEN
	F_DayType := 2;
ELSE
	F_DayType := 0;
END_IF;
