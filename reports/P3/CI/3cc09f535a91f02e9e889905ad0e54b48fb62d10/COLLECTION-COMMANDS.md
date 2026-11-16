# Executed collection and packet commands

Use the absolute checkout output paths consistently. Substitute your own absolute checkout path when reproducing.

```sh
.venv/bin/python -B scripts/p3_collect_ci.py --commit 3cc09f535a91f02e9e889905ad0e54b48fb62d10 --output /workspace/Knowledge-/reports/P3/CI/3cc09f535a91f02e9e889905ad0e54b48fb62d10
.venv/bin/python -B scripts/make_review_p3.py --native-dir /workspace/Knowledge-/reports/P3/CI/3cc09f535a91f02e9e889905ad0e54b48fb62d10
```

Local verification: .venv/bin/python -B scripts/verify_p3.py. Native CI uses powershell -NoProfile -File scripts/verify-windows.ps1. Raw native source/package/all artifact hashes are checked by the collector, and the review gate independently validates the native ledger. The review ZIP is generated twice and its exact bytes compared; every member hash/path is verified. reports/P3/.gitattributes preserves native raw CRLF bytes through Git staging. Historical failures and superseded PASS data are clearly scoped under history and never qualify the current source. Redundant transport tars and full superseded local build trees remain outside the review/distribution.
