"""Native, PLC-bound HMI screens. Uses real editor exports, not a browser mockup."""
from copy import deepcopy
from pathlib import Path
import json
import uuid
import xml.etree.ElementTree as E

B = Path(__file__).resolve().parent
OUT = B / 'generated'
OUT.mkdir(exist_ok=True)
NS = uuid.UUID('343b607e-c166-4563-a55c-d45491147459')
P = dict(bg='F3F6FA', white='FFFFFF', ink='17304B', muted='60758C', line='DCE4ED',
         navy='142D48', teal='008D83', teal_light='E2F3F0', amber='E5A12C',
         amber_light='FFF4DB', blue='397CC1', blue_light='E8F1FB', green='29A474',
         purple='7861B6', purple_light='F0EBFA', red='CF4F56', red_light='FCEAEC')
PAGES = [('Overview', 'PREGLED'), ('EVs', 'EV PUNJACI'), ('Trends', 'TRENDOVI'),
         ('Energy', 'ENERGIJA'), ('Costs', 'TROSKOVI'), ('Alarms', 'ALARMI'), ('Controls', 'SIMULACIJA')]

def parse(name): return E.parse(B / name)
def elems(tree): return tree.find('.//List[@Name="VisualElementList"]')
def kind(el): return el.find('./Single[@Name="VisualElementName"]').text
RECT = deepcopy(elems(parse('Overview.export'))[0])
BUTTON = deepcopy(next(e for e in elems(parse('Controls_bound.export')) if kind(e) == 'Button'))
NAV = deepcopy(next(e for e in elems(parse('Navigation_seed.export')) if kind(e) == 'Button'))
ST = deepcopy(next(e for e in elems(parse('ST_action_seed.export')) if kind(e) == 'Button'))
WRITE = deepcopy(next(e for e in elems(parse('Write_action_seed.export')) if kind(e) == 'Button'))
CHART = deepcopy(next(e for e in elems(parse('Graphics_seed.export')) if kind(e) == 'XYChart'))
assert CHART.find('.//Single[@Name="DataYVariable"]').text == 'Team_HMI.aTrFne'

def named(el, name): return el.find('./*[@Name="%s"]' % name)
def put(el, name, value):
    node = named(el, name)
    assert node is not None, name
    node.text = str(value)
def members(el): return el.find('./Single[@Name="VisualElemMemberList"]/List')
def member(el, ident, value, typ='string'):
    ms = members(el)
    for row in ms:
        if row.find('./Single[@Name="Id"]').text == str(ident):
            node = row.find('./Single[@Name="Value"]')
            if node is None: node = row.find('./List[@Name="Value"]')
            assert node is not None, ident
            if node.tag == 'Single': node.text = str(value)
            return node
    row = E.SubElement(ms, 'Single', Type='{c694e3a2-5c0b-4177-ab35-cb06bd5a6a02}', Method='IArchivable')
    E.SubElement(row, 'Single', Name='Id', Type='long').text = str(ident)
    node = E.SubElement(row, 'Single', Name='Value', Type=typ)
    node.text = str(value)
    return node
def argb(color): return 0xff000000 | int(P.get(color, color), 16)
def signed(color):
    value = argb(color)
    return value - 0x100000000
def fixed_color(container, color):
    # Editor custom colours are uint scalars, not named-style objects with
    # an empty CanonicalName. Preserve a property's Name when replacing it.
    if container.tag == 'List':
        for child in list(container): container.remove(child)
        E.SubElement(container,'Single',Type='uint').text=str(argb(color))
    else:
        name=container.get('Name')
        container.clear();container.tag='Single';container.set('Type','uint')
        if name:container.set('Name',name)
        container.text=str(argb(color))
def color_member(el, ident, color):
    node = member(el, ident, argb(color), 'uint')
    if node.tag == 'List': fixed_color(node, color)
    else: node.text = str(argb(color) if node.get('Type') == 'uint' else signed(color))

def chart_color(container,color):
    # XY packets store INamedStyleColor objects rather than the primitive's
    # array-valued colour property. Keep that object representation.
    builtins={'amber':('Yellow','FFFF00'),'green':('Green','008000'),
              'teal':('Red','FF0000'),'blue':('Blue','0000FF'),
              'purple':('Black','000000'),'red':('Red','FF0000'),
              'white':('White','FFFFFF'),'line':('Black','000000'),'muted':('Black','000000')}
    name,rgb=builtins[color]
    put(container,'CanonicalName',name)
    value=int(rgb,16)|0xff000000
    put(container,'Color',value-0x100000000)
