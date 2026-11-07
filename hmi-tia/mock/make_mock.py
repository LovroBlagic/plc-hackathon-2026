#!/usr/bin/env python3
"""Writes the MOCK prototype exports used to dry-run gen_hmi.py without TIA.

TextField and IOField are copied from a REAL V21 export (tia-work/export/xml/HMI_SCREEN_Screen_1.xml).
Rectangle/Button/SymbolicIOField/Bar/animations, tag table, text list and template are BEST GUESSES of the
SimaticML schema; the real ones come from HmiGen.exe --export of the human-made prototypes and replace these.
"""
import os
D = os.path.dirname(os.path.abspath(__file__))

HDR = '''<?xml version="1.0" encoding="utf-8"?>
<Document>
  <Engineering version="V21" />
  <DocumentInfo><Created>2026-11-07T00:00:00Z</Created><ExportSetting>WithDefaults</ExportSetting></DocumentInfo>
'''

def font(size=15, style="Bold"):
    return ('<Hmi.Globalization.MultiLingualFont ID="0" CompositionName="Font"><ObjectList>'
            '<Hmi.Globalization.FontItem ID="0" CompositionName="Items"><AttributeList><Culture>en-US</Culture>'
            '<FontFamily>Tahoma</FontFamily><FontSize>%d</FontSize><FontStyle>%s</FontStyle></AttributeList>'
            '</Hmi.Globalization.FontItem></ObjectList></Hmi.Globalization.MultiLingualFont>' % (size, style))

def ml(comp, text=None):
    t = '<Text />' if text is None else '<Text><body><p>%s</p></body></Text>' % text
    return ('<MultilingualText ID="0" CompositionName="%s"><ObjectList><MultilingualTextItem ID="0" CompositionName="Items">'
            '<AttributeList><Culture>en-US</Culture>%s</AttributeList></MultilingualTextItem></ObjectList></MultilingualText>' % (comp, t))

def taglink(prop, tag):
    return ('<Hmi.Screen.Property ID="0" CompositionName="Properties"><AttributeList><Name>%s</Name></AttributeList><ObjectList>'
            '<Hmi.Dynamic.TagConnectionDynamic ID="0" CompositionName="Dynamic"><AttributeList><Indirect>false</Indirect></AttributeList>'
            '<LinkList><Tag TargetID="@OpenLink"><Name>%s</Name></Tag></LinkList></Hmi.Dynamic.TagConnectionDynamic></ObjectList>'
            '</Hmi.Screen.Property>' % (prop, tag))

def geo(name, l=0, t=0, w=100, h=30):
    return '<Left>%d</Left><Top>%d</Top><Width>%d</Width><Height>%d</Height><ObjectName>%s</ObjectName>' % (l, t, w, h, name)

def textfield(name):   # REAL structure (Screen_1 export)
    return ('<Hmi.Screen.TextField ID="0" CompositionName="ScreenItems"><AttributeList>'
            '<BackColor>255, 255, 255</BackColor><BackFillStyle>Transparent</BackFillStyle><BorderBackColor>101, 103, 115</BorderBackColor>'
            '<BorderColor>71, 73, 87</BorderColor><BorderWidth>0</BorderWidth><BottomMargin>2</BottomMargin><CornerRadius>3</CornerRadius>'
            '<EdgeStyle>Double</EdgeStyle><FitToLargest>true</FitToLargest><Flashing>None</Flashing><ForeColor>49, 52, 74</ForeColor>'
            '%s<HorizontalAlignment>Left</HorizontalAlignment><LeftMargin>3</LeftMargin><RightMargin>2</RightMargin><TabIndex>-1</TabIndex>'
            '<TextOrientation>Horizontal</TextOrientation><TopMargin>2</TopMargin><UseDesignColorSchema>false</UseDesignColorSchema>'
            '<VerticalAlignment>Middle</VerticalAlignment></AttributeList><ObjectList>%s%s</ObjectList></Hmi.Screen.TextField>'
            % (geo(name), font(), ml("Text", "Text")))

