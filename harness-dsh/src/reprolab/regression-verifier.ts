export interface BaselineRegressionFacts {
  /** Normalized failing test names already observed at baseline. */
  failures: string[]
  /** False when the baseline check never ran. */
  ran: boolean
}

export interface CandidateRegressionFacts {
  /** Normalized failing test names observed in the candidate run. */
  failures: string[]
  /** False when the run crashed/timed out/failed to spawn and cannot be compared. */
  comparable: boolean
}

export interface RegressionComparison {
  baseline: BaselineRegressionFacts
  candidate: CandidateRegressionFacts
}

export type RegressionVerdict = 'pass' | 'pass_with_baseline_failures' | 'regression' | 'inconclusive'

export interface RegressionResult {
  verdict: RegressionVerdict
  newFailures: string[]
}

/**
 * Compare the candidate regression run with the baseline's already-known
 * failures (design spec §7.6). Only `pass` and `pass_with_baseline_failures`
 * are acceptable outcomes; a candidate that cannot be compared is
 * `inconclusive`, never silently "pass".
 */
export function verifyRegression(input: RegressionComparison): RegressionResult {
  if (!input.baseline.ran || !input.candidate.comparable) {
    return { verdict: 'inconclusive', newFailures: [] }
  }
  const baselineSet = new Set(input.baseline.failures)
  const newFailures = input.candidate.failures.filter((failure) => !baselineSet.has(failure))
  if (newFailures.length > 0) {
    return { verdict: 'regression', newFailures }
  }
  if (input.candidate.failures.length === 0) {
    return { verdict: 'pass', newFailures: [] }
  }
  return { verdict: 'pass_with_baseline_failures', newFailures: [] }
}
