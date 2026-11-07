#!/usr/bin/env python3
"""proto_src.py - write the AUTHORED prototype set that replaces the human-drawn "Proto" screen (HUMAN_STEPS B).

Output dir (default hmi-tia/proto) gets the same layout as an HmiGen --export:
  screens/Proto.xml  templates/Tpl.xml  tags/Proto_tags.xml  textlists/TL_State.xml
gen_hmi.py then clones these objects exactly as it would clone human prototypes:
  python hmi-tia/gen_hmi.py all --export hmi-tia/proto --out hmi-tia/out

The SimaticML class / composition names are copied from real WinCC Advanced exports (V18 GitHub samples
CJMORE66/Garett-GMT-OP010, and our own V21 exports in hmi-tia/lab/*_exp) and were verified by importing each
object into HMI_RT_1 (hmi-tia/lab/r1.log, r2.log):
  events      Hmi.Event.Event[Events] > Hmi.Event.FunctionListEventHandler[EventHandler]
              > Hmi.Event.FunctionListEntry[FunctionListEntries] > Hmi.Event.FunctionListEntryParameter[Parameters]
  appearance  Hmi.Dynamic.RangeAppearanceAnimation[Animations] > Hmi.Dynamic.TagElementTrigger[RangeTag]
              + Hmi.Dynamic.Range[RangeValues] (LowerLimit/UpperLimit/BackColor/ForeColor/FlashingType No|Medium)
  movement    Hmi.Dynamic.HorizontalMovementAnimation / VerticalMovementAnimation[Animations]
              > Hmi.Dynamic.TagElementTrigger[MovementTag]
  tag         Hmi.Tag.Tag with LinkList AcquisitionCycle, Connection, ControllerTag, DataType, HmiDataType
  text list   ListRange Decimal (not "Range")
Screen size must equal the device size (HMI_RT_1 = 1024 x 768), otherwise the import aborts TIA.
"""
import os, re, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "proto")
MOTION = json.load(open(os.path.join(HERE, "motion_attrs.json"), encoding="utf-8")) if os.path.isfile(os.path.join(HERE, "motion_attrs.json")) else {}


def renum(s):
    n = [0]
    def f(m):
        r = 'ID="%X"' % n[0]; n[0] += 1; return r
    return re.sub(r'(?<![A-Za-z])ID="[^"]*"', f, s)


