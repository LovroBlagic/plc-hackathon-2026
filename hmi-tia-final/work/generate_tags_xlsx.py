"""Generate native TIA HMI Excel tags from a GUI-exported, PLC-linked tag."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
import copy
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
ET.register_namespace('x', NS)
q = lambda n: '{%s}%s' % (NS, n)
with ZipFile(HERE / 'linked_tags.xlsx') as archive:
    files = {n: archive.read(n) for n in archive.namelist()}
sheet = ET.fromstring(files['xl/worksheets/sheet1.xml'])
strings = ET.fromstring(files['xl/sharedStrings.xml'])
values = [''.join(item.itertext()) for item in strings]
lookup = {value: index for index, value in enumerate(values)}

def string_id(value):
    value = str(value)
    if value not in lookup:
        lookup[value] = len(values)
        values.append(value)
        ET.SubElement(ET.SubElement(strings, q('si')), q('t')).text = value
    return lookup[value]

data = sheet.find(q('sheetData'))
prototype = copy.deepcopy(list(data)[1])
for row in list(data)[1:]:
    data.remove(row)
source = (ROOT / 'tia-src/03_HMI_IF.db').read_text(encoding='utf-8-sig')
body = source.split('VAR', 1)[1].split('END_VAR', 1)[0]
members = list(re.finditer(r'^\s*(\w+)\s*:\s*(?:Array\[(\d+)\.\.(\d+)\]\s+of\s+(\w+)|(\w+))', body, re.M))
lengths = {'Bool': 1, 'SInt': 1, 'USInt': 1, 'Byte': 1, 'Int': 2, 'UInt': 2, 'Word': 2, 'DInt': 4, 'UDInt': 4, 'DWord': 4, 'Real': 4}
manifest = []
for match in members:
    member, lo, hi, array_type, scalar_type = match.groups()
    typ = array_type or scalar_type
    assert typ in lengths, typ
    indices = [None] if lo is None else range(int(lo), int(hi) + 1)
    for index in indices:
        name = member if index is None else '%s_%02d' % (member, index)
        ref = 'HMI_IF.' + member + ('' if index is None else '[%d]' % index)
        number = len(manifest) + 2
        row = copy.deepcopy(prototype)
        row.set('r', str(number))
        replacements = {'A': name, 'B': 'HMI_IF_gen', 'C': 'HMI_Connection_1', 'D': ref,
                        'E': typ, 'F': str(lengths[typ]), 'G': 'IEEE754' if typ == 'Real' else 'Binary',
                        'O': ref, 'Q': '100 ms'}
        for cell in row:
            column = re.match(r'[A-Z]+', cell.get('r')).group()
            cell.set('r', column + str(number))
            if column in replacements:
                cell.set('t', 's')
                cell.find(q('v')).text = str(string_id(replacements[column]))
        data.append(row)
        manifest.append({'name': name, 'plc': ref, 'type': typ})
dimension = sheet.find(q('dimension'))
if dimension is not None:
    dimension.set('ref', 'A1:AG%d' % (len(manifest) + 1))
strings.set('uniqueCount', str(len(values)))
strings.set('count', str(sum(1 for node in sheet.iter(q('c')) if node.get('t') == 's')))
files['xl/worksheets/sheet1.xml'] = ET.tostring(sheet, encoding='utf-8', xml_declaration=True)
files['xl/sharedStrings.xml'] = ET.tostring(strings, encoding='utf-8', xml_declaration=True)
output = HERE / 'HMI_IF_gen.xlsx'
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for name, content in files.items():
        archive.writestr(name, content)
(HERE / 'tags_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('EXCEL_TAGS_GENERATED count=%d path=%s' % (len(manifest), output))
