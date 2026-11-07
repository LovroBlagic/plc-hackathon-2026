"""Keep the HMI copy online for direct visualization/button verification."""
from __future__ import print_function
import os, time
base = r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
current = projects.primary
assert current.path.lower().endswith('me_v7_webvisu.project')
app = current.active_application
dev = [obj for obj in current.get_children() if obj.is_device][0]
dev.set_simulation_mode(True)
oa = online.create_online_application(app)
oa.login(OnlineChangeOption.Never, True)
oa.start()
def hmi_write(values):
    for key, value in values.items(): oa.set_prepared_value(key, value)
    oa.write_prepared_values()
hmi_write({'SimCtrl.run': 'FALSE', 'SimCtrl.change_cycle': 'FALSE'})
time.sleep(0.5)
hmi_write({'SimCtrl.price_mode': '0', 'SimCtrl.cycle_time_ms': '10',
           'SimCtrl.change_cycle': 'TRUE', 'SimCtrl.reset': 'TRUE'})
time.sleep(1)
hmi_write({'SimCtrl.change_cycle': 'FALSE'})
with open(os.path.join(base, 'online_ready.log'), 'w') as result:
    for expr in ['SimCtrl.run', 'SimCtrl.k', 'SimCtrl.tripped', 'Team_HMI.sDateTime', 'Team_HMI.rSoc']:
        line = '%s = %s' % (expr, oa.read_value(expr))
        print(line)
        result.write(line + '\n')
print('ONLINE_EDITOR_READY: paused at reset; test the native RUN / PAUSE button')
