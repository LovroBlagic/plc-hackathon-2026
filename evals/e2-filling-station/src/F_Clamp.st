FUNCTION F_Clamp : INT
VAR_INPUT
    iVal : INT;
    iMin : INT;
    iMax : INT;
END_VAR
// ---IMPL---
F_Clamp := MAX(iMin, MIN(iVal, iMax));
