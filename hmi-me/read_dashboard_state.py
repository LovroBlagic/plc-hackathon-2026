from __future__ import print_function
import os,time
base=r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
assert projects.primary.path.lower().endswith('me_v7_webvisu.project')
expressions=['SimCtrl.run','SimCtrl.k','SimCtrl.tripped','SimCtrl.price_mode',
 'SimCtrl.cycle_time_ms','Team_HMI.sDateTime','Team_HMI.rSoc',
 'Team_HMI.iSelDay','Team_HMI.iSelMonth','Team_Visu.iAlarmPage',
 'Team_Visu.xResetArmed','Team_HMI.aTrFne[95]','Team_HMI.aTrGrid[95]',
 'Team_HMI.aTrSoc[95]','Team_Results.cost_total']
with open(os.path.join(base,'dashboard_runtime.log'),'a') as f:
    f.write('\nREAD '+time.strftime('%H:%M:%S')+'\n')
    for expression in expressions:
        line='%s = %s' % (expression,oa.read_value(expression))
        f.write(line+'\n');print(line)
