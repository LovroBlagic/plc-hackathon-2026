"""Import all generated HMI pages into the HMI copy only, then compile."""
from __future__ import print_function
import os, json, time
base = r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
p = projects.primary
assert p.path.lower().endswith('me_v7_webvisu.project')
app = p.active_application
p.save()
app.rebuild()
errors=[]; warnings=[]
for cat in system.get_message_categories(True):
    for msg in system.get_message_objects(cat):
        severity=str(msg.severity)
        if severity in ('Error','FatalError'): errors.append(str(msg.text))
        elif severity=='Warning':warnings.append(str(msg.text))
with open(os.path.join(base,'dashboard_rebuild.log'),'w') as report:
    report.write('DASHBOARD_BUILD_RESULT errors=%d warnings=%d\n'%(len(errors),len(warnings)))
    for line in errors:report.write('ERROR '+line+'\n')
    for line in warnings:report.write('WARNING '+line+'\n')
print('DASHBOARD_BUILD_RESULT errors=%d warnings=%d'%(len(errors),len(warnings)))
for line in errors:print('ERROR',line)
p.save()
