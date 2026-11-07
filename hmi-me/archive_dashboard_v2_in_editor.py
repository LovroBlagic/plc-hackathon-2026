from __future__ import print_function
import os,time
base=r'C:\Users\sajic\Documents\plc-hackathon'
p=projects.primary
assert p.path.lower().endswith('me_v7_webvisu.project')
execfile(os.path.join(base,'hmi-me','verify_sources_in_editor.py'))
try:
    hmi_write({'SimCtrl.run':'FALSE'})
    oa.logout()
except Exception as exc: print('LOGOUT_NOTE',exc)
dev=[o for o in p.get_children() if o.is_device][0]
dev.set_simulation_mode(False)
p.save()
destination=os.path.join(base,'deliver','ME_v7_WebVisu_dashboard_v2.projectarchive')
assert not os.path.exists(destination), 'Keep existing archive; use a new version name'
p.save_archive(destination)
open(os.path.join(base,'hmi-me','dashboard_archive_v2.log'),'w').write('DASHBOARD_ARCHIVE_SAVED '+destination+'\n')
print('DASHBOARD_ARCHIVE_SAVED',destination)
