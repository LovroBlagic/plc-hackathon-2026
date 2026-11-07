import os, sys, re
OUT = sys.argv[1]

def renum(s):
    n = [0]
    def f(m):
        r = 'ID="%X"' % n[0]; n[0] += 1; return r
    return re.sub(r'(?<![A-Za-z])ID="[^"]*"', f, s)

def doc(body):
    return '<?xml version="1.0" encoding="utf-8"?>\n<Document>\n<Engineering version="V21" />\n' + renum(body) + '\n</Document>\n'

def w(sub, name, body):
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    open(os.path.join(OUT, sub, name + ".xml"), "w", encoding="utf-8").write(doc(body))

def ml(comp, text):
    t = "<Text />" if text is None else "<Text><body><p>%s</p></body></Text>" % text
    return ('<MultilingualText ID="0" CompositionName="%s"><ObjectList><MultilingualTextItem ID="0" CompositionName="Items">'
            '<AttributeList><Culture>en-US</Culture>%s</AttributeList></MultilingualTextItem></ObjectList></MultilingualText>') % (comp, t)

def screen(name, num, items, tpl=True, w_=1024, h_=768):
    ll = '<LinkList><Template TargetID="@OpenLink"><Name>Tpl</Name></Template></LinkList>' if tpl else ''
    return ('<Hmi.Screen.Screen ID="0"><AttributeList><ActiveLayer>0</ActiveLayer><BackColor>182, 182, 182</BackColor><GridColor>0, 0, 0</GridColor>'
            '<Height>%d</Height><Name>%s</Name><Number>%d</Number><Visible>true</Visible><Width>%d</Width></AttributeList>%s<ObjectList>%s'
            '<Hmi.Screen.ScreenLayer ID="0" CompositionName="Layers"><AttributeList><Index>0</Index><Name /><VisibleES>true</VisibleES></AttributeList>'
            '<ObjectList>%s</ObjectList></Hmi.Screen.ScreenLayer></ObjectList></Hmi.Screen.Screen>') % (h_, name, num, w_, ll, ml("HelpText", None), "".join(items))

def geo(name, x=10, y=10, ww=100, hh=30, extra=""):
    return '<AttributeList><Left>%d</Left><Top>%d</Top><Width>%d</Width><Height>%d</Height><ObjectName>%s</ObjectName>%s</AttributeList>' % (x, y, ww, hh, name, extra)

def tagtrig(tag, comp="RangeTag"):
    return ('<Hmi.Dynamic.TagElementTrigger ID="0" CompositionName="%s"><LinkList><Tag TargetID="@OpenLink"><Name>%s</Name></Tag></LinkList>'
            '</Hmi.Dynamic.TagElementTrigger>') % (comp, tag)

def rng(lo, hi, bc, fl="No"):
    return ('<Hmi.Dynamic.Range ID="0" CompositionName="RangeValues"><AttributeList><BackColor>%s</BackColor><FlashingType>%s</FlashingType>'
            '<ForeColor>0, 0, 0</ForeColor><LowerLimit>%s</LowerLimit><UpperLimit>%s</UpperLimit></AttributeList></Hmi.Dynamic.Range>') % (bc, fl, lo, hi)

def appear(tag, ranges):
    return ('<Hmi.Dynamic.RangeAppearanceAnimation ID="0" CompositionName="Animations"><AttributeList><Name>RangeAppearanceAnimation</Name></AttributeList>'
            '<ObjectList>%s%s</ObjectList></Hmi.Dynamic.RangeAppearanceAnimation>') % (tagtrig(tag), "".join(ranges))

def rect(name, anim="", extra="<BackColor>222, 222, 222</BackColor>"):
    return '<Hmi.Screen.Rectangle ID="0" CompositionName="ScreenItems">%s<ObjectList>%s</ObjectList></Hmi.Screen.Rectangle>' % (geo(name, extra=extra), anim)

def fparam_tag(tag):
    return ('<Hmi.Event.FunctionListEntryParameter ID="0" CompositionName="Parameters"><AttributeList><Name>Tag</Name></AttributeList>'
            '<LinkList><Value TargetID="@OpenLink"><Name>%s</Name></Value></LinkList></Hmi.Event.FunctionListEntryParameter>') % tag

