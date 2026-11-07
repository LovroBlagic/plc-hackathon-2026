from __future__ import print_function
import os
base = r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
p = projects.primary
assert p.path.lower().endswith('me_v7_webvisu.project')
app = p.active_application
for obj in app.find('StyleProbe', True):
    if str(obj.type).lower().strip('{}') == 'f18bec89-9fef-401d-9953-2f11739a6808': obj.remove()
app.import_native([os.path.join(base, 'generated', 'StyleProbe.export')])
app.build()
with open(os.path.join(base,'style_probe.log'),'w') as f:
    for cat in system.get_message_categories(True):
        for msg in system.get_message_objects(cat):
            f.write('%s %s\n' % (msg.severity, msg.text))
print('STYLE_PROBE_FINISHED')
