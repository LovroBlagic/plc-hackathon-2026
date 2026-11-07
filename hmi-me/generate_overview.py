"""Generate native Machine Expert visualization from an editor-created seed."""
from copy import deepcopy
from pathlib import Path
import uuid
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
tree = ET.parse(BASE / 'Overview.export')
root = tree.getroot()
elements = root.find('.//List[@Name="VisualElementList"]')
seed = deepcopy(elements[0])
elements.clear()
elements.set('Name', 'VisualElementList')
elements.set('Type', '{ef9d0b20-c96e-48db-b361-2ded4063150e}')

def box(text, variable, x, y, width, height, size=16):
    element = deepcopy(seed)
    index = len(elements)
    members = element.find('.//List[@Name="VisualElemMemberList"]')
    values = {n.find('./Single[@Name="Id"]').text: n.find('./Single[@Name="Value"]')
              for n in members if n.find('./Single[@Name="Value"]') is not None}
    for key, value in {
        '1649127785': x, '357335551': y, '2422045748': width, '2134141914': height,
        '550940142': x + width // 2, '1473355128': y + height // 2,
        '390574330': text, '2477733581': variable, '823443203': str(9000 + index),
        '4253639993': size,
    }.items():
        values[key].text = str(value)
    for font in element.findall('.//Single[@Name="FontSize"]'):
        font.text = str(size)
    for name, value in {
        'VisualElementIdentifier': 'GenElemInst_' + str(index + 1),
        'VisualElementIdentification': str(uuid.uuid4()),
        'VisualElementId': str(index),
    }.items():
        element.find('./Single[@Name="%s"]' % name).text = value
    elements.append(element)

box('ENERGETSKI MENADZER | v7', '', 20, 16, 754, 54, 24)
controls = ET.parse(BASE / 'Controls_bound.export')
button = deepcopy(next(e for e in controls.find('.//List[@Name="VisualElementList"]')
                       if e.find('./Single[@Name="VisualElementName"]').text == 'Button'))
assert any(n.text == 'SimCtrl.run' for n in button.iter('Single')), 'Run toggle binding missing'
button_members = button.find('./Single[@Name="VisualElemMemberList"]/List')
button_values = {n.find('./Single[@Name="Id"]').text: n.find('./Single[@Name="Value"]')
                 for n in button_members if n.find('./Single[@Name="Value"]') is not None}
for key, value in {'1649127785': 794, '357335551': 16, '2422045748': 210,
                   '2134141914': 54, '550940142': 899, '1473355128': 43,
                   '390574330': 'RUN / PAUSE', '823443203': '9900'}.items():
    button_values[key].text = str(value)
button.find('./Single[@Name="VisualElementIdentifier"]').text = 'GenElemInst_2'
button.find('./Single[@Name="VisualElementIdentification"]').text = str(uuid.uuid4())
button.find('./Single[@Name="VisualElementId"]').text = str(len(elements))
elements.append(button)
box('SIM TIME: %s', 'Team_HMI.sDateTime', 20, 84, 470, 42)
box('MODE: %s', 'Team_HMI.sPriceMode', 510, 84, 494, 42)
box('YEAR: %.1f %%', 'Team_HMI.rProgressPct', 20, 140, 310, 58)
box('PRICE: %.4f EUR/kWh', 'Team_HMI.rPrice', 350, 140, 310, 58)
box('BATTERY: %.1f %%', 'Team_HMI.rSoc', 680, 140, 324, 58)
box('PV available: %.1f kW', 'Team_HMI.rFneAvail', 20, 226, 470, 70)
box('PV actual (k-1): %.1f kW', 'Team_HMI.rFneAct', 510, 226, 494, 70)
box('LOAD now: %.1f kW', 'Team_HMI.rFec', 20, 312, 470, 70)
box('LOAD actual (k-1): %.1f kW', 'Team_HMI.rFecPrev', 510, 312, 494, 70)
box('BESS request: %.1f kW', 'Team_HMI.rBessReq', 20, 398, 470, 70)
box('BESS actual (k-1): %.1f kW', 'Team_HMI.rBessAct', 510, 398, 494, 70)
box('GRID predicted: %.1f kW', 'Team_HMI.rGridPred', 20, 484, 470, 70)
box('GRID import (k-1): %.1f kW', 'Team_HMI.rImportAct', 510, 484, 494, 70)
box('EV request total: %.1f kW', 'Team_HMI.rEvReqSum', 20, 570, 470, 58)
box('EV actual (k-1): %.1f kW', 'Team_HMI.rEvActSum', 510, 570, 494, 58)
box('MONTH PEAK: %.1f kW', 'Team_HMI.rPeakMonth', 20, 644, 470, 58)
box('PEAK TARGET: %.1f kW', 'Team_HMI.rPeakTarget', 510, 644, 494, 58)
box('BESS signed power: + discharge / - charge | Actual values describe interval k-1', '', 20, 718, 984, 34, 12)

root.find('.//Single[@Name="LastUsedIdForIdentifier"]').text = str(len(elements) + 1)
root.find('.//Single[@Name="UniqueIdGenerator"]').text = str(len(elements) * 5 + 10)
for node in root.findall('.//Single[@Name="Width"]'):
    node.text = '1024'
for node in root.findall('.//Single[@Name="Height"]'):
    node.text = '768'
ET.indent(tree)
tree.write(BASE / 'Overview_generated.export', encoding='utf-8', xml_declaration=True)
print('GENERATED', len(elements), 'elements')
