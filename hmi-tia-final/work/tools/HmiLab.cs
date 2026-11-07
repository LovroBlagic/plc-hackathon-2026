// HmiLab: Openness helper for building the crane HMI without GUI clicks (WinCC RT Advanced / HMI Classic).
// C# 5, build with hmi-tia\build_hmilab.ps1.
//
//   HmiLab.exe --project C:\abs\ProjDir [--headless] [--lock hmi-builder]
//              [--probe]                 dump devices, interfaces, subnets, comm services, HMI attributes
//              [--net]                   connect PLC_1 PN + HMI PC station IE to one subnet, create HMI connection
//              [--import C:\abs\dir]     import dir\{connections,cycles,textlists,tags,templates,screens}\*.xml
//                                        one file at a time (Override), full exception text on failure
//              [--delete-screens a,b]    delete these screens before importing
//              [--hmi-set Name=Value;..] set HmiTarget/HMI device-item attributes (best effort)
//              [--compile]               compile HMI (and PLC with --compile-plc)
//              [--export C:\abs\dir]     export screens, templates, tag tables, text lists, connections
//              [--archive C:\abs\x.zap21]
//              [--no-save]
// Summary line: LAB_RESULT errors=N import_errors=K
using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Reflection;
using System.Collections.Generic;
using Siemens.Engineering;
using Siemens.Engineering.HW;
using Siemens.Engineering.HW.Features;
using Siemens.Engineering.Hmi;
using Siemens.Engineering.Hmi.Screen;
using Siemens.Engineering.Hmi.Tag;
using Siemens.Engineering.SW;
using CC = Siemens.Engineering.HW.CommunicationConnections;

internal static class Program
{
    const string ApiDir = @"C:\Program Files\Siemens\Automation\Portal V21\PublicAPI\V21\net48";
    static Program() { AppDomain.CurrentDomain.AssemblyResolve += Resolve; }
    static Assembly Resolve(object s, ResolveEventArgs e)
    {
        var n = new AssemblyName(e.Name).Name;
        var f = Path.Combine(ApiDir, n + ".dll");
        return (n.StartsWith("Siemens.Engineering") && File.Exists(f)) ? Assembly.LoadFrom(f) : null;
    }
    static int Main(string[] args)
    {
        try { return Lab.Run(args); }
        catch (Exception ex) { Console.WriteLine("FATAL: " + Lab.ExText(ex)); return 2; }
        finally { Lab.ReleaseLock(); }
    }
}

internal static class Lab
{
    static string Arg(string[] a, string k) { int i = Array.IndexOf(a, k); return (i >= 0 && i + 1 < a.Length) ? a[i + 1] : null; }
    static bool Flag(string[] a, string k) { return Array.IndexOf(a, k) >= 0; }
    public static string ExText(Exception ex)
    {
        var sb = new StringBuilder();
        for (var e = ex; e != null; e = e.InnerException) {
            if (sb.Length > 0) sb.Append(" | ");
            sb.Append(e.GetType().Name).Append(": ").Append(e.Message.Replace("\r", " ").Replace("\n", " "));
        }
        return sb.ToString();
    }