def iofield(name, tag, mode="Output"):   # REAL structure (Screen_1 export)
    return ('<Hmi.Screen.IOField ID="0" CompositionName="ScreenItems"><AttributeList>'
            '<AboveUpperLimitColor>237, 88, 97</AboveUpperLimitColor><BackColor>255, 255, 255</BackColor><BackFillStyle>Solid</BackFillStyle>'
            '<BelowLowerLimitColor>241, 161, 44</BelowLowerLimitColor><BorderBackColor>101, 103, 115</BorderBackColor><BorderColor>71, 73, 87</BorderColor>'
            '<BorderWidth>1</BorderWidth><BottomMargin>2</BottomMargin><CornerRadius>3</CornerRadius><DataFormat>Decimal</DataFormat>'
            '<EdgeStyle>Double</EdgeStyle><Enabled>true</Enabled><FieldLength>13</FieldLength><FitToLargest>false</FitToLargest>'
            '<Flashing>None</Flashing><ForeColor>49, 52, 74</ForeColor><FormatPattern>s999999999.999</FormatPattern>%s'
            '<HiddenInput>false</HiddenInput><HorizontalAlignment>Left</HorizontalAlignment><LeftMargin>3</LeftMargin><Mode>%s</Mode>'
            '<RightMargin>2</RightMargin><ShiftDecimalPoint>0</ShiftDecimalPoint><ShowLeadingZeros>false</ShowLeadingZeros><TabIndex>1</TabIndex>'
            '<TextOrientation>Horizontal</TextOrientation><TopMargin>2</TopMargin><Unit /><UseDesignColorSchema>false</UseDesignColorSchema>'
            '<UseTwoHandOperation>false</UseTwoHandOperation><VerticalAlignment>Middle</VerticalAlignment></AttributeList>'
            '<ObjectList>%s%s%s</ObjectList></Hmi.Screen.IOField>' % (geo(name), mode, font(), ml("HelpText"), taglink("ProcessValue", tag)))

def symio(name, tag, tl):   # GUESS
    return ('<Hmi.Screen.SymbolicIOField ID="0" CompositionName="ScreenItems"><AttributeList><BackColor>255, 255, 255</BackColor>'
            '<BackFillStyle>Solid</BackFillStyle><BorderWidth>1</BorderWidth>%s<Mode>Output</Mode><TabIndex>-1</TabIndex></AttributeList>'
            '<LinkList><TextList TargetID="@OpenLink"><Name>%s</Name></TextList></LinkList>'
            '<ObjectList>%s%s%s</ObjectList></Hmi.Screen.SymbolicIOField>' % (geo(name), tl, font(), ml("HelpText"), taglink("ProcessValue", tag)))

def appearance(tag, ranges):   # GUESS
    rs = "".join('<Hmi.Dynamic.AppearanceAnimationRange ID="0" CompositionName="Ranges"><AttributeList><Range>%s</Range>'
                 '<BackColor>%s</BackColor><Flashing>%s</Flashing></AttributeList></Hmi.Dynamic.AppearanceAnimationRange>' % r for r in ranges)
    return ('<Hmi.Dynamic.AppearanceAnimation ID="0" CompositionName="Animations"><AttributeList><AnimationMode>Range</AnimationMode></AttributeList>'
            '<LinkList><Tag TargetID="@OpenLink"><Name>%s</Name></Tag></LinkList><ObjectList>%s</ObjectList></Hmi.Dynamic.AppearanceAnimation>' % (tag, rs))

def rect(name, tag, ranges, extra=""):   # GUESS
    return ('<Hmi.Screen.Rectangle ID="0" CompositionName="ScreenItems"><AttributeList><BackColor>222, 222, 222</BackColor>'
            '<BorderColor>128, 128, 128</BorderColor><BorderWidth>1</BorderWidth>%s</AttributeList><ObjectList>%s%s</ObjectList>'
            '</Hmi.Screen.Rectangle>' % (geo(name), appearance(tag, ranges), extra))

