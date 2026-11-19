# Development history, excluded from current acceptance

The raw local run `8d2a4189d93a4910944b704cae4bec08` is retained for audit, not used as the source-commit-bound qualification in the review packet. It began with the rc4 installer present in the working tree before that installer change was committed separately. Its ledger records HEAD `f495dc5`, while its inventoried input bytes match the subsequent committed implementation `72c46b8`. The original ledger is preserved unchanged. Do not interpret its recorded HEAD as a claim that those working-tree bytes were committed at that revision.

It passed 224 discovered tests (214 PASS, 10 native-Windows-only SKIP) and the full portable route. The authoritative submitted qualification is the exact committed Linux/native CI evidence linked from `../REVIEW-INDEX.md`. This development folder is outside the selected run and is not included in `P4-review.zip`.