def style(el, fill='white', edge=None, ink='ink', size=14, bold=False):
    for ident in (2812299069, 493260384): color_member(el, ident, fill)
    for ident in (494569607, 135947015): color_member(el, ident, edge or fill)
    color_member(el, 663104332, ink)
    member(el, 3488306084, argb(ink), 'uint')
    member(el, 1603690730, 'Segoe UI')
    member(el, 4253639993, size, 'short')
    for font in el.findall('.//Single[@Name="FontSize"]'): font.text = str(size)
    for font in el.findall('.//Single[@Name="FontName"]'): font.text = 'Segoe UI'
    for font in el.findall('.//Single[@Name="FontStyle"]'): font.text = '1' if bold else '0'
    for font in el.findall('.//Single[@Name="DoubleFontSize"]'): font.text = str(float(size))
    for font in el.findall('.//Single[@Type="{9e842eb2-1463-4af2-b605-4fbb17044f94}"]'):
        font.set('Type','{896a5e54-96c3-433b-96d2-4f1442fef591}')
        canonical=named(font,'CanonicalName')
        if canonical is not None:font.remove(canonical)
        put(font,'DisplayName','Segoe UI')
    for font in el.findall('.//Single[@Type="{896a5e54-96c3-433b-96d2-4f1442fef591}"]'):
        color=named(font,'NamedColor')
        if color is not None:
            color.clear();color.tag='Null';color.set('Name','NamedColor')
    for node in el.findall('.//Single[@Name="ExplicitColor"]'): node.text = str(signed(ink))
    return el
