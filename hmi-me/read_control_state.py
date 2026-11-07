from __future__ import print_function
import os, time
base = r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
assert projects.primary.path.lower().endswith('me_v7_webvisu.project')
exprs = ['SimCtrl.run', 'SimCtrl.k', 'SimCtrl.tripped', 'Team_HMI.sDateTime', 'Team_HMI.rSoc']
with open(os.path.join(base, 'control_state.log'), 'a') as result:
    result.write('CHECK %.3f\n' % time.time())
    for expr, value in zip(exprs, oa.read_values(exprs)):
        line = '%s = %s' % (expr, value)
        print(line)
        result.write(line + '\n')
