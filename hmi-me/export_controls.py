from __future__ import print_function
import os
base = r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
p = projects.open(os.path.join(base, 'ControlSeed.project'), primary=True)
p.active_application.find('Overview', True)[0].export_native(os.path.join(base, 'Controls_seed.export'))
p.close()
print('CONTROL_SEED_EXPORTED')
