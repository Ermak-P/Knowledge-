# Functional review after initial P1 publication

Run `776dcec359fe4b60abe9556eeb06722e`; source `7d604fc63ec0e5b28f9b55a6ed2d475bc9514d614d84a9af24760c9bf5c17e4b`. Raw evidence: `runs/776dcec359fe4b60abe9556eeb06722e/`.

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