def button(name, fn, tag=None, screen=None):   # GUESS
    if fn == "ActivateScreen":
        par = '<Hmi.Event.FunctionParameter ID="0" CompositionName="Parameters"><AttributeList><Name>Screen name</Name><Value>%s</Value></AttributeList></Hmi.Event.FunctionParameter>' % screen
    else:
        par = ('<Hmi.Event.FunctionParameter ID="0" CompositionName="Parameters"><AttributeList><Name>Tag</Name></AttributeList>'
               '<LinkList><Tag TargetID="@OpenLink"><Name>%s</Name></Tag></LinkList></Hmi.Event.FunctionParameter>' % tag)
    ev = ('<Hmi.Event.EventHandler ID="0" CompositionName="EventHandlers"><AttributeList><EventType>Press</EventType></AttributeList><ObjectList>'
          '<Hmi.Event.FunctionCall ID="0" CompositionName="FunctionList"><AttributeList><Name>%s</Name></AttributeList><ObjectList>%s</ObjectList>'
          '</Hmi.Event.FunctionCall></ObjectList></Hmi.Event.EventHandler>' % (fn, par))
    return ('<Hmi.Screen.Button ID="0" CompositionName="ScreenItems"><AttributeList><BackColor>190, 190, 190</BackColor>%s<TabIndex>2</TabIndex>'
            '</AttributeList><ObjectList>%s%s%s%s%s</ObjectList></Hmi.Screen.Button>' % (geo(name), font(), ml("HelpText"), ml("TextOff", "BTN"), ml("TextOn", "BTN"), ev))

def bar(name, tag):   # GUESS
    return ('<Hmi.Screen.Bar ID="0" CompositionName="ScreenItems"><AttributeList>%s<MaximumValue>24</MaximumValue><MinimumValue>0</MinimumValue>'
            '</AttributeList><ObjectList>%s</ObjectList></Hmi.Screen.Bar>' % (geo(name), taglink("ProcessValue", tag)))

def movement(kind, tag, sx, sy, ex, ey):   # GUESS
    return ('<Hmi.Dynamic.%sMovementAnimation ID="0" CompositionName="Animations"><AttributeList><RangeFrom>0</RangeFrom><RangeTo>9</RangeTo>'
            '<StartLeft>%d</StartLeft><StartTop>%d</StartTop><EndLeft>%d</EndLeft><EndTop>%d</EndTop></AttributeList>'
            '<LinkList><Tag TargetID="@OpenLink"><Name>%s</Name></Tag></LinkList></Hmi.Dynamic.%sMovementAnimation>' % (kind, sx, sy, ex, ey, tag, kind))

CELL = [("0", "222, 222, 222", "None"), ("1", "165, 165, 165", "None"), ("2", "140, 175, 215", "None"), ("3", "185, 160, 210", "None"),
        ("4", "165, 200, 165", "None"), ("5", "70, 140, 230", "None"), ("6", "205, 235, 255", "None"), ("7", "255, 215, 0", "None")]

def proto_screen():
    items = [
        textfield("P_Text"), iofield("P_IO", "M"), symio("P_SymIO", "State", "TL_State"),
        button("P_Btn", "SetBit", tag="BtnStart"), button("P_BtnInv", "InvertBit", tag="SwOn"),
        button("P_NavBtn", "ActivateScreen", screen="Screen_1"),
        rect("P_CellRect", "CellSt0_00", CELL),
        rect("P_Lamp", "LampReady", [("0", "170, 170, 170", "None"), ("1", "40, 160, 60", "None")]),
        rect("P_LampAlarm", "LampAlarm", [("0", "170, 170, 170", "None"), ("1", "220, 0, 0", "Standard")]),
        bar("P_Bar", "BalL"),
        iofield("P_CraneX", "Carried").replace("</ObjectList></Hmi.Screen.IOField>",
                                               movement("Horizontal", "CraneGX", 62, 188, 1088, 188) + "</ObjectList></Hmi.Screen.IOField>"),
        rect("P_CraneY", "CraneY", [("0", "70, 70, 70", "None")], movement("Vertical", "CraneY", 566, 237, 566, 897)),
    ]
    return (HDR + '<Hmi.Screen.Screen ID="0"><AttributeList><ActiveLayer>0</ActiveLayer><BackColor>182, 182, 182</BackColor>'
            '<GridColor>0, 0, 0</GridColor><Height>1080</Height><Name>Proto</Name><Number>99</Number><Visible>true</Visible><Width>1920</Width>'
            '</AttributeList><LinkList><Template TargetID="@OpenLink"><Name>Tpl</Name></Template></LinkList><ObjectList>%s'
            '<Hmi.Screen.ScreenLayer ID="0" CompositionName="Layers"><AttributeList><Index>0</Index><Name /><VisibleES>true</VisibleES></AttributeList>'
            '<ObjectList>%s</ObjectList></Hmi.Screen.ScreenLayer></ObjectList></Hmi.Screen.Screen></Document>\n' % (ml("HelpText"), "".join(items)))

