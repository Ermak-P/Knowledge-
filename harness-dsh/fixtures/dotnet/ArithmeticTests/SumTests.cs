using AcceptanceFixture;
using Xunit;

public class SumTests
{
    [Fact]
    public void AddsTwoNumbers() => Assert.Equal(5, Calculator.Sum(2, 3));
}
