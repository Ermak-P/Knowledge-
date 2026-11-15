# Executed collection and review commands

Use absolute output/native directory paths: collection.json retains native_root in that spelling and the review gate checks containment under the repository reports/P3 directory. Relative and absolute spellings must not be mixed.

The successful exact-source native collection and packet generation used:

```sh
.venv/bin/python -B scripts/p3_collect_ci.py --commit 3c28581124a4b045f1339c09fa3fd6bcd06f2983 --output /workspace/Knowledge-/reports/P3/CI/3c28581124a4b045f1339c09fa3fd6bcd06f2983
.venv/bin/python -B scripts/make_review_p3.py --native-dir /workspace/Knowledge-/reports/P3/CI/3c28581124a4b045f1339c09fa3fd6bcd06f2983
```

Substitute the absolute checkout path when reproducing. The initial relative-path packet invocation refused containment; rerunning collection and generation with consistent absolute paths succeeded. No product source or failed native receipt was modified to bypass a gate. Every raw CI artifact and both current wheel hashes were verified.

reports/P3/.gitattributes disables Git text normalization for evidence, preserving native CRLF bytes and the recorded hashes in the delivery commit. The archive itself has fixed member metadata, unique safe relative paths and SHA-256 inventory checks. Transport tar files and superseded full build trees are retained locally outside the distribution/review packet; selected historical failures remain explicitly labelled under history/.
