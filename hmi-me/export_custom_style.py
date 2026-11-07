from __future__ import print_function
import os
p=projects.primary
assert p.path.lower().endswith('me_v7_webvisu.project')
p.save()
path=r'C:\Users\sajic\Documents\plc-hackathon\hmi-me\Custom_style.export'
if os.path.exists(path): os.remove(path)
p.active_application.find('Overview',True)[0].export_native(path)
print('CUSTOM_STYLE_EXPORTED')
