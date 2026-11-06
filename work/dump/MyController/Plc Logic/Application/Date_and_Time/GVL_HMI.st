VAR_GLOBAL
	// PLC datum i vrijeme - DT format SET
	PLC_Datum_Vrijeme_Get_DT : DT;
	// PLC datum i vrijeme - trenutna godina
	PLC_Datum_Vrijeme_Godina AT %MW490: INT;
	// PLC datum i vrijeme - trenutni mjesec
	PLC_Datum_Vrijeme_Mjesec AT %MW491: INT;
	// PLC datum i vrijeme - trenutni dan
	PLC_Datum_Vrijeme_Dan AT %MW492: INT;
	// PLC datum i vrijeme - trenutni sat
	PLC_Datum_Vrijeme_Sat AT %MW493: INT;
	// PLC datum i vrijeme - trenutna minuta
	PLC_Datum_Vrijeme_Minuta AT %MW494: INT;
	// PLC datum i vrijeme - trenutna sekunda
	PLC_Datum_Vrijeme_Sekunda AT %MW495: INT;

	// PLC datum i vrijeme - DT format GET
	PLC_Datum_Vrijeme_Set_DT : DT;
	promjeni : BOOL;
	
	// Parametar - PLC datum i vrijeme - godina
	PAR_PLC_Datum_Vrijeme_Godina AT %MW1020: INT;
	// Parametar - PLC datum i vrijeme - mjesec
	PAR_PLC_Datum_Vrijeme_Mjesec AT %MW1021: INT;
	// Parametar - PLC datum i vrijeme - dan
	PAR_PLC_Datum_Vrijeme_Dan AT %MW1022: INT;
	// Parametar - PLC datum i vrijeme - sat
	PAR_PLC_Datum_Vrijeme_Sat AT %MW1023: INT;
	// Parametar - PLC datum i vrijeme - minuta
	PAR_PLC_Datum_Vrijeme_Minuta AT %MW1024: INT;
	// Parametar - PLC datum i vrijeme - sekunda
	PAR_PLC_Datum_Vrijeme_Sekunda AT %MW1025: INT;
END_VAR