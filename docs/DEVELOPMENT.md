# Flash-iOS development baseline

Status recorded 2026-10-05 from the local source tree. The local tree is the
authority for this baseline. [CURRENT_STATUS.md](CURRENT_STATUS.md) is the
authoritative summary of the active production configuration, accepted and
rejected experiments, and pending validation. `Anemll/Flash-iOS` is the upstream
ancestry, not a source to copy over newer work. The long-form runtime design is in
[kevin/ARCHITECTURE.md](kevin/ARCHITECTURE.md), the optimization history is in
[kevin/DEVELOPMENT_HISTORY.md](kevin/DEVELOPMENT_HISTORY.md), and the N-row
prefill evidence is in
[prefill-nrow-architecture-2026-09-28.md](prefill-nrow-architecture-2026-09-28.md).
The historical measurement method is documented in
[benchmark-writeup.md](benchmark-writeup.md).

## Code and deployment

`metal_infer/infer.m` owns model loading, tokenization, Metal/CPU execution,
tool calls, the local OpenAI-compatible HTTP server, resident sessions, and
Flash-profile orchestration. `warm_state_cache.inc` owns persistent prefix
state and compatibility checks. `prefill_nrow_grouped_async.inc` contains the
grouped N-row prefill implementation; `prefill_probe/chunk_kernels.metal`
contains its Metal kernels. The current target is Qwen3.5-35B-A3B with native
K=8 routing on Apple Silicon. The model, expert layers, and tokenizer are
separate local assets and are never versioned here.

The macOS production **build configuration in source** is:

```text
FLASH_PREFILL_NROW_PRODUCTION + FLASH_PREFILL_NROW_ASYNC
N=128; 1024 routed assignments per slab
gate+up: grouped_tiered_gate_up_m4_8row
routed down: grouped_tiered_projection_m4_2row
expert staging slots: 256
```

This is selected by the normal `metal_infer/Makefile` `infer` target. Full
128-token slabs use the grouped path; smaller tails and decode use the
established scalar paths. `--no-prefill-nrow` is the runtime fallback. See the
production gate and performance figures in the N-row architecture note.

The iOS app under `FlashMoE-iOS/` uses a copied snapshot of the runtime under
`EngineSources/` and a Swift/Objective-C bridge. Its deployment target is iOS
26.6. The snapshot was copied on 2026-10-04; synchronize and revalidate it
deliberately when desktop inference changes. A device-target Release build
succeeded with Xcode 27, but model loading and generation on a physical iPhone
have not been verified for this snapshot.

## Build targets

On macOS, install Xcode command-line tools and Zstd headers/library. The
Makefile currently expects Homebrew Zstd under `/opt/homebrew`. Build from
`metal_infer/` with `make infer`, or compile to an isolated output path when
testing a development revision so the serving binary is not replaced.

`make n128bench` and the `n128gateup*` targets write experimental binaries to
`Testing/Temporary Testing Files/Apps/`. `make n128serve8row` and
`make n128serve8bits` create separate serving candidates. Their output path is
not the production `infer` binary. `make clean` deletes target outputs, so
inspect its target list before using it in a live environment.

The iOS project is `FlashMoE-iOS/FlashMoE.xcodeproj`, scheme `FlashMoE`.
The model stays outside the app bundle and is imported into the app's Documents
directory using Files or the existing USB copy script. Do not add its weight
or expert files to the Xcode target.

## Accepted and experimental performance work

N128 prefill with M4-8row gate+up and M4-2row down passed scalar-state,
continuation, serving, and DSH-scale gates and is the accepted macOS source
configuration. Accepted N128 work also includes batched full attention,
batched linear-post processing, and parallel expert staging. The controlled
1024-token N128 result before the M4-8row selection reported 25.232 tok/s;
M4-8row selection reported 25.659 tok/s in
its controlled comparison. A 4099-token serving comparison reported N64
202.424 s versus N128 185.576 s; the larger DSH-scale comparison is recorded
in the N-row architecture note. These are historical measurements on the M4,
not portable promises for iOS.

