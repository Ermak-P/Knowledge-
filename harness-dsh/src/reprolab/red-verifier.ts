import type { ClassifierKind, ClassifierVerdict } from './types.ts'

export interface RedVerificationFacts {
  testPatchHash: string
  commandHash: string
  /** True when a fix patch is already frozen (control must stay fix-free). */
  fixFrozen: boolean
  classifier: ClassifierVerdict
}

export interface RedVerdict {
  verdict: 'valid_red' | 'insufficient'
  reasons: string[]
  fingerprint: string | null
}

const KIND_REASONS: Record<ClassifierKind, string | null> = {
  test_failure: null,
  test_pass: 'test_not_failed',
  not_discovered: 'test_not_discovered',
  infra_failure: 'infra_failure',
  timed_out: 'timed_out',
  cancelled: 'cancelled',
  spawn_failed: 'spawn_failed',
  crashed: 'crashed',
}

/**
 * RED is valid only when the classifier proved a genuine executed-test
 * failure (kind test_failure with a fingerprint) and control contains no
 * frozen fix. Infrastructure failures, timeouts, crashes and plain nonzero
 * exits can never count as RED (design spec §7.3).
 */
export function verifyRed(facts: RedVerificationFacts): RedVerdict {
  const reasons: string[] = []
  const kindReason = KIND_REASONS[facts.classifier.kind]
  if (kindReason !== null) reasons.push(kindReason)
  if (facts.fixFrozen) reasons.push('fix_present')
  if (reasons.length === 0 && facts.classifier.fingerprint !== null) {
    return { verdict: 'valid_red', reasons: [], fingerprint: facts.classifier.fingerprint }
  }
  return { verdict: 'insufficient', reasons, fingerprint: facts.classifier.fingerprint }
}
