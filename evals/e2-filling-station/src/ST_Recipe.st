TYPE ST_Recipe :
STRUCT
    tFillTime  : TIME := T#1S;
    tCapTime   : TIME := T#500MS;
    iBatchSize : INT  := 3;
END_STRUCT
END_TYPE