def w(sub, name, body):
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    with open(os.path.join(OUT, sub, name + ".xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n<Document>\n<Engineering version="V21" />\n' + renum(body) + '\n</Document>\n')


def ml(comp, text):
    t = "<Text />" if text is None else "<Text><body><p>%s</p></body></Text>" % text
    return ('<MultilingualText ID="0" CompositionName="%s"><ObjectList><MultilingualTextItem ID="0" CompositionName="Items">'
            '<AttributeList><Culture>en-US</Culture>%s</AttributeList></MultilingualTextItem></ObjectList></MultilingualText>') % (comp, t)


def font(size=15, bold=False):
    return ('<Hmi.Globalization.MultiLingualFont ID="0" CompositionName="Font"><ObjectList><Hmi.Globalization.FontItem ID="0" CompositionName="Items">'
            '<AttributeList><Culture>en-US</Culture><FontFamily>Tahoma</FontFamily><FontSize>%d</FontSize><FontStyle>%s</FontStyle></AttributeList>'
            '</Hmi.Globalization.FontItem></ObjectList></Hmi.Globalization.MultiLingualFont>') % (size, "Bold" if bold else "Regular")


def attrs(name, x, y, ww, hh, extra=""):
    return '<AttributeList><Left>%d</Left><Top>%d</Top><Width>%d</Width><Height>%d</Height><ObjectName>%s</ObjectName>%s</AttributeList>' % (
        x, y, ww, hh, name, extra)


def tagtrig(tag, comp):
    return ('<Hmi.Dynamic.TagElementTrigger ID="0" CompositionName="%s"><LinkList><Tag TargetID="@OpenLink"><Name>%s</Name></Tag></LinkList>'
            '</Hmi.Dynamic.TagElementTrigger>') % (comp, tag)


def rng(lo, hi, bc, fl="No"):
    return ('<Hmi.Dynamic.Range ID="0" CompositionName="RangeValues"><AttributeList><BackColor>%s</BackColor><FlashingType>%s</FlashingType>'
            '<ForeColor>0, 0, 0</ForeColor><LowerLimit>%s</LowerLimit><UpperLimit>%s</UpperLimit></AttributeList></Hmi.Dynamic.Range>') % (bc, fl, lo, hi)


def appear(tag, ranges):
    return ('<Hmi.Dynamic.RangeAppearanceAnimation ID="0" CompositionName="Animations"><AttributeList><Name>RangeAppearanceAnimation</Name></AttributeList>'
            '<ObjectList>%s%s</ObjectList></Hmi.Dynamic.RangeAppearanceAnimation>') % (tagtrig(tag, "RangeTag"), "".join(ranges))


def move(kind, tag, vals):
    extra = "".join("<%s>%s</%s>" % (k, v, k) for k, v in vals.items())
    return ('<Hmi.Dynamic.%sMovementAnimation ID="0" CompositionName="Animations"><AttributeList>%s<Name>%sMovementAnimation</Name></AttributeList>'
            '<ObjectList>%s</ObjectList></Hmi.Dynamic.%sMovementAnimation>') % (kind, extra, kind, tagtrig(tag, "MovementTag"), kind)


def pv(tag):
    return ('<Hmi.Screen.Property ID="0" CompositionName="Properties"><AttributeList><Name>ProcessValue</Name></AttributeList><ObjectList>'
            '<Hmi.Dynamic.TagConnectionDynamic ID="0" CompositionName="Dynamic"><AttributeList><Indirect>false</Indirect></AttributeList>'
            '<LinkList><Tag TargetID="@OpenLink"><Name>%s</Name></Tag></LinkList></Hmi.Dynamic.TagConnectionDynamic></ObjectList></Hmi.Screen.Property>') % tag


def fentry(fn, params):
    return ('<Hmi.Event.FunctionListEntry ID="0" CompositionName="FunctionListEntries"><AttributeList><Name>%s</Name><Type>SystemFunction</Type></AttributeList>'
            '<ObjectList>%s</ObjectList></Hmi.Event.FunctionListEntry>') % (fn, params)


def p_tag(tag):
    return ('<Hmi.Event.FunctionListEntryParameter ID="0" CompositionName="Parameters"><AttributeList><Name>Tag</Name></AttributeList>'
            '<LinkList><Value TargetID="@OpenLink"><Name>%s</Name></Value></LinkList></Hmi.Event.FunctionListEntryParameter>') % tag


def p_screen(screen):
    return ('<Hmi.Event.FunctionListEntryParameter ID="0" CompositionName="Parameters"><AttributeList><Name>Screen name</Name></AttributeList>'
            '<LinkList><Value TargetID="@OpenLink"><Name>%s</Name></Value></LinkList></Hmi.Event.FunctionListEntryParameter>'
            '<Hmi.Event.FunctionListEntryParameter ID="0" CompositionName="Parameters"><AttributeList><Name>Object number</Name>'
            '<Value Type="System.Int32">0</Value></AttributeList></Hmi.Event.FunctionListEntryParameter>') % screen


def event(ev, entries):
    return ('<Hmi.Event.Event ID="0" CompositionName="Events"><AttributeList><Name>%s</Name></AttributeList><ObjectList>'
            '<Hmi.Event.FunctionListEventHandler ID="0" CompositionName="EventHandler"><ObjectList>%s</ObjectList></Hmi.Event.FunctionListEventHandler>'
            '</ObjectList></Hmi.Event.Event>') % (ev, entries)


BTN_STYLE = ('<BackColor>190, 190, 190</BackColor><BorderColor>90, 90, 90</BorderColor><BorderWidth>1</BorderWidth><ForeColor>0, 0, 0</ForeColor>'
             '<TabIndex>2</TabIndex><UseDesignColorSchema>false</UseDesignColorSchema>')
IO_STYLE = ('<BackColor>236, 236, 236</BackColor><BackFillStyle>Solid</BackFillStyle><BorderColor>128, 128, 128</BorderColor><BorderWidth>1</BorderWidth>'
            '<ForeColor>0, 0, 0</ForeColor><HorizontalAlignment>Right</HorizontalAlignment><UseDesignColorSchema>false</UseDesignColorSchema>')


def button(name, x, ev):
    return '<Hmi.Screen.Button ID="0" CompositionName="ScreenItems">%s<ObjectList>%s%s%s%s%s</ObjectList></Hmi.Screen.Button>' % (
        attrs(name, x, 10, 120, 40, BTN_STYLE), font(15, True), ml("HelpText", None), ml("TextOff", "BTN"), ml("TextOn", "BTN"), ev)


def rect(name, x, y, ww, hh, back, anim, border=1):
    return ('<Hmi.Screen.Rectangle ID="0" CompositionName="ScreenItems">%s<ObjectList>%s</ObjectList></Hmi.Screen.Rectangle>') % (
        attrs(name, x, y, ww, hh, '<BackColor>%s</BackColor><BorderColor>90, 90, 90</BorderColor><BorderWidth>%d</BorderWidth>' % (back, border)), anim)


def main():
    cols = ["222, 222, 222", "165, 165, 165", "140, 175, 215", "185, 160, 210", "165, 200, 165", "70, 140, 230", "205, 235, 255", "255, 215, 0"]
    mx = MOTION.get("horizontal", {})
    my = MOTION.get("vertical", {})
    items = [
        '<Hmi.Screen.TextField ID="0" CompositionName="ScreenItems">%s<ObjectList>%s%s</ObjectList></Hmi.Screen.TextField>' % (
            attrs("P_Text", 10, 60, 120, 30, '<BackFillStyle>Transparent</BackFillStyle><BorderWidth>0</BorderWidth><EdgeStyle>None</EdgeStyle>'
                  '<FitToLargest>false</FitToLargest><ForeColor>0, 0, 0</ForeColor><HorizontalAlignment>Left</HorizontalAlignment>'
                  '<UseDesignColorSchema>false</UseDesignColorSchema><VerticalAlignment>Middle</VerticalAlignment>'),
            font(15), ml("Text", "Text")),
        '<Hmi.Screen.IOField ID="0" CompositionName="ScreenItems">%s<ObjectList>%s%s%s</ObjectList></Hmi.Screen.IOField>' % (
            attrs("P_IO", 140, 60, 100, 30, IO_STYLE + '<DataFormat>Decimal</DataFormat><FieldLength>5</FieldLength><FormatPattern>99999</FormatPattern><Mode>Output</Mode>'),
            font(15), ml("HelpText", None), pv("M")),
        '<Hmi.Screen.SymbolicIOField ID="0" CompositionName="ScreenItems">%s<LinkList><TextList TargetID="@OpenLink"><Name>TL_State</Name></TextList></LinkList>'
        '<ObjectList>%s%s%s</ObjectList></Hmi.Screen.SymbolicIOField>' % (
            attrs("P_SymIO", 250, 60, 200, 30, '<BackColor>236, 236, 236</BackColor><BorderColor>128, 128, 128</BorderColor><BorderWidth>1</BorderWidth>'
                  '<ForeColor>0, 0, 0</ForeColor><Mode>Output</Mode><UseDesignColorSchema>false</UseDesignColorSchema>'),
            font(15), ml("HelpText", None), pv("State")),
        button("P_Btn", 10, event("Press", fentry("SetBit", p_tag("BtnStart")))),
        button("P_BtnInv", 140, event("Press", fentry("InvertBit", p_tag("SwOn")))),
        button("P_NavBtn", 270, event("Press", fentry("ActivateScreen", p_screen("Screen_1")))),
        rect("P_CellRect", 10, 110, 60, 40, cols[0], appear("CellSt0_00", [rng(i, i, c) for i, c in enumerate(cols)])),
        rect("P_Lamp", 80, 110, 30, 30, "170, 170, 170", appear("LampReady", [rng(0, 0, "170, 170, 170"), rng(1, 1, "40, 160, 60")])),
        rect("P_LampAlarm", 120, 110, 30, 30, "170, 170, 170", appear("LampAlarm", [rng(0, 0, "170, 170, 170"), rng(1, 1, "220, 0, 0", "Medium")])),
        '<Hmi.Screen.Bar ID="0" CompositionName="ScreenItems">%s<ObjectList>%s</ObjectList></Hmi.Screen.Bar>' % (
            attrs("P_Bar", 160, 110, 200, 30, '<MaximumValue>24</MaximumValue><MinimumValue>0</MinimumValue>'), pv("BalL")),
        '<Hmi.Screen.IOField ID="0" CompositionName="ScreenItems">%s<ObjectList>%s%s%s%s</ObjectList></Hmi.Screen.IOField>' % (
            attrs("P_CraneX", 10, 200, 100, 32, '<BackColor>255, 255, 255</BackColor><BackFillStyle>Solid</BackFillStyle><BorderColor>40, 40, 40</BorderColor>'
                  '<BorderWidth>2</BorderWidth><ForeColor>0, 0, 0</ForeColor><HorizontalAlignment>Center</HorizontalAlignment><UseDesignColorSchema>false</UseDesignColorSchema>'
                  '<DataFormat>Decimal</DataFormat><FieldLength>3</FieldLength><FormatPattern>999</FormatPattern><Mode>Output</Mode>'),
            font(15, True), ml("HelpText", None), pv("Carried"), move("Horizontal", "CraneGX", mx)),
        rect("P_CraneY", 10, 300, 120, 36, "70, 70, 70", move("Vertical", "CraneY", my)),
        '<Hmi.Screen.DateTimeField ID="0" CompositionName="ScreenItems">%s<ObjectList>%s%s</ObjectList></Hmi.Screen.DateTimeField>' % (
            attrs("P_DateTime", 400, 10, 346, 40, '<DisplaySystemTime>true</DisplaySystemTime><Mode>Output</Mode><ShowDate>true</ShowDate><ShowTime>true</ShowTime>'
                  '<BackColor>236, 236, 236</BackColor><ForeColor>0, 0, 0</ForeColor><UseDesignColorSchema>false</UseDesignColorSchema><VerticalAlignment>Middle</VerticalAlignment>'),
            font(15, True), ml("HelpText", None)),
    ]
    w("screens", "Proto",
      '<Hmi.Screen.Screen ID="0"><AttributeList><ActiveLayer>0</ActiveLayer><BackColor>214, 214, 214</BackColor><GridColor>0, 0, 0</GridColor>'
      '<Height>768</Height><Name>Proto</Name><Number>99</Number><Visible>true</Visible><Width>1024</Width></AttributeList>'
      '<LinkList><Template TargetID="@OpenLink"><Name>Tpl</Name></Template></LinkList><ObjectList>%s'
      '<Hmi.Screen.ScreenLayer ID="0" CompositionName="Layers"><AttributeList><Index>0</Index><Name /><VisibleES>true</VisibleES></AttributeList>'
      '<ObjectList>%s</ObjectList></Hmi.Screen.ScreenLayer></ObjectList></Hmi.Screen.Screen>' % (ml("HelpText", None), "".join(items)))
    w("templates", "Tpl",
      '<Hmi.Screen.ScreenTemplate ID="0"><AttributeList><ActiveLayer>0</ActiveLayer><BackColor>214, 214, 214</BackColor><Name>Tpl</Name></AttributeList>'
      '<ObjectList><Hmi.Screen.ScreenLayer ID="0" CompositionName="Layers"><AttributeList><Index>0</Index><Name /><VisibleES>true</VisibleES></AttributeList>'
      '<ObjectList /></Hmi.Screen.ScreenLayer></ObjectList></Hmi.Screen.ScreenTemplate>')
    w("tags", "Proto_tags",
      '<Hmi.Tag.TagTable ID="0"><AttributeList><Name>Proto tags</Name></AttributeList><ObjectList>'
      '<Hmi.Tag.Tag ID="0" CompositionName="Tags"><AttributeList><AcquisitionTriggerMode>Visible</AcquisitionTriggerMode>'
      '<AddressAccessMode>Symbolic</AddressAccessMode><Length>1</Length><LogicalAddress /><Name>P_SwOn</Name></AttributeList>'
      '<LinkList><AcquisitionCycle TargetID="@OpenLink"><Name>100 ms</Name></AcquisitionCycle>'
      '<Connection TargetID="@OpenLink"><Name>HMI_Connection_1</Name></Connection>'
      '<ControllerTag TargetID="@OpenLink"><Name>HMI_IF.SwOn</Name></ControllerTag>'
      '<DataType TargetID="@OpenLink"><Name>Bool</Name></DataType><HmiDataType TargetID="@OpenLink"><Name>Bool</Name></HmiDataType>'
      '</LinkList><ObjectList>%s</ObjectList></Hmi.Tag.Tag></ObjectList></Hmi.Tag.TagTable>' % ml("Comment", None))
    entries = "".join(
        ('<Hmi.TextGraphicList.TextListEntry ID="0" CompositionName="Entries"><AttributeList><DefaultEntry>false</DefaultEntry>'
         '<From>%d</From><To>%d</To></AttributeList><ObjectList>%s</ObjectList></Hmi.TextGraphicList.TextListEntry>') % (v, v, ml("Text", t))
        for v, t in ((0, "OFF"), (1, "INIT")))
    w("textlists", "TL_State",
      '<Hmi.TextGraphicList.TextList ID="0"><AttributeList><ListRange>Decimal</ListRange><Name>TL_State</Name></AttributeList><ObjectList>'
      + ml("Comment", None) + entries + '</ObjectList></Hmi.TextGraphicList.TextList>')
    print("PROTO written ->", OUT, "motion attrs:", MOTION or "(none yet)")


if __name__ == "__main__":
    main()
