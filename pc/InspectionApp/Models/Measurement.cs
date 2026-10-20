using System.Globalization;

namespace InspectionApp.Models;

/// <summary>
/// One result line of the board (docs/PROTOCOL.md):
/// R,frame,status,A_px,cx,cy,L_px,W_px,angle_deg,L_mm,W_mm,verdict
/// A "record" is a small class that only holds data and compares by value.
/// </summary>
public record Measurement(
    int Frame, string Status, int AreaPx, double Cx, double Cy,
    double LPx, double WPx, double AngleDeg, double LMm, double WMm, string Verdict)
{
    private static readonly HashSet<string> Statuses = new() { "NOPART", "EDGE", "NOISY", "MEASURED" };
    private static readonly HashSet<string> Verdicts = new() { "PASS", "FAIL", "NOCAL", "NONE" };

    /// <summary>
    /// Parse one line. Returns null for anything that is not a complete, valid R line
    /// (comments, status lines, damaged lines), so the caller can simply skip it.
    /// </summary>
    public static Measurement? TryParse(string? line)
    {
        if (line is null) return null;
        var p = line.Trim().Split(',');
        if (p.Length != 12 || p[0] != "R" || !Statuses.Contains(p[2]) || !Verdicts.Contains(p[11])) return null;
        var ci = CultureInfo.InvariantCulture;           // always "." as the decimal point, whatever the PC language
        if (!int.TryParse(p[1], NumberStyles.Integer, ci, out var frame) ||
            !int.TryParse(p[3], NumberStyles.Integer, ci, out var area)) return null;
        var d = new double[7];
        for (var i = 0; i < 7; i++)
            if (!double.TryParse(p[4 + i], NumberStyles.Float, ci, out d[i])) return null;
        return new Measurement(frame, p[2], area, d[0], d[1], d[2], d[3], d[4], d[5], d[6], p[11]);
    }
}