def template():
    return (HDR + '<Hmi.Screen.ScreenTemplate ID="0"><AttributeList><ActiveLayer>0</ActiveLayer><BackColor>182, 182, 182</BackColor>'
            '<Name>Tpl</Name></AttributeList><ObjectList><Hmi.Screen.ScreenLayer ID="0" CompositionName="Layers"><AttributeList><Index>0</Index>'
            '<Name /><VisibleES>true</VisibleES></AttributeList><ObjectList /></Hmi.Screen.ScreenLayer></ObjectList></Hmi.Screen.ScreenTemplate></Document>\n')

def tagtable():
    return (HDR + '<Hmi.Tag.TagTable ID="0"><AttributeList><Name>Proto tags</Name></AttributeList><ObjectList>'
            '<Hmi.Tag.Tag ID="0" CompositionName="Tags"><AttributeList><AcquisitionMode>CyclicOnUse</AcquisitionMode>'
            '<AddressAccessMode>Symbolic</AddressAccessMode><Coding>Binary</Coding><Length>1</Length><LinearScaling>false</LinearScaling>'
            '<Name>P_SwOn</Name><Persistency>false</Persistency><StartValue /><UpdateMode>ProjectWide</UpdateMode></AttributeList>'
            '<LinkList><AcquisitionCycle TargetID="@OpenLink"><Name>100 ms</Name></AcquisitionCycle>'
            '<Connection TargetID="@OpenLink"><Name>HMI_Connection_1</Name></Connection>'
            '<ControllerTag TargetID="@OpenLink"><Name>HMI_IF.SwOn</Name></ControllerTag>'
            '<DataType TargetID="@OpenLink"><Name>Bool</Name></DataType><HmiDataType TargetID="@OpenLink"><Name>Bool</Name></HmiDataType></LinkList>'
            '<ObjectList>%s</ObjectList></Hmi.Tag.Tag></ObjectList></Hmi.Tag.TagTable></Document>\n' % ml("Comment"))

def textlist():
    e = lambda v, t: ('<Hmi.TextGraphicList.TextListEntry ID="0" CompositionName="Entries"><AttributeList><DefaultEntry>false</DefaultEntry>'
                      '<From>%d</From><To>%d</To></AttributeList><ObjectList>%s</ObjectList></Hmi.TextGraphicList.TextListEntry>' % (v, v, ml("Text", t)))
    return (HDR + '<Hmi.TextGraphicList.TextList ID="0"><AttributeList><ListRange>Range</ListRange><Name>TL_State</Name></AttributeList>'
            '<ObjectList>%s%s%s</ObjectList></Hmi.TextGraphicList.TextList></Document>\n' % (ml("Comment"), e(0, "OFF"), e(1, "INIT")))

for sub, fn, body in (("screens", "Proto.xml", proto_screen()), ("templates", "Tpl.xml", template()),
                      ("tags", "Proto_tags.xml", tagtable()), ("textlists", "TL_State.xml", textlist())):
    os.makedirs(os.path.join(D, sub), exist_ok=True)
    with open(os.path.join(D, sub, fn), "w", encoding="utf-8") as f:
        f.write(body)
    print("mock", sub, fn)
