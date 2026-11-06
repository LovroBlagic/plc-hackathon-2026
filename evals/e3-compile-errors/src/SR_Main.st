PROGRAM SR_Main
VAR
    eMode  : E_Mode;
    iCount : INT;
    xOut   : BOOL;
END_VAR
// ---IMPL---
IF eMode = AUTO THEN
    iCount := iCount + 1
END_IF
xOut := iCount;
rTemp := 1.5;
