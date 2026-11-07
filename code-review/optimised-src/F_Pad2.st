FUNCTION F_Pad2 : STRING(2)
// Two-digit zero padded number for date/time strings.
VAR_INPUT
	v : USINT;
END_VAR
// ---IMPL---
IF v < 10 THEN
	F_Pad2 := CONCAT('0', USINT_TO_STRING(v));
ELSE
	F_Pad2 := USINT_TO_STRING(v);
END_IF;
