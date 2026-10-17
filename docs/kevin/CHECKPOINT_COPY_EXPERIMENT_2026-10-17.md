# Flash-iOS — checkpoint-copy and allocator-retention experiment (2026-10-17)

## Accepted baseline

The October 17 exact-M2 repair corrected a stale 4 MiB comparison against the new 2 MiB DeltaNet state allocation, plus stale warm-state serialization/transfer sizes. AddressSanitizer reproduced the out-of-bounds read. The final repaired build passed **30/30** raw/zero-block oracle cases across contexts 32/4096/8191/8192/8193 and outcomes accept0/accept1/accept2; production, prefix, tool continuation, persistence and ASan qualifications passed. The retained raw two-bank GPU checkpoint footprint is **191.27 MiB** (120 MiB less than pre-geometry). Existing version-1 warm caches must be recaptured, not silently loaded.

Source report: `docs/kevin/exact-m2-state-integrity-results-2026-10-17.md` (Google Drive). Raw codec remains the default: experimental zero-block had higher peak process memory despite smaller on-bank payload.

## Next experiment: identify avoidable CPU anchor copies

The validated report measured approximately **62.8 MiB of CPU state copies** in the verifier anchor (distinct from its GPU raw banks). This is *not* yet demonstrated redundant. Our goal is to discover whether any snapshot has an identical immutable lifetime/identity and could be safely referenced instead of copied; characterize allocator retention, compression scratch and resident memory high-water.

### Stage 0 — repeatability baseline (already provided)

`zsh tools/checkpoint_copy_probe.zsh 3` creates timestamped `benchmark-logs/checkpoint-copy-probe-*` cases for raw and zero-block short oracles. It runs only six cheap 32-token cases and refuses to interpret failures as performance results. Verify whether the helper preserves `FLASH_TARGET_GPU_ZERO4K`; inspect generated underlying oracle logs separately. This is a smoke/baseline script, not a replacement for detailed copy instrumentation.

### Stage 1 — guarded CPU copy tracer (Work engineer implements)

Add *disabled-by-default* `FLASH_CHECKPOINT_COPY_PROFILE=1` instrumentation to the relevant `ServeStateSnapshot`, target verifier bank/anchor, and warm checkpoint routines. Keep production and oracle decisions byte-identical. Record at minimum:

- unique checkpoint/snapshot ID, capture position, model/quantization/prefix identity or opaque hash;
- copy purpose: anchor, row0 bank, restore, tool/prefix capture, compression scratch;
- per-component bytes for CPU KV, CPU recurrent matrices and convolution histories, hidden state, GPU DeltaNet and GPU convolution buffers (never expose tokens or secrets);
- allocation/reservation bytes, current live bytes, high-water, free/deallocation events, copy count and wall microseconds;
- state owner and reference-lifetime transitions; avoid logging memory addresses/tokens outside debug output;
- explicit synchronization boundary for GPU-backed states.

No checkpoint aliasing or ownership changes in this first instrumentation stage. Use an independent monotonic timer and minimize logging within hot dispatch. Emit one machine-readable structured summary per request alongside human-readable breakdown.

### Stage 2 — experiments

1. Build noninstrumented baseline and separately instrumented binary from the same verified source and feature flags; preserve production `infer` binary.
2. Run raw context-32 accept0/1/2 three times and raw context-4096 accept0 once; capture instrumentation and `/usr/bin/time -l`; only then assess whether a longer case adds information.
3. Repeat raw warm-profile same-prefix restores 3+ times and a profile-switch sequence; verify cache restore IDs, checkpoint identity, output equivalence and no stale references.
4. Run zero-block context-32 accept0 as allocator-retention control, not as production candidate.
5. Compare current, peak, retained, and freed bytes and distinguish process footprint vs maximum RSS. Compare at fixed model/process state and idle windows.
6. Identify exact callsites and life spans for every suspected redundant copy; prepare a proposal with proposed refcounts/immutability proof and rollback behavior.

### Acceptance and stop rules

- Every observed oracle case must retain all four `yes` checks and exit 0.
- No inference slowdown from profiling when feature flag is absent; no persistent caches or formats modified.
- No optimization applied solely because a checkpoint has the same token position; model, quantization, prefix content, recurrent-state history, and lifetime must match.
- A proposed optimization requires measured copy elimination, memory improvement, and the existing 30-case oracle before promotion. If additional tests fail, stop and report first divergence.
- Never commit build outputs, model data, caches, benchmark logs or credentials. No GitHub push unless specifically requested.

## Handoff

Detailed Work-thread execution instructions are appended to `Flash-iOS/chatgpt-communication.md` with heading `2026-10-17 — CHECKPOINT-COPY-PROBE`.
