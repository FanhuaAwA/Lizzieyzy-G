namespace Lizzie.Core;

public readonly record struct BoardSize
{
    public static BoardSize Standard { get; } = new(19, 19);

    public BoardSize(int width, int height)
    {
        ArgumentOutOfRangeException.ThrowIfLessThan(width, 2);
        ArgumentOutOfRangeException.ThrowIfLessThan(height, 2);

        Width = width;
        Height = height;
    }

    public int Width { get; }

    public int Height { get; }
}
