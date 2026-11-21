using Xunit;
public class Behavior { [Fact] public void ReturnsFixed() { Assert.Equal("fixed", Feature.Value); } }
