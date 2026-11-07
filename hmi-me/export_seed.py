from __future__ import print_function
import os
base = r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
p = projects.open(os.path.join(base, 'ME_v7_WebVisu.project'), primary=True)
app = p.active_application
for obj in app.get_children(False):
    print('OBJECT', obj.get_name(), obj.type)
for name in ['Overview', 'Visualization Manager']:
    found = app.find(name, True)
    if found:
        found[0].export_xml(path=os.path.join(base, name.replace(' ', '_') + '_seed.xml'), recursive=True)
        print('EXPORTED', name)
        found[0].export_native(os.path.join(base, name.replace(' ', '_') + '.export'))
        print('NATIVE_EXPORTED', name)
p.close()
