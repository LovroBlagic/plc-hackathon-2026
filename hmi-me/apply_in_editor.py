"""Run from Scripting Immediate; switches from the seed to the HMI copy only."""
from __future__ import print_function
import os
base = r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
current = projects.primary
assert current.path.lower().endswith(('controlseed.project', 'me_v7_webvisu.project'))
if current.path.lower().endswith('controlseed.project'):
    current.save()
    current.close()
    current = projects.open(os.path.join(base, 'ME_v7_WebVisu.project'), primary=True)
app = current.active_application
for obj in app.find('Overview', True): obj.remove()
app.import_native([os.path.join(base, 'Overview_generated.export')])
current.save()
app.build()
errors = []
for cat in system.get_message_categories(True):
    for msg in system.get_message_objects(cat):
        if str(msg.severity) in ('Error', 'FatalError'): errors.append(msg.text)
with open(os.path.join(base, 'editor_build.log'), 'w') as result:
    result.write('HMI_BUILD_RESULT errors=%d\n' % len(errors))
    for err in errors: result.write(str(err) + '\n')
print('HMI_BUILD_RESULT errors=%d' % len(errors))
current.save()
