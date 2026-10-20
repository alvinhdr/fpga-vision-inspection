using System.IO;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Globalization;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using InspectionApp.Models;
using InspectionApp.Services;

namespace InspectionApp.ViewModels;

/// <summary>
/// Everything the window shows, and the actions the buttons run. The window (MainWindow.xaml) only binds to this class,
/// so the logic can be tested without a window ("MVVM"). [ObservableProperty] generates a property that tells the window
/// when it changes; [RelayCommand] turns a method into a command that a button can call.
/// </summary>
public partial class MainViewModel : ObservableObject
{
    private const int TrendLength = 400;

    [ObservableProperty] private string _verdict = "--";
    [ObservableProperty] private string _verdictColor = "#444444";
    [ObservableProperty] private string _statusText = "";
    [ObservableProperty] private string _lengthText = "";
    [ObservableProperty] private string _widthText = "";
    [ObservableProperty] private string _angleText = "";
    [ObservableProperty] private string _areaText = "";
    [ObservableProperty] private string _frameText = "";
    [ObservableProperty] private string _partsText = "parts 0   PASS 0   FAIL 0";
    [ObservableProperty] private string _yieldText = "yield --";
    [ObservableProperty] private string _message = "Choose a recorded CSV and press Replay, or press Live.";
    [ObservableProperty] private string _replayPath = "";
    [ObservableProperty] private string _comPort = "COM11";
    [ObservableProperty] private double _speed = 20;
    [ObservableProperty] private double _nominal = 11.3;
    [ObservableProperty] private double _tolerance = 1.6;
    [ObservableProperty] private bool _isRunning;

    public ObservableCollection<string> FailLog { get; } = new();
    public PartTracker Tracker { get; private set; } = new();

    /// <summary>Raised about 10 times per second with the last measurements, so the chart can redraw.</summary>
    public event Action<IReadOnlyList<Measurement>>? TrendChanged;

    private readonly List<Measurement> _trend = new();
    private readonly Stopwatch _clock = Stopwatch.StartNew();
    private long _lastTrendMs;
    private CancellationTokenSource? _cts;
    private ICommandSink? _sink;

    /// <summary>Used by the tests: show one measurement exactly as the live view would.</summary>
    public void Show(Measurement m)
    {
        var v = m.Status == "MEASURED" ? m.Verdict : m.Status;
        Verdict = v;
        VerdictColor = v switch { "PASS" => "#1FAA3C", "FAIL" => "#D62D2D", "NOCAL" => "#AA8A1F", "NOISY" or "EDGE" => "#AA8A1F", _ => "#444444" };
        StatusText = $"status {m.Status}";
        LengthText = $"length {m.LMm,7:F2} mm   ({m.LPx:F1} px)";
        WidthText = $"width  {m.WMm,7:F2} mm   ({m.WPx:F1} px)";
        AngleText = $"angle  {m.AngleDeg,6:F1} deg";
        AreaText = $"area   {m.AreaPx} px   centre {m.Cx:F1}, {m.Cy:F1}";
        FrameText = $"frame {m.Frame}";
        if (m.Status == "MEASURED")
        {
            _trend.Add(m);
            if (_trend.Count > TrendLength) _trend.RemoveAt(0);
        }
        var finished = Tracker.Feed(m);
        if (finished is not null) OnPartFinished(finished);
        if (_clock.ElapsedMilliseconds - _lastTrendMs > 100)
        {
            _lastTrendMs = _clock.ElapsedMilliseconds;
            TrendChanged?.Invoke(_trend);
        }
    }

    private void OnPartFinished(FinishedPart p)
    {
        PartsText = $"parts {Tracker.Parts.Count}   PASS {Tracker.PassParts}   FAIL {Tracker.FailParts}";
        YieldText = $"yield {Tracker.YieldPercent:F1} %";
        if (p.Verdict == "FAIL")
            FailLog.Insert(0, $"{DateTime.Now:HH:mm:ss}  part {Tracker.Parts.Count}  FAIL  length {p.MedianLengthMm:F1} mm  ({p.DecidedLines} frames)");
    }

    private async Task RunAsync(IMeasurementSource source, string name)
    {
        Stop();
        Tracker = new PartTracker();
        _trend.Clear();
        FailLog.Clear();
        PartsText = "parts 0   PASS 0   FAIL 0";
        YieldText = "yield --";
        _cts = new CancellationTokenSource();
        IsRunning = true;
        Message = name;
        try
        {
            await foreach (var m in source.ReadAsync(_cts.Token)) Show(m);   // runs on the window thread between awaits
            var last = Tracker.Finish();
            if (last is not null) OnPartFinished(last);
            TrendChanged?.Invoke(_trend);
            Message = "Finished.";
        }
        catch (OperationCanceledException) { Message = "Stopped."; }
        catch (Exception ex) { Message = "Error: " + ex.Message; }
        finally { IsRunning = false; }
    }

    [RelayCommand]
    private Task StartReplay()
    {
        if (!File.Exists(ReplayPath)) { Message = "File not found: " + ReplayPath; return Task.CompletedTask; }
        return RunAsync(new CsvReplaySource(ReplayPath, Speed), $"Replay of {Path.GetFileName(ReplayPath)} at {Speed}x");
    }

    [RelayCommand]
    private Task StartLive()
    {
        var src = new SerialSource(ComPort);
        _sink = src;
        return RunAsync(src, $"Live from {ComPort}");
    }

    [RelayCommand]
    private void Stop() => _cts?.Cancel();

    /// <summary>Send the nominal length and tolerance to the board (command n, docs/PROTOCOL.md).</summary>
    [RelayCommand]
    private void ApplyTolerance()
    {
        if (_sink is null) { Message = "Not connected: start Live first."; return; }
        _sink.Send(string.Create(CultureInfo.InvariantCulture, $"n {Nominal} {Tolerance}"));
        Message = "Sent tolerance to the board.";
    }

    /// <summary>Lets the tests replace the serial port with a fake command sink.</summary>
    public void SetCommandSink(ICommandSink sink) => _sink = sink;

    public void ExportParts(string path)
    {
        var lines = new List<string> { "part,verdict,decided_frames,median_length_mm" };
        for (var i = 0; i < Tracker.Parts.Count; i++)
        {
            var p = Tracker.Parts[i];
            lines.Add(string.Create(CultureInfo.InvariantCulture, $"{i + 1},{p.Verdict},{p.DecidedLines},{p.MedianLengthMm:F2}"));
        }
        File.WriteAllLines(path, lines);
        Message = $"Saved {Tracker.Parts.Count} parts to {path}";
    }
}