def geometry(el, x, y, w, h):
    for ident, value in ((1649127785,x), (357335551,y), (2422045748,w), (2134141914,h),
                         (550940142,x+w//2), (1473355128,y+h//2)):
        member(el, ident, value, 'int')
def remove_actions(el):
    for name in ('ConfiguredComplexInputs', 'VisualElementInputActions'):
        node = named(el, name)
        for child in list(node): node.remove(child)
def action_only(el):
    node = named(el, 'ConfiguredComplexInputs')
    for child in list(node): node.remove(child)

class Scene:
    def __init__(self, name):
        self.name = name
        self.tree = parse('Overview.export')
        self.root = self.tree.getroot()
        meta = self.root.find('.//Single[@Name="MetaObject"]')
        old = named(meta, 'Guid').text
        self.guid = str(uuid.uuid5(NS, name))
        for node in self.root.iter('Single'):
            if node.text == old: node.text = self.guid
        put(meta, 'Name', name)
        for node in self.root.findall('.//Single[@Name="GeneratedLMMDescriptions"]//Single[@Type="System.Guid"]'):
            if node.text: node.text = str(uuid.uuid5(NS, name + ':' + node.text))
        self.elements = elems(self.tree)
        for node in list(self.elements): self.elements.remove(node)
        self.box('', '', 0, 0, 1024, 768, fill='bg')
    def add(self, el, x, y, w, h, invisible=None):
        i = len(self.elements)
        geometry(el,x,y,w,h)
        put(el,'VisualElementIdentifier','GenElemInst_%d' % (i+1))
        put(el,'VisualElementIdentification',str(uuid.uuid5(NS,self.name+':element:'+str(i))))
        put(el,'VisualElementOwningObjectGuid',self.guid)
        put(el,'VisualElementId',i)
        for node in el.findall('./Array[@Name="LMGuids"]/Single'):
            node.text=str(uuid.uuid5(NS,self.name+':element:'+str(i)+':lm:'+node.text))
        member(el,823443203,str(10000+i))
        if invisible: member(el,2880254039,invisible)
        self.elements.append(el)
        return el
    def box(self,text='',var='',x=0,y=0,w=100,h=30,fill='white',ink='ink',edge=None,size=14,bold=False,invisible=None):
        el = style(deepcopy(RECT),fill,edge,ink,size,bold)
        member(el,390574330,text)
        member(el,2477733581,var)
        return self.add(el,x,y,w,h,invisible)
    def label(self,text,x,y,w,h=28,ink='muted',size=12,fill='bg',var='',bold=False):
        return self.box(text,var,x,y,w,h,fill,ink,size=size,bold=bold)
    def button(self,text,x,y,w=130,h=38,target=None,code=None,toggle=None,write=None,minimum=1,maximum=12,invisible=None):
        seed = NAV if target else ST if code else WRITE if write else BUTTON
        el = style(deepcopy(seed),'teal',ink='white',size=13,bold=True)
        member(el,390574330,text)
        # The face uses a separate style colour from its base fill.
        color_member(el,2341735680,'teal')
        if toggle:
            actions=named(el,'VisualElementInputActions')
            for child in list(actions): actions.remove(child)
            for n in el.findall('.//Single[@Name="Value"]'):
                if n.text == 'SimCtrl.run': n.text = toggle
        else:
            action_only(el)
            if target: el.find('.//Single[@Name="Assign33"]').text = target
            if code: el.find('.//Single[@Name="STSnippet"]').text = code
            if write:
                el.find('.//Single[@Name="InputBoxVariable"]').text = write
                el.find('.//Single[@Name="InputBoxMin"]').text = str(minimum)
                el.find('.//Single[@Name="InputBoxMax"]').text = str(maximum)
                el.find('.//Single[@Name="InputBoxDialogTitle"]').text = "'"+text.replace("'","''")+"'"
        return self.add(el,x,y,w,h,invisible)
    def header(self,title):
        self.box('', '',0,0,1024,104,fill='navy')
        self.label('ENERGETSKI MENADZER',20,10,460,34,ink='white',size=23,fill='navy',bold=True)
        self.label(title,20,48,220,28,ink='white',size=14,fill='navy')
        self.label('%s',260,49,260,26,ink='white',size=14,fill='navy',var='Team_HMI.sDateTime')
        self.label('%s',530,49,220,26,ink='white',size=13,fill='navy',var='Team_HMI.sPriceMode')
        self.button('RUN / PAUSE',818,18,184,48,toggle='SimCtrl.run')
        self.box('PAUSED','',620,12,90,27,fill='amber',ink='white',size=12,invisible='SimCtrl.run')
        self.box('RUNNING','',620,12,90,27,fill='green',ink='white',size=12,invisible='NOT SimCtrl.run')
        self.box('TRIPPED','',716,12,90,27,fill='red',ink='white',size=12,invisible='NOT SimCtrl.tripped')
        for i,(target,label) in enumerate(PAGES):
            el = self.button(label,20+i*142,115,132,36,target=target)
            if target == self.name:
                style(el,'navy',ink='white',size=13,bold=True)
                color_member(el,2341735680,'navy')
    def segment_bar(self,x,y,w,h,expression,color='green',segments=20):
        self.box('', '', x,y,w,h,fill='line')
        for i in range(segments):
            threshold=(i+1)*100.0/segments
            self.box('','',x+i*w//segments+2,y+2,max(1,w//segments-4),h-4,
                     fill=color,invisible='(%s) < %.3f' % (expression,threshold))
    def chart(self,x,y,w,h,curves,ymin=0,ymax=100,monthly=False):
        el=deepcopy(CHART)
        packet=el.find('.//Single[@Name="XYPacket"]')
        curve_list=named(packet,'Curves')
        base_curve=deepcopy(curve_list[0])
        for child in list(curve_list):curve_list.remove(child)
        for i,(title,var,color) in enumerate(curves):
            curve=deepcopy(base_curve)
            for key,value in {'CurveName':title,'DataYVariablePath':var,'DataYVariable':var,'ChartLineLineWidth':2}.items(): put(curve,key,value)
            chart_color(named(curve,'ChartLineStyleColor'),color)
            if monthly:
                put(curve,'ChartType','Bar')
                put(curve,'DataXVariablePath','Team_Visu.aMonths')
                put(curve,'DataXVariable','Team_Visu.aMonths')
                put(curve,'DataXVariableBaseType','ARRAY [1..12] OF REAL')
                put(curve,'DataYVariableBaseType','ARRAY [1..12] OF typeTeamAgg')
                put(curve,'DataYVariableElement','C_total')
                put(curve,'LowerBorderX1',1);put(curve,'UpperBorderX1',12)
                put(curve,'LowerBorderY1',1);put(curve,'UpperBorderY1',12)
                put(curve,'DataIxMinValue',1);put(curve,'DataIxMaxValue',12)
                for field in ('ArrayDescDataXVariable','ArrayDescDataYVariable'):
                    desc=named(curve,field)[0]
                    for key,value in {'LowerBorderLit':1,'UpperBorderLit':12,'LowerBorder':1,'UpperBorder':12}.items():put(desc,key,value)
                chart_color(named(curve,'ChartBarStyleColorMain'),color)
                chart_color(named(curve,'ChartBarStyleColorBorder'),color)
            curve_list.append(curve)
        axes=named(packet,'Axes')
        for axis in axes:
            is_x=named(axis,'AxisName').text=='AxisX'
            put(axis,'Autoscale','True' if monthly and not is_x else 'False')
            put(axis,'MinValue',0.5 if monthly and is_x else -24 if is_x else ymin)
            put(axis,'MaxValue',12.5 if monthly and is_x else 0 if is_x else ymax)
            chart_color(named(axis,'AxisColor'),'muted')
            chart_color(named(axis,'BackgroundStyleColor'),'white')
            # Preserve the chart seed's registered font identifier.
            for n in axis.findall('.//Single[@Name="Size"]'):n.text='10'
        chart_color(named(packet,'GridStyleColor'),'line')
        chart_color(named(packet,'BackgroundStyleColor'),'white')
        self.add(el,x,y,w,h)
    def save(self):
        put(self.root.find('.//Single[@Name="Object"]'),'LastUsedIdForIdentifier',len(self.elements)+1)
        self.root.find('.//Single[@Name="UniqueIdGenerator"]').text=str(len(self.elements)*8+20)
        for node in self.root.findall('.//Single[@Name="Width"]'):node.text='1024'
        for node in self.root.findall('.//Single[@Name="Height"]'):node.text='768'
        E.indent(self.tree)
        path=OUT/(self.name+'.export')
        self.tree.write(path,encoding='utf-8',xml_declaration=True)
        return dict(page=self.name,elements=len(self.elements),file=path.name)

def overview():
    s=Scene('Overview');s.header('Tokovi energije')
    # A common electrical bus links four visible equipment cards.
    s.box('', '',324,294,338,5,fill='line')
    s.box('', '',490,294,5,110,fill='line')
    s.box('', '',380,342,4,142,fill='line');s.box('', '',362,482,22,4,fill='line')
    s.box('', '',380,342,22,4,fill='line')
    s.box('', '',618,342,4,142,fill='line');s.box('', '',618,482,44,4,fill='line')
    s.box('', '',590,342,32,4,fill='line')
    for title,x,y,color in [('SOLAR / FNE',22,184,'amber'),('MREZA / GRID',662,184,'blue'),
                             ('BATERIJA / BESS',22,404,'green'),('OBJEKT / FEC',662,404,'purple')]:
        s.box('', '',x,y,340,184,fill='white',edge='line')
        s.box(title,'',x,y,340,34,fill=color,ink='white',size=16,bold=True)
    # Solar cells, grid mast, battery and factory icons are native shapes.
    for row in range(2):
        for col in range(4):s.box('','',40+col*17,238+row*18,14,15,fill='blue')
    s.box('Dostupno %.1f kW','Team_HMI.rFneAvail',128,232,218,36,size=17)
    s.box('Zahtjev %.1f kW','Team_HMI.rFneExpected',128,271,218,29,size=13)
    s.box('Ostvareno %.1f kW','Team_HMI.rFneAct',40,315,302,30,size=13,ink='muted')
    s.box('','',694,240,4,54,fill='blue');s.box('','',674,251,44,4,fill='blue');s.box('','',679,273,34,4,fill='blue')
    s.box('Plan %.1f kW','Team_HMI.rGridPred',730,232,256,36,size=17)
    s.box('Uvoz %.1f kW','Team_HMI.rImportAct',730,273,256,29,size=13,ink='muted')
    s.box('Izvoz %.1f kW','Team_HMI.rExportAct',730,310,256,29,size=13,ink='muted')
    s.box('>>','',370,270,80,44,fill='bg',ink='amber',size=24,invisible='Team_HMI.rFneExpected <= 0.1')
    s.box('<<','',562,270,80,44,fill='bg',ink='blue',size=24,invisible='Team_HMI.rGridPred <= 0.1')
    s.box('>>','',562,270,80,44,fill='bg',ink='blue',size=24,invisible='Team_HMI.rGridPred >= -0.1')
    s.box('SABIRNICA','',402,322,188,40,fill='navy',ink='white',size=15,bold=True)
    s.box('SOC %.1f %%','Team_HMI.rSoc',40,454,302,40,size=23,ink='green',bold=True)
    s.segment_bar(42,501,296,24,'Team_HMI.rSoc','green')
    s.box('%s','Team_HMI.sBessDir',40,535,144,27,size=12)
    s.box('%.1f kW','Team_HMI.rBessReq',188,535,154,27,size=15)
    s.box('>','',364,460,28,44,fill='bg',ink='green',size=24,invisible='Team_HMI.rBessReq <= 0.1')
    s.box('<','',364,460,28,44,fill='bg',ink='green',size=24,invisible='Team_HMI.rBessReq >= -0.1')
    for j,height in enumerate((28,46,36)):
        s.box('','',682+j*14,505-height,11,height,fill='purple')
    s.box('Potrosnja %.1f kW','Team_HMI.rFec',730,454,256,38,size=17)
    s.box('Ostvareno %.1f kW','Team_HMI.rFecPrev',682,535,304,27,size=13,ink='muted')
    s.box('>','',624,460,30,44,fill='bg',ink='purple',size=24,invisible='Team_HMI.rFec <= 0.1')
    s.box('EV PUNJACI','',396,404,204,34,fill='teal',ink='white',size=16,bold=True)
    s.box('%.1f kW','Team_HMI.rEvReqSum',396,446,204,40,fill='teal_light',size=23,ink='teal')
    s.box('Ostvareno %.1f kW','Team_HMI.rEvActSum',396,493,204,28,fill='teal_light',size=12)
    s.box('v','',469,366,46,28,fill='bg',ink='teal',size=20,invisible='Team_HMI.rEvReqSum <= 0.1')
    for x,title,var,color,fmt in [(22,'CIJENA','Team_HMI.rPrice','amber','%.4f EUR/kWh'),
                                 (358,'MJESECNI VRH','Team_HMI.rPeakMonth','blue','%.1f kW'),
                                 (694,'UKUPNI TROSAK','Team_Results.cost_total','teal','%.2f EUR')]:
        s.box('','',x,616,308,98,fill='white',edge='line')
        s.label(title,x+12,626,284,24,ink=color,fill='white',bold=True)
        s.box(fmt,var,x+12,657,284,39,size=22,ink=color,bold=True)
    return s

def evs():
    s=Scene('EVs');s.header('Status i napredak punjenja')
    for j in range(4):
        x=22+(j%2)*502;y=174+(j//2)*270
        s.box('','',x,y,480,250,fill='white',edge='line')
        s.box('EV %d'%(j+1),'',x,y,480,36,fill='teal',ink='white',size=18,bold=True)
        s.box('SPOJEN','',x+328,y+45,136,26,fill='green',ink='white',size=12,invisible='NOT Team_HMI.aEvConnected[%d]'%j)
        s.box('SLOBODAN','',x+328,y+45,136,26,fill='line',size=12,invisible='Team_HMI.aEvConnected[%d]'%j)
        s.box('Zahtjev %.1f kW','Team_HMI.aEvReq[%d]'%j,x+16,y+44,280,36,size=20)
        s.box('Ostvareno %.1f kW','Team_HMI.aEvAct[%d]'%j,x+16,y+82,448,26,size=13,ink='muted')
        expr='100.0 * Team_HMI.aEvDelivered[%d] / MAX(0.001, Team_HMI.aEvDelivered[%d] + Team_HMI.aEvRemaining[%d])'%(j,j,j)
        s.segment_bar(x+16,y+119,448,22,expr,'teal',20)
        s.box('Predano %.1f kWh','Team_HMI.aEvDelivered[%d]'%j,x+16,y+151,216,30,size=14)
        s.box('Preostalo %.1f kWh','Team_HMI.aEvRemaining[%d]'%j,x+244,y+151,220,30,size=14)
        s.box('Odlazak: %s','Team_HMI.aEvDeparture[%d]'%j,x+16,y+193,448,30,size=13)
    s.label('Napredak: predana energija / (predana + preostala energija sesije). Ostvarena snaga je za k-1.',22,718,980,22,size=10)
    return s

def trends():
    s=Scene('Trends');s.header('Posljednja 24 simulirana sata')
    s.label('SNAGE [kW]',22,165,220,28,ink='ink',size=16,bold=True)
    curves=[('FNE','Team_HMI.aTrFne','amber'),('FEC','Team_HMI.aTrFec','blue'),
            ('Mreza','Team_HMI.aTrGrid','teal'),('BESS','Team_HMI.aTrBess','green'),('EV','Team_HMI.aTrEv','purple')]
    legend={'amber':('FFFF00','ink'),'blue':('0000FF','white'),
            'teal':('FF0000','white'),'green':('00FF00','ink'),'purple':('000000','white')}
    for i,(title,var,color) in enumerate(curves):
        fill,ink=legend[color]
        s.box(title,'',300+i*140,165,125,25,fill=fill,ink=ink,size=12)
    s.chart(22,202,980,280,curves,-750,1000)
    s.label('BATERIJA SOC [%]',22,494,470,28,ink='green',size=15,bold=True)
    s.label('CIJENA ENERGIJE [EUR/kWh]',530,494,470,28,ink='amber',size=15,bold=True)
    s.chart(22,530,470,176,[('SOC','Team_HMI.aTrSoc','green')],0,100)
    s.chart(530,530,470,176,[('Cijena','Team_HMI.aTrPrice','amber')],-0.2,0.7)
    s.label('X os: sati prije najnovijeg zavrsenog intervala | 96 uzoraka, razmak 15 min | 0 = najnoviji uzorak',22,714,980,22,size=10)
    return s

def selectors(s):
    s.button('< DAN',22,172,100,34,code='Team_HMI.iSelDay := MAX(0, Team_HMI.iSelDay - 1);')
    s.box('Dan %d','Team_HMI.iSelDay + 1',128,172,130,34,size=16)
    s.button('DAN >',264,172,100,34,code='Team_HMI.iSelDay := MIN(364, Team_HMI.iSelDay + 1);')
    s.button('< MJESEC',538,172,120,34,code='Team_HMI.iSelMonth := MAX(1, Team_HMI.iSelMonth - 1);')
    s.box('Mjesec %d','Team_HMI.iSelMonth',664,172,190,34,size=16)
    s.button('MJESEC >',860,172,142,34,code='Team_HMI.iSelMonth := MIN(12, Team_HMI.iSelMonth + 1);')

def energy():
    s=Scene('Energy');s.header('Dnevne, mjesecne i godisnje energije');selectors(s)
    for x,w,title in [(22,290,'ENERGIJA [kWh]'),(312,230,'ODABRANI DAN'),(542,230,'ODABRANI MJESEC'),(772,230,'GODINA')]:
        s.box(title,'',x,226,w,34,fill='navy',ink='white',size=13,bold=True)
    rows=[('FNE proizvodnja','E_fne'),('Objekt / FEC','E_fec'),('BESS punjenje','E_bess_chg'),('BESS praznjenje','E_bess_dch'),
          ('EV ukupno','E_ev')]+[('EV punjac %d'%(i+1),'E_ev_ch[%d]'%i) for i in range(4)]+[('Uvoz iz mreze','E_import'),('Izvoz u mrezu','E_export')]
    for i,(title,field) in enumerate(rows):
        y=260+i*37;fill='white' if i%2==0 else 'blue_light'
        s.box(title,'',22,y,290,37,fill=fill,size=13)
        for x,prefix in [(312,'Team_Log.aDay[Team_HMI.iSelDay]'),(542,'Team_Log.aMonth[Team_HMI.iSelMonth]'),(772,'Team_Results')]:
            s.box('%.1f',prefix+'.'+field,x,y,230,37,fill=fill,size=14)
    s.label('Sve energije u kWh. Dan 1 = 1. sijecnja. Dnevni i mjesecni izbori ne mijenjaju simulaciju.',22,689,980,27,size=11)
    return s

def costs():
    s=Scene('Costs');s.header('Troskovi i mjesecni pregled');selectors(s)
    for x,w,title in [(22,290,'TROSAK [EUR]'),(312,230,'ODABRANI DAN'),(542,230,'ODABRANI MJESEC'),(772,230,'GODINA')]:
        s.box(title,'',x,226,w,34,fill='navy',ink='white',size=13,bold=True)
    rows=[('Kupnja energije','C_purchase'),('Prihod od izvoza','C_revenue'),('Mrezarina','C_grid'),('Vrsna snaga','C_peak'),('UKUPNO','C_total')]
    for i,(title,field) in enumerate(rows):
        y=260+i*36;fill='teal_light' if i==4 else 'white' if i%2==0 else 'blue_light'
        s.box(title,'',22,y,290,36,fill=fill,size=13,bold=i==4)
        for x,prefix in [(312,'Team_Log.aDay[Team_HMI.iSelDay]'),(542,'Team_Log.aMonth[Team_HMI.iSelMonth]'),(772,'Team_Results')]:
            s.box('%.2f',prefix+'.'+field,x,y,230,36,fill=fill,size=14,bold=i==4)
    s.label('UKUPNI TROSAK PO MJESECIMA [EUR]',22,452,980,28,ink='ink',size=15,bold=True)
    s.chart(22,490,980,200,[('Trosak','Team_Log.aMonth','teal')],0,50000,monthly=True)
    s.label('Ukupno = kupnja - prihod + mrezarina + vrh. Dnevni troskovi ne ukljucuju obracun vrha.',22,700,980,28,size=11)
    return s

def alarms():
    s=Scene('Alarms');s.header('Aktivna stanja i povijest poruka')
    flags=[('IMPORT LIMIT','xAlmImport','red'),('EXPORT LIMIT','xAlmExport','red'),('POSTROJENJE ODSPOJENO','xAlmTripped','red'),
           ('EV ENERGIJA NEDOSTAJE','xAlmEvUnmet','red'),('EV SNAGA OGRANICENA','xAlmGuardEv','amber'),
           ('FNE OGRANICENA','xAlmGuardCurt','amber'),('ZASTITA: NEMA REZERVE','xAlmGuardFail','red'),('SIMULACIJA ZAVRSENA','xAlmFinished','green')]
    for i,(title,var,color) in enumerate(flags):
        x=22+(i%4)*248;y=174+(i//4)*48
        s.box(title,'',x,y,236,38,fill='line',ink='muted',size=10)
        s.box(title,'',x,y,236,38,fill=color,ink='white',size=10,bold=True,invisible='NOT Team_HMI.'+var)
    s.label('POVIJEST ALARMA / PORUKA',22,278,600,30,ink='ink',size=16,bold=True)
    s.button('< NOVIJE',668,274,148,34,code='Team_Visu.iAlarmPage := MAX(0, Team_Visu.iAlarmPage - 1);')
    s.button('STARIJE >',832,274,170,34,code='Team_Visu.iAlarmPage := MIN(4, Team_Visu.iAlarmPage + 1);')
    for x,w,t in [(22,230,'SIMULIRANO VRIJEME'),(252,90,'KOD'),(342,660,'PORUKA')]:s.box(t,'',x,322,w,32,fill='navy',ink='white',size=12)
    for i in range(10):
        y=354+i*34;fill='white' if i%2==0 else 'blue_light';prefix='Team_HMI.aAlarmHist[Team_Visu.iAlarmPage * 10 + %d]'%i
        for x,w,fmt,field in [(22,230,'%s','sStamp'),(252,90,'%d','iCode'),(342,660,'%s','sText')]:
            s.box(fmt,prefix+'.'+field,x,y,w,34,fill=fill,size=11)
    s.box('Poruke od reseta: %d','Team_HMI.nAlarms',22,704,350,28,fill='bg',size=12)
    s.box('Stranica %d / 5','Team_Visu.iAlarmPage + 1',650,704,352,28,fill='bg',size=12)
    return s

def controls():
    s=Scene('Controls');s.header('Upravljanje simulacijom')
    s.box('','',22,174,980,160,fill='white',edge='line')
    s.label('SIMULACIJA',42,185,900,28,ink='ink',size=17,fill='white',bold=True)
    s.box('Korak %d / 35040','SimCtrl.k',42,229,290,34,size=17)
    s.box('Napredak %.1f %%','Team_HMI.rProgressPct',352,229,290,34,size=17)
    s.box('Zavrseno %d','BOOL_TO_INT(SimCtrl.finished)',662,229,320,34,size=17)
    s.segment_bar(42,280,920,22,'Team_HMI.rProgressPct','teal')
    s.box('','',22,350,476,176,fill='white',edge='line')
    s.label('MODEL CIJENA',42,360,436,28,ink='ink',size=16,fill='white',bold=True)
    s.button('DVOTARIFNI (HEP)',42,408,204,42,code='IF NOT SimCtrl.run THEN SimCtrl.price_mode := 0; END_IF;')
    s.button('DAN UNAPRIJED',262,408,216,42,code='IF NOT SimCtrl.run THEN SimCtrl.price_mode := 1; END_IF;')
    s.label('Pauzirajte, odaberite model, zatim resetirajte.',42,470,436,28,size=11,fill='white')
    s.box('','',518,350,484,176,fill='white',edge='line')
    s.label('BRZINA SIMULACIJE',538,360,444,28,ink='ink',size=16,fill='white',bold=True)
    s.box('Period: %u ms','SimCtrl.cycle_time_ms',538,400,216,38,size=17)
    s.button('UNOS PERIODA',770,400,212,38,write='SimCtrl.cycle_time_ms',minimum=10,maximum=60000)
    if (B/'Tap_seed.export').exists():
        tap=next(e for e in elems(parse('Tap_seed.export')) if kind(e)=='Button')
        el=style(deepcopy(tap),'teal',ink='white',size=13,bold=True)
        color_member(el,2341735680,'teal')
        member(el,390574330,'PRIMIJENI PERIOD')
        complex_inputs=named(el,'ConfiguredComplexInputs')
        for child in list(complex_inputs):
            if named(child,'SignatureName').text != 'Visu_TapInput': complex_inputs.remove(child)
        assert any(n.text=='SimCtrl.change_cycle' for n in complex_inputs.iter('Single'))
        actions=named(el,'VisualElementInputActions')
        for child in list(actions): actions.remove(child)
        s.add(el,538,455,444,40)
    else:
        s.label('Tipka za primjenu se jos konfigurira.',538,455,444,40,fill='white',size=12)
    s.box('','',22,546,980,162,fill='white',edge='line')
    s.label('NOVI POKUS',42,557,600,28,ink='ink',size=16,fill='white',bold=True)
    s.label('Reset brise akumulirane energije, troskove, trendove i povijest.',42,594,700,28,size=12,fill='white')
    s.button('RESET...',770,581,212,50,code='Team_Visu.xResetArmed := TRUE;')
    for el in [s.box('','',230,268,564,232,fill='white',edge='red'),
               s.box('POTVRDA RESETA','',250,288,524,42,fill='red',ink='white',size=20,bold=True),
               s.box('Obrisati rezultate i pokrenuti novi pokus?','',250,346,524,46,size=15)]:
        member(el,2880254039,'NOT Team_Visu.xResetArmed')
    s.button('ODUSTANI',250,420,246,48,code='Team_Visu.xResetArmed := FALSE;',invisible='NOT Team_Visu.xResetArmed')
    s.button('POTVRDI RESET',524,420,250,48,code='SimCtrl.run := FALSE; SimCtrl.reset := TRUE; Team_Visu.xResetArmed := FALSE;',invisible='NOT Team_Visu.xResetArmed')
    return s

if __name__ == '__main__':
    result=[fn().save() for fn in (overview,evs,trends,energy,costs,alarms,controls)]
    (OUT/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    hours=', '.join('%.2f'%((i-95)*.25) for i in range(96))
    gvl=('// HMI-only state and simulated-time chart axes. No control-strategy logic.\n'
         'VAR_GLOBAL\n xResetArmed : BOOL;\n iAlarmPage : INT;\nEND_VAR\n'
         'VAR_GLOBAL CONSTANT\n aHours : ARRAY[0..95] OF REAL := ['+hours+'];\n'
         ' aMonths : ARRAY[1..12] OF REAL := ['+', '.join(str(i)+'.0' for i in range(1,13))+'];\nEND_VAR\n')
    (OUT/'Team_Visu.st').write_text(gvl,encoding='utf-8')
    print(json.dumps(result))
