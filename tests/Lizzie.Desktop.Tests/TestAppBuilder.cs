using Avalonia;
using Avalonia.Headless;

[assembly: AvaloniaTestApplication(typeof(Lizzie.Desktop.Tests.TestAppBuilder))]

namespace Lizzie.Desktop.Tests;

public static class TestAppBuilder
{
    public static AppBuilder BuildAvaloniaApp()
    {
        return AppBuilder.Configure<App>()
        .UseHeadless(new AvaloniaHeadlessPlatformOptions());
    }
}
