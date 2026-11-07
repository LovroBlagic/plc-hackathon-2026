// TiaDownload: Openness download of the PLC of a TIA V21 project into a PLCSIM (Advanced API) instance.
// ONLY for a TEST COPY of the project and a virtual PLCSIM target. Caller holds tia-work/openness.lock.
//
//   TiaDownload.exe --project C:\abs\Dir\Name [--list] [--mode PN/IE] [--pc PLCSIM] [--target "1 X1"]
//                   [--sw-only] [--no-start]
// --list prints connection modes / PC interfaces / target interfaces and exits.
// Prints DOWNLOAD_RESULT state=.. errors=.. warnings=..
using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Collections.Generic;
using Siemens.Engineering;
using Siemens.Engineering.HW;
using Siemens.Engineering.Connection;
using Siemens.Engineering.Download;
using DC = Siemens.Engineering.Download.Configurations;

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
    static int Main(string[] a)
    {
        try { return Dl.Run(a); }
        catch (Exception ex) { Console.WriteLine("FATAL: " + Dl.ExText(ex)); return 2; }
    }
}

internal static class Dl
{
    static string Arg(string[] a, string k) { int i = Array.IndexOf(a, k); return (i >= 0 && i + 1 < a.Length) ? a[i + 1] : null; }
    static bool Flag(string[] a, string k) { return Array.IndexOf(a, k) >= 0; }
    public static string ExText(Exception ex)
    {
        var s = ""; for (var e = ex; e != null; e = e.InnerException) s += (s.Length > 0 ? " | " : "") + e.GetType().Name + ": " + e.Message.Replace("\r", " ").Replace("\n", " ");
        return s;
    }
    static IEnumerable<DeviceItem> Walk(DeviceItemComposition items)
    {
        foreach (var i in items) { yield return i; foreach (var c in Walk(i.DeviceItems)) yield return c; }
    }

    static bool noStart; static bool simTarget = true;

    public static int Run(string[] a)
    {
        string proj = Path.GetFullPath(Arg(a, "--project")).TrimEnd('\\');
        string ap21 = Directory.GetFiles(proj, "*.ap21").First();
        Console.WriteLine("STARTING headless TIA Portal");
        using (var portal = new TiaPortal(TiaPortalMode.WithoutUserInterface)) {
            var p = portal.Projects.Open(new FileInfo(ap21));
            Console.WriteLine("OPENED " + ap21);
            DownloadProvider dp = null; DeviceItem cpu = null;
            foreach (var d in p.Devices) foreach (var di in Walk(d.DeviceItems)) {
                var x = di.GetService<DownloadProvider>();
                if (x != null && dp == null && di.GetService<Siemens.Engineering.HW.Features.SoftwareContainer>() != null) { dp = x; cpu = di; }
            }
            if (dp == null) { Console.WriteLine("FATAL: no downloadable CPU"); return 2; }
            Console.WriteLine("CPU item: " + cpu.Name);
            var cfg = dp.Configuration;
            foreach (ConfigurationMode m in cfg.Modes) {
                Console.WriteLine("MODE '" + m.Name + "'");
                foreach (ConfigurationPcInterface pc in m.PcInterfaces) {
                    Console.WriteLine("   PC '" + pc.Name + "' #" + pc.Number);
                    if (Flag(a, "--scan")) {
                        try { foreach (var ad in pc.GetAccessibleDevices()) Console.WriteLine("      ACCESSIBLE name='" + ad.Name + "' addr=" + ad.Address + " mac=" + ad.MACAddress + " series=" + ad.DeviceSeries); }
                        catch (Exception ex) { Console.WriteLine("      ACCESSIBLE scan failed: " + ExText(ex)); }
                    }
                    foreach (ConfigurationTargetInterface t in pc.TargetInterfaces) Console.WriteLine("      TARGET '" + t.Name + "'");
                }
            }
            foreach (var di in Walk(cpu.DeviceItems)) {
                var ni = di.GetService<Siemens.Engineering.HW.Features.NetworkInterface>();
                if (ni == null) continue;
                foreach (Node nd in ni.Nodes) { object ad = null; try { ad = nd.GetAttribute("Address"); } catch { } Console.WriteLine("NODE " + di.Name + " / " + nd.Name + " addr=" + ad + " subnet=" + (nd.ConnectedSubnet == null ? "-" : nd.ConnectedSubnet.Name)); }
            }
            if (Flag(a, "--attrs")) {
                foreach (var ai in cpu.GetAttributeInfos()) { object v = null; try { v = cpu.GetAttribute(ai.Name); } catch { v = "<n/a>"; } Console.WriteLine("ATTR " + ai.Name + " = " + v); }
            }
            if (Flag(a, "--list")) return 0;
            string card = Arg(a, "--card");
            if (card != null) {
                card = Path.GetFullPath(card);
                if (Directory.Exists(card)) Directory.Delete(card, true);
                Directory.CreateDirectory(card);
                Console.WriteLine("CARD image -> " + card);
                DownloadResult rc = dp.Download(new DirectoryInfo(card), Pre);
                DumpMsgs(rc.Messages, "");
                Console.WriteLine("DOWNLOAD_RESULT state=" + rc.State + " errors=" + rc.ErrorCount + " warnings=" + rc.WarningCount);
                p.Close();
                return rc.ErrorCount > 0 ? 1 : 0;
            }
            string mode = Arg(a, "--mode") ?? "PN/IE", pcName = Arg(a, "--pc") ?? "PLCSIM", tgt = Arg(a, "--target");
            ConfigurationMode cm = cfg.Modes.Find(mode);
            if (cm == null) { Console.WriteLine("FATAL: mode not found " + mode); return 2; }
            ConfigurationPcInterface pci = cm.PcInterfaces.Cast<ConfigurationPcInterface>().FirstOrDefault(x => x.Name.IndexOf(pcName, StringComparison.OrdinalIgnoreCase) >= 0);
            if (pci == null) { Console.WriteLine("FATAL: PC interface containing '" + pcName + "' not found"); return 2; }
            ConfigurationTargetInterface ti = tgt == null ? pci.TargetInterfaces.Cast<ConfigurationTargetInterface>().FirstOrDefault()
                                                          : pci.TargetInterfaces.Cast<ConfigurationTargetInterface>().FirstOrDefault(x => x.Name == tgt);
            if (ti == null) { Console.WriteLine("FATAL: target interface not found"); return 2; }
            Console.WriteLine("USING mode='" + cm.Name + "' pc='" + pci.Name + "' target='" + ti.Name + "'");
            noStart = Flag(a, "--no-start"); simTarget = !Flag(a, "--real-cpu");
            var opts = Flag(a, "--sw-only") ? DownloadOptions.Software : (DownloadOptions.Hardware | DownloadOptions.Software);
            string addr = Arg(a, "--address");
            DownloadResult r;
            if (addr != null) {
                var ca = ti.Addresses.Find(addr) ?? ti.Addresses.Create(addr);
                Console.WriteLine("ADDRESS " + addr);
                r = dp.Download(ti, ca, Pre, Post, opts);
            } else r = dp.Download(ti, Pre, Post, opts);
            DumpMsgs(r.Messages, "");
            Console.WriteLine("DOWNLOAD_RESULT state=" + r.State + " errors=" + r.ErrorCount + " warnings=" + r.WarningCount);
            p.Close();
            return r.ErrorCount > 0 ? 1 : 0;
        }
    }

