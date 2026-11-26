export type Framework = 'vitest' | 'jest' | 'node:test' | 'pytest' | 'generic'

export type ClassifierKind =
  | 'test_failure'
  | 'test_pass'
  | 'not_discovered'
  | 'infra_failure'
  | 'spawn_failed'
  | 'timed_out'
  | 'cancelled'
  | 'crashed'

export interface ClassifierVerdict {
  kind: ClassifierKind
  /** Discovered/executed test names (or ids), in a redaction-safe form. */
  matchedTests: string[]
  summary: string
  /** Stable identity of the failure; only present for kind test_failure. */
  fingerprint: string | null
}

export interface FrameworkParserInput {
  stdout: string
  stderr: string
  exitCode: number | null
  declared?: { testNames?: string[]; failurePatterns?: string[] }
}

export type FrameworkParseResult = Omit<ClassifierVerdict, 'fingerprint'>

export type FrameworkParser = (input: FrameworkParserInput) => FrameworkParseResult
