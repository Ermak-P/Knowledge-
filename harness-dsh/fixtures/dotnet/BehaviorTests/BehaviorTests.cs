using AcceptanceFixture;
using Xunit;

public class BehaviorTests
{
    [Fact]
    public void AddsNegativeNumbers() => Assert.Equal(-5, Calculator.Sum(-2, -3));

    [Fact]
    public void WaitsWhenRequested()
    {
        var signalFile = System.Environment.GetEnvironmentVariable("HARNESS_FIXTURE_SIGNAL_FILE");
        if (!string.IsNullOrEmpty(signalFile))
        {
            System.IO.File.WriteAllText(signalFile, System.Environment.ProcessId.ToString());
            var wait = System.Diagnostics.Stopwatch.StartNew();
            while (wait.ElapsedMilliseconds < 30000 && !System.IO.File.Exists(signalFile + ".release"))
                System.Threading.Thread.Sleep(50);
        }
        Assert.Equal(0, Calculator.Sum(-2, 2));
    }
}
