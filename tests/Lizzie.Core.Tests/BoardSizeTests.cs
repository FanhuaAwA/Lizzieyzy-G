namespace Lizzie.Core.Tests;

public sealed class BoardSizeTests
{
    [Fact]
    public void StandardBoardIsNineteenByNineteen()
    {
        Assert.Equal(new BoardSize(19, 19), BoardSize.Standard);
    }

    [Theory]
    [InlineData(1, 19)]
    [InlineData(19, 1)]
    public void BoardRejectsDimensionsSmallerThanTwo(int width, int height)
    {
        _ = Assert.Throws<ArgumentOutOfRangeException>(() => new BoardSize(width, height));
    }
}
