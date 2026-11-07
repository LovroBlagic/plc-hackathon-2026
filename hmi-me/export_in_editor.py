from __future__ import print_function
import os
base = r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
p = projects.primary
assert p.path.lower().endswith('controlseed.project'), 'Use only the ControlSeed copy'
p.save()
p.active_application.find('Overview', True)[0].export_native(os.path.join(base, 'Controls_bound.export'))
print('CONTROLS_BOUND_EXPORTED')
