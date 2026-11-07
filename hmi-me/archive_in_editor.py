"""Archive the HMI prototype separately; leave frozen optimisation archive untouched."""
from __future__ import print_function
import os
base = r'C:\Users\sajic\Documents\plc-hackathon'
current = projects.primary
assert current.path.lower().endswith('me_v7_webvisu.project')
try:
    hmi_write({'SimCtrl.run': 'FALSE'})
    oa.logout()
except Exception as exc:
    print('HMI_LOGOUT_NOTE', exc)
dev.set_simulation_mode(False)
current.save()
archive_path = os.path.join(base, 'deliver', 'ME_v7_WebVisu_overview_prototype.projectarchive')
current.save_archive(archive_path)
with open(os.path.join(base, 'hmi-me', 'archive.log'), 'w') as result:
    result.write('HMI_ARCHIVE_SAVED ' + archive_path + '\n')
print('HMI_ARCHIVE_SAVED', archive_path)
