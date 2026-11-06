FUNCTION_BLOCK FB_FillStation
VAR_INPUT
    xStart, xStop, xBottle, xLevel, xReset : BOOL;
    stRecipe : ST_Recipe;
END_VAR
VAR_OUTPUT
    xConveyor, xValve, xCapper, xFault : BOOL;
    eState   : E_FillState;
    iCount   : INT;
END_VAR
VAR
    tonFill    : TON;   // watchdog: level must be reached within 2x fill time
    tonCap     : TON;
    rtStart    : R_TRIG;
    rtBottle   : R_TRIG;   // a NEW bottle must arrive (the capped one is still on the sensor)
    iBatch     : INT;
END_VAR
// ---IMPL---
rtStart(CLK := xStart);
rtBottle(CLK := xBottle);
iBatch := F_Clamp(stRecipe.iBatchSize, 1, 100);

IF NOT xStop AND eState <> E_FillState.FAULT THEN
    eState := E_FillState.IDLE;
END_IF

CASE eState OF
    E_FillState.IDLE:
        IF rtStart.Q AND xStop THEN
            iCount := 0;
            eState := E_FillState.WAIT_BOTTLE;
        END_IF
    E_FillState.WAIT_BOTTLE:
        IF rtBottle.Q THEN eState := E_FillState.FILLING; END_IF
    E_FillState.FILLING:
        IF xLevel THEN
            eState := E_FillState.CAPPING;
        ELSIF tonFill.Q THEN
            eState := E_FillState.FAULT;
        END_IF
    E_FillState.CAPPING:
        IF tonCap.Q THEN
            iCount := iCount + 1;
            IF iCount >= iBatch THEN eState := E_FillState.DONE; ELSE eState := E_FillState.WAIT_BOTTLE; END_IF
        END_IF
    E_FillState.DONE:
        IF rtStart.Q THEN iCount := 0; eState := E_FillState.WAIT_BOTTLE; END_IF
    E_FillState.FAULT:
        IF xReset THEN eState := E_FillState.IDLE; END_IF
END_CASE

tonFill(IN := eState = E_FillState.FILLING, PT := stRecipe.tFillTime * 2);
tonCap (IN := eState = E_FillState.CAPPING, PT := stRecipe.tCapTime);

xConveyor := eState = E_FillState.WAIT_BOTTLE;
xValve    := eState = E_FillState.FILLING;
xCapper   := eState = E_FillState.CAPPING;
xFault    := eState = E_FillState.FAULT;
