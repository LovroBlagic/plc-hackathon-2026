// TiaRun: TIA Portal V21 Openness one-shot runner (C# 5, build with build.ps1 / csc.exe of .NET Framework 4.8)
//
//   TiaRun.exe --project C:\abs\Dir\Name            project folder (holds Name.ap21) or the .ap21 itself
//              [--retrieve C:\x.zap21 --to C:\dir]  retrieve an archive into dir (project = dir\<archive project>)
//              [--headless]                          start TIA without UI (default: attach to running TIA,
//                                                    or start headless automatically if none is running)
//              [--create] [--cpu "6ES7 511-1AK0"]
//              [--lock <worker>] [--lock-wait 900]  take tia-work\openness.lock (CONTRACT §5) for the run
//              [--src C:\abs\src]                    import *.udt|*.db|*.scl|*.awl as external sources (alphabetical)
//              [--numbers file]                      Name=Kind:Number lines -> AutoNumber=false + Number
//              [--ob30-ms 1000]                      enforce cyclic time of OB30 (attribute CyclicTime, us)
//              [--no-compile]
//              [--export C:\abs\dir]                 export all blocks/UDTs (SCL source + SimaticML), tag tables,
//                                                    HMI inventory, inventory.txt
//              [--archive C:\abs\out.zap21]          Project.Archive (compressed)
//              [--no-save]
// Summary line:  TIA_RESULT errors=N warnings=M
using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Reflection;
using System.Collections.Generic;
using Siemens.Engineering;
using Siemens.Engineering.SW;
using Siemens.Engineering.SW.Blocks;
using Siemens.Engineering.SW.Types;
using Siemens.Engineering.SW.Tags;
using Siemens.Engineering.SW.ExternalSources;

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
        string lockFile = null;
        try { return Runner.Run(args, out lockFile); }
        catch (Exception ex) { Console.WriteLine("FATAL: " + Runner.ExText(ex)); return 2; }
        finally { Runner.ReleaseLock(); }
    }
}

