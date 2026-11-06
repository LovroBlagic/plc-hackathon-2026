// TiaRun: TIA Portal V21 Openness one-shot runner (C# 5, build with build.ps1 / csc.exe of .NET Framework 4.8)
//   TiaRun.exe --project C:\abs\Dir\Name [--create] [--cpu "6ES7 511-1AK0"] [--src C:\abs\src] [--headless] [--no-compile]
// Steps: attach to running TIA (or start headless) -> open/create project -> ensure one PLC -> import every
//   src/*.scl|*.db|*.udt as external source and generate blocks -> compile PLC software -> save.
// Summary line:  TIA_RESULT errors=N warnings=M
using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Collections.Generic;

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
        try { return Runner.Run(args); }
        catch (Exception ex) { Console.WriteLine("FATAL: " + ex.GetType().Name + ": " + ex.Message); return 2; }
    }
}

internal static class Runner
{
    static string Arg(string[] a, string k) { int i = Array.IndexOf(a, k); return (i >= 0 && i + 1 < a.Length) ? a[i + 1] : null; }
    static bool Flag(string[] a, string k) { return Array.IndexOf(a, k) >= 0; }

    public static int Run(string[] a)
    {
        string proj = Arg(a, "--project");
        if (proj == null) { Console.WriteLine("FATAL: --project C:\\abs\\Dir\\Name required"); return 2; }
        proj = proj.Replace('/', '\\');
        if (proj.EndsWith(".ap21")) proj = Path.Combine(Path.GetDirectoryName(Path.GetDirectoryName(proj)), Path.GetFileNameWithoutExtension(proj));
        string name = Path.GetFileName(proj), dir = Path.GetDirectoryName(proj);
        string ap21 = Path.Combine(proj, name + ".ap21");

        Siemens.Engineering.TiaPortal portal;
        if (Flag(a, "--headless")) {
            portal = new Siemens.Engineering.TiaPortal(Siemens.Engineering.TiaPortalMode.WithoutUserInterface);
            Console.WriteLine("STARTED headless TIA Portal");
        } else {
            var procs = Siemens.Engineering.TiaPortal.GetProcesses();
            if (procs.Count == 0) { Console.WriteLine("FATAL: no running TIA Portal V21. Start it, or pass --headless"); return 2; }
            Console.WriteLine("ATTACHING to TIA PID " + procs[0].Id + " (first time: answer TIA's Openness access dialog with 'Yes to all')");
            portal = procs[0].Attach();
        }

        using (portal)
        {
            Siemens.Engineering.Project p = portal.Projects.FirstOrDefault(x => string.Equals(x.Path.FullName, ap21, StringComparison.OrdinalIgnoreCase));
            if (p == null && portal.Projects.Count > 0) {
                Console.WriteLine("FATAL: another project is open in this TIA: " + portal.Projects[0].Path.FullName + ". Close it first.");
                return 2;
            }
            if (p == null) {
                if (File.Exists(ap21)) { p = portal.Projects.Open(new FileInfo(ap21)); Console.WriteLine("OPENED " + ap21); }
                else if (Flag(a, "--create")) { Directory.CreateDirectory(dir); p = portal.Projects.Create(new DirectoryInfo(dir), name); Console.WriteLine("CREATED " + ap21); }
                else { Console.WriteLine("FATAL: project not found (use --create): " + ap21); return 2; }
            } else Console.WriteLine("USING open project " + ap21);

            Siemens.Engineering.SW.PlcSoftware sw = FindPlc(p);
            if (sw == null) {
                string search = Arg(a, "--cpu") ?? "6ES7 511-1AK0";   // CPU 1511-1 PN: smallest S7-1500, supported by PLCSIM Advanced
                var entries = portal.HardwareCatalog.Find(search).Where(c => c.TypeIdentifier.StartsWith("OrderNumber:")).ToList();
                if (entries.Count == 0) { Console.WriteLine("FATAL: no catalog entry for " + search); return 2; }
                var pick = entries.OrderBy(c => c.TypeIdentifier).Last();   // newest article/firmware
                p.Devices.CreateWithItem(pick.TypeIdentifier, "PLC_1", "PLC_1");
                Console.WriteLine("ADDED CPU " + pick.TypeIdentifier);
                sw = FindPlc(p);
            }
            if (sw == null) { Console.WriteLine("FATAL: no PLC software found in project"); return 2; }

            string src = Arg(a, "--src");
            if (src != null) {
                var files = Directory.GetFiles(src).Where(f => new[] { ".scl", ".db", ".udt", ".awl" }.Contains(Path.GetExtension(f).ToLower())).OrderBy(f => f).ToList();
                foreach (var f in files) {
                    string sname = Path.GetFileName(f);
                    var old = sw.ExternalSourceGroup.ExternalSources.Find(sname);
                    if (old != null) old.Delete();
                    var es = sw.ExternalSourceGroup.ExternalSources.CreateFromFile(sname, f);
                    try {
                        es.GenerateBlocksFromSource(Siemens.Engineering.SW.ExternalSources.GenerateBlockOption.KeepOnError);
                        Console.WriteLine("IMPORT " + sname + " ok");
                    } catch (Exception ex) {
                        Console.WriteLine("[ERROR] IMPORT " + sname + ": " + ex.Message);
                    }
                }
            }

            int errs = 0, warns = 0;
            if (!Flag(a, "--no-compile")) {
                var comp = ((Siemens.Engineering.IEngineeringServiceProvider)sw).GetService<Siemens.Engineering.Compiler.ICompilable>();
                var res = comp.Compile();
                Dump(res.Messages, 0);
                errs = res.ErrorCount; warns = res.WarningCount;
            }
            p.Save();
            Console.WriteLine("SAVED");
            Console.WriteLine("TIA_RESULT errors=" + errs + " warnings=" + warns);
            return errs > 0 ? 1 : 0;
        }
    }

    static Siemens.Engineering.SW.PlcSoftware FindPlc(Siemens.Engineering.Project p)
    {
        foreach (var d in p.Devices)
            foreach (var di in Walk(d.DeviceItems)) {
                var sc = ((Siemens.Engineering.IEngineeringServiceProvider)di).GetService<Siemens.Engineering.HW.Features.SoftwareContainer>();
                if (sc != null && sc.Software is Siemens.Engineering.SW.PlcSoftware) return (Siemens.Engineering.SW.PlcSoftware)sc.Software;
            }
        return null;
    }

    static IEnumerable<Siemens.Engineering.HW.DeviceItem> Walk(Siemens.Engineering.HW.DeviceItemComposition items)
    {
        foreach (var i in items) { yield return i; foreach (var c in Walk(i.DeviceItems)) yield return c; }
    }

    static void Dump(Siemens.Engineering.Compiler.CompilerResultMessageComposition msgs, int depth)
    {
        foreach (var m in msgs) {
            string st = m.State.ToString();
            bool leaf = m.Messages.Count == 0;
            if (leaf && (st == "Error" || st == "Warning"))
                Console.WriteLine("[" + st.ToUpper() + "] " + (m.Path ?? "") + " :: " + m.Description);
            Dump(m.Messages, depth + 1);
        }
    }
}
