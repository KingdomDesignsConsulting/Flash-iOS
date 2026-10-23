# 32K opt-in production-integration gate (do not merge)
This work is intentionally restricted to the experimental branch. Production `metal_infer/infer` and default `GPU_KV_SEQ=8192` remain unchanged.

## Source review
- 8K default, 16K fallback, 32K candidate are selected at build time through mutually exclusive flags.
- `integration-kv-candidates` creates separate `infer-candidate-lazy16k` and `infer-candidate-lazy32k` from the same `INFER_CFLAGS` used by the default target; it does not build or overwrite `infer`.
- Both binaries use production expert cache/prefetch and the same 32K-qualified state execution version 2; no qualification-only macros in the integration binaries.
- The serving smoke has an explicit `--integration-candidates` mode to run precisely those binaries, not separate qualification executables.
- Existing correctness and long-serving reports are qualification evidence, not proof of a successful post-integration build/run.

## Native M4 gate (single command)
Run with a sufficiently idle GPU, after ensuring the local worktree is clean and the branch is current:

```sh
cd '/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS'
git fetch origin
git switch experiment/gqa-32k-lazy-kv-20261022
git pull --ff-only
python3 tools/verify_gpu_32k_integration.py --out '/Users/knagel/My Drive/Flash-iOS/Testing/gpu-32k-attention/integration-gate-01'
```

The test must PASS before any merge/default change. If it fails, inspect `report.json`, build and per-arm server logs; fix defects on this branch, then rerun with a fresh output directory.

## Merge gate
- [ ] Native integration binaries built using production flags
- [ ] No changes to production `infer` checksum
- [ ] 16K fallback and 32K candidate both passed real HTTP streaming/session replay and memory checks
- [ ] No orphan server processes/listeners
- [ ] Final report and logs uploaded/visible in Drive
- [ ] Explicit user confirmation to proceed with merge as step 4

**Do not merge the draft PR automatically.**