def fentry(fn, params):
    return ('<Hmi.Event.FunctionListEntry ID="0" CompositionName="FunctionListEntries"><AttributeList><Name>%s</Name><Type>SystemFunction</Type></AttributeList>'
            '<ObjectList>%s</ObjectList></Hmi.Event.FunctionListEntry>') % (fn, params)

def event(ev, entries):
    return ('<Hmi.Event.Event ID="0" CompositionName="Events"><AttributeList><Name>%s</Name></AttributeList><ObjectList>'
            '<Hmi.Event.FunctionListEventHandler ID="0" CompositionName="EventHandler"><ObjectList>%s</ObjectList></Hmi.Event.FunctionListEventHandler>'
            '</ObjectList></Hmi.Event.Event>') % (ev, entries)

def btn(name, evs):
    return '<Hmi.Screen.Button ID="0" CompositionName="ScreenItems">%s<ObjectList>%s%s%s%s</ObjectList></Hmi.Screen.Button>' % (
        geo(name), ml("HelpText", None), ml("TextOff", "BTN"), ml("TextOn", "BTN"), evs)

def pv(tag):
    return ('<Hmi.Screen.Property ID="0" CompositionName="Properties"><AttributeList><Name>ProcessValue</Name></AttributeList><ObjectList>'
            '<Hmi.Dynamic.TagConnectionDynamic ID="0" CompositionName="Dynamic"><AttributeList><Indirect>false</Indirect></AttributeList>'
            '<LinkList><Tag TargetID="@OpenLink"><Name>%s</Name></Tag></LinkList></Hmi.Dynamic.TagConnectionDynamic></ObjectList></Hmi.Screen.Property>') % tag

def io(name, tag, anim="", extra="<Mode>Output</Mode>"):
    return '<Hmi.Screen.IOField ID="0" CompositionName="ScreenItems">%s<ObjectList>%s%s%s</ObjectList></Hmi.Screen.IOField>' % (
        geo(name, extra=extra), ml("HelpText", None), pv(tag), anim)

def tag(name, ref, dt="Bool"):
    return ('<Hmi.Tag.Tag ID="0" CompositionName="Tags"><AttributeList><AcquisitionTriggerMode>Visible</AcquisitionTriggerMode>'
            '<AddressAccessMode>Symbolic</AddressAccessMode><Length>%s</Length><LogicalAddress /><Name>%s</Name></AttributeList>'
            '<LinkList><AcquisitionCycle TargetID="@OpenLink"><Name>100 ms</Name></AcquisitionCycle>'
            '<Connection TargetID="@OpenLink"><Name>HMI_Connection_1</Name></Connection>'
            '<ControllerTag TargetID="@OpenLink"><Name>%s</Name></ControllerTag><DataType TargetID="@OpenLink"><Name>%s</Name></DataType>'
            '<HmiDataType TargetID="@OpenLink"><Name>%s</Name></HmiDataType></LinkList></Hmi.Tag.Tag>') % ({"Bool": 1, "USInt": 1, "Int": 2}[dt], name, ref, dt, dt)

