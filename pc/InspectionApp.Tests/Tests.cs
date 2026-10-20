using System.IO;
using InspectionApp.Models;
using InspectionApp.Services;
using InspectionApp.ViewModels;
using Xunit;

namespace InspectionApp.Tests;

public class ParserTests
{
    [Fact]
    public void ParsesAValidLine()
    {
        var m = Measurement.TryParse("R,1234,MEASURED,325,640.2,350.1,72.98,10.45,-87.9,10.00,1.43,PASS");
        Assert.NotNull(m);
        Assert.Equal(1234, m!.Frame);
        Assert.Equal("MEASURED", m.Status);
        Assert.Equal(325, m.AreaPx);
        Assert.Equal(72.98, m.LPx, 2);
        Assert.Equal(-87.9, m.AngleDeg, 1);
        Assert.Equal("PASS", m.Verdict);
    }

    [Theory]
    [InlineData("# comment")]
    [InlineData("")]
    [InlineData("S,id=0x1a570001")]
    [InlineData("R,1234,MEASURED,325,640.2,350.1,72.98,10.45,-87.9,10.00,1.43")]                 // too short
    [InlineData("R,12x4,MEASURED,325,640.2,350.1,72.98,10.45,-87.9,10.00,1.43,PASS")]            // bad number
    [InlineData("R,1234,WEIRD,325,640.2,350.1,72.98,10.45,-87.9,10.00,1.43,PASS")]               // unknown status
    public void RejectsDamagedLines(string line) => Assert.Null(Measurement.TryParse(line));

    [Fact]
    public void RejectsNull() => Assert.Null(Measurement.TryParse(null));
}

public class TrackerTests
{
    private static Measurement M(int frame, string status, string verdict, double l = 11.5) =>
        new(frame, status, 300, 640, 360, 67, 7, 0, l, 1.2, verdict);

    [Fact]
    public void CountsPartsAndYield()
    {
        var t = new PartTracker();
        var f = 0;
        for (var part = 0; part < 4; part++)
        {
            var verdict = part == 2 ? "FAIL" : "PASS";
            for (var i = 0; i < 40; i++) t.Feed(M(f++, "MEASURED", verdict));
            for (var i = 0; i < 20; i++) t.Feed(M(f++, "NOPART", "NONE"));      // empty mat: the part left
        }
        t.Finish();
        Assert.Equal(4, t.Parts.Count);
        Assert.Equal(3, t.PassParts);
        Assert.Equal(1, t.FailParts);
        Assert.Equal(75.0, t.YieldPercent, 1);
    }

    [Fact]
    public void IgnoresShortFlickers()
    {
        var t = new PartTracker();
        for (var i = 0; i < 10; i++) t.Feed(M(i, "MEASURED", "PASS"));          // only 10 decided lines
        t.Finish();
        Assert.Empty(t.Parts);
    }

    [Fact]
    public void FrameJumpStartsANewPart()
    {
        var t = new PartTracker();
        for (var i = 0; i < 30; i++) t.Feed(M(i, "MEASURED", "PASS"));
        for (var i = 0; i < 30; i++) t.Feed(M(5000 + i, "MEASURED", "FAIL"));    // new recording
        t.Finish();
        Assert.Equal(2, t.Parts.Count);
        Assert.Equal("PASS", t.Parts[0].Verdict);
        Assert.Equal("FAIL", t.Parts[1].Verdict);
    }
}

public class ViewModelTests
{
    private class FakeSink : ICommandSink
    {
        public List<string> Sent { get; } = new();
        public void Send(string command) => Sent.Add(command);
    }

    [Fact]
    public void ShowsPassAsGreen()
    {
        var vm = new MainViewModel();
        vm.Show(new Measurement(1, "MEASURED", 300, 640, 360, 67, 7, 0, 11.5, 1.2, "PASS"));
        Assert.Equal("PASS", vm.Verdict);
        Assert.Equal("#1FAA3C", vm.VerdictColor);
    }

    [Fact]
    public void ShowsNoPartAsGrey()
    {
        var vm = new MainViewModel();
        vm.Show(new Measurement(1, "NOPART", 0, 0, 0, 0, 0, 0, 0, 0, "NONE"));
        Assert.Equal("NOPART", vm.Verdict);
        Assert.Equal("#444444", vm.VerdictColor);
    }

    [Fact]
    public void ToleranceCommandUsesDotAsDecimalPoint()
    {
        var vm = new MainViewModel { Nominal = 11.3, Tolerance = 1.6 };
        var sink = new FakeSink();
        vm.SetCommandSink(sink);
        vm.ApplyToleranceCommand.Execute(null);
        Assert.Equal(new[] { "n 11.3 1.6" }, sink.Sent);       // never "11,3", whatever the PC language
    }

    [Fact]
    public void ToleranceWithoutConnectionDoesNotCrash()
    {
        var vm = new MainViewModel();
        vm.ApplyToleranceCommand.Execute(null);
        Assert.Contains("Not connected", vm.Message);
    }
}

public class ReplayTests
{
    private static string? FindEvidence()
    {
        var dir = AppContext.BaseDirectory;
        for (var i = 0; i < 8 && dir is not null; i++, dir = Path.GetDirectoryName(dir))
        {
            var p = Path.Combine(dir, "data", "runs", "20261020_final.csv");
            if (File.Exists(p)) return p;
        }
        return null;
    }

    [Fact]
    public void ReplayOfTheRealEvidenceGivesTheSamePartCountsAsPython()
    {
        var path = FindEvidence();
        Assert.NotNull(path);                                  // the recorded evidence is part of the repository
        var list = CsvReplaySource.Load(path);
        var t = new PartTracker();
        foreach (var m in list) t.Feed(m);
        t.Finish();
        // py/viewer.py --selftest prints: 7664 lines -> 22 parts counted: PASS 14, FAIL 8
        Assert.Equal(7664, list.Count);
        Assert.Equal(22, t.Parts.Count);
        Assert.Equal(14, t.PassParts);
        Assert.Equal(8, t.FailParts);
    }

    [Fact]
    public async Task ReplaySourceDeliversAllLines()
    {
        var csv = Path.GetTempFileName();
        File.WriteAllLines(csv, new[]
        {
            "pc_time,frame,status,A_px,cx,cy,L_px,W_px,angle_deg,L_mm,W_mm,verdict",
            "1.0,1,MEASURED,300,640.0,360.0,67.0,7.0,0.0,11.50,1.20,PASS",
            "1.1,2,NOPART,0,0.0,0.0,0.00,0.00,0.0,0.00,0.00,NONE",
        });
        var n = 0;
        await foreach (var _ in new CsvReplaySource(csv, 0).ReadAsync(CancellationToken.None)) n++;
        Assert.Equal(2, n);
        File.Delete(csv);
    }
}


