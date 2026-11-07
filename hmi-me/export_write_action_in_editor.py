from __future__ import print_function
import os
base = r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
p = projects.primary
assert p.path.lower().endswith('me_v7_webvisu.project')
p.save()
destination = os.path.join(base, 'Write_action_seed.export')
if os.path.exists(destination): os.remove(destination)
p.active_application.find('Overview', True)[0].export_native(destination)
print('WRITE_ACTION_SEED_EXPORTED')
