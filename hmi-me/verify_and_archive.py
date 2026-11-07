from __future__ import print_function
import os, glob, time
base = r'C:\Users\sajic\Documents\plc-hackathon'
assert projects.primary.path.lower().endswith('me_v7_webvisu.project')
assert str(oa.read_value('SimCtrl.run')).strip().upper() == 'FALSE', 'Pause using the actual HMI button first'
first = str(oa.read_value('SimCtrl.k'))
time.sleep(2)
last = str(oa.read_value('SimCtrl.k'))
assert first == last, 'Step counter advanced while paused'
assert str(oa.read_value('SimCtrl.tripped')).strip().upper() == 'FALSE'
app = projects.primary.active_application
def norm(text):
    return text.replace('\r\n', '\n').strip()
checked = 0
for path in glob.glob(os.path.join(base, 'deliver', 'ME_v7_src', '*.st')):
    raw = open(path, 'rb').read()
    if raw.startswith('\xef\xbb\xbf'): raw = raw[3:]
    text = raw.decode('utf-8')
    pieces = text.split('// ---IMPL---', 1)
    name = os.path.splitext(os.path.basename(path))[0]
    objs = [o for o in app.find(name, True) if getattr(o, 'has_textual_declaration', False)]
    assert objs, 'Missing frozen source: ' + name
    assert norm(objs[0].textual_declaration.text) == norm(pieces[0]), 'Declaration changed: ' + name
    if len(pieces) > 1:
        assert norm(objs[0].textual_implementation.text) == norm(pieces[1]), 'Implementation changed: ' + name
    checked += 1
with open(os.path.join(base, 'hmi-me', 'control_test_result.log'), 'w') as result:
    result.write('HMI_BUTTON_PAUSE_PASS k=%s stable_for=2s tripped=FALSE\n' % first)
    result.write('FROZEN_V7_SOURCE_PARITY_PASS files=%d\n' % checked)
print('HMI_BUTTON_PAUSE_PASS k=%s' % first)
print('FROZEN_V7_SOURCE_PARITY_PASS files=%d' % checked)
execfile(os.path.join(base, 'hmi-me', 'archive_in_editor.py'))
