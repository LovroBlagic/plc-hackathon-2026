from __future__ import print_function
import os
base = r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
p = projects.primary
assert p.path.lower().endswith('me_v7_webvisu.project')
app = p.active_application
found = [o for o in app.find('Team_Visu', True) if getattr(o, 'has_textual_declaration', False)]
gvl = found[0] if found else app.create_gvl('Team_Visu')
hours = ', '.join('%.2f' % ((i - 95) * 0.25) for i in range(96))
gvl.textual_declaration.replace('VAR_GLOBAL CONSTANT\n aHours : ARRAY[0..95] OF REAL := [' + hours + '];\nEND_VAR\n')
p.save()
destination = os.path.join(base, 'Graphics_seed.export')
if os.path.exists(destination): os.remove(destination)
app.find('Overview', True)[0].export_native(destination)
print('GRAPHICS_SEED_EXPORTED')
