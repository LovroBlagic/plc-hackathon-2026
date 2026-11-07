"""Clone a native TIA alarm workbook, preserving its metadata and exact columns."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
import copy
import importlib.util
import json
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('alarm_definitions', ROOT / 'hmi-tia/alarms_gen.py')
defs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(defs)
NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
ET.register_namespace('x', NS)
q = lambda name: '{%s}%s' % (NS, name)
with ZipFile(HERE / 'alarm_sample.xlsx') as archive:
    files = {name: archive.read(name) for name in archive.namelist()}
sheet = ET.fromstring(files['xl/worksheets/sheet1.xml'])
strings = ET.fromstring(files['xl/sharedStrings.xml'])
values = [''.join(item.itertext()) for item in strings]
lookup = {value: index for index, value in enumerate(values)}

def get_cell(cell):
    value = cell.find(q('v')).text
    return values[int(value)] if cell.get('t') == 's' else value

def string_id(value):
    value = str(value)
    if value not in lookup:
        lookup[value] = len(values)
        values.append(value)
        ET.SubElement(ET.SubElement(strings, q('si')), q('t')).text = value
    return lookup[value]

data = sheet.find(q('sheetData'))
headers = [get_cell(cell) for cell in data[0]]
prototype = copy.deepcopy(data[1])
for row in list(data)[1:]:
    data.remove(row)
rows = [defs.row_values(headers, item, 'AlarmWord', 'Warnings') for item in defs.ALARMS]
rows += [defs.row_values(headers, item, 'AlarmWord2', 'Warnings', id_base=17, word='AlarmWord2') for item in defs.ALARMS2]
if '--no-plc-ack' in sys.argv:
    for row in rows:
        row[headers.index('PLC acknowledgement tag')] = '<No value>'
        row[headers.index('PLC acknowledgement bit')] = 0
for number, row_values in enumerate(rows, 2):
    row = copy.deepcopy(prototype)
    row.set('r', str(number))
    for index, cell in enumerate(row):
        column = ''.join(char for char in cell.get('r') if char.isalpha())
        cell.set('r', column + str(number))
        cell.set('t', 's')
        cell.find(q('v')).text = str(string_id(row_values[index]))
    data.append(row)
strings.set('uniqueCount', str(len(values)))
strings.set('count', str(sum(1 for cell in sheet.iter(q('c')) if cell.get('t') == 's')))
files['xl/worksheets/sheet1.xml'] = ET.tostring(sheet, encoding='utf-8', xml_declaration=True)
files['xl/sharedStrings.xml'] = ET.tostring(strings, encoding='utf-8', xml_declaration=True)
output = HERE / ('alarms/crane_alarms_no_plc_ack.xlsx' if '--no-plc-ack' in sys.argv else 'alarms/crane_alarms_native.xlsx')
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for name, content in files.items():
        archive.writestr(name, content)
(HERE / 'alarms/native_manifest.json').write_text(json.dumps({'headers': headers, 'rows': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
print('NATIVE_ALARMS_GENERATED count=%d path=%s' % (len(rows), output))
