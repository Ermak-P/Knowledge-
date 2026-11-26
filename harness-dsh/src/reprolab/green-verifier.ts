import type { ClassifierKind, ClassifierVerdict } from './types.ts'

export interface GreenVerificationFacts {
  red: { testPatchHash: string; commandHash: string; fingerprint: string | null }
  green: { testPatchHash: string; commandHash: string; classifier: ClassifierVerdict }
}

export interface GreenVerdict {
  verdict: 'valid_green' | 'insufficient'
  reasons: string[]
}

const KIND_REASONS: Record<ClassifierKind, string | null> = {
  test_pass: null,
  test_failure: 'tests_failed',
  not_discovered: 'test_not_discovered',
  infra_failure: 'infra_failure',
  timed_out: 'timed_out',
  cancelled: 'cancelled',
  spawn_failed: 'spawn_failed',
  crashed: 'crashed',
}

/**
 * GREEN requires the exact same test patch hash and command hash as the RED
 * run, and a genuine all-pass result (design spec §7.5). A zero-test run or a
 * hash drift can never be GREEN.
 */
export function verifyGreen(facts: GreenVerificationFacts): GreenVerdict {
  const reasons: string[] = []
  if (facts.green.testPatchHash !== facts.red.testPatchHash || facts.green.commandHash !== facts.red.commandHash) {
    reasons.push('hash_mismatch')
  }
  const kindReason = KIND_REASONS[facts.green.classifier.kind]
  if (kindReason !== null) reasons.push(kindReason)
  if (reasons.length === 0) return { verdict: 'valid_green', reasons: [] }
  return { verdict: 'insufficient', reasons }
}
