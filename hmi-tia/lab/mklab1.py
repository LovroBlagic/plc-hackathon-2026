# Build lab round-1 import set: one test screen per object type, from mock prototypes.
import os, re, sys, copy
import xml.etree.ElementTree as ET
HERE=os.path.dirname(os.path.abspath(__file__)); MOCK=os.path.join(HERE,"..","mock")
OUT=sys.argv[1]
HDR='<?xml version="1.0" encoding="utf-8"?>\n<Document>\n  <Engineering version="V21" />\n'
def rd(p):
    s=open(p,encoding="utf-8-sig").read(); return s
def items():
    t=ET.fromstring(rd(os.path.join(MOCK,"screens","Proto.xml")).split("\n",1)[1] if False else rd(os.path.join(MOCK,"screens","Proto.xml")).replace('<?xml version="1.0" encoding="utf-8"?>',''))
    P={}
    for el in t.iter():
        if el.get("CompositionName")=="ScreenItems":
            P[el.find("AttributeList").find("ObjectName").text]=el
    return P
def renum(root):
    n=0
    for el in root.iter():
        if "ID" in el.attrib: el.set("ID",format(n,"X")); n+=1
def screen(name,num,its,tpl=False):
    s=ET.Element("Hmi.Screen.Screen",ID="0")
    al=ET.SubElement(s,"AttributeList")
    for k,v in (("ActiveLayer","0"),("BackColor","182, 182, 182"),("GridColor","0, 0, 0"),("Height","768"),("Name",name),("Number",str(num)),("Visible","true"),("Width","1024")):
        ET.SubElement(al,k).text=v
    if tpl:
        ll=ET.SubElement(s,"LinkList"); t=ET.SubElement(ll,"Template",TargetID="@OpenLink"); ET.SubElement(t,"Name").text="Tpl"
    ol=ET.SubElement(s,"ObjectList")
    lay=ET.SubElement(ol,"Hmi.Screen.ScreenLayer",ID="0",CompositionName="Layers")
    lal=ET.SubElement(lay,"AttributeList")
    ET.SubElement(lal,"Index").text="0"; ET.SubElement(lal,"Name"); ET.SubElement(lal,"VisibleES").text="true"
    lol=ET.SubElement(lay,"ObjectList")
    for i in its: lol.append(i)
    doc=ET.Element("Document"); ET.SubElement(doc,"Engineering",version="V21"); doc.append(s)
    renum(doc)
    os.makedirs(os.path.join(OUT,"screens"),exist_ok=True)
    open(os.path.join(OUT,"screens",name+".xml"),"w",encoding="utf-8").write('<?xml version="1.0" encoding="utf-8"?>\n'+ET.tostring(doc,encoding="unicode"))
P=items()
def strip_anim(el):
    el=copy.deepcopy(el)
    ol=el.find("ObjectList")
    if ol is not None:
        for c in list(ol):
            if c.get("CompositionName") in ("Animations","EventHandlers"): ol.remove(c)
    return el
def only(el,keep):
    el=copy.deepcopy(el); ol=el.find("ObjectList")
    if ol is not None:
        for c in list(ol):
            if c.get("CompositionName") in ("Animations","EventHandlers") and c.tag not in keep: ol.remove(c)
    return el
n=20
def S(name,its,tpl=False):
    global n; n+=1; screen(name,n,its,tpl)
S("T01_Rect",[strip_anim(P["P_CellRect"])])
S("T02_RectApp",[copy.deepcopy(P["P_CellRect"])])
S("T03_Btn",[strip_anim(P["P_Btn"])])
S("T04_BtnSet",[copy.deepcopy(P["P_Btn"])])
S("T05_BtnInv",[copy.deepcopy(P["P_BtnInv"])])
S("T06_BtnNav",[copy.deepcopy(P["P_NavBtn"])])
S("T07_Sym",[copy.deepcopy(P["P_SymIO"])])
S("T08_Bar",[copy.deepcopy(P["P_Bar"])])
S("T09_IOMove",[copy.deepcopy(P["P_CraneX"])])
S("T10_RectV",[only(P["P_CraneY"],("Hmi.Dynamic.VerticalMovementAnimation",))])
S("T11_LampAlarm",[copy.deepcopy(P["P_LampAlarm"])])
# date time minimal
dt=ET.Element("Hmi.Screen.DateTimeField",ID="0",CompositionName="ScreenItems"); al=ET.SubElement(dt,"AttributeList")
for k,v in (("Left","10"),("Top","10"),("Width","346"),("Height","40"),("ObjectName","P_DateTime")): ET.SubElement(al,k).text=v
S("T12_DT",[dt])
S("T13_TplLink",[copy.deepcopy(P["P_Text"])],tpl=True)
screen("Alarms",15,[],tpl=True)
# template, textlist, tag table from mock
import shutil
for sub in ("templates","textlists","tags"):
    os.makedirs(os.path.join(OUT,sub),exist_ok=True)
    for f in os.listdir(os.path.join(MOCK,sub)): shutil.copy(os.path.join(MOCK,sub,f),os.path.join(OUT,sub,f))
print("ok",os.listdir(os.path.join(OUT,"screens")))
