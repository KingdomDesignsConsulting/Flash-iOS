# Changelog


## 2026-10-01/02 — N64 production prefill

- Promoted the correctness-validated N-row prefill path to the normal `infer`
  build with N64 enabled by default.
- Accepted expert kernels:
  `grouped_tiered_gate_up_m4_2row` and
  `grouped_tiered_projection_m4_2row`.
- Retained `--no-prefill-nrow` as the scalar runtime fallback.
- Full 64-token chunks use N64; prompt remainders remain scalar; decode is
  unchanged.
- Corrected routed-expert staging to use
  `min(g_cfg.num_experts, PREFILL_NROW_ASSIGNMENTS)`, giving 256 staging slots
  on the current 256-expert model instead of 512.
- Controlled N64 1024-token benchmark median: 23.182 tok/s with exact
  hidden/logit/next-token/state equivalence.
- Warm real HTTP prefill test (211 actual tokens): scalar 13.515 tok/s /
  15.612 s versus N64 24.990 tok/s / 8.443 s.
- Session continuation successfully reused an N64-created session state; an
  equivalent scalar control matched the continuation behavior.
- Added N-row source/kernel files to normal `infer` Makefile dependencies.


This changelog reconstructs the development of the current Flash-iOS `infer.m`. The project working tree was created from the upstream GitHub clone on **September 16, 2026**; source snapshots survive from September 18–23, followed by the current `infer.m` and current `warm_state_cache.inc`. A contemporaneous chat record documents the September 16 clone/build and the initial goal of running the tiered Qwen3.5-35B-A3B model behind the runtime's OpenAI-compatible server.

The snapshot dates below are backup timestamps, not formal release tags or Git commit times. Because no September 16–17 source backup was supplied, this changelog does **not** assign specific code changes to those first two days unless they are independently visible in later source. The September 18 file remains the source-diff baseline.

## Current — after the September 23 snapshot

### Flash profiles and persistent warm state

- Generalized the earlier DSH-specific warm-profile mechanism into named **Flash profiles**.
  - Added `--flash-profile NAME`.
  - Added request-level selection with `"flash_profile":"NAME"` and `X-Flash-Profile: NAME`.
  - Added `--flash-profile-recapture NAME` for explicit replacement of an existing profile source.
  - Profile names are restricted to 1–64 lowercase ASCII letters, digits, `-`, and `_`.
- Replaced the old `--dsh` CLI mode with the generic profile model. DSH behavior is represented by `dsh-*` profile names.
- Made profile sources immutable by default. A request whose rendered prefix does not match an existing profile does not silently overwrite it; explicit recapture is required.
- Keyed profile identity to the exact rendered prefix-token sequence rather than JSON formatting, so semantically irrelevant JSON whitespace/key-order differences do not invalidate a profile.
- Added profile-source cleanup and retention controls:
  - stale temporary-file cleanup;
  - maximum profile count;
  - source-byte budget;
  - protection for selected/current profile sources while pruning.
- Added `--self-test-profiles` coverage for profile naming, capture, mismatch rejection, recapture, request/header selection, and pruning.

### Warm-state persistence

- Added selectable checkpoint storage with `--warm-state-compression raw|zstd`; current default is Zstd level 1.
- Current persistence layer uses a selective **state-compatibility identity** instead of invalidating checkpoints after every unrelated executable rebuild.
  - Hashes model and expert-file identities, manifest/vocabulary/configuration inputs, `shaders.metal`, and state-affecting execution flags.
  - Explicitly does **not** require HTTP, tool UI, logging, or other non-state-producing code changes to invalidate a checkpoint.
  - Documents a correctness contract requiring state-producing inference changes to alter the execution-mode hash or bump `WARM_STATE_EXECUTION_VERSION`.
