using Avalonia.Controls;
using Avalonia.Headless.XUnit;
using Lizzie.Core;
using Lizzie.Desktop.Views;

namespace Lizzie.Desktop.Tests;

public sealed class MainWindowTests
{
    [AvaloniaFact]
    public void WindowShowsAStandardEmptyBoard()
    {
        MainWindow window = new();

        try
        {
            window.Show();

            BoardView board = Assert.IsType<BoardView>(window.FindControl<BoardView>("Board"));
            Assert.Equal(BoardSize.Standard, board.BoardSize);
            Assert.True(board.Bounds.Width > 0);
            Assert.True(board.Bounds.Height > 0);
        }
        finally
        {
            window.Close();
        }

        Assert.False(window.IsVisible);
    }
}
