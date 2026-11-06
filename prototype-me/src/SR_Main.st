PROGRAM SR_Main
VAR
    fbConveyor : FB_MotorStartStop;
    xStartPB   : BOOL;
    xStopPB    : BOOL := TRUE;
    xOverload  : BOOL;
END_VAR
// ---IMPL---
fbConveyor(xStart := xStartPB, xStop := xStopPB, xFault := xOverload);
