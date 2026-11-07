from __future__ import print_function
import os, glob
base = r'C:\Users\sajic\Documents\plc-hackathon'
assert projects.primary.path.lower().endswith('me_v7_webvisu.project')
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

open(os.path.join(base,'hmi-me','source_parity.log'),'w').write('FROZEN_V7_SOURCE_PARITY_PASS files=%d\n' % checked)
print('FROZEN_V7_SOURCE_PARITY_PASS files=%d' % checked)
