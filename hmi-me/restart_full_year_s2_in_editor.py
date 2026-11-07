from __future__ import print_function
import os,time,json
year_directory=r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
assert projects.primary.path.lower().endswith('me_v7_webvisu.project')
hmi_write({'SimCtrl.run':'FALSE','SimCtrl.change_cycle':'FALSE'})
time.sleep(.2)
hmi_write({'SimCtrl.price_mode':'1','SimCtrl.cycle_time_ms':'10','SimCtrl.change_cycle':'TRUE','SimCtrl.reset':'TRUE'})
time.sleep(.5)
hmi_write({'SimCtrl.change_cycle':'FALSE'})
assert str(oa.read_value('SimCtrl.k')).split('#')[-1]=='0'
year_started=time.time()
with open(os.path.join(year_directory,'full_year_s2_start.json'),'w') as f:
    json.dump({'started':year_started,'mode':1,'cycle_ms':10,'baseline_cost':169833.86},f)
hmi_write({'SimCtrl.run':'TRUE'})
print('HMI_FULL_YEAR_RESTARTED_FROM_ZERO mode=1 cycle_ms=10')