- Removed the filesystem device ID from the current compatibility identity and added guarded migration of compatible legacy checkpoints that included the device ID.
- Hardened checkpoint loading and saving:
  - validates magic/version/layout, geometry, prefix/tool/token signatures, compatibility identity, payload size, and exact file size;
  - validates raw payload checksums before checkpoint-sized allocation;
  - validates both compressed bytes and decompressed payload for Zstd checkpoints;
  - uses regular-file and `O_NOFOLLOW` checks on loads;
  - writes to same-directory temporary files, `fsync`s, atomically renames, then `fsync`s the directory;
  - cleans stale temporary files and prunes old checkpoints;
  - enforces a 4 GiB warm-state directory budget.
- Added fallback between raw and Zstd checkpoint forms and repair behavior when the preferred compressed sidecar is damaged but a valid alternate form can be loaded.
- Expanded synthetic warm-state tests to cover corruption, truncation, oversized compressed sections, compatibility mismatch, source/profile mismatch, format fallback, and rebuild behavior.

### Tool/API correctness refinements

- Scoped the repeated-failed-tool-call guard to DSH-style profiles by default, with explicit `--tool-retry-guard` / `--no-tool-retry-guard` override.
- Refined DSH `Write` handling so speculative sandbox-escalation fields are suppressed until a preceding tool result actually indicates a sandbox denial.
- Refined literal-path preservation so a source path from a prior `Read` is not incorrectly forced into a later `Write` destination after a `role=tool` boundary.
- Standardized malformed-tool compatibility recovery to mark the resident session invalid and tell the caller to resend full history.
- Preserved `session_id` as the identity of resident conversation state while keeping `flash_profile` as the identity of a reusable static prefix; the two are deliberately separate.

## 2026-09-23 13:39 snapshot

### Persistent named warm profiles

- Added named warm-state modes for DSH and agent-stack workloads.
- Added source files under the project-local `warm-tools-cache` directory and persistent checkpoint integration through `warm_state_cache.inc`.
- Added `--self-test-warm-state`.
- Added executable-relative cache-path resolution so profile/tool-set cache behavior does not depend on the process working directory.
- Added persistence of requested OpenAI tool sets for later warm loading.

> Historical limitation: this snapshot already includes `warm_state_cache.inc`, but no historical copy of that include was available. The exact September 23 on-disk checkpoint implementation therefore cannot be diffed. The current include documents the endpoint architecture, not necessarily every detail of the first implementation.

### Bounded dynamic prefix cache

- Added a byte budget to dynamic tool-prefix snapshots (`--tool-prefix-cache-mb`, default 768 MiB).
- Retained a pinned warm entry outside the dynamic budget while evicting non-pinned entries by LRU within the budget.
- Added expected/captured snapshot-size checks before admitting new entries.

### OpenAI API and tool-loop hardening

- Added completion-usage accounting, including logical prompt-token accounting when resident prefix/session state is reused.
- Added final streaming usage data before `[DONE]`.
- Added SSE keepalive output for long prefill periods.
- Added configurable malformed-tool policy:
  - compatibility recovery mode;
  - strict provider-error mode.
- Added repeated-identical-failed-tool-call detection to stop unproductive tool loops.
- Added literal absolute-path preservation for tool arguments, including a narrow exact-read shortcut and constrained token-wire path handling.
- Added DSH `Write` sanitization for unsupported speculative sandbox-escalation fields.
- Added `--self-test-api` coverage for API, session, recovery, cache-directory, and tool-wire behavior.

## 2026-09-22 00:57 snapshot

### Native Qwen tool calling

- Added OpenAI-style tool ingestion and Qwen3.5-native tool rendering.
- Added rendering of:
  - `# Tools` definitions;
  - native `<tool_call>` function/parameter syntax;
  - historical assistant `tool_calls`;
  - `role:"tool"` results as `<tool_response>`.
- Added native tool-call parsing with schema-aware argument validation.
- Added structured SSE `tool_calls` output and `finish_reason:"tool_calls"`.
- Added strict validation for the supported schema subset instead of silently accepting unsupported constructs.
  - Rejects `oneOf` and general `anyOf`.
  - Rejects schema-valued `additionalProperties`.
  - Supports `tool_choice` `auto`/`none`; forced-function/`required` modes are not implemented.
  - `parallel_tool_calls:false` is not supported.
