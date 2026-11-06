PROGRAM SR_Main
VAR
    fbStation : FB_FillStation;
    stRecipe  : ST_Recipe := (tFillTime := T#1S, tCapTime := T#300MS, iBatchSize := 2);
END_VAR
// ---IMPL---
fbStation(xStart := GVL_IO.xStart, xStop := GVL_IO.xStop, xBottle := GVL_IO.xBottlePresent,
          xLevel := GVL_IO.xLevelReached, xReset := GVL_IO.xReset, stRecipe := stRecipe);
GVL_IO.xConveyor  := fbStation.xConveyor;
GVL_IO.xValve     := fbStation.xValve;
GVL_IO.xCapper    := fbStation.xCapper;
GVL_IO.xLampFault := fbStation.xFault;
