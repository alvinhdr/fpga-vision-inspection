using InspectionApp.Models;

namespace InspectionApp.Services;

/// <summary>A part that stayed in the window and then left.</summary>
public record FinishedPart(string Verdict, int DecidedLines, double MedianLengthMm);

/// <summary>
/// Counts parts and yield from the stream of measurements. Same rules as py/viewer.py (Tracker):
/// a part ends when NOPART lasts 15 frames, or the frame number jumps by more than 100 (new recording).
/// Its verdict is the majority of its PASS / FAIL lines; parts with fewer than 20 decided lines are ignored.
/// </summary>
public class PartTracker
{
    public const int GapFrames = 15, MaxJump = 100, MinDecided = 20;

    private int _pass, _fail, _noPartRun;
    private int? _lastFrame;
    private readonly List<double> _lengths = new();

    public List<FinishedPart> Parts { get; } = new();
    public int PassParts => Parts.Count(p => p.Verdict == "PASS");
    public int FailParts => Parts.Count(p => p.Verdict == "FAIL");
    public double YieldPercent => Parts.Count == 0 ? double.NaN : 100.0 * PassParts / Parts.Count;

    /// <summary>Called for every new measurement. Returns the part that just finished, if any.</summary>
    public FinishedPart? Feed(Measurement m)
    {
        FinishedPart? finished = null;
        if (_lastFrame is int last && (m.Frame - last < 0 || m.Frame - last > MaxJump)) finished = Close();
        _lastFrame = m.Frame;

        if (m.Status == "NOPART")
        {
            if (++_noPartRun >= GapFrames) finished ??= Close();
        }
        else _noPartRun = 0;

        if (m.Verdict is "PASS" or "FAIL")
        {
            if (m.Verdict == "PASS") _pass++; else _fail++;
            _lengths.Add(m.LMm);
        }
        return finished;
    }

    /// <summary>Call at the end of a recording to close the last part.</summary>
    public FinishedPart? Finish() => Close();

    private FinishedPart? Close()
    {
        FinishedPart? part = null;
        var n = _pass + _fail;
        if (n >= MinDecided)
        {
            _lengths.Sort();
            part = new FinishedPart(_pass >= _fail ? "PASS" : "FAIL", n, _lengths[_lengths.Count / 2]);
            Parts.Add(part);
        }
        _pass = _fail = 0;
        _lengths.Clear();
        return part;
    }
}