    static string heldLock;
    static System.Threading.Timer heartbeat;
    public static void ReleaseLock()
    {
        if (heartbeat != null) { heartbeat.Dispose(); heartbeat = null; }
        if (heldLock != null) { try { File.Delete(heldLock); Console.WriteLine("LOCK released"); } catch { } heldLock = null; }
    }
    static string FindTiaWork(string proj)
    {
        var d = new DirectoryInfo(proj);
        while (d != null) { if (d.Name.Equals("tia-work", StringComparison.OrdinalIgnoreCase)) return d.FullName; d = d.Parent; }
        return Path.GetDirectoryName(proj);
    }
    static bool TakeLock(string proj, string worker, int waitS)
    {
        string lf = Path.Combine(FindTiaWork(proj), "openness.lock");
        DateTime until = DateTime.Now.AddSeconds(waitS);
        while (true) {
            if (!File.Exists(lf) && System.Diagnostics.Process.GetProcessesByName("Siemens.Automation.Portal").Length > 0
                && DateTime.Now < until) { Console.WriteLine("LOCK free but a TIA Portal process is running, waiting..."); System.Threading.Thread.Sleep(20000); continue; }
            if (File.Exists(lf)) {
                double age = (DateTime.Now - File.GetLastWriteTime(lf)).TotalMinutes;
                string who = ""; try { who = File.ReadAllText(lf).Trim(); } catch { }
                if (DateTime.Now < until) { Console.WriteLine("LOCK held by '" + who + "' (" + age.ToString("0.0") + " min), waiting..."); System.Threading.Thread.Sleep(20000); continue; }
                Console.WriteLine("FATAL: lock held by '" + who + "': " + lf); return false;
            }
            File.WriteAllText(lf, worker + " " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
            heldLock = lf;
            Console.WriteLine("LOCK taken: " + lf);
            // heartbeat: others treat a lock older than 10 min as stale, so refresh it every 2 min
            heartbeat = new System.Threading.Timer(_ => {
                try { if (heldLock != null) File.WriteAllText(heldLock, worker + " " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")); } catch { }
            }, null, 120000, 120000);
            return true;
        }
    }

    public static int Run(string[] a)
    {
        string proj = Arg(a, "--project");
        if (proj == null) { Console.WriteLine("FATAL: --project required"); return 2; }
        proj = Path.GetFullPath(proj.Replace('/', '\\')).TrimEnd('\\');
        if (proj.EndsWith(".ap21", StringComparison.OrdinalIgnoreCase)) proj = Path.GetDirectoryName(proj);
        string lockOwner = Arg(a, "--lock");
        if (lockOwner != null) { int w = 3600; int.TryParse(Arg(a, "--lock-wait") ?? "3600", out w); if (!TakeLock(proj, lockOwner, w)) return 2; }

        Console.WriteLine("STARTING headless TIA Portal " + DateTime.Now.ToString("HH:mm:ss"));
        using (var portal = Flag(a, "--attach") ? TiaPortal.GetProcesses().First().Attach() : new TiaPortal(TiaPortalMode.WithoutUserInterface))
        {
            string ap21 = Directory.GetFiles(proj, "*.ap21").First();
            Project p = portal.Projects.FirstOrDefault(x => string.Equals(x.Path.FullName, ap21, StringComparison.OrdinalIgnoreCase)) ?? portal.Projects.Open(new FileInfo(ap21));
            Console.WriteLine("OPENED " + ap21 + " " + DateTime.Now.ToString("HH:mm:ss"));
            int errs = 0, importErrors = 0;

            if (Flag(a, "--probe")) Probe(p);
            if (Flag(a, "--probe-plc")) {
                foreach (var d in AllDevices(p)) foreach (var di in Walk(d.DeviceItems)) {
                    var sc = di.GetService<SoftwareContainer>();
                    var plc = sc == null ? null : sc.Software as PlcSoftware;
                    if (plc == null) continue;
                    foreach (var b in plc.BlockGroup.Blocks) Console.WriteLine("PLC BLOCK " + b.Name + " #" + b.Number + " " + b.GetType().Name + " consistent=" + b.IsConsistent);
                    foreach (var g in plc.BlockGroup.Groups) foreach (var b in g.Blocks) Console.WriteLine("PLC BLOCK " + g.Name + "/" + b.Name + " #" + b.Number + " consistent=" + b.IsConsistent);
                }
            }
            if (Flag(a, "--net")) { try { Net(p); } catch (Exception ex) { errs++; Console.WriteLine("[ERROR] NET: " + ExText(ex)); } }

            HmiTarget hmi = FindHmi(p);
            if (hmi == null) { Console.WriteLine("FATAL: no HmiTarget"); return 2; }
            Console.WriteLine("HMI software: " + hmi.Name);
            foreach (var c in hmi.Connections) Console.WriteLine("HMI CONNECTION \"" + c.Name + "\"");

            if (Flag(a, "--probe")) DumpAttrs("HmiTarget", hmi, null);
            if (Flag(a, "--compile-hw")) {
                foreach (var d in AllDevices(p)) {
                    var comp = d.GetService<Siemens.Engineering.Compiler.ICompilable>();
                    if (comp == null) { Console.WriteLine("HW " + d.Name + " not compilable"); continue; }
                    try { var res = comp.Compile(); Dump(res.Messages, ""); Console.WriteLine("HW_COMPILE " + d.Name + " state=" + res.State + " errors=" + res.ErrorCount + " warnings=" + res.WarningCount); }
                    catch (Exception ex) { Console.WriteLine("HW_COMPILE " + d.Name + ": " + ExText(ex)); }
                }
                foreach (var c in hmi.Connections) Console.WriteLine("HMI CONNECTION after hw compile \"" + c.Name + "\"");
                Console.WriteLine("HMI CONNECTIONS count=" + hmi.Connections.Count);
            }
            if (Flag(a, "--tag-probe")) {
                foreach (var t in hmi.TagFolder.TagTables) foreach (var tg in t.Tags) {
                    DumpAttrs("TAG " + t.Name + "/" + tg.Name, tg, null);
                    try { foreach (var ci in ((IEngineeringObject)tg).GetCompositionInfos()) Console.WriteLine("    TAG comp " + ci.Name); } catch { }
                }
            }
            foreach (var c in hmi.Connections) DumpAttrs("HMI-CONNECTION " + c.Name, c, null);
            string linkedExport = Arg(a, "--export-linked-tags");
            if (linkedExport != null) {
                Directory.CreateDirectory(linkedExport);
                foreach (var table in hmi.TagFolder.TagTables) foreach (var tag in table.Tags) {
                    DumpAttrs("EXPORTED-TAG " + table.Name + "/" + tag.Name, tag, null);
                    tag.Export(new FileInfo(Path.Combine(linkedExport, table.Name.Replace(" ", "_") + "__" + tag.Name + ".xml")), ExportOptions.WithDefaults);
                }
            }
            string tagTest = Arg(a, "--single-tag-test");
            if (tagTest != null) {
                try {
                    var table = hmi.TagFolder.TagTables.Find("T_LinkProbe");
                    if (table == null) {
                        hmi.TagFolder.TagTables.Import(new FileInfo(Path.Combine(tagTest, "empty_table.xml")), ImportOptions.Override);
                        table = hmi.TagFolder.TagTables.Find("T_LinkProbe");
                    }
                    foreach (var tag in table.Tags.Import(new FileInfo(Path.Combine(tagTest, "single_tag.xml")), ImportOptions.Override)) {
                        Console.WriteLine("SINGLE_TAG_IMPORTED " + tag.Name);
                        DumpAttrs("LINKED-TAG " + tag.Name, tag, null);
                        tag.Export(new FileInfo(Path.Combine(tagTest, "linked_tag_export.xml")), ExportOptions.WithDefaults);
                    }
                } catch (Exception ex) { errs++; Console.WriteLine("[ERROR] SINGLE_TAG: " + ExText(ex)); }
            }
            string screenOut = Arg(a, "--screen-out");
            if (screenOut != null) {
                var screen = hmi.ScreenFolder.Screens.Find(Arg(a, "--screen-name") ?? "Alarms");
                screen.Export(new FileInfo(screenOut), ExportOptions.WithDefaults);
                Console.WriteLine("SCREEN_EXPORTED " + screenOut);
            }
            string hs = Arg(a, "--hmi-set");
            if (hs != null) HmiSet(p, hmi, hs);

            string del = Arg(a, "--delete-screens");
            if (del != null) foreach (var n in del.Split(',')) {
                var s = hmi.ScreenFolder.Screens.Find(n.Trim());
                if (s != null) { s.Delete(); Console.WriteLine("DELETED screen " + n); }
            }
            string imp = Arg(a, "--import");
            if (imp != null) importErrors = Import(hmi, Path.GetFullPath(imp));

            if (Flag(a, "--compile-plc")) errs += CompilePlc(p);
            if (Flag(a, "--compile")) {
                var comp = ((IEngineeringServiceProvider)hmi).GetService<Siemens.Engineering.Compiler.ICompilable>();
                var res = comp.Compile();
                Dump(res.Messages, "");
                errs += res.ErrorCount;
                Console.WriteLine("HMI_COMPILE state=" + res.State + " errors=" + res.ErrorCount + " warnings=" + res.WarningCount);
            }
            string exp = Arg(a, "--export");
            if (exp != null) Export(hmi, Path.GetFullPath(exp));

            if (!Flag(a, "--no-save")) { p.Save(); Console.WriteLine("SAVED"); }
            string arc = Arg(a, "--archive");
            if (arc != null) {
                var fi = new FileInfo(Path.GetFullPath(arc));
                if (fi.Exists) fi.Delete();
                p.Archive(fi.Directory, fi.Name, ProjectArchivationMode.Compressed);
                Console.WriteLine("ARCHIVED " + fi.FullName);
            }
            if (!Flag(a, "--attach")) p.Close();
            Console.WriteLine("LAB_RESULT errors=" + errs + " import_errors=" + importErrors);
            return (errs + importErrors) > 0 ? 1 : 0;
        }
    }

    // ---------------- device walk ----------------
    static IEnumerable<DeviceItem> Walk(DeviceItemComposition items)
    {
        foreach (var i in items) { yield return i; foreach (var c in Walk(i.DeviceItems)) yield return c; }
    }
    static IEnumerable<Device> AllDevices(Project p)
    {
        foreach (var d in p.Devices) yield return d;
        foreach (var g in p.DeviceGroups) foreach (var d in Grp(g)) yield return d;
        foreach (var d in p.UngroupedDevicesGroup.Devices) yield return d;
    }
    static IEnumerable<Device> Grp(DeviceUserGroup g)
    {
        foreach (var d in g.Devices) yield return d;
        foreach (var s in g.Groups) foreach (var d in Grp(s)) yield return d;
    }
    static HmiTarget FindHmi(Project p)
    {
        foreach (var d in AllDevices(p)) foreach (var di in Walk(d.DeviceItems)) {
            var sc = di.GetService<SoftwareContainer>();
            var h = sc == null ? null : sc.Software as HmiTarget;
            if (h != null) return h;
        }
        return null;
    }

    static void Probe(Project p)
    {
        foreach (var s in p.Subnets) Console.WriteLine("SUBNET " + s.Name + " " + s.NetType);
        foreach (var d in AllDevices(p)) {
            Console.WriteLine("DEVICE " + d.Name + " type=" + d.TypeIdentifier);
            foreach (var di in Walk(d.DeviceItems)) {
                var sb = new StringBuilder("  ITEM " + di.Name + " [" + di.TypeIdentifier + "]");
                var ni = di.GetService<NetworkInterface>();
                if (ni != null) {
                    sb.Append(" NI type=" + ni.InterfaceType);
                    foreach (Node n in ni.Nodes) {
                        object addr = null; try { addr = n.GetAttribute("Address"); } catch { }
                        sb.Append(" node=" + n.Name + " addr=" + addr + " subnet=" + (n.ConnectedSubnet == null ? "-" : n.ConnectedSubnet.Name));
                    }
                }
                var cm = di.GetService<CommunicationManagement>();
                if (cm != null) sb.Append(" COMM(" + cm.Connections.Count + ")");
                var sc = di.GetService<SoftwareContainer>();
                if (sc != null && sc.Software != null) sb.Append(" SW=" + sc.Software.GetType().Name + ":" + sc.Software.Name);
                Console.WriteLine(sb.ToString());
                if (cm != null) foreach (CC.Connection c in cm.Connections) DumpConn(c);
                if (sc != null && sc.Software is HmiTarget) DumpAttrs("HMI-ITEM " + di.Name, di, null);
                if (d.Name.StartsWith("PC")) DumpAttrs("PC-ITEM " + di.Name, di, "resol|screen|start|display|width|height");
            }
        }
    }
    static void DumpConn(CC.Connection c)
    {
        Console.WriteLine("    CONN type=" + c.ConnectionType + " valid=" + c.IsValid + " local=" + (c.LocalTarget == null ? "-" : c.LocalTarget.Name) +
            " partner=" + (c.PartnerTarget == null ? "-" : c.PartnerTarget.Name) + " subnet=" + c.LocalSubnetName);
        DumpAttrs("    CONN-ATTR", c, null);
    }
    static void DumpAttrs(string what, IEngineeringObject o, string filter)
    {
        try {
            foreach (var ai in o.GetAttributeInfos()) {
                if (filter != null && !System.Text.RegularExpressions.Regex.IsMatch(ai.Name, filter, System.Text.RegularExpressions.RegexOptions.IgnoreCase)) continue;
                object v = null; string err = "";
                try { v = o.GetAttribute(ai.Name); } catch (Exception ex) { err = " (" + ex.GetType().Name + ")"; }
                Console.WriteLine("    " + what + " ." + ai.Name + " = " + v + err + " [" + ai.AccessMode + "]");
            }
        } catch (Exception ex) { Console.WriteLine("    " + what + " attrs: " + ExText(ex)); }
    }

    // ---------------- network + HMI connection ----------------
    static void Net(Project p)
    {
        DeviceItem plcCpu = null; Node plcNode = null; Node hmiNode = null; DeviceItem hmiRt = null;
        foreach (var d in AllDevices(p)) foreach (var di in Walk(d.DeviceItems)) {
            var sc = di.GetService<SoftwareContainer>();
            if (sc != null && sc.Software is PlcSoftware) plcCpu = di;
            if (sc != null && sc.Software is HmiTarget) hmiRt = di;
        }
        if (plcCpu == null || hmiRt == null) throw new Exception("PLC CPU or HMI item not found");
        Device plcDev = (Device)FindDevice(plcCpu), hmiDev = (Device)FindDevice(hmiRt);
        foreach (var di in Walk(plcDev.DeviceItems)) {
            var ni = di.GetService<NetworkInterface>();
            if (ni != null && ni.InterfaceType == NetType.Ethernet && ni.Nodes.Count > 0 && plcNode == null) plcNode = ni.Nodes[0];
        }
        foreach (var di in Walk(hmiDev.DeviceItems)) {
            var ni = di.GetService<NetworkInterface>();
            if (ni != null && ni.InterfaceType == NetType.Ethernet && ni.Nodes.Count > 0 && hmiNode == null) hmiNode = ni.Nodes[0];
        }
        if (plcNode == null || hmiNode == null) throw new Exception("Ethernet nodes not found plc=" + plcNode + " hmi=" + hmiNode);
        Console.WriteLine("NET plc node " + plcNode.Name + " addr=" + plcNode.GetAttribute("Address") + "; hmi node " + hmiNode.Name + " addr=" + hmiNode.GetAttribute("Address"));
        Subnet sn = plcNode.ConnectedSubnet ?? hmiNode.ConnectedSubnet;
        if (sn == null) { sn = plcNode.CreateAndConnectToSubnet("PN/IE_1"); Console.WriteLine("NET created subnet " + sn.Name); }
        if (plcNode.ConnectedSubnet == null) plcNode.ConnectToSubnet(sn);
        if (hmiNode.ConnectedSubnet == null) { hmiNode.ConnectToSubnet(sn); Console.WriteLine("NET hmi connected to " + sn.Name); }
        if (string.Equals("" + plcNode.GetAttribute("Address"), "" + hmiNode.GetAttribute("Address"))) {
            hmiNode.SetAttribute("Address", "192.168.0.2"); Console.WriteLine("NET hmi address -> 192.168.0.2");
        }
        Console.WriteLine("NET plc addr=" + plcNode.GetAttribute("Address") + " hmi addr=" + hmiNode.GetAttribute("Address") + " subnet=" + sn.Name);

        // HMI connection: try comm services on HMI-side items, then PLC-side
        var cands = new List<Tuple<DeviceItem, Node, DeviceItem, Node>>();
        foreach (var di in new[] { hmiRt }.Concat(Walk(hmiDev.DeviceItems))) cands.Add(Tuple.Create(di, hmiNode, plcCpu, plcNode));
        foreach (var di in new[] { plcCpu }.Concat(Walk(plcDev.DeviceItems))) cands.Add(Tuple.Create(di, plcNode, hmiRt, hmiNode));
        var seen = new HashSet<DeviceItem>();
        foreach (var c in cands) {
            if (!seen.Add(c.Item1)) continue;
            var cm = c.Item1.GetService<CommunicationManagement>();
            if (cm == null) continue;
            foreach (CC.Connection ex in cm.Connections)
                if (ex.ConnectionType == CC.ConnectionType.HmiConnection) { Console.WriteLine("NET HMI connection already exists on " + c.Item1.Name); DumpConn(ex); return; }
            try {
                var hc = cm.Connections.Create<CC.HmiConnection>(c.Item2, c.Item3, c.Item4);
                Console.WriteLine("NET created HmiConnection via " + c.Item1.Name + " valid=" + hc.IsValid);
                try { hc.SetAttribute("Name", "HMI_Connection_1"); } catch (Exception ex) { Console.WriteLine("NET set Name: " + ExText(ex)); }
                DumpConn(hc);
                return;
            } catch (Exception ex) { Console.WriteLine("NET create via " + c.Item1.Name + ": " + ExText(ex)); }
        }
        throw new Exception("could not create HMI connection");
    }
    static object FindDevice(IEngineeringObject o)
    {
        while (o != null && !(o is Device)) o = o.Parent;
        return o;
    }

    static void HmiSet(Project p, HmiTarget hmi, string spec)
    {
        foreach (var kv in spec.Split(';')) {
            if (kv.Trim().Length == 0) continue;
            var parts = kv.Split(new[] { '=' }, 2);
            string n = parts[0].Trim(), v = parts[1].Trim();
            bool done = false;
            foreach (IEngineeringObject o in new IEngineeringObject[] { hmi }) {
                try {
                    var info = o.GetAttributeInfos().FirstOrDefault(x => x.Name == n);
                    if (info == null) continue;
                    object cur = o.GetAttribute(n);
                    object val = cur == null ? (object)v : (cur is Enum ? Enum.Parse(cur.GetType(), v) : Convert.ChangeType(v, cur.GetType()));
                    o.SetAttribute(n, val); done = true;
                    Console.WriteLine("SET " + n + " = " + o.GetAttribute(n));
                } catch (Exception ex) { Console.WriteLine("[WARNING] SET " + n + ": " + ExText(ex)); }
            }
            if (!done) Console.WriteLine("[WARNING] SET " + n + ": attribute not found/set");
        }
    }

    // ---------------- import / export ----------------
    static int Import(HmiTarget hmi, string dir)
    {
        int bad = 0;
        bad += ImportSet(Path.Combine(dir, "connections"), "connection", f => hmi.Connections.Import(f, ImportOptions.Override));
        bad += ImportSet(Path.Combine(dir, "cycles"), "cycle", f => hmi.Cycles.Import(f, ImportOptions.Override));
        bad += ImportSet(Path.Combine(dir, "textlists"), "textlist", f => hmi.TextLists.Import(f, ImportOptions.Override));
        bad += ImportSet(Path.Combine(dir, "tags"), "tagtable", f => hmi.TagFolder.TagTables.Import(f, ImportOptions.Override));
        bad += ImportSet(Path.Combine(dir, "templates"), "template", f => hmi.ScreenTemplateFolder.ScreenTemplates.Import(f, ImportOptions.Override));
        bad += ImportSet(Path.Combine(dir, "screens"), "screen", f => hmi.ScreenFolder.Screens.Import(f, ImportOptions.Override));
        return bad;
    }
    static int ImportSet(string d, string kind, Action<FileInfo> f)
    {
        if (!Directory.Exists(d)) return 0;
        int bad = 0;
        foreach (var x in Directory.GetFiles(d, "*.xml").OrderBy(s => s, StringComparer.OrdinalIgnoreCase)) {
            try { f(new FileInfo(x)); Console.WriteLine("IMPORT " + kind + " " + Path.GetFileName(x) + " ok"); }
            catch (Exception ex) { bad++; Console.WriteLine("[ERROR] IMPORT " + kind + " " + Path.GetFileName(x) + ": " + ExText(ex)); }
        }
        return bad;
    }
    static void Export(HmiTarget hmi, string dir)
    {
        Func<string, string> sub = s => { var x = Path.Combine(dir, s); Directory.CreateDirectory(x); return x; };
        string ds = sub("screens"), dt = sub("templates"), dg = sub("tags"), dl = sub("textlists"), dc = sub("connections"), dy = sub("cycles");
        foreach (var s in AllScreens(hmi.ScreenFolder)) Try("screen " + s.Name, () => s.Export(new FileInfo(Path.Combine(ds, Safe(s.Name) + ".xml")), ExportOptions.WithDefaults));
        foreach (var t in hmi.ScreenTemplateFolder.ScreenTemplates) Try("template " + t.Name, () => t.Export(new FileInfo(Path.Combine(dt, Safe(t.Name) + ".xml")), ExportOptions.WithDefaults));
        foreach (var t in hmi.TagFolder.TagTables) Try("tagtable " + t.Name, () => t.Export(new FileInfo(Path.Combine(dg, Safe(t.Name) + ".xml")), ExportOptions.WithDefaults));
        foreach (var l in hmi.TextLists) Try("textlist " + l.Name, () => l.Export(new FileInfo(Path.Combine(dl, Safe(l.Name) + ".xml")), ExportOptions.WithDefaults));
        foreach (var c in hmi.Connections) Try("connection " + c.Name, () => c.Export(new FileInfo(Path.Combine(dc, Safe(c.Name) + ".xml")), ExportOptions.WithDefaults));
        foreach (var c in hmi.Cycles) Try("cycle " + c.Name, () => c.Export(new FileInfo(Path.Combine(dy, Safe(c.Name) + ".xml")), ExportOptions.WithDefaults));
        Console.WriteLine("EXPORT done -> " + dir);
    }
    static void Try(string what, Action f)
    {
        try { f(); Console.WriteLine("EXPORT " + what + " ok"); }
        catch (Exception ex) { Console.WriteLine("[WARNING] EXPORT " + what + ": " + ExText(ex)); }
    }
    static IEnumerable<Screen> AllScreens(ScreenFolder f)
    {
        foreach (var s in f.Screens) yield return s;
        foreach (var g in f.Folders) foreach (var s in AllScreens(g)) yield return s;
    }
    static string Safe(string s) { foreach (var c in Path.GetInvalidFileNameChars()) s = s.Replace(c, '_'); return s.Replace(' ', '_'); }

    static int CompilePlc(Project p)
    {
        foreach (var d in AllDevices(p)) foreach (var di in Walk(d.DeviceItems)) {
            var sc = di.GetService<SoftwareContainer>();
            var plc = sc == null ? null : sc.Software as PlcSoftware;
            if (plc == null) continue;
            var comp = plc.GetService<Siemens.Engineering.Compiler.ICompilable>();
            var res = comp.Compile();
            Dump(res.Messages, "");
            Console.WriteLine("PLC_COMPILE state=" + res.State + " errors=" + res.ErrorCount + " warnings=" + res.WarningCount);
            return res.ErrorCount;
        }
        return 0;
    }
    static void Dump(Siemens.Engineering.Compiler.CompilerResultMessageComposition msgs, string ctx)
    {
        foreach (var m in msgs) {
            string st = m.State.ToString();
            string path = m.Path ?? "";
            if (m.Messages.Count == 0 && (st == "Error" || st == "Warning"))
                Console.WriteLine("[" + st.ToUpper() + "] " + ctx + (path.Length > 0 ? "/" + path : "") + " :: " + m.Description);
            Dump(m.Messages, path.Length == 0 ? ctx : (ctx.Length > 0 ? ctx + "/" : "") + path);
        }
    }
}
