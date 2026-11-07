FUNCTION F_DtString : STRING(20)
// DT -> "DD.MM.YYYY HH:MM" (simulated time). Pure calendar arithmetic, no clock access.
VAR_INPUT
	dtIn : DT;
END_VAR
VAR
	udSec : UDINT;
	iDoy : INT;
	iYear : INT;
	iMon : INT;
	iDim : INT;
	xLeap : BOOL;
	uH : USINT;
	uM : USINT;
END_VAR
// ---IMPL---
udSec := DT_TO_UDINT(dtIn);                          // seconds since 1970-01-01
uH := UDINT_TO_USINT((udSec MOD 86400) / 3600);
uM := UDINT_TO_USINT((udSec MOD 3600) / 60);
iDoy := UDINT_TO_INT(udSec / 86400);
iYear := 1970;
xLeap := FALSE;
WHILE iYear < 2200 DO
	xLeap := ((iYear MOD 4) = 0 AND (iYear MOD 100) <> 0) OR ((iYear MOD 400) = 0);
	IF xLeap THEN iDim := 366; ELSE iDim := 365; END_IF;
	IF iDoy < iDim THEN EXIT; END_IF;
	iDoy := iDoy - iDim;
	iYear := iYear + 1;
END_WHILE;
iMon := 1;
WHILE iMon < 12 DO
	CASE iMon OF
		2: IF xLeap THEN iDim := 29; ELSE iDim := 28; END_IF;
		4, 6, 9, 11: iDim := 30;
	ELSE
		iDim := 31;
	END_CASE;
	IF iDoy < iDim THEN EXIT; END_IF;
	iDoy := iDoy - iDim;
	iMon := iMon + 1;
END_WHILE;
F_DtString := CONCAT(CONCAT(CONCAT(F_Pad2(INT_TO_USINT(iDoy + 1)), '.'), CONCAT(F_Pad2(INT_TO_USINT(iMon)), '.')),
	CONCAT(CONCAT(INT_TO_STRING(iYear), ' '), CONCAT(CONCAT(F_Pad2(uH), ':'), F_Pad2(uM))));
