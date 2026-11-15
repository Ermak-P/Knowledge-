# Functional review after initial P1 publication

Run `fe11fd6fd62e4372b5d6e830889775be`; source `f6fbbd3dc18cfe085c3694bd6ab529f23e5eb7ac7b0c54bb450083bb33069954`. Raw evidence: `runs/fe11fd6fd62e4372b5d6e830889775be/`.

The previously passing 68-test suite did not cover four reproduced failures:
C# literals manufactured declarations/registrations; // inside route literals
was treated as a comment; block-commented evidence remained trusted current;
rename re-observation promoted INFERRED confidence and reset reviewed edges.
The new FunctionalReviewTests reproduce these boundaries and verify the repairs.
Additional cases cover XML comment dependencies, old extractor false positives
with unchanged hashes, and evidence paths through linked ancestors.

Discovery now uses offset-preserving lexical masks, re-extracts source support
before freshness decisions, and preserves reviewed claim metadata on revision.
Extractor version 2 refuses stale version-1 scan checkpoints. This remains a
lexical capability pack, not a C# compiler or runtime proof.

All claims of current verification refer to the new run above; earlier passing
results describe their earlier source identities. No external acceptance is claimed.
