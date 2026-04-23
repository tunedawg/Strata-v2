using Microsoft.UI.Xaml;
using Microsoft.Web.WebView2.Core;
using System.Diagnostics;
using System.Net.Http;

namespace Strata.Desktop;

public sealed partial class MainWindow : Window
{
    private readonly HttpClient _httpClient = new();
    private Process? _backendProcess;
    private readonly int _backendPort = 18888;

    public MainWindow()
    {
        InitializeComponent();
        Activated += OnActivated;
        Closed += OnClosed;
    }

    private async void OnActivated(object sender, WindowActivatedEventArgs args)
    {
        Activated -= OnActivated;
        await StartBackendAsync();
        await ShellView.EnsureCoreWebView2Async();
        ShellView.CoreWebView2.Settings.IsStatusBarEnabled = false;
        ShellView.CoreWebView2.Settings.AreDefaultContextMenusEnabled = true;
        ShellView.Source = new Uri($"http://127.0.0.1:{_backendPort}");
    }

    private async Task StartBackendAsync()
    {
        var baseDirectory = AppContext.BaseDirectory;
        var runtimePython = Path.Combine(baseDirectory, "runtime", "python", "python.exe");
        var backendScript = Path.Combine(baseDirectory, "backend", "run_waitress.py");
        var pythonExecutable = File.Exists(runtimePython) ? runtimePython : "python";
        var scriptPath = File.Exists(backendScript) ? backendScript : Path.Combine(baseDirectory, "run_waitress.py");

        var startInfo = new ProcessStartInfo
        {
            FileName = pythonExecutable,
            Arguments = $"\"{scriptPath}\"",
            WorkingDirectory = Path.GetDirectoryName(scriptPath) ?? baseDirectory,
            UseShellExecute = false,
            CreateNoWindow = true,
        };

        startInfo.Environment["STRATA_PORT"] = _backendPort.ToString();
        startInfo.Environment["STRATA_DATA_ROOT"] = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
            "Strata"
        );

        _backendProcess = Process.Start(startInfo);
        await WaitForBackendAsync();
    }

    private async Task WaitForBackendAsync()
    {
        for (var attempt = 0; attempt < 60; attempt++)
        {
            try
            {
                using var request = new HttpRequestMessage(HttpMethod.Get, $"http://127.0.0.1:{_backendPort}/api/bootstrap");
                using var response = await _httpClient.SendAsync(request);
                if (response.IsSuccessStatusCode)
                {
                    return;
                }
            }
            catch
            {
            }

            await Task.Delay(500);
        }

        throw new InvalidOperationException("The Strata backend did not start in time.");
    }

    private void OnClosed(object sender, WindowEventArgs args)
    {
        try
        {
            if (_backendProcess is { HasExited: false })
            {
                _backendProcess.Kill(entireProcessTree: true);
            }
        }
        catch
        {
        }
    }
}
