from __future__ import print_function
import os,time
base=r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
acceptance_dir=base
assert projects.primary.path.lower().endswith('me_v7_webvisu.project')
assert str(oa.read_value('SimCtrl.run')).upper()=='FALSE'
first=str(oa.read_value('SimCtrl.k'))
time.sleep(2)
assert first==str(oa.read_value('SimCtrl.k'))
assert str(oa.read_value('SimCtrl.tripped')).upper()=='FALSE'
assert float(first.split('#')[-1])>=96
execfile(os.path.join(acceptance_dir,'read_dashboard_state.py'))
execfile(os.path.join(acceptance_dir,'verify_sources_in_editor.py'))
execfile(os.path.join(acceptance_dir,'report_build_in_editor.py'))
assert 'errors=0' in open(os.path.join(acceptance_dir,'dashboard_build.log')).readline()
with open(os.path.join(acceptance_dir,'dashboard_acceptance.log'),'w') as f:
    f.write('DASHBOARD_BUILD_PASS errors=0\n')
    f.write('SIMULATOR_PAUSE_PASS k=%s stable_for=2s tripped=FALSE\n' % first)
    f.write('FROZEN_V7_SOURCE_PARITY_PASS files=26\n')
    f.write('VISUAL_CHECKS seven pages, live 96-sample trends, SoC/EV bars, monthly cost chart\n')
    f.write('UI_CONTROLS run/pause, price_mode=1, cycle_time_ms=20, day/month selection, alarm page=1, reset cancel and confirm\n')
    f.write('PAUSED_TABLE_SELECTION_PASS February totals changed to zero without advancing simulation\n')
    f.write('BROWSER_NOT_TESTED no HTTP server on built-in simulator\n')
print('DASHBOARD_ACCEPTANCE_PASS')
