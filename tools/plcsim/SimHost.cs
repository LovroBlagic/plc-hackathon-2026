// SimHost: keeps one PLCSIM (Advanced API 8.0 / S7-PLCSIM V21 runtime) instance alive and serves a tiny
// line protocol on 127.0.0.1:<port> so scripts (tools/plcsim/simclient.py) can drive and read the virtual CPU.
// The instance only lives as long as the process that registered it, hence a host process.
//
//   SimHost.exe [--name crane] [--cpu CPU1515] [--port 50123]
//
// Commands (one per line, answer one line "OK ..." or "ERR ..."):
//   STATE | PON | POFF | RUN | STOP | MRES | TAGS (UpdateTagList IOMCTDB) | INFO (name, cpu, ip, licence, scale)
//   R <tag>                       read one tag ("DB".member[i,j] / "tagname" syntax of the API)
//   RB <tag>|<tag>|...            batch read (ReadSignals), answer values joined by |
//   W <tag> <value>               typed write (type from a prior read)
//   WB <tag>=<v>|<tag>=<v>...     several writes
//   LIST <substring>              tag names from the tag list containing substring (max 400)
//   SCALE <factor>                ScaleFactor (virtual time speed)
//   LOG <ms> <file> <tag>|<tag>.. sample tags every ms into file (CSV, wall ms + values); LOG STOP ends it
//   QUIT                          power off, unregister, exit
using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Linq;
using System.Globalization;
using System.Collections.Generic;
using Siemens.Simatic.Simulation.Runtime;

internal static class SimHost
{
    static IInstance inst;
    static readonly object gate = new object();
    static Thread logThread; static volatile bool logRun;
    static Dictionary<string, EPrimitiveDataType> types = new Dictionary<string, EPrimitiveDataType>();
    static CultureInfo IC = CultureInfo.InvariantCulture;

    static int Main(string[] a)
    {
        string name = Arg(a, "--name") ?? "crane";
        string cpu = Arg(a, "--cpu") ?? "CPU1515";
        int port = int.Parse(Arg(a, "--port") ?? "50123");
        try {
            var existing = SimulationRuntimeManager.RegisteredInstanceInfo.FirstOrDefault(i => i.Name == name);
            if (existing.Name == name) { inst = SimulationRuntimeManager.CreateInterface(name); Console.WriteLine("ATTACHED " + name); }
            else { inst = SimulationRuntimeManager.RegisterInstance((ECPUType)Enum.Parse(typeof(ECPUType), cpu), name); Console.WriteLine("REGISTERED " + name + " " + cpu); }
            Console.WriteLine("LICENCE " + inst.LicenseStatus + " COMM " + inst.CommunicationInterface + " STATE " + inst.OperatingState);
        } catch (Exception ex) { Console.WriteLine("FATAL " + ex.Message); return 2; }

        var l = new TcpListener(IPAddress.Loopback, port);
        l.Start();
        Console.WriteLine("LISTEN 127.0.0.1:" + port);
        bool quit = false;
        while (!quit) {
            using (var c = l.AcceptTcpClient())
            using (var s = c.GetStream())
            using (var rd = new StreamReader(s, new UTF8Encoding(false)))
            using (var wr = new StreamWriter(s, new UTF8Encoding(false)) { AutoFlush = true, NewLine = "\n" }) {
                string line;
                try {
                    while ((line = rd.ReadLine()) != null) {
                        string ans;
                        try { ans = Handle(line.Trim(), ref quit); } catch (Exception ex) { ans = "ERR " + ex.GetType().Name + ": " + ex.Message.Replace("\n", " "); }
                        wr.WriteLine(ans);
                        if (quit) break;
                    }
                } catch (IOException) { }
            }
        }
        l.Stop();
        return 0;
    }

    static string Arg(string[] a, string k) { int i = Array.IndexOf(a, k); return (i >= 0 && i + 1 < a.Length) ? a[i + 1] : null; }

    static string Fmt(SDataValue v)
    {
        switch (v.Type) {
            case EPrimitiveDataType.Bool: return v.Bool ? "1" : "0";
            case EPrimitiveDataType.Int8: return v.Int8.ToString(IC);
            case EPrimitiveDataType.Int16: return v.Int16.ToString(IC);
            case EPrimitiveDataType.Int32: return v.Int32.ToString(IC);
            case EPrimitiveDataType.Int64: return v.Int64.ToString(IC);
            case EPrimitiveDataType.UInt8: return v.UInt8.ToString(IC);
            case EPrimitiveDataType.UInt16: return v.UInt16.ToString(IC);
            case EPrimitiveDataType.UInt32: return v.UInt32.ToString(IC);
            case EPrimitiveDataType.UInt64: return v.UInt64.ToString(IC);
            case EPrimitiveDataType.Float: return v.Float.ToString("R", IC);
            case EPrimitiveDataType.Double: return v.Double.ToString("R", IC);
            case EPrimitiveDataType.Char: return ((int)v.Char).ToString(IC);
            case EPrimitiveDataType.WChar: return ((int)v.WChar).ToString(IC);
        }
        return "?" + v.Type;
    }

    static string ReadOne(string tag)
    {
        var v = inst.Read(tag);
        types[tag] = v.Type;
        return Fmt(v);
    }

