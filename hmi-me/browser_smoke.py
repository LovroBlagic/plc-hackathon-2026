"""Run only the separate HMI project in the ME simulator for browser verification."""
from __future__ import print_function
import os, sys, time
base = r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
p = projects.open(os.path.join(base, 'ME_v7_WebVisu.project'), primary=True)
app = p.active_application
for name in ('Overview', 'Visualization Manager', 'WebVisu'):
    matches = app.find(name, True)
    if not matches:
        raise Exception('Missing HMI object: ' + name)
    print('HMI_OBJECT', name)
    matches[0].export_native(os.path.join(base, name.replace(' ', '_') + '_current.export'))
sys.stdout.flush()
dev = [obj for obj in p.get_children() if obj.is_device][0]
dev.set_simulation_mode(True)
oa = online.create_online_application(app)
try:
    oa.login(OnlineChangeOption.Never, True)
    oa.start()
    print('HMI_SIM_LOGGED_IN')
    sys.stdout.flush()
    def write(values):
        for key, value in values.items(): oa.set_prepared_value(key, value)
        oa.write_prepared_values()
    write({'SimCtrl.run': 'FALSE', 'SimCtrl.change_cycle': 'FALSE'})
    time.sleep(0.5)
    write({'SimCtrl.price_mode': '0', 'SimCtrl.cycle_time_ms': '10',
           'SimCtrl.change_cycle': 'TRUE', 'SimCtrl.reset': 'TRUE'})
    time.sleep(1)
    write({'SimCtrl.change_cycle': 'FALSE', 'SimCtrl.run': 'TRUE'})
    time.sleep(12)
    write({'SimCtrl.run': 'FALSE'})
    time.sleep(1)
    exprs = ['SimCtrl.k', 'SimCtrl.tripped', 'Team_HMI.sDateTime', 'Team_HMI.rSoc',
             'Team_HMI.rGridPred', 'Team_Results.cost_total']
    for key, value in zip(exprs, oa.read_values(exprs)):
        print('HMI_VALUE', key, value)
    print('HMI_BROWSER_READY hold_seconds=180')
    sys.stdout.flush()
    for n in range(180):
        time.sleep(1)
        if n % 30 == 29:
            print('HMI_HOLD', n + 1)
            sys.stdout.flush()
finally:
    try:
        write({'SimCtrl.run': 'FALSE'})
        oa.logout()
    except Exception:
        pass
    dev.set_simulation_mode(False)
    p.save()
    p.close()
print('HMI_SMOKE_COMPLETE')
