using System.Reflection;

namespace Lizzie.Engine.Tests;

public sealed class DependencyTests
{
    [Fact]
    public void EngineDoesNotReferenceDesktopOrAvalonia()
    {
        string?[] references = [.. Assembly.Load("Lizzie.Engine")
            .GetReferencedAssemblies()
            .Select(reference => reference.Name)];

        Assert.DoesNotContain("Lizzie.Desktop", references);
        Assert.DoesNotContain(references, name => name?.StartsWith("Avalonia", StringComparison.Ordinal) is true);
    }
}