if __name__ == "__main__":
    SW = "P_SwOn"
    entries = "".join(
        ('<Hmi.TextGraphicList.TextListEntry ID="0" CompositionName="Entries"><AttributeList><DefaultEntry>false</DefaultEntry>'
         '<From>%d</From><To>%d</To></AttributeList><ObjectList>%s</ObjectList></Hmi.TextGraphicList.TextListEntry>') % (v, v, ml("Text", t))
        for v, t in ((0, "OFF"), (1, "INIT")))
    w("textlists", "TL_State", '<Hmi.TextGraphicList.TextList ID="0"><AttributeList><ListRange>Decimal</ListRange><Name>TL_State</Name></AttributeList><ObjectList>'
      + ml("Comment", None) + entries + '</ObjectList></Hmi.TextGraphicList.TextList>')
    w("tags", "Proto_tags", '<Hmi.Tag.TagTable ID="0"><AttributeList><Name>Proto tags</Name></AttributeList><ObjectList>'
      + tag("P_SwOn", "HMI_IF.SwOn") + tag("P_SwOn_q", '"HMI_IF".SwOn') + tag("P_Cell", "HMI_IF.CellSt0[0]", "USInt") + '</ObjectList></Hmi.Tag.TagTable>')
    w("templates", "Tpl", '<Hmi.Screen.ScreenTemplate ID="0"><AttributeList><ActiveLayer>0</ActiveLayer><BackColor>182, 182, 182</BackColor><Name>Tpl</Name></AttributeList>'
      '<ObjectList><Hmi.Screen.ScreenLayer ID="0" CompositionName="Layers"><AttributeList><Index>0</Index><Name /><VisibleES>true</VisibleES></AttributeList>'
      '<ObjectList /></Hmi.Screen.ScreenLayer></ObjectList></Hmi.Screen.ScreenTemplate>')
    cols = ["222, 222, 222", "165, 165, 165", "140, 175, 215", "185, 160, 210", "165, 200, 165", "70, 140, 230", "205, 235, 255", "255, 215, 0"]
    nav = fentry("ActivateScreen",
                 '<Hmi.Event.FunctionListEntryParameter ID="0" CompositionName="Parameters"><AttributeList><Name>Screen name</Name></AttributeList>'
                 '<LinkList><Value TargetID="@OpenLink"><Name>Alarms</Name></Value></LinkList></Hmi.Event.FunctionListEntryParameter>'
                 '<Hmi.Event.FunctionListEntryParameter ID="0" CompositionName="Parameters"><AttributeList><Name>Object number</Name>'
                 '<Value Type="System.Int32">0</Value></AttributeList></Hmi.Event.FunctionListEntryParameter>')
    mh = '<Hmi.Dynamic.HorizontalMovementAnimation ID="0" CompositionName="Animations"><AttributeList><Name>HorizontalMovementAnimation</Name></AttributeList>%s</Hmi.Dynamic.HorizontalMovementAnimation>'
    S = [
        ("R02_RectApp", [rect("P_CellRect", appear("P_Cell", [rng(i, i, c) for i, c in enumerate(cols)]))]),
        ("R03_BtnSet", [btn("P_Btn", event("Press", fentry("SetBit", fparam_tag(SW))))]),
        ("R04_BtnInv", [btn("P_BtnInv", event("Press", fentry("InvertBit", fparam_tag(SW))))]),
        ("R05_BtnNav", [btn("P_NavBtn", event("Press", nav))]),
        ("R06a_MoveH", [io("P_CraneX", "P_Cell", mh % "")]),
        # ("R06b_MoveH", [io("P_CraneX", "P_Cell", mh % ("<ObjectList>" + tagtrig("P_Cell", "Tag") + "</ObjectList>"))]),
        ("R06c_MoveH", [io("P_CraneX", "P_Cell", mh % ("<ObjectList>" + tagtrig("P_Cell", "MovementTag") + "</ObjectList>"))]),
        ("R07_MoveV", [rect("P_CraneY", '<Hmi.Dynamic.VerticalMovementAnimation ID="0" CompositionName="Animations"><AttributeList><Name>VerticalMovementAnimation</Name></AttributeList></Hmi.Dynamic.VerticalMovementAnimation>')]),
        ("R08_Sym", ['<Hmi.Screen.SymbolicIOField ID="0" CompositionName="ScreenItems">' + geo("P_SymIO", extra="<Mode>Output</Mode>")
                     + '<LinkList><TextList TargetID="@OpenLink"><Name>TL_State</Name></TextList></LinkList><ObjectList>' + ml("HelpText", None) + pv("P_Cell")
                     + '</ObjectList></Hmi.Screen.SymbolicIOField>']),
        ("R09_Bar", ['<Hmi.Screen.Bar ID="0" CompositionName="ScreenItems">' + geo("P_Bar", extra="<MaximumValue>24</MaximumValue><MinimumValue>0</MinimumValue>")
                     + '<ObjectList>' + pv("P_Cell") + '</ObjectList></Hmi.Screen.Bar>']),
        ("R10_LampA", [rect("P_LampAlarm", appear("P_SwOn", [rng(0, 0, "170, 170, 170"), rng(1, 1, "220, 0, 0", "Medium")]))]),
        # ("R11_AlarmView", ['<Hmi.Screen.AlarmView ID="0" CompositionName="ScreenItems">' + geo("AV1", ww=900, hh=300) + '</Hmi.Screen.AlarmView>']),
        # ("R13_Big", [rect("P_Big")]),
    ]
    n = 40
    for name, items in S:
        n += 1
        big = name == "R13_Big"
        w("screens", name, screen(name, n, items, w_=1920 if big else 1024, h_=1080 if big else 768))
    w("screens", "Alarms", screen("Alarms", 15, []))
    print("ok")