    static void DumpMsgs(DownloadResultMessageComposition msgs, string ind)
    {
        foreach (DownloadResultMessage m in msgs) {
            Console.WriteLine(ind + "[" + m.State + "] " + m.Message);
            DumpMsgs(m.Messages, ind + "  ");
        }
    }

    static void SetSel(object cfg, string want)
    {
        var pr = cfg.GetType().GetProperty("CurrentSelection");
        var et = pr.PropertyType;
        pr.SetValue(cfg, Enum.Parse(et, want));
    }

    // Virtual PLCSIM test target only: stop / reinit / overwrite / start are all acceptable here.
    static readonly Dictionary<string, string> PreSel = new Dictionary<string, string> {
        { "StopModules", "StopAll" }, { "ConsistentBlocksDownload", "ConsistentDownload" }, { "AllBlocksDownload", "DownloadAllBlocks" },
        { "OverwriteSystemData", "Overwrite" }, { "DifferentTargetConfiguration", "AcceptAll" }, { "DataBlockReinitialization", "StopPlcAndReinitialize" },
        { "DataBlockReinitializationOrKeepActualValues", "StopPlcAndReinitialize" }, { "InitializeMemory", "AcceptAll" }, { "ResetModule", "DeleteAll" },
        { "AlarmTextLibrariesDownload", "ConsistentDownload" }, { "LoadIdentificationData", "LoadNothing" }, { "ExpandDownload", "Download" },
        { "SelectiveDeleteDownload", "AcceptAll" }, { "OverwriteOnMemoryCard", "Load" }, { "WaitOnReboot", "Wait" },
        { "UserManagementDownload", "DownloadAllUserManagementDataResetToProject" }, { "ProtectionLevelChanged", "ContinueDownloading" },
        { "ActiveTestCanBeAborted", "AcceptAll" }, { "ActiveTestCanPreventDownload", "AcceptAll" },
    };

    static void Pre(DC.DownloadConfiguration c)
    {
        string n = c.GetType().Name;
        Console.WriteLine("PRE " + n + ": " + c.Message);
        string sel;
        if (n == "TargetForSoftware") { SetSel(c, simTarget ? "PlcSimulationAdvanced" : "CPU"); Console.WriteLine("    -> " + (simTarget ? "PlcSimulationAdvanced" : "CPU")); return; }
        if (PreSel.TryGetValue(n, out sel)) { SetSel(c, sel); Console.WriteLine("    -> " + sel); return; }
        var chk = c as DC.DownloadCheckConfiguration;
        if (chk != null) { chk.Checked = true; Console.WriteLine("    -> Checked"); return; }
        throw new NotSupportedException("unhandled pre-download configuration " + c.GetType().FullName + ": " + c.Message);
    }

    static void Post(DC.DownloadConfiguration c)
    {
        string n = c.GetType().Name;
        Console.WriteLine("POST " + n + ": " + c.Message);
        if (n == "StartModules") { SetSel(c, noStart ? "NoAction" : "StartModule"); return; }
        if (n == "WaitOnReboot") { SetSel(c, "Wait"); return; }
        var chk = c as DC.DownloadCheckConfiguration;
        if (chk != null) { chk.Checked = true; return; }
        throw new NotSupportedException("unhandled post-download configuration " + c.GetType().FullName + ": " + c.Message);
    }
}
