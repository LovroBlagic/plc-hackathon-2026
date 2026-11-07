from __future__ import print_function
import os,time,json
year_directory=r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
assert projects.primary.path.lower().endswith('me_v7_webvisu.project')
def year_value(expression):
    raw=str(oa.read_value(expression)).strip()
    value=raw.split('#')[-1]
    if value.upper() in ('TRUE','FALSE'):return value.upper()=='TRUE'
    try:return float(value)
    except ValueError:return value.strip("'")
year_state={e:year_value(e) for e in ['SimCtrl.price_mode','SimCtrl.k','SimCtrl.run','SimCtrl.tripped','SimCtrl.finished','Team_HMI.sDateTime','Team_Results.nLogged','SimScore.total.cost_total','SimScore.total.E_ev_required','SimScore.total.E_ev_unmet']}
year_state['elapsed_s']=time.time()-json.load(open(os.path.join(year_directory,'full_year_s2_start.json')))['started']
year_state['percent']=100.0*year_state['SimCtrl.k']/35040.0
assert year_state['SimCtrl.price_mode']==1, 'S2 requires day-ahead mode'
with open(os.path.join(year_directory,'full_year_s2_progress.json'),'w') as f:json.dump(year_state,f,indent=2)
with open(os.path.join(year_directory,'full_year_s2_progress.jsonl'),'a') as f:f.write(json.dumps(year_state)+'\n')
print('HMI_YEAR_PROGRESS',json.dumps(year_state))
if year_state['SimCtrl.finished'] or year_state['SimCtrl.tripped']:
    year_fields=['E_fne','E_fec','E_bess_chg','E_bess_dch','E_ev','E_import','E_export','cost_energy','cost_grid','cost_peak','cost_total']
    year_state['totals']={}
    for field in year_fields:
        actual=year_value('SimScore.total.'+field)
        logged=year_value('Team_Results.'+field)
        error=abs(logged-actual)/max(1.0,abs(actual))*100
        year_state['totals'][field]={'official':actual,'logged':logged,'error_percent':error}
    year_state['max_logging_error_percent']=max(v['error_percent'] for v in year_state['totals'].values())
    year_state['ev_fulfilment_percent']=100*(1-year_state['SimScore.total.E_ev_unmet']/max(1,year_state['SimScore.total.E_ev_required']))
    year_state['pass']=bool(year_state['SimCtrl.finished'] and not year_state['SimCtrl.tripped'] and year_state['Team_Results.nLogged']==35040 and year_state['max_logging_error_percent']<=0.1 and year_state['SimScore.total.E_ev_unmet']<=0.001)
    with open(os.path.join(year_directory,'full_year_s2_result.json'),'w') as f:json.dump(year_state,f,indent=2)
    print('HMI_YEAR_RESULT',json.dumps(year_state))
