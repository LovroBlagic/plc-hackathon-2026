FUNCTION_BLOCK FB_MotorStartStop
VAR_INPUT
    xStart     : BOOL;          // NO push button
    xStop      : BOOL;          // NC push button (TRUE = not pressed)
    xFault     : BOOL;          // motor protection tripped
    tStartDelay: TIME := T#2S;  // warning horn time before motor runs
END_VAR
VAR_OUTPUT
    xHorn      : BOOL;
    xMotor     : BOOL;
    xFaultLamp : BOOL;
END_VAR
VAR
    xRunReq    : BOOL;
    tonDelay   : TON;
END_VAR
// ---IMPL---
// Seal-in start request; stop or fault breaks it
xRunReq := (xStart OR xRunReq) AND xStop AND NOT xFault;

tonDelay(IN := xRunReq, PT := tStartDelay);
xHorn  := xRunReq AND NOT tonDelay.Q;
xMotor := tonDelay.Q;
xFaultLamp := xFault;