- Added tool/session continuity checks so a resident continuation is reused only when tool results correspond to the expected pending call IDs and order.

### In-memory prefix-state snapshots

- Introduced `ServeStateSnapshot` to capture the actual prefilled runtime state:
  - full-attention CPU KV cache;
  - linear-attention CPU convolution/recurrent state;
  - GPU DeltaNet and convolution state when the GPU path is active.
- Added a five-slot exact-prefix cache keyed by tool signature, token signature, and token count.
- Added a pinned startup warm prefix with `--warm-tools`.
- Added optional `--sort-tools-alpha` canonicalization to make differently ordered but otherwise identical tool sets share the same rendered tool context.
- Added `--self-test-tools`.

## 2026-09-21 14:55 snapshot

### Thinking-policy redesign

- Changed the default thinking budget to automatic policy (`g_think_budget = -1`).
- Added prompt/generation-length-sensitive automatic thinking behavior rather than applying one fixed budget to every request.
- Changed budget exhaustion from an abrupt synthetic close to an internal early-stop handoff sequence followed by the Qwen think-end token.
- Kept explicit `--think-budget` behavior available for fixed/unlimited control.

### Output and HTTP response handling

- Added incremental UTF-8 byte assembly so multibyte characters such as emoji are not split or emitted as invalid partial sequences at token boundaries.
- Added explicit no-thinking chat rendering behavior.
- Made the server honor the request `stream` flag:
  - SSE streaming path;
  - non-stream JSON Chat Completions path.
- Separated collected `reasoning_content` and normal `content` for non-stream responses.

## 2026-09-20 17:55 snapshot

### Pipeline profiling

- Added low-overhead `--pipeline-profile` instrumentation using a common Mach timing domain.
- Added decode timeline measurements for:
  - CMD1, CMD2, and CMD3 GPU duration;
  - CMD1→CMD2, CMD2→CMD3, and CMD3→next-CMD1 gaps;
  - routing and expert-I/O dependencies;
  - command-buffer submission/queueing;
  - LM-head transitions and token wall time.

### Command-buffer chaining and I/O overlap

- Added CMD1→CMD2 GPU chaining for linear-attention layers (`--cmd12-chain`).
- Added independently controllable full-attention CMD1→CMD2 chaining (`--cmd12-full-chain`).
- Added GPU-side full-attention preparation and synchronization back to CPU KV state where required.
- Added default-on CMD3 expert-I/O event gating (`--cmd3-io-gate`) so CMD3 can be encoded/committed behind an asynchronous expert-read completion signal instead of requiring all I/O to finish before submission.
- Added optional confidence-gated temporal expert prefetch:
  - short routing history;
  - minimum-hit threshold;
  - bounded number of predicted experts;
  - incorrect predictions are discarded rather than inserted into the cache.

### Storage and server robustness

- Hardened expert-storage mode detection for raw, tiered, and LZ4 layouts.
- Added tiered-manifest and LZ4 index/file-size/capacity validation.
- Rejected cache/predict/prefetch combinations that are unsafe for a selected expert-storage format.
- Added deadline-aware socket reads to prevent indefinite request-body stalls.
- Expanded Metal allocation checks.

## 2026-09-19 16:16 snapshot

### Target-model and input hardening

- Reworked the source from a fixed Qwen3.5-397B-style geometry toward runtime-loaded configuration with explicit validation for the supported **Qwen3.5-35B-A3B** target.
- Changed fallback geometry to the 35B-A3B layout:
  - hidden size 2048;
  - 40 layers;
  - 16 attention heads / 2 KV heads;
  - head dimension 256;
  - 256 routed experts, native top-8 routing;
  - 512 MoE/shared intermediate size;
  - 30 linear-attention and 10 full-attention layers.
- Removed the hard-coded developer-local default model path; `--model PATH` became required.
- Reduced the compile-time native context ceiling to 262,144 tokens and introduced runtime context preflight against the configured CPU KV capacity.
- Added validation for:
  - primitive model geometry;
  - target architecture;
  - tensor-manifest bounds;
  - required model tensors;
  - prompt/vocabulary inputs;
  - model/expert file readability and expert stride.
