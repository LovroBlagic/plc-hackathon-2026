// HmiGen: WinCC RT Advanced (HMI Classic) Openness round-trip tool for the crane HMI.
// C# 5, build with hmi-tia\build_hmigen.ps1 (csc of .NET Framework 4.8).
//
//   HmiGen.exe --project C:\abs\ProjDir           project folder (holds *.ap21) or the .ap21 itself
//              [--headless]                        start TIA without UI (default: attach to a running TIA,
//                                                  or start headless automatically if none is running)
//              [--lock hmi] [--lock-wait 900]      take tia-work\openness.lock (CONTRACT §5) for the run
//              [--hmi HMI_RT_1]                    HMI software name (default: first HmiTarget found)
//              [--export C:\abs\dir]               export screens, templates, tag tables, text lists,
//                                                  graphic lists, connections -> dir\{screens,templates,tags,textlists,...}
//              [--import C:\abs\dir]               import dir\textlists\*.xml, dir\tags\*.xml, dir\templates\*.xml,
//                                                  dir\screens\*.xml (in this order, ImportOptions.Override)
//              [--compile]                         compile the HMI device (ICompilable)
//              [--no-save]
// Summary line:  HMI_RESULT errors=N warnings=M [import_errors=K]
// Exit code: 0 ok, 1 errors, 2 fatal.
using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Reflection;
using System.Collections.Generic;
using Siemens.Engineering;
using Siemens.Engineering.Hmi;
using Siemens.Engineering.Hmi.Screen;
using Siemens.Engineering.Hmi.Tag;
using Siemens.Engineering.Hmi.TextGraphicList;

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
        try { return Gen.Run(args); }
        catch (Exception ex) { Console.WriteLine("FATAL: " + Gen.ExText(ex)); return 2; }
        finally { Gen.ReleaseLock(); }
    }
}

