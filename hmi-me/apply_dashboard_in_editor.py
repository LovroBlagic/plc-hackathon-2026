"""Import all generated HMI pages into the HMI copy only, then compile."""
from __future__ import print_function
import os, json, time
base = r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
p = projects.primary
assert p.path.lower().endswith('me_v7_webvisu.project')
app = p.active_application
def stage(message):
    with open(os.path.join(base,'dashboard_import_stage.log'),'a') as f:
        f.write(time.strftime('%H:%M:%S ') + message + '\n')
stage('BEGIN')
manifest = json.load(open(os.path.join(base, 'generated', 'manifest.json')))
for obj in app.find('StyleProbe', True):
    if str(obj.type).lower().strip('{}') == 'f18bec89-9fef-401d-9953-2f11739a6808': obj.remove()
gvl = [o for o in app.find('Team_Visu', True) if getattr(o, 'has_textual_declaration', False)]
gvl = gvl[0] if gvl else app.create_gvl('Team_Visu')
gvl.textual_declaration.replace(open(os.path.join(base, 'generated', 'Team_Visu.st'), 'rb').read().decode('utf-8'))
for page in manifest:
    stage('REMOVE '+page['page'])
    for obj in app.find(page['page'], True):
        if str(obj.type).lower().strip('{}') == 'f18bec89-9fef-401d-9953-2f11739a6808': obj.remove()
stage('IMPORT')
app.import_native([os.path.join(base, 'generated', page['file']) for page in manifest])
stage('SAVE')
p.save()
stage('BUILD')
app.build()
stage('BUILD COMPLETE')
errors=[]; warnings=[]
for cat in system.get_message_categories(True):
    if system.get_message_category_description(cat) not in ('Build','Additional code checks'): continue
    for msg in system.get_message_objects(cat):
        severity=str(msg.severity)
        if severity in ('Error','FatalError'): errors.append(str(msg.text))
        elif severity=='Warning':warnings.append(str(msg.text))
with open(os.path.join(base,'dashboard_build.log'),'w') as report:
    report.write('DASHBOARD_BUILD_RESULT errors=%d warnings=%d\n'%(len(errors),len(warnings)))
    for line in errors:report.write('ERROR '+line+'\n')
    for line in warnings:report.write('WARNING '+line+'\n')
print('DASHBOARD_BUILD_RESULT errors=%d warnings=%d'%(len(errors),len(warnings)))
for line in errors:print('ERROR',line)
p.save()
