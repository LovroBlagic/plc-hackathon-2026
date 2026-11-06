FUNCTION Sim_Accumulate : BOOL
VAR_INPUT
      ts : LREAL;   // [h]
      pFne : LReal;
      pFneCurt : LReal;
      pFec : LReal;
      pChg : LReal;
      pDch : LReal;
      pEv : LReal;
      pImp : LReal;
      pExp : LReal;
      costEnergy : LReal;   // [EUR] za ovaj korak
      costGrid : LReal;   // [EUR] za ovaj korak
END_VAR
VAR_IN_OUT
      agg : typeAgg;
END_VAR
VAR
END_VAR

// ---IMPL---
// FUNCTION "Sim_Accumulate"
// ---------------------------------------------------------------------
// Dodaje jedan korak (15 min) u agregat. Vrijednosti snaga u [kW].
// ---------------------------------------------------------------------
	agg.E_fne := agg.E_fne + pFne * ts;
	agg.E_fne_curtailed := agg.E_fne_curtailed + pFneCurt * ts;
	agg.E_fec := agg.E_fec + pFec * ts;
	agg.E_bess_chg := agg.E_bess_chg + pChg * ts;
	agg.E_bess_dch := agg.E_bess_dch + pDch * ts;
	agg.E_ev := agg.E_ev + pEv * ts;
	agg.E_import := agg.E_import + pImp * ts;
	agg.E_export := agg.E_export + pExp * ts;
	IF pImp > agg.P_peak THEN
	    agg.P_peak := pImp;
	END_IF;
	agg.cost_energy := agg.cost_energy + costEnergy;
	agg.cost_grid := agg.cost_grid + costGrid;
	agg.cost_total := agg.cost_energy + agg.cost_grid + agg.cost_peak;