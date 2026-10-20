using System.Globalization;
using System.IO;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using InspectionApp.Models;
using InspectionApp.ViewModels;
using Microsoft.Win32;

namespace InspectionApp;

/// <summary>
/// The window. It only connects the view model to the chart (the chart library is not data-bound) and opens file dialogs.
/// </summary>
public partial class MainWindow : Window
{
    private readonly MainViewModel _vm = new();

    public MainWindow()
    {
        InitializeComponent();
        DataContext = _vm;
        _vm.TrendChanged += DrawTrend;
        TrendPlot.Plot.Title("Length of the part (mm), last 400 measured frames");
        HandleCommandLine();
    }

    /// <summary>
    /// Optional start options: --replay file.csv [--speed 30]  starts a replay at once;
    /// --screenshot out.png [--after 8]  saves a picture of this window after some seconds and closes it.
    /// </summary>
    private void HandleCommandLine()
    {
        var args = Environment.GetCommandLineArgs();
        string? Arg(string name) { var i = Array.IndexOf(args, name); return i >= 0 && i + 1 < args.Length ? args[i + 1] : null; }
        var replay = Arg("--replay");
        if (replay is not null)
        {
            _vm.ReplayPath = replay;
            if (Arg("--speed") is { } sp) _vm.Speed = double.Parse(sp, CultureInfo.InvariantCulture);
            Loaded += (_, _) => _vm.StartReplayCommand.Execute(null);
        }
        if (Arg("--screenshot") is { } png)
        {
            var seconds = Arg("--after") is { } a ? double.Parse(a, CultureInfo.InvariantCulture) : 8;
            var timer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(seconds) };
            timer.Tick += (_, _) =>
            {
                timer.Stop();
                var w = (int)ActualWidth; var h = (int)ActualHeight;
                var bmp = new RenderTargetBitmap(w, h, 96, 96, PixelFormats.Pbgra32);
                bmp.Render(this);
                var enc = new PngBitmapEncoder();
                enc.Frames.Add(BitmapFrame.Create(bmp));
                using (var fs = File.Create(png)) enc.Save(fs);
                Close();
            };
            Loaded += (_, _) => timer.Start();
        }
    }

    private void DrawTrend(IReadOnlyList<Measurement> trend)
    {
        var plot = TrendPlot.Plot;
        plot.Clear();
        if (trend.Count > 1)
        {
            var xs = Enumerable.Range(0, trend.Count).Select(i => (double)i).ToArray();
            var ys = trend.Select(m => m.LMm).ToArray();
            plot.Add.Scatter(xs, ys);
            foreach (var y in new[] { _vm.Nominal - _vm.Tolerance, _vm.Nominal, _vm.Nominal + _vm.Tolerance })
            {
                var line = plot.Add.HorizontalLine(y);
                line.Color = ScottPlot.Colors.Green;
                line.LinePattern = ScottPlot.LinePattern.Dashed;
            }
            plot.Axes.AutoScale();
        }
        TrendPlot.Refresh();
    }

    private void Browse_Click(object sender, RoutedEventArgs e)
    {
        var dlg = new OpenFileDialog { Filter = "CSV files (*.csv)|*.csv|All files|*.*", Title = "Recorded results" };
        if (dlg.ShowDialog() == true) _vm.ReplayPath = dlg.FileName;
    }

    private void Export_Click(object sender, RoutedEventArgs e)
    {
        var dlg = new SaveFileDialog { Filter = "CSV files (*.csv)|*.csv", FileName = "parts.csv" };
        if (dlg.ShowDialog() == true) _vm.ExportParts(dlg.FileName);
    }
}
