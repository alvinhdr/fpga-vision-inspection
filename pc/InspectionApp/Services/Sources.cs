using System.IO;
using System.IO.Ports;
using System.Runtime.CompilerServices;
using InspectionApp.Models;

namespace InspectionApp.Services;

/// <summary>Where measurements come from: the live board, or a recorded file. The window does not care which.</summary>
public interface IMeasurementSource
{
    IAsyncEnumerable<Measurement> ReadAsync(CancellationToken ct);
}

/// <summary>Where commands to the board go (threshold, tolerance, ...). A fake one is used in the tests.</summary>
public interface ICommandSink
{
    void Send(string command);
}

/// <summary>
/// Replay of a CSV written by py/uart_log.py or py/evidence.py. Needs no board.
/// speed = how many times faster than real time (0 = as fast as possible).
/// </summary>
public class CsvReplaySource : IMeasurementSource
{
    private readonly string _path;
    private readonly double _speed;

    public CsvReplaySource(string path, double speed = 1.0) { _path = path; _speed = speed; }

    /// <summary>Read all rows of a CSV into measurements (also used by the tests).</summary>
    public static List<Measurement> Load(string path)
    {
        var lines = File.ReadAllLines(path);
        var head = lines[0].Split(',');
        int Col(string name) => Array.IndexOf(head, name);
        string[] names = { "frame", "status", "A_px", "cx", "cy", "L_px", "W_px", "angle_deg", "L_mm", "W_mm", "verdict" };
        var idx = names.Select(n => Col(n)).ToArray();
        if (idx.Any(i => i < 0)) throw new InvalidDataException("CSV is missing a column of docs/PROTOCOL.md");
        int iGroup = Col("group"), iPart = Col("part"), iPl = Col("placement");

        var rows = lines.Skip(1).Select(l => l.Split(',')).Where(c => c.Length == head.Length).ToList();
        if (iGroup >= 0) rows = StripStalePrefix(rows, idx[0], iGroup, iPart, iPl);

        var list = new List<Measurement>();
        foreach (var c in rows)
        {
            var m = Measurement.TryParse("R," + string.Join(",", idx.Select(i => c[i])));
            if (m is not null) list.Add(m);
        }
        return list;
    }

    /// <summary>
    /// Evidence recordings begin with about 60 STALE lines (old output still held by the USB-serial chip).
    /// They show up as a jump of the frame number inside the first 120 lines of a recording; drop everything before it.
    /// Same rule as strip_stale_prefix() in py/uart_log.py.
    /// </summary>
    public static List<string[]> StripStalePrefix(List<string[]> rows, int iFrame, int iGroup, int iPart, int iPl)
    {
        var result = new List<string[]>();
        foreach (var g in rows.GroupBy(r => (r[iGroup], r[iPart], r[iPl])))   // keeps the first-seen order of groups
        {
            var r = g.ToList();
            var cut = 0;
            for (var i = 1; i < Math.Min(r.Count, 120); i++)
                if (int.Parse(r[i][iFrame]) - int.Parse(r[i - 1][iFrame]) >= 100) { cut = i; break; }
            result.AddRange(r.Skip(cut));
        }
        return result;
    }

    public async IAsyncEnumerable<Measurement> ReadAsync([EnumeratorCancellation] CancellationToken ct)
    {
        foreach (var m in Load(_path))
        {
            ct.ThrowIfCancellationRequested();
            yield return m;
            if (_speed > 0) await Task.Delay(TimeSpan.FromSeconds(1.0 / 60 / _speed), ct);
        }
    }
}

/// <summary>The live board over the serial port (115200 8N1). Also sends commands.</summary>
public sealed class SerialSource : IMeasurementSource, ICommandSink, IDisposable
{
    private readonly SerialPort _port;

    public SerialSource(string portName)
    {
        _port = new SerialPort(portName, 115200, Parity.None, 8, StopBits.One) { ReadTimeout = 300, NewLine = "\n" };
    }

    public void Send(string command)
    {
        if (!_port.IsOpen) _port.Open();
        _port.WriteLine(command);
    }

    public async IAsyncEnumerable<Measurement> ReadAsync([EnumeratorCancellation] CancellationToken ct)
    {
        if (!_port.IsOpen) _port.Open();
        while (!ct.IsCancellationRequested)
        {
            string? line = null;
            try { line = await Task.Run(() => _port.ReadLine(), ct); }
            catch (TimeoutException) { }               // no line for 300 ms: try again
            var m = Measurement.TryParse(line);
            if (m is not null) yield return m;
        }
    }

    public void Dispose() => _port.Dispose();
}