The newer fixed-Q4/Q2 **bitsplit** M4-8row gate+up is still a candidate. Its
benchmark target defines `FLASH_PREFILL_NROW_GATEUP_M4_8ROW_BITSPLIT`; the
separate `n128serve8bits` target exists for a production-style 4K comparison.
Repeated 1024-token checks show scalar/state agreement: hidden maximum
`1.0490417e-05`, logits maximum `1.3828278e-05`, next token `1752/1752`,
and `state_equal=1`. Repeated bitsplit gate+up phase timings averaged
4270.800 ms against a bracketed ordinary M4-8row baseline midpoint of
4356.440 ms, about 1.97% faster. Bitsplit is accepted for production-style
4K serving validation, but that gate has not yet passed and bitsplit is not
production. The ordinary M4-8row kernel remains the default in `infer.m` and
the Makefile.

Rejected or deferred paths, with measurements and reasons, are in the N-row
architecture and verifier notes. Examples include M8-2row and M4-16row
gate+up packing and the M4-8row cooperative input cache (`xcache`), which
regressed against ordinary M4-8row; the LM-head-only batched
verifier, which left serial attention/MoE cost dominant; and the earlier V5
expert accumulator change, which slowed the full 1K path. Keep the results in
Markdown; raw logs and benchmark executables belong under ignored `Testing/`
or `benchmark-logs/`.

## Correctness and benchmark method

Build candidates to distinct paths. Verify hidden and final logits against a
scalar run, exact next-token selection, byte-identical final state where the
test provides it, and deterministic decode continuation. Record KV, GPU
convolution, and DeltaNet state maxima. Floating-point tolerances depend on
the tested kernel; do not turn one historical maximum into a universal limit.
State equality and continuation are required because matching logits alone
cannot prove future turns are safe.

Run paired trials with the same model, prompt tokens, runtime flags, and cache
conditions. Report median wall time and throughput over repeated valid runs,
plus phase timings and memory use where available. Keep candidate tests away
from the production server and persistent checkpoints. Do not promote a
microbenchmark gain without an end-to-end serving comparison.

## Serving, sessions, and warm state

The local server exposes OpenAI-compatible chat completions. `flash_profile`
identifies a reusable static system/tool prefix; `session_id` identifies an
evolving resident conversation. They must never be used interchangeably.
Profile sources live in `warm-tools-cache/`; persistent prefix checkpoints
live in `warm-state/`. Both directories are ignored by Git.

Checkpoint compatibility covers the actual prefix-token identity, model and
expert inputs, shader source, relevant runtime modes, and an explicit
inference execution version. State-producing math changes must update a
hashed mode/configuration value or bump `WARM_STATE_EXECUTION_VERSION`.
HTTP, UI, and logging-only rebuilds are intentionally not full-binary cache
invalidations. The loader validates format, dimensions, sizes, checksums,
compatibility, and exact file length; saving uses temporary files, `fsync`,
rename, and directory `fsync`. Raw and Zstd storage forms are supported.
See `warm_state_cache.inc` and [kevin/CHANGELOG.md](kevin/CHANGELOG.md).

For a server test, use a separate binary and test port, record start/stop
times, and send one request at a time. Check `/health`, a normal completion,
streaming usage, and any profile/session behavior targeted by the change.
Afterward confirm the test port has no listener and the production binary and
checkpoint hashes are unchanged. Hardware inference tests require Metal
access and should be run only when explicitly in scope.

## Git workflow and exclusions

Develop on `flash-moe-production`, with `upstream` pointing to
`Anemll/Flash-iOS` and `origin` pointing to the writable
`KingdomDesignsConsulting/Flash-iOS` fork. Meaningful development changes are
now committed as focused commits. Inspect diffs, build or test the relevant
target, and make focused commits. Use separate
`experiment:`, `bench:`, `perf:`, `fix:`, and `docs:` commits as appropriate.
Never force-push or silently rewrite published history. Before pulling from
upstream, compare refs and review the merge; the local source contains newer
work and must not be overwritten.

The previous Drive symlinks were preserved under ignored `.drive-links/`
while the repository was materialized. Google Drive remains a separate mirror;
edits to this Git checkout do not automatically update that mirror. Ignored
content includes model weights, GGUF/safetensors, executables, benchmark
binaries, checkpoints, logs, temporary testing data, and the communications
file. Existing tracked paper artifacts remain part of upstream history.

Pending validation: bitsplit 4K serving and any physical-iPhone inference
check. The current Git baseline does not claim either has passed.
