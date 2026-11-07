from __future__ import print_function
import os,time,json
year_directory=r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
execfile(os.path.join(year_directory,'online_in_editor.py'))
year_started=time.time()
hmi_write({'SimCtrl.run':'TRUE'})
with open(os.path.join(year_directory,'full_year_start.json'),'w') as f:
    json.dump({'started':year_started,'mode':0,'cycle_ms':10,'baseline_cost':204598.62},f)
print('HMI_FULL_YEAR_STARTED mode=0 cycle_ms=10; GUI remains free to render live HMI')