internal static class Runner
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

    // ---------------- lock (CONTRACT §5) ----------------
    // 7 Nov incident: a 10-min "stale" rule let one tool take another tool's ACTIVE lock -> two TIA instances.
    // Rule now: stale only after 45 min AND only when no TIA / Openness client process (other than us) runs;
    // the holder rewrites the lock every 150 s (heartbeat) so an active lock never looks stale.
    static string heldLock;
    static string heldText;
    static System.Threading.Timer heartbeat;
    const double StaleMin = 45;
    public static void ReleaseLock()
    {
        if (heartbeat != null) { try { heartbeat.Dispose(); } catch { } heartbeat = null; }
        if (heldLock != null) {
            try {
                string cur = File.Exists(heldLock) ? File.ReadAllText(heldLock).Trim() : "";
                if (cur == heldText) { File.Delete(heldLock); Console.WriteLine("LOCK released"); }
                else Console.WriteLine("LOCK now held by '" + cur + "', not removed");
            } catch { }
            heldLock = null;
        }
    }
    static string FindTiaWork(string proj)
    {
        var d = new DirectoryInfo(proj);
        while (d != null) { if (d.Name.Equals("tia-work", StringComparison.OrdinalIgnoreCase)) return d.FullName; d = d.Parent; }
        return Path.GetDirectoryName(proj);
    }
    static string OtherTiaProcesses()
    {
        int me = System.Diagnostics.Process.GetCurrentProcess().Id;
        var names = new[] { "Siemens.Automation.Portal", "TiaRun", "HmiGen", "HmiLab", "TiaDownload" };
        var found = new List<string>();
        foreach (var n in names) foreach (var p in System.Diagnostics.Process.GetProcessesByName(n)) if (p.Id != me) found.Add(n + "#" + p.Id);
        return string.Join(",", found.ToArray());
    }
    static void Beat(object o)
    {
        try { if (heldLock != null && File.Exists(heldLock) && File.ReadAllText(heldLock).Trim() == heldText) File.SetLastWriteTime(heldLock, DateTime.Now); } catch { }
    }
    static bool TakeLock(string proj, string worker, int waitS)
    {
        string lf = Path.Combine(FindTiaWork(proj), "openness.lock");
        DateTime until = DateTime.Now.AddSeconds(waitS);
        while (true) {
            if (File.Exists(lf)) {
                double age = (DateTime.Now - File.GetLastWriteTime(lf)).TotalMinutes;
                string who = ""; try { who = File.ReadAllText(lf).Trim(); } catch { }
                string busy = OtherTiaProcesses();
                if (age >= StaleMin && busy.Length == 0) { Console.WriteLine("LOCK stale (" + age.ToString("0.0") + " min, '" + who + "', no TIA running) -> taking over"); }
                else if (DateTime.Now < until) { Console.WriteLine("LOCK held by '" + who + "' (" + age.ToString("0.0") + " min" + (busy.Length > 0 ? ", running: " + busy : "") + "), waiting..."); System.Threading.Thread.Sleep(15000); continue; }
                else { Console.WriteLine("FATAL: lock held by '" + who + "': " + lf); return false; }
            }
            heldText = worker + " " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            File.WriteAllText(lf, heldText);
            heldLock = lf;
            heartbeat = new System.Threading.Timer(Beat, null, 150000, 150000);
            Console.WriteLine("LOCK taken: " + lf + " (heartbeat 150 s)");
            return true;
        }
    }

    public static int Run(string[] a, out string lockFile)
    {
        lockFile = null;
        string proj = Arg(a, "--project");
        string retrieve = Arg(a, "--retrieve");
        if (proj == null && retrieve == null) { Console.WriteLine("FATAL: --project C:\\abs\\Dir\\Name (or --retrieve x.zap21 --to dir) required"); return 2; }
        if (proj != null) {
            proj = Path.GetFullPath(proj.Replace('/', '\\')).TrimEnd('\\');
            if (proj.EndsWith(".ap21", StringComparison.OrdinalIgnoreCase)) proj = Path.GetDirectoryName(proj);
        }
        string lockOwner = Arg(a, "--lock");
        if (lockOwner != null) {
            int w = 900; int.TryParse(Arg(a, "--lock-wait") ?? "900", out w);
            if (!TakeLock(proj ?? Path.GetFullPath(Arg(a, "--to") ?? "."), lockOwner, w)) return 2;
        }

        TiaPortal portal;
        var procs = TiaPortal.GetProcesses();
        if (Flag(a, "--headless") || procs.Count == 0) {
            Console.WriteLine("STARTING headless TIA Portal" + (procs.Count == 0 && !Flag(a, "--headless") ? " (none running)" : ""));
            portal = new TiaPortal(TiaPortalMode.WithoutUserInterface);
            Console.WriteLine("STARTED headless TIA Portal");
        } else {
            Console.WriteLine("ATTACHING to TIA PID " + procs[0].Id + " (first time: answer TIA's Openness access dialog with 'Yes to all')");
            portal = procs[0].Attach();
        }

        using (portal)
        {
            Project p = null;
            if (retrieve != null) {
                string to = Arg(a, "--to");
                if (to == null) { Console.WriteLine("FATAL: --retrieve needs --to <dir>"); return 2; }
                to = Path.GetFullPath(to);
                if (portal.Projects.Count > 0) { Console.WriteLine("FATAL: a project is already open in this TIA: " + portal.Projects[0].Path.FullName); return 2; }
                Directory.CreateDirectory(to);
                Console.WriteLine("RETRIEVING " + retrieve + " -> " + to);
                p = portal.Projects.Retrieve(new FileInfo(Path.GetFullPath(retrieve)), new DirectoryInfo(to));
                Console.WriteLine("RETRIEVED project " + p.Name + " at " + p.Path.FullName);
                Console.WriteLine("PROJECT_DIR " + p.Path.Directory.FullName);
            } else {
                string name = Path.GetFileName(proj), dir = Path.GetDirectoryName(proj);
                string ap21 = Path.Combine(proj, name + ".ap21");
                if (!File.Exists(ap21) && Directory.Exists(proj)) {
                    var any = Directory.GetFiles(proj, "*.ap21").FirstOrDefault();
                    if (any != null) ap21 = any;
                }
                p = portal.Projects.FirstOrDefault(x => string.Equals(x.Path.FullName, ap21, StringComparison.OrdinalIgnoreCase));
                if (p == null && portal.Projects.Count > 0) {
                    Console.WriteLine("FATAL: another project is open in this TIA: " + portal.Projects[0].Path.FullName + ". Close it first.");
                    return 2;
                }
                if (p == null) {
                    if (File.Exists(ap21)) { p = portal.Projects.Open(new FileInfo(ap21)); Console.WriteLine("OPENED " + ap21); }
                    else if (Flag(a, "--create")) { Directory.CreateDirectory(dir); p = portal.Projects.Create(new DirectoryInfo(dir), name); Console.WriteLine("CREATED " + ap21); }
                    else { Console.WriteLine("FATAL: project not found (use --create): " + ap21); return 2; }
                } else Console.WriteLine("USING open project " + ap21);
            }

            PlcSoftware sw = FindPlc(p);
            if (sw == null && Flag(a, "--create")) {
                string search = Arg(a, "--cpu") ?? "6ES7 511-1AK0";
                var entries = portal.HardwareCatalog.Find(search).Where(c => c.TypeIdentifier.StartsWith("OrderNumber:")).ToList();
                if (entries.Count == 0) { Console.WriteLine("FATAL: no catalog entry for " + search); return 2; }
                var pick = entries.OrderBy(c => c.TypeIdentifier).Last();
                p.Devices.CreateWithItem(pick.TypeIdentifier, "PLC_1", "PLC_1");
                Console.WriteLine("ADDED CPU " + pick.TypeIdentifier);
                sw = FindPlc(p);
            }
            if (sw == null) { Console.WriteLine("FATAL: no PLC software found in project"); return 2; }
            Console.WriteLine("PLC software: " + sw.Name);

            int importErrors = 0;
            string src = Arg(a, "--src");
            if (src != null) importErrors = Import(sw, Path.GetFullPath(src));

            string numbers = Arg(a, "--numbers");
            if (numbers != null) ApplyNumbers(sw, Path.GetFullPath(numbers));

            string ob30 = Arg(a, "--ob30-ms");
            if (ob30 != null) EnsureOb30(sw, int.Parse(ob30));

            int errs = 0, warns = 0;
            if (!Flag(a, "--no-compile")) {
                var comp = ((IEngineeringServiceProvider)sw).GetService<Siemens.Engineering.Compiler.ICompilable>();
                var res = comp.Compile();
                Dump(res.Messages, "");
                errs = res.ErrorCount; warns = res.WarningCount;
                Console.WriteLine("COMPILE state=" + res.State + " errors=" + errs + " warnings=" + warns);
            }

            string exp = Arg(a, "--export");
            if (exp != null) Export(p, sw, Path.GetFullPath(exp));

            if (!Flag(a, "--no-save")) { p.Save(); Console.WriteLine("SAVED " + p.Path.FullName); }

            string arch = Arg(a, "--archive");
            if (arch != null) {
                arch = Path.GetFullPath(arch);
                Directory.CreateDirectory(Path.GetDirectoryName(arch));
                if (File.Exists(arch)) File.Delete(arch);
                p.Archive(new DirectoryInfo(Path.GetDirectoryName(arch)), Path.GetFileName(arch), ProjectArchivationMode.Compressed);
                Console.WriteLine("ARCHIVED " + arch);
            }

            errs += importErrors;
            Console.WriteLine("TIA_RESULT errors=" + errs + " warnings=" + warns + (importErrors > 0 ? " import_errors=" + importErrors : ""));
            return errs > 0 ? 1 : 0;
        }
    }

    // ---------------- import ----------------
    static int Import(PlcSoftware sw, string src)
    {
        int bad = 0;
        var exts = new[] { ".udt", ".db", ".scl", ".awl" };
        var files = Directory.GetFiles(src).Where(f => exts.Contains(Path.GetExtension(f).ToLower()))
                    .OrderBy(f => Path.GetFileName(f), StringComparer.OrdinalIgnoreCase).ToList();
        foreach (var f in files) {
            string sname = Path.GetFileName(f);
            var old = sw.ExternalSourceGroup.ExternalSources.Find(sname);
            if (old != null) old.Delete();
            var es = sw.ExternalSourceGroup.ExternalSources.CreateFromFile(sname, f);
            try {
                var made = es.GenerateBlocksFromSource(GenerateBlockOption.KeepOnError);
                var names = new List<string>();
                if (made != null) foreach (var o in made) { var b = o as PlcBlock; var t = o as PlcType; names.Add(b != null ? b.Name : (t != null ? t.Name : o.GetType().Name)); }
                Console.WriteLine("IMPORT " + sname + " ok -> " + string.Join(", ", names));
                RecordSource(f, sname);
            } catch (Exception ex) {
                bad++;
                Console.WriteLine("[ERROR] IMPORT " + sname + ": " + ExText(ex));
            }
        }
        return bad;
    }

    static void RecordSource(string file, string sname)
    {
        // map every block declared in the file to (file, line of its BEGIN) so compiler line numbers can be translated
        var lines = File.ReadAllLines(file);
        string cur = null;
        for (int i = 0; i < lines.Length; i++) {
            string t = lines[i].Trim();
            var mm = System.Text.RegularExpressions.Regex.Match(t, "^(FUNCTION_BLOCK|FUNCTION|ORGANIZATION_BLOCK|DATA_BLOCK|TYPE)[ \t]+\"([^\"]+)\"", System.Text.RegularExpressions.RegexOptions.IgnoreCase);
            if (mm.Success) cur = mm.Groups[2].Value;
            if (cur != null && t.Equals("BEGIN", StringComparison.OrdinalIgnoreCase)) { blockSrc[cur] = new KeyValuePair<string, int>(sname, i + 1); cur = null; }
            else if (cur != null && !blockSrc.ContainsKey(cur)) blockSrc[cur] = new KeyValuePair<string, int>(sname, 0);
        }
    }

    // ---------------- numbers ----------------
    static void ApplyNumbers(PlcSoftware sw, string file)
    {
        var all = AllBlocks(sw.BlockGroup).ToList();
        foreach (var raw in File.ReadAllLines(file)) {
            string line = raw.Trim();
            if (line.Length == 0 || line.StartsWith("#") || line.StartsWith("//")) continue;
            int eq = line.IndexOf('='), col = line.LastIndexOf(':');
            if (eq < 0 || col < eq) { Console.WriteLine("[WARNING] NUMBERS bad line: " + line); continue; }
            string name = line.Substring(0, eq).Trim().Trim('"');
            string kind = line.Substring(eq + 1, col - eq - 1).Trim().ToUpper();
            int num = int.Parse(line.Substring(col + 1).Trim());
            var b = all.FirstOrDefault(x => x.Name == name);
            if (b == null) { Console.WriteLine("[WARNING] NUMBERS " + name + ": block not found"); continue; }
            string k = Kind(b);
            if (k != kind) { Console.WriteLine("[WARNING] NUMBERS " + name + ": is " + k + " not " + kind); continue; }
            if (b.Number == num && !b.AutoNumber) { Console.WriteLine("NUMBERS " + name + " = " + k + num + " (unchanged)"); continue; }
            var clash = all.FirstOrDefault(x => x != b && x.Number == num && SameSpace(Kind(x), k));
            if (clash != null) { Console.WriteLine("[ERROR] NUMBERS " + name + ": " + k + num + " already used by " + clash.Name); continue; }
            try {
                b.AutoNumber = false;
                b.Number = num;
                Console.WriteLine("NUMBERS " + name + " = " + k + num + " (set)");
            } catch (Exception ex) { Console.WriteLine("[ERROR] NUMBERS " + name + ": " + ExText(ex)); }
        }
        var main = all.FirstOrDefault(x => x.Name == "Main") as OB;
        if (main != null) Console.WriteLine("CHECK OB \"Main\" number=" + main.Number + " type=" + main.SecondaryType + (main.Number == 1 && main.SecondaryType == "ProgramCycle" ? " OK" : " [WARNING] expected OB1 ProgramCycle"));
    }
    static bool SameSpace(string a, string b) { return a == b; }   // OB/FB/FC/DB have separate number spaces

    static string Kind(PlcBlock b)
    {
        if (b is OB) return "OB";
        if (b is FB) return "FB";
        if (b is FC) return "FC";
        if (b is DataBlock) return "DB";
        return b.GetType().Name;
    }

    // ---------------- OB30 ----------------
    static void EnsureOb30(PlcSoftware sw, int ms)
    {
        var ob = AllBlocks(sw.BlockGroup).OfType<OB>().FirstOrDefault(x => x.Number == 30);
        if (ob == null) { Console.WriteLine("[WARNING] OB30: not found"); return; }
        object cur = null;
        try { cur = ob.GetAttribute("CyclicTime"); } catch (Exception ex) { Console.WriteLine("[WARNING] OB30 CyclicTime read: " + ExText(ex)); return; }
        int want = ms * 1000;
        if (Convert.ToInt32(cur) != want) {
            ob.SetAttribute("CyclicTime", want);
            Console.WriteLine("OB30 \"" + ob.Name + "\" CyclicTime " + cur + " us -> " + want + " us (set)");
        } else Console.WriteLine("OB30 \"" + ob.Name + "\" CyclicTime = " + cur + " us (" + ms + " ms) OK");
        try { Console.WriteLine("OB30 PhaseOffset = " + ob.GetAttribute("PhaseOffset") + " us, Priority = " + ob.GetAttribute("PriorityNumber")); } catch { }
    }

    // ---------------- export ----------------
    static void Export(Project p, PlcSoftware sw, string dir)
    {
        Directory.CreateDirectory(dir);
        string xdir = Path.Combine(dir, "xml"); Directory.CreateDirectory(xdir);
        string sdir = Path.Combine(dir, "src"); Directory.CreateDirectory(sdir);
        var inv = new StringBuilder();
        inv.AppendLine("# Inventory of " + p.Path.FullName + "  (" + DateTime.Now.ToString("yyyy-MM-dd HH:mm") + ")");
        inv.AppendLine("## Blocks");
        foreach (var b in AllBlocks(sw.BlockGroup)) {
            string line = Kind(b) + b.Number + " \"" + b.Name + "\" lang=" + b.ProgrammingLanguage + " khp=" + b.IsKnowHowProtected + " consistent=" + b.IsConsistent;
            var ob = b as OB;
            if (ob != null) {
                line += " type=" + ob.SecondaryType;
                foreach (var at in new[] { "CyclicTime", "PhaseOffset", "PriorityNumber" }) { try { line += " " + at + "=" + ob.GetAttribute(at); } catch { } }
            }
            var idb = b as InstanceDB;
            if (idb != null) line += " instanceOf=" + idb.InstanceOfName;
            inv.AppendLine(line);
            string safe = Safe(Kind(b) + b.Number + "_" + b.Name);
            try { b.Export(new FileInfo(Path.Combine(xdir, safe + ".xml")), ExportOptions.WithDefaults); }
            catch (Exception ex) { Console.WriteLine("[WARNING] EXPORT xml " + b.Name + ": " + ExText(ex)); inv.AppendLine("   xml export failed: " + ExText(ex)); }
            string ext = (b is DataBlock) ? ".db" : ".scl";
            try {
                sw.ExternalSourceGroup.GenerateSource(new IGenerateSource[] { (IGenerateSource)b }, new FileInfo(Path.Combine(sdir, safe + ext)), GenerateOptions.None);
            } catch (Exception ex) { inv.AppendLine("   source export n/a: " + ExText(ex)); }
            Console.WriteLine("EXPORT " + line);
        }
        inv.AppendLine("## Types");
        foreach (var t in AllTypes(sw.TypeGroup)) {
            inv.AppendLine("UDT \"" + t.Name + "\"");
            try { t.Export(new FileInfo(Path.Combine(xdir, "UDT_" + Safe(t.Name) + ".xml")), ExportOptions.WithDefaults); } catch (Exception ex) { inv.AppendLine("   xml export failed: " + ExText(ex)); }
            try { sw.ExternalSourceGroup.GenerateSource(new IGenerateSource[] { (IGenerateSource)t }, new FileInfo(Path.Combine(sdir, "UDT_" + Safe(t.Name) + ".udt")), GenerateOptions.None); } catch { }
        }
        inv.AppendLine("## Tag tables");
        foreach (var tt in AllTagTables(sw.TagTableGroup)) {
            inv.AppendLine("TAGTABLE \"" + tt.Name + "\" default=" + tt.IsDefault);
            foreach (PlcTag tag in tt.Tags) inv.AppendLine("   \"" + tag.Name + "\" " + tag.LogicalAddress + " : " + tag.DataTypeName + (string.IsNullOrEmpty(GetComment(tag)) ? "" : "   // " + GetComment(tag)));
            foreach (PlcUserConstant c in tt.UserConstants) inv.AppendLine("   CONST \"" + c.Name + "\" = " + c.Value + " : " + c.DataTypeName);
            try { tt.Export(new FileInfo(Path.Combine(xdir, "TAGS_" + Safe(tt.Name) + ".xml")), ExportOptions.WithDefaults); } catch (Exception ex) { inv.AppendLine("   xml export failed: " + ExText(ex)); }
        }
        inv.AppendLine("## Devices / HMI");
        foreach (var d in p.Devices) {
            inv.AppendLine("DEVICE \"" + d.Name + "\" type=" + d.TypeIdentifier);
            foreach (var di in Walk(d.DeviceItems)) {
                var sc = ((IEngineeringServiceProvider)di).GetService<Siemens.Engineering.HW.Features.SoftwareContainer>();
                if (sc == null || sc.Software == null) continue;
                inv.AppendLine("   item \"" + di.Name + "\" software=" + sc.Software.GetType().Name + " \"" + sc.Software.Name + "\"");
                var hmi = sc.Software as Siemens.Engineering.Hmi.HmiTarget;
                if (hmi != null) HmiInventory(hmi, inv, xdir);
            }
        }
        File.WriteAllText(Path.Combine(dir, "inventory.txt"), inv.ToString());
        Console.WriteLine("EXPORT done -> " + dir);
    }

    static string GetComment(PlcTag t)
    {
        try { var c = t.Comment.Items.FirstOrDefault(); return c == null ? "" : c.Text; } catch { return ""; }
    }

    static void HmiInventory(Siemens.Engineering.Hmi.HmiTarget hmi, StringBuilder inv, string xdir)
    {
        inv.AppendLine("   HMI \"" + hmi.Name + "\"");
        foreach (var c in hmi.Connections) {
            string s = "      CONNECTION \"" + c.Name + "\"";
            foreach (var at in new[] { "Partner", "CommunicationDriver", "Station", "Node", "Online" }) { try { s += " " + at + "=" + c.GetAttribute(at); } catch { } }
            inv.AppendLine(s);
        }
        foreach (var sc in AllScreens(hmi.ScreenFolder)) {
            inv.AppendLine("      SCREEN \"" + sc.Name + "\"");
            try { sc.Export(new FileInfo(Path.Combine(xdir, "HMI_SCREEN_" + Safe(sc.Name) + ".xml")), ExportOptions.WithDefaults); } catch (Exception ex) { inv.AppendLine("         export failed: " + ExText(ex)); }
        }
        foreach (var st in hmi.ScreenTemplateFolder.ScreenTemplates) inv.AppendLine("      TEMPLATE \"" + st.Name + "\"");
        foreach (var tt in AllHmiTagTables(hmi.TagFolder)) {
            inv.AppendLine("      HMITAGTABLE \"" + tt.Name + "\" tags=" + tt.Tags.Count);
            foreach (var t in tt.Tags) {
                string s = "         \"" + t.Name + "\"";
                foreach (var at in new[] { "Connection", "PlcTag", "DataType", "AcquisitionCycle" }) { try { s += " " + at + "=" + t.GetAttribute(at); } catch { } }
                inv.AppendLine(s);
            }
        }
    }

    static IEnumerable<Siemens.Engineering.Hmi.Screen.Screen> AllScreens(Siemens.Engineering.Hmi.Screen.ScreenFolder f)
    {
        foreach (var s in f.Screens) yield return s;
        foreach (var g in f.Folders) foreach (var s in AllScreens(g)) yield return s;
    }
    static IEnumerable<Siemens.Engineering.Hmi.Tag.TagTable> AllHmiTagTables(Siemens.Engineering.Hmi.Tag.TagSystemFolder f)
    {
        foreach (var t in f.TagTables) yield return t;
        foreach (var g in f.Folders) foreach (var t in AllHmiTagTables2(g)) yield return t;
    }
    static IEnumerable<Siemens.Engineering.Hmi.Tag.TagTable> AllHmiTagTables2(Siemens.Engineering.Hmi.Tag.TagUserFolder f)
    {
        foreach (var t in f.TagTables) yield return t;
        foreach (var g in f.Folders) foreach (var t in AllHmiTagTables2(g)) yield return t;
    }

    static string Safe(string s) { foreach (var c in Path.GetInvalidFileNameChars()) s = s.Replace(c, '_'); return s.Replace(' ', '_'); }

    static IEnumerable<PlcBlock> AllBlocks(PlcBlockGroup g)
    {
        foreach (PlcBlock b in g.Blocks) yield return b;
        foreach (PlcBlockGroup c in g.Groups) foreach (var b in AllBlocks(c)) yield return b;
    }
    static IEnumerable<PlcType> AllTypes(PlcTypeGroup g)
    {
        foreach (PlcType t in g.Types) yield return t;
        foreach (PlcTypeGroup c in g.Groups) foreach (var t in AllTypes(c)) yield return t;
    }
    static IEnumerable<PlcTagTable> AllTagTables(PlcTagTableGroup g)
    {
        foreach (PlcTagTable t in g.TagTables) yield return t;
        foreach (PlcTagTableGroup c in g.Groups) foreach (var t in AllTagTables(c)) yield return t;
    }

    static PlcSoftware FindPlc(Project p)
    {
        foreach (var d in p.Devices)
            foreach (var di in Walk(d.DeviceItems)) {
                var sc = ((IEngineeringServiceProvider)di).GetService<Siemens.Engineering.HW.Features.SoftwareContainer>();
                if (sc != null && sc.Software is PlcSoftware) return (PlcSoftware)sc.Software;
            }
        return null;
    }

    static IEnumerable<Siemens.Engineering.HW.DeviceItem> Walk(Siemens.Engineering.HW.DeviceItemComposition items)
    {
        foreach (var i in items) { yield return i; foreach (var c in Walk(i.DeviceItems)) yield return c; }
    }

    // block name -> (source file, line of BEGIN in that file), filled by Import
    static Dictionary<string, KeyValuePair<string, int>> blockSrc = new Dictionary<string, KeyValuePair<string, int>>();

    static void Dump(Siemens.Engineering.Compiler.CompilerResultMessageComposition msgs, string ctx)
    {
        foreach (var m in msgs) {
            string st = m.State.ToString();
            string path = m.Path ?? "";
            bool leaf = m.Messages.Count == 0;
            if (leaf && (st == "Error" || st == "Warning")) {
                string where = ctx;
                int ln;
                if (int.TryParse(path, out ln)) {
                    // leaf path is the line/network number inside the block named by the last ctx element
                    string blk = ctx.Contains("/") ? ctx.Substring(ctx.LastIndexOf('/') + 1) : ctx;
                    string bname = blk.Contains(" (") ? blk.Substring(0, blk.IndexOf(" (")) : blk;
                    KeyValuePair<string, int> sf;
                    if (blockSrc.TryGetValue(bname, out sf)) where += " [" + sf.Key + ":" + (sf.Value + ln) + "]";
                    where += " line " + ln;
                } else if (path.Length > 0) where += (where.Length > 0 ? "/" : "") + path;
                Console.WriteLine("[" + st.ToUpper() + "] " + where + " :: " + m.Description);
            }
            Dump(m.Messages, path.Length == 0 ? ctx : (ctx.Length > 0 ? ctx + "/" : "") + path);
        }
    }
}