    static void WriteOne(string tag, string val)
    {
        EPrimitiveDataType t;
        if (!types.TryGetValue(tag, out t)) { t = inst.Read(tag).Type; types[tag] = t; }
        switch (t) {
            case EPrimitiveDataType.Bool: inst.WriteBool(tag, val == "1" || val.Equals("true", StringComparison.OrdinalIgnoreCase)); break;
            case EPrimitiveDataType.Int8: inst.WriteInt8(tag, sbyte.Parse(val, IC)); break;
            case EPrimitiveDataType.Int16: inst.WriteInt16(tag, short.Parse(val, IC)); break;
            case EPrimitiveDataType.Int32: inst.WriteInt32(tag, int.Parse(val, IC)); break;
            case EPrimitiveDataType.Int64: inst.WriteInt64(tag, long.Parse(val, IC)); break;
            case EPrimitiveDataType.UInt8: inst.WriteUInt8(tag, byte.Parse(val, IC)); break;
            case EPrimitiveDataType.UInt16: inst.WriteUInt16(tag, ushort.Parse(val, IC)); break;
            case EPrimitiveDataType.UInt32: inst.WriteUInt32(tag, uint.Parse(val, IC)); break;
            case EPrimitiveDataType.UInt64: inst.WriteUInt64(tag, ulong.Parse(val, IC)); break;
            case EPrimitiveDataType.Float: inst.WriteFloat(tag, float.Parse(val, IC)); break;
            case EPrimitiveDataType.Double: inst.WriteDouble(tag, double.Parse(val, IC)); break;
            default: throw new Exception("unsupported type " + t + " for " + tag);
        }
    }

    static string[] ReadBatch(string[] tags)
    {
        var arr = tags.Select(t => new SDataValueByName { Name = t }).ToArray();
        inst.ReadSignals(ref arr);
        return arr.Select(x => x.ErrorCode == ERuntimeErrorCode.OK ? Fmt(x.DataValue) : ("E:" + x.ErrorCode)).ToArray();
    }

    static string Handle(string line, ref bool quit)
    {
        if (line.Length == 0) return "OK";
        int sp = line.IndexOf(' ');
        string cmd = (sp < 0 ? line : line.Substring(0, sp)).ToUpperInvariant();
        string rest = sp < 0 ? "" : line.Substring(sp + 1);
        lock (gate) {
            switch (cmd) {
                case "STATE": return "OK " + inst.OperatingState;
                case "PON": return "OK " + inst.PowerOn(60000) + " " + inst.OperatingState;
                case "POFF": inst.PowerOff(60000); return "OK " + inst.OperatingState;
                case "RUN": inst.Run(60000); return "OK " + inst.OperatingState;
                case "STOP": inst.Stop(60000); return "OK " + inst.OperatingState;
                case "MRES": inst.MemoryReset(60000); return "OK " + inst.OperatingState;
                case "TAGS": inst.UpdateTagList(ETagListDetails.IOMCTDB, true); types.Clear(); return "OK " + inst.TagInfos.Length;
                case "INFO":
                    return "OK name=" + inst.Name + " cpu=" + inst.CPUType + " ctrl=" + inst.ControllerName + " ip=" + string.Join(",", inst.ControllerIP ?? new string[0])
                         + " lic=" + inst.LicenseStatus + " state=" + inst.OperatingState + " scale=" + inst.ScaleFactor.ToString(IC) + " mode=" + inst.OperatingMode;
                case "R": return "OK " + ReadOne(rest.Trim());
                case "RB": return "OK " + string.Join("|", ReadBatch(rest.Split('|')));
                case "W": { int k = rest.LastIndexOf(' '); WriteOne(rest.Substring(0, k).Trim(), rest.Substring(k + 1).Trim()); return "OK"; }
                case "WB":
                    foreach (var kv in rest.Split('|')) { int e = kv.LastIndexOf('='); WriteOne(kv.Substring(0, e).Trim(), kv.Substring(e + 1).Trim()); }
                    return "OK";
                case "LIST": {
                    var names = inst.TagInfos.Select(t => t.Name + ":" + t.DataType).Where(n => n.IndexOf(rest, StringComparison.OrdinalIgnoreCase) >= 0).Take(400);
                    return "OK " + string.Join("|", names);
                }
                case "SCALE": inst.ScaleFactor = double.Parse(rest, IC); return "OK " + inst.ScaleFactor.ToString(IC);
                case "LOG": {
                    if (rest.Trim().ToUpperInvariant() == "STOP") { logRun = false; if (logThread != null) logThread.Join(5000); return "OK stopped"; }
                    var p = rest.Split(new[] { ' ' }, 3);
                    int ms = int.Parse(p[0]); string file = p[1]; string[] tags = p[2].Split('|');
                    logRun = false; if (logThread != null) logThread.Join(5000);
                    logRun = true;
                    logThread = new Thread(() => LogLoop(ms, file, tags)) { IsBackground = true };
                    logThread.Start();
                    return "OK logging";
                }
                case "QUIT":
                    logRun = false;
                    try { inst.PowerOff(60000); } catch { }
                    try { inst.UnregisterInstance(); } catch { }
                    quit = true; return "OK bye";
            }
        }
        return "ERR unknown command " + cmd;
    }

    static void LogLoop(int ms, string file, string[] tags)
    {
        var sw = System.Diagnostics.Stopwatch.StartNew();
        using (var w = new StreamWriter(file, false, new UTF8Encoding(false))) {
            w.WriteLine("ms|" + string.Join("|", tags));
            while (logRun) {
                string[] v;
                try { lock (gate) v = ReadBatch(tags); } catch (Exception ex) { v = new[] { "EX:" + ex.Message }; }
                w.WriteLine(sw.ElapsedMilliseconds + "|" + string.Join("|", v));
                w.Flush();
                Thread.Sleep(ms);
            }
        }
    }
}