internal static class Gen
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

    // ---------------- lock (CONTRACT §5), same protocol as TiaRun ----------------
    static string heldLock;
    public static void ReleaseLock()
    {
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
            if (File.Exists(lf)) {
                double age = (DateTime.Now - File.GetLastWriteTime(lf)).TotalMinutes;
                string who = ""; try { who = File.ReadAllText(lf).Trim(); } catch { }
                if (age >= 10) Console.WriteLine("LOCK stale (" + age.ToString("0.0") + " min, '" + who + "') -> taking over");
                else if (DateTime.Now < until) { Console.WriteLine("LOCK held by '" + who + "' (" + age.ToString("0.0") + " min), waiting..."); System.Threading.Thread.Sleep(15000); continue; }
                else { Console.WriteLine("FATAL: lock held by '" + who + "': " + lf); return false; }
            }
            File.WriteAllText(lf, worker + " " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
            heldLock = lf;
            Console.WriteLine("LOCK taken: " + lf);
            return true;
        }
    }

    public static int Run(string[] a)
    {
        string proj = Arg(a, "--project");
        if (proj == null) { Console.WriteLine("FATAL: --project C:\\abs\\ProjDir required"); return 2; }
        proj = Path.GetFullPath(proj.Replace('/', '\\')).TrimEnd('\\');
        if (proj.EndsWith(".ap21", StringComparison.OrdinalIgnoreCase)) proj = Path.GetDirectoryName(proj);
        string lockOwner = Arg(a, "--lock");
        if (lockOwner != null) {
            int w = 900; int.TryParse(Arg(a, "--lock-wait") ?? "900", out w);
            if (!TakeLock(proj, lockOwner, w)) return 2;
        }

        TiaPortal portal;
        var procs = TiaPortal.GetProcesses();
        if (Flag(a, "--headless") || procs.Count == 0) {
            Console.WriteLine("STARTING headless TIA Portal");
            portal = new TiaPortal(TiaPortalMode.WithoutUserInterface);
        } else {
            Console.WriteLine("ATTACHING to TIA PID " + procs[0].Id + " (first time: answer the Openness access dialog with 'Yes to all')");
            portal = procs[0].Attach();
        }

        using (portal)
        {
            string ap21 = Path.Combine(proj, Path.GetFileName(proj) + ".ap21");
            if (!File.Exists(ap21) && Directory.Exists(proj)) { var any = Directory.GetFiles(proj, "*.ap21").FirstOrDefault(); if (any != null) ap21 = any; }
            Project p = portal.Projects.FirstOrDefault(x => string.Equals(x.Path.FullName, ap21, StringComparison.OrdinalIgnoreCase));
            if (p == null && portal.Projects.Count > 0) { Console.WriteLine("FATAL: another project is open in this TIA: " + portal.Projects[0].Path.FullName); return 2; }
            if (p == null) {
                if (!File.Exists(ap21)) { Console.WriteLine("FATAL: project not found: " + ap21); return 2; }
                p = portal.Projects.Open(new FileInfo(ap21)); Console.WriteLine("OPENED " + ap21);
            } else Console.WriteLine("USING open project " + ap21);

            HmiTarget hmi = FindHmi(p, Arg(a, "--hmi"));
            if (hmi == null) { Console.WriteLine("FATAL: no HmiTarget (WinCC Classic/RT Advanced) found"); return 2; }
            Console.WriteLine("HMI software: " + hmi.Name);
            foreach (var c in hmi.Connections) Console.WriteLine("CONNECTION \"" + c.Name + "\"");

            int importErrors = 0;
            string imp = Arg(a, "--import");
            if (imp != null) importErrors = Import(hmi, Path.GetFullPath(imp));

            int errs = 0, warns = 0;
            if (Flag(a, "--compile")) {
                var comp = ((IEngineeringServiceProvider)hmi).GetService<Siemens.Engineering.Compiler.ICompilable>();
                if (comp == null) { Console.WriteLine("[ERROR] HMI has no ICompilable service"); errs++; }
                else {
                    var res = comp.Compile();
                    Dump(res.Messages, "");
                    errs += res.ErrorCount; warns = res.WarningCount;
                    Console.WriteLine("COMPILE state=" + res.State + " errors=" + res.ErrorCount + " warnings=" + warns);
                }
            }

            string exp = Arg(a, "--export");
            if (exp != null) Export(hmi, Path.GetFullPath(exp));

            if (!Flag(a, "--no-save") && (imp != null || Flag(a, "--compile"))) { p.Save(); Console.WriteLine("SAVED " + p.Path.FullName); }

            errs += importErrors;
            Console.WriteLine("HMI_RESULT errors=" + errs + " warnings=" + warns + (importErrors > 0 ? " import_errors=" + importErrors : ""));
            return errs > 0 ? 1 : 0;
        }
    }

    // ---------------- find ----------------
    static HmiTarget FindHmi(Project p, string name)
    {
        foreach (var d in p.Devices)
            foreach (var di in Walk(d.DeviceItems)) {
                var sc = ((IEngineeringServiceProvider)di).GetService<Siemens.Engineering.HW.Features.SoftwareContainer>();
                var h = sc == null ? null : sc.Software as HmiTarget;
                if (h != null && (name == null || h.Name == name)) return h;
            }
        return null;
    }
    static IEnumerable<Siemens.Engineering.HW.DeviceItem> Walk(Siemens.Engineering.HW.DeviceItemComposition items)
    {
        foreach (var i in items) { yield return i; foreach (var c in Walk(i.DeviceItems)) yield return c; }
    }

    // ---------------- export ----------------
    static void Export(HmiTarget hmi, string dir)
    {
        Func<string, string> sub = s => { var x = Path.Combine(dir, s); Directory.CreateDirectory(x); return x; };
        string ds = sub("screens"), dt = sub("templates"), dg = sub("tags"), dl = sub("textlists"), dc = sub("connections");
        foreach (var s in AllScreens(hmi.ScreenFolder)) Try("screen " + s.Name, () => s.Export(new FileInfo(Path.Combine(ds, Safe(s.Name) + ".xml")), ExportOptions.WithDefaults));
        foreach (var t in AllTemplates(hmi.ScreenTemplateFolder)) Try("template " + t.Name, () => t.Export(new FileInfo(Path.Combine(dt, Safe(t.Name) + ".xml")), ExportOptions.WithDefaults));
        foreach (var t in AllTagTables(hmi.TagFolder)) Try("tagtable " + t.Name, () => t.Export(new FileInfo(Path.Combine(dg, Safe(t.Name) + ".xml")), ExportOptions.WithDefaults));
        foreach (var l in hmi.TextLists) Try("textlist " + l.Name, () => l.Export(new FileInfo(Path.Combine(dl, Safe(l.Name) + ".xml")), ExportOptions.WithDefaults));
        foreach (var c in hmi.Connections) Try("connection " + c.Name, () => c.Export(new FileInfo(Path.Combine(dc, Safe(c.Name) + ".xml")), ExportOptions.WithDefaults));
        Console.WriteLine("EXPORT done -> " + dir);
    }
    static void Try(string what, Action f)
    {
        try { f(); Console.WriteLine("EXPORT " + what + " ok"); }
        catch (Exception ex) { Console.WriteLine("[WARNING] EXPORT " + what + ": " + ExText(ex)); }
    }

    // ---------------- import ----------------
    static int Import(HmiTarget hmi, string dir)
    {
        int bad = 0;
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

    // ---------------- helpers ----------------
    static IEnumerable<Screen> AllScreens(ScreenFolder f)
    {
        foreach (var s in f.Screens) yield return s;
        foreach (var g in f.Folders) foreach (var s in AllScreens(g)) yield return s;
    }
    static IEnumerable<ScreenTemplate> AllTemplates(ScreenTemplateFolder f)
    {
        foreach (var s in f.ScreenTemplates) yield return s;
        foreach (var g in f.Folders) foreach (var s in AllTemplates(g)) yield return s;
    }
    static IEnumerable<TagTable> AllTagTables(TagSystemFolder f)
    {
        foreach (var t in f.TagTables) yield return t;
        foreach (var g in f.Folders) foreach (var t in AllTagTables2(g)) yield return t;
    }
    static IEnumerable<TagTable> AllTagTables2(TagUserFolder f)
    {
        foreach (var t in f.TagTables) yield return t;
        foreach (var g in f.Folders) foreach (var t in AllTagTables2(g)) yield return t;
    }
    static string Safe(string s) { foreach (var c in Path.GetInvalidFileNameChars()) s = s.Replace(c, '_'); return s.Replace(' ', '_'); }

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
