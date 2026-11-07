from __future__ import print_function
import os, sys
base = r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
p = projects.open(os.path.join(base, 'ME_v7_WebVisu.project'), primary=True)
app = p.active_application
for obj in app.find('Overview', True):
    obj.remove()
app.import_native([os.path.join(base, 'Overview_generated.export')])
p.save()
print('OVERVIEW_IMPORTED')
app.build()
errors = 0
for cat in system.get_message_categories(True):
    for msg in system.get_message_objects(cat):
        if str(msg.severity) in ('Error', 'FatalError', 'Warning'):
            print(str(msg.severity), msg.text)
            if 'Error' in str(msg.severity): errors += 1
print('HMI_BUILD_RESULT errors=%d' % errors)
p.save()
p.close()
sys.exit(1 if errors else 0)