- Added checked forward execution and error propagation instead of allowing failed layer execution to continue silently.
- Added bounded/fallback embedding-batch allocation.
- Hardened Metal buffer allocation failure handling.

### Resident-session correctness

- Made resident-session publication transactional:
  - old identity is invalidated before state mutation;
  - a new session identity is published only after successful prefill;
  - failed/non-reusable requests clear resident state instead of leaving a misleading reusable session ID.

## 2026-09-19 13:28 snapshot

### Cache telemetry

- Expanded expert-cache telemetry with per-layer hits/misses, cold versus eviction misses, reuse distance, and same-layer/cross-layer eviction attribution.
- Added shadow-cache simulations at multiple capacities to estimate whether larger or differently segmented caches would have avoided observed misses.

### CMD1 production replay profiler

- Added `--cmd1-profile` to capture real decode-time projection inputs and replay them after generation.
- Added A/B replay of candidate kernels, including V3/fast and Q8 paths, with correctness and estimated per-token contribution reporting.

## 2026-09-19 12:24 snapshot

### Tiny-matvec kernel experimentation

- Added `--tiny-matvec-fast` for small MLX4 dispatches used by 32×2048 and 1×2048 shapes.
- Added `--tiny-matvec-telemetry` to capture real production inputs at safe synchronization points and replay candidate kernels after generation.
- Added alternating production-input A/B measurements with maximum-absolute and RMS error checks, allowing kernel selection to be based on observed inference inputs rather than an isolated synthetic microbenchmark.

## 2026-09-19 00:58 snapshot

### GPU residency and decode-path performance

- Generalized timing math to runtime model dimensions instead of hard-coded layer counts and top-K values.
- Added a real-model MLX4 matvec benchmark with GPU/wall-clock medians and correctness comparison.
- Added GPU greedy argmax.
- Added `--gpu-resident-moe` to keep MoE handoff/combine state on the GPU where queue ordering makes the dependency safe.
- Added the `--oproj-v3` optimized output-projection path.
- Reduced synchronization of routing information to cases where an optional CPU consumer actually needs it.

### Expert cache policy

- Added selectable malloc-backed expert-cache eviction policies.
- Added O(1) list-LRU bookkeeping and clock/reference-bit behavior in addition to scan-based eviction.

## 2026-09-18 17:10 — oldest supplied snapshot

The oldest available source was already a mature, heavily optimized Flash-iOS/Flash-MoE runtime. Features already present at the start of this reconstruction include:

- Metal-based Qwen3.5 inference with hybrid full attention and gated linear/DeltaNet attention.
- A three-command-buffer-per-layer fused pipeline with deferred CMD3 execution and GPU-side MoE combine/residual/next-layer normalization.
- Memory-mapped non-expert weights and per-layer routed-expert loading with `pread`.
- Multiple expert caching/storage experiments, including malloc/OS-cache behavior and tiered/quantized expert support.
- OpenAI-compatible HTTP serving and resident `session_id` state.
- System-prompt prefill reuse/snapshot infrastructure.
- Timing/profiling switches and streaming generation.

Because no earlier source snapshot was supplied, these features should be treated as the **baseline of the available history**, not as changes introduced on September 18.

## 2026-09-16 — project inception (context, not a source snapshot)

- Cloned the upstream `Anemll/Flash-iOS` repository and built `metal_infer/infer` on the Mac mini M4.
- Selected the Flash-iOS/Flash-MoE CLI as a candidate backend for the tiered Qwen3.5-35B-A3B model rather than continuing to treat it only as another inference benchmark.
- Confirmed that the CLI retained `--serve` and could expose the local model through an OpenAI-compatible HTTP endpoint.
- Established the initial project goal: combine native Apple-Silicon/tiered-MoE inference with an endpoint usable by the local multi-agent stack.

> No September 16–17 `infer.m` backup is available. This section records project origin and intent from contemporaneous notes; it does not claim a precise source diff for those dates.
