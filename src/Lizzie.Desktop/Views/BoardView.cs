using Avalonia;
using Avalonia.Controls;
using Avalonia.Media;
using Lizzie.Core;

namespace Lizzie.Desktop.Views;

public sealed class BoardView : Control
{
    public static readonly StyledProperty<BoardSize> BoardSizeProperty =
        AvaloniaProperty.Register<BoardView, BoardSize>(nameof(BoardSize), BoardSize.Standard);

    private static readonly IBrush BoardBrush = new SolidColorBrush(Color.Parse("#D6A65A"));
    private static readonly Pen GridPen = new(new SolidColorBrush(Color.Parse("#3B2A1A")), 1);

    static BoardView()
    {
        AffectsRender<BoardView>(BoardSizeProperty);
    }

    public BoardSize BoardSize
    {
        get => GetValue(BoardSizeProperty);
        set => SetValue(BoardSizeProperty, value);
    }

    public override void Render(DrawingContext context)
    {
        base.Render(context);

        double side = Math.Min(Bounds.Width, Bounds.Height);
        if (side <= 0)
        {
            return;
        }

        Rect board = new((Bounds.Width - side) / 2, (Bounds.Height - side) / 2, side, side);
        context.FillRectangle(BoardBrush, board);

        double inset = Math.Max(16, side * 0.05);
        double gridSide = side - (2 * inset);
        if (gridSide <= 0)
        {
            return;
        }

        double left = board.X + inset;
        double top = board.Y + inset;
        double columnStep = gridSide / (BoardSize.Width - 1);
        double rowStep = gridSide / (BoardSize.Height - 1);

        for (int column = 0; column < BoardSize.Width; column++)
        {
            double x = left + (column * columnStep);
            context.DrawLine(GridPen, new Point(x, top), new Point(x, top + gridSide));
        }

        for (int row = 0; row < BoardSize.Height; row++)
        {
            double y = top + (row * rowStep);
            context.DrawLine(GridPen, new Point(left, y), new Point(left + gridSide, y));
        }
    }
}
