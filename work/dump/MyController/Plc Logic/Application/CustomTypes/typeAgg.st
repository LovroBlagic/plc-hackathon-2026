TYPE typeAgg:
// VERSION : 0.1
// ---------------------------------------------------------------------
// Agregirane energije [kWh] i troskovi [EUR] - LReal zbog preciznosti
// ---------------------------------------------------------------------
   STRUCT
      E_fne : LReal;   // ostvarena proizvodnja FNE (nakon curtailmenta)
      E_fne_curtailed : LReal;   // energija odrezana curtailmentom
      E_fec : LReal;   // fiksna potrosnja
      E_bess_chg : LReal;   // punjenje baterije (sa strane sabirnice)
      E_bess_dch : LReal;   // praznjenje baterije (sa strane sabirnice)
      E_ev : LReal;   // energija na sabirnici predana punjacima
      E_ev_required : LReal;   // zatrazena energija (sesije zapoceta u periodu)
      E_ev_unmet : LReal;   // nepredana energija pri odlasku vozila
      E_import : LReal;
      E_export : LReal;
      P_peak : LReal;   // max snaga uvoza na 15-min intervalu [kW]
      cost_energy : LReal;   // trosak energije (uvoz - izvoz)
      cost_grid : LReal;   // mrezarina
      cost_peak : LReal;   // trosak vrsne snage
      cost_total : LReal;
   END_STRUCT
END_TYPE