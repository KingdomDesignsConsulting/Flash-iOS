# Flash-iOS Development History

> **Current-status note (2026-10-05):** This is a historical/long-form document. For the authoritative active production configuration, Git workflow, accepted N128 optimizations, rejected experiments, and current bitsplit candidate measurements, see [CURRENT_STATUS.md](../CURRENT_STATUS.md). Production is N128 with M4-8row gate+up and M4-2row down. Bitsplit is a correctness-clean ~1.97% gate+up candidate awaiting 4K serving validation and is not yet the production default.


## Scope and evidence

This document reconstructs the development of the current Flash-iOS inference runtime from two kinds of evidence: the surviving source snapshots/current source, and a contemporaneous chat record that documents the project's selection and initial setup on September 16, 2026.

| Order | Historical snapshot timestamp | Source |
|---:|---|---|
| 1 | 2026-09-18 17:10:28 | `infer.m.zip` |
| 2 | 2026-09-19 00:58:18 | `infer 2.m.zip` |
| 3 | 2026-09-19 12:24:46 | `infer 3.m.zip` |
| 4 | 2026-09-19 13:28:04 | `infer 5.m.zip` |
| 5 | 2026-09-19 16:16:22 | `infer 4.m.zip` |
| 6 | 2026-09-20 17:55:04 | `infer 6.m.zip` |
| 7 | 2026-09-21 14:55:48 | `infer 7.m.zip` |
| 8 | 2026-09-22 00:57:46 | `infer 8.m.zip` |
| 9 | 2026-09-23 13:39:24 | `infer 9.m.zip` |
| 10 | current | `infer.m` |
| — | current | `warm_state_cache.inc` |

The snapshot timestamps are metadata carried by the supplied backups; they are not Git commit timestamps or formal release dates. The numeric filenames do not perfectly match chronological order: `infer 5.m.zip` predates `infer 4.m.zip` according to the stored timestamps, so this history follows the timestamps rather than the suffixes.

The Flash-iOS working directory was created from the upstream GitHub clone on **September 16, 2026**, which provides a strong project-start boundary. The earliest surviving source backup is from September 18, however, and is already a large, highly modified runtime. Accordingly, the **project origin can be dated to September 16**, while source-level change attribution begins with the September 18 snapshot. No September 16–17 `infer.m` backup was supplied, so this document does not invent a line-by-line history for those first two days.

The supplied chat record also includes September 14 discussion about assigning smaller models to the user's multi-agent stack. That material is useful prehistory because it shows the performance/memory problem that preceded the Flash-iOS experiment, but it predates the Flash-iOS clone and is not counted as Flash-iOS development.

A second limitation applies to persistent warm-state history. The September 23 `infer.m` already contains `#include "warm_state_cache.inc"`, but only the **current** `warm_state_cache.inc` was available. We can establish when the persistence interface appears in `infer.m`, but we cannot reconstruct every intermediate implementation detail inside that include. Where the current include is discussed as the endpoint of that work, this document says so explicitly.

### Interpretation convention

Most of the rationale below is directly supported by comments, validation logic, diagnostics, CLI descriptions, or the structure of the source changes. Where a motivation is not explicitly encoded in the source and is instead inferred from the before/after design, it is labeled as an inference.

---

## 0. Project origins: September 14–16, 2026

### Prehistory: local-agent performance was already the problem

Two days before the Flash-iOS clone, the work was still centered on model/backend selection for the broader five-part agent stack. The September 14 chat record discusses moving the main/orchestrator and Browser Use roles onto smaller, faster local models while reserving a larger Qwen model for OpenHands. The recurring constraints were already the ones that later shaped the Flash-iOS work: wall-clock latency, tool-call reliability, context size, unified-memory pressure, and avoiding unnecessary contention between specialist agents.

This is relevant context, but it is **not** the start of the Flash-iOS codebase. At that point the discussion was still comparing alternative runtimes and model-role assignments.

### September 16: clone Flash-iOS and test the tiered Qwen3.5 path

The Flash-iOS project itself begins on September 16. The contemporaneous record shows the decision to clone `Anemll/Flash-iOS`, build `metal_infer/infer`, and test the downloaded tiered Qwen3.5-35B-A3B model. The attraction was unusually specific: the macOS CLI already loaded model dimensions from configuration/manifest data, understood the tiered expert layout, and could therefore serve as a plausible native Apple-Silicon runtime for the 35B-A3B model rather than merely another benchmark target.

The initial setup sequence was straightforward:

```bash
git clone https://github.com/Anemll/Flash-iOS.git
cd Flash-iOS
make -C metal_infer clean
make -C metal_infer infer
```

The next discovery immediately changed the project's role. The user asked whether the runtime could serve the agent stack as an endpoint; inspection showed that `infer` retained `--serve`, and the user confirmed the option was present. That established the first concrete project objective:

> run the tiered Qwen3.5-35B-A3B model natively on the M4 and expose it through an OpenAI-compatible local endpoint.

That objective is important when reading the later history. The project did not begin as an attempt to rewrite Flash-iOS wholesale. It began as a practical effort to make an existing Metal/tiered-MoE runtime useful as the high-performance backend for a local agent stack. The subsequent work then expanded in response to measured bottlenecks and integration requirements.

### September 16–17: source-history gap

No source snapshot from the first approximately two days survives in the supplied backup set. The September 18 file is therefore the first point at which implementation changes can be compared directly. Features already present in that snapshot may have come from upstream, may have been modified during September 16–17, or may combine both. Unless a later Git history or earlier backup resolves that boundary, this document treats September 18 as the **source-analysis baseline**, not as the project's creation date.

---

## 1. Starting point: September 18, 2026

The first available snapshot was already well beyond a conventional reference inference implementation. Its central design was a hybrid CPU/Metal pipeline optimized around Apple unified memory and the cost structure of a sparse MoE model.

The source describes a three-command-buffer per-layer organization inside `fused_layer_forward`:

1. **CMD1** performs attention input projections.
2. The CPU performs attention-side work that is not already fused into the GPU path.
3. **CMD2** performs output projection, residual handling, normalization, routing, and shared-expert preparation.
4. The CPU computes router softmax/top-K and loads the selected routed experts.
5. **CMD3** performs the routed-expert forwards, shared expert, GPU-side MoE combination, residual update, and—where possible—the next layer's input normalization.

CMD3 is deferred and the Metal queue is used as a dependency mechanism. Instead of waiting after every layer, the next layer can submit work behind the previous layer's GPU-side combine. This baseline already embodies a major architectural principle that persists in the current version: **avoid CPU round trips and explicit waits when the serial Metal queue can carry the dependency safely**.

The baseline also already has several storage and memory ideas that shape later work:

- non-expert weights are memory-mapped;
- routed experts are read per layer/per token with `pread`;
- multiple expert-cache strategies are available;
- quantized/tiered expert formats are part of the runtime;
- server mode exposes an OpenAI-compatible interface;
- resident session state already exists in some form;
- system-prompt prefill reuse/snapshotting already exists;
- timing and diagnostic modes are first-class parts of development.

This matters for interpreting the subsequent history. The work from September 18 onward is not primarily about getting inference to function. It is increasingly about **measuring the real bottlenecks, reducing avoidable synchronization and I/O, hardening correctness, then turning a fast experimental runtime into an agent-facing service with reusable state**.

---

## 2. September 18 evening → September 19 00:58: keeping more work on the GPU

The first transition is dominated by decode-path performance and measurement.

### Runtime-aware timing and benchmarking

Several pieces of timing logic stop assuming one fixed model geometry. Hard-coded layer/top-K assumptions are replaced by runtime counts. This is an early sign of a broader change that becomes explicit later: the runtime is being moved away from assumptions inherited from a larger fixed Qwen configuration and toward the actual target configuration.

A real-model MLX4 matvec benchmark is introduced. It measures both GPU and wall-clock medians and includes correctness comparison rather than reporting speed alone. GPU greedy argmax is also added.

The important design pattern here is **benchmark the actual primitive under the same Metal/runtime conditions used by inference**. That pattern repeats in the next two snapshots with production-input replay profilers.

### `--gpu-resident-moe`

The new GPU-resident MoE mode keeps the handoff/combine state on the GPU when queue ordering makes that safe. The source explicitly takes advantage of the fact that command buffers submitted to the same queue are serialized. Rather than copying intermediate state back to the CPU merely to submit the next stage, the next stage can consume buffers that the previous queued command will populate.

This is not just a kernel optimization. It changes where ownership of intermediate state lives and reduces synchronization boundaries. The current architecture still depends heavily on this idea.

### Output-projection and router fast paths

An `--oproj-v3` path appears, and routing readback is narrowed so it is synchronized only when a CPU-side consumer actually requires it. Both changes pursue the same target: avoid paying synchronization/readback cost on the normal fast path merely because a diagnostic or alternate path needs the data.

### Malloc expert-cache policy

The malloc-backed expert cache gains selectable eviction behavior, including list-LRU and clock/reference-bit policies in addition to scanning. O(1) list-LRU bookkeeping reduces the cache-management work that can otherwise become noticeable around frequent expert accesses.

**What changed conceptually:** the runtime is beginning to distinguish between expensive work intrinsic to the model and overhead introduced by its own bookkeeping. GPU residency, conditional readback, and O(1) cache policy all attack the latter.

---

## 3. September 19 00:58 → 12:24: measure tiny matvecs on real inference inputs

The next snapshot adds `--tiny-matvec-fast` and `--tiny-matvec-telemetry` for the small MLX4 shapes used repeatedly in the model, including 32×2048 and 1×2048 cases.

The notable part is the telemetry design. Rather than trusting a synthetic benchmark, the runtime captures real decode-time inputs at synchronization points where the data is known to be valid. After generation, candidate kernels are replayed against those captured inputs. The profiler alternates implementations and reports numerical error (including maximum absolute and RMS error) as well as timing.

This reflects a deliberate development method:

> a fast microbenchmark is not sufficient if the production input distribution, queue state, or dispatch context changes the result.

The code therefore creates an evidence loop inside the runtime itself: capture representative production data, replay candidate implementations, compare correctness, and only then decide whether a fast path is worthwhile.

That methodology becomes even more explicit in the following snapshot.

---

## 4. September 19 12:24 → 13:28: find the real cache and CMD1 bottlenecks

This transition is primarily diagnostic rather than architectural.

### Cache telemetry becomes explanatory

Expert-cache telemetry expands from aggregate hit/miss information into information useful for making a design decision:

- per-layer hit and miss counts;
- cold misses versus eviction misses;
- reuse distance;
- same-layer versus cross-layer eviction attribution.

The runtime also simulates several **shadow cache sizes** without actually requiring those capacities for the live run. These shadow simulations estimate which observed misses would have been avoided at larger cache sizes.

The purpose is more useful than merely printing a hit rate. It separates questions such as:

- Is the cache too small?
- Is one layer evicting another layer's useful experts?
- Are misses unavoidable cold accesses?
- Would adding hundreds of entries materially change the result?

This is a good example of instrumentation being designed to answer an optimization question rather than simply produce counters.

### `--cmd1-profile`

A CMD1 production replay profiler is added. Like the tiny-matvec telemetry, it captures actual decode-time projection families and replays alternative implementations after the main generation path. Candidate paths include V3/fast and Q8 variants, with correctness and projected per-token impact.

At this point the development approach is clear: **measure the actual production pipeline first, then optimize the component whose measured contribution justifies the complexity**.

---

## 5. September 19 13:28 → 16:16: hardening and the Qwen3.5-35B-A3B target pivot

This is the first major structural transition in the supplied history.

The file header changes from a fixed, much larger Qwen3.5 geometry to a more general “Qwen3.5 inference engine,” and model geometry begins to come from `config.json` / model metadata. At the same time, the runtime becomes explicitly validated for the Qwen3.5-35B-A3B target.

### From fixed constants to loaded configuration—with a deliberate target lock

The fallback geometry changes to the 35B-A3B model:

- hidden size: 2048;
- layers: 40;
- attention heads: 16;
- KV heads: 2;
- head dimension: 256;
- vocabulary: 248,320;
- routed experts: 256;
- experts per token: 8;
- routed/shared intermediate size: 512;
- full-attention interval: 4;
- 30 linear-attention layers and 10 full-attention layers;
- 32 value heads / 16 key heads for linear attention;
- 128-dimensional linear key/value state;
- convolution kernel size 4;
- RoPE theta 10,000,000 and 0.25 partial rotary fraction.

It is important not to overstate the “runtime-configurable” part. The **current** source still calls `validate_target_architecture()` and rejects configurations that do not match this exact Qwen3.5-35B-A3B geometry. Runtime loading therefore improves validation and removes scattered hard-coded assumptions, but the build remains intentionally target-specific.

### Local-path assumptions are removed

The previous hard-coded developer model path disappears and `--model PATH` becomes required. This is both a portability improvement and a correctness improvement: the runtime no longer silently points at one developer-specific model tree.

### Context preflight

The native ceiling becomes 262,144 tokens, while the practical CPU KV allocation is controlled by the runtime `g_kv_seq_len` (currently 65,536 by default). `context_preflight()` is introduced so prompts fail before the runtime mutates state or runs out of allocated KV capacity.

The distinction matters: the source can describe a model-native or compile-time maximum while still enforcing a lower memory-conscious runtime capacity on the actual machine.

### Validation becomes a subsystem

This snapshot adds a large amount of defensive validation:

- primitive geometry checks;
- exact target-architecture validation;
- manifest bounds and tensor metadata validation;
- required-tensor checks;
- prompt-token and vocabulary validation;
- model/expert file checks;
- expert-stride validation;
- Metal buffer allocation checks;
- bounded embedding-batch allocation with a fallback path;
- checked layer execution and propagation of errors.

The significance is larger than the raw number of checks. Prior performance work assumed the expected model layout. This transition begins to make the runtime **fail closed when the on-disk model, manifest, or allocation does not match those assumptions**.

### Resident session state becomes transactional

The server's resident session identity is also hardened. The code invalidates the old identity before mutating the underlying state and only publishes the new session ID after a successful prefill. If the operation fails or cannot be reused safely, the session identity is cleared.

This enforces an important invariant that survives into the current architecture:

> the session ID must describe the state actually resident in KV/recurrent memory; it must never claim reuse is possible after a failed or partial state transition.

This snapshot therefore marks a shift from “fast experimental inference” toward a runtime that can safely sit behind a client or agent.

---

## 6. September 19 16:16 → September 20 17:55: attack pipeline bubbles and expert-I/O latency

This is the largest performance-oriented transition in the backup series.

### A common timing domain and closed decode timeline

A Mach-based timing helper and `--pipeline-profile` are added. Rather than measuring only aggregate layer time, the profiler decomposes the decode path into the command buffers and the gaps between them:

- CMD1 GPU time;
- CMD1→CMD2 idle/gap;
- CMD2 GPU time;
- CMD2→CMD3 dependency gap;
- CMD3 GPU time;
- CMD3→next-CMD1 gap;
- routing and top-K CPU work;
- expert cache lookup and disk I/O;
- command-buffer encode/commit delay;
- transition to/from the LM head;
- total token wall time.

This matters because a GPU optimization that saves 0.2 ms is irrelevant if the queue is idle for several milliseconds waiting on routed-expert I/O. The new profiler is designed to show that distinction.

### CMD1→CMD2 chaining

`--cmd12-chain` allows linear-attention layers to queue CMD2 behind CMD1 without an unnecessary CPU synchronization boundary. `--cmd12-full-chain` extends the same principle to full-attention layers with GPU-side preparation and only synchronizes the CPU KV mirror when the CPU actually needs it.

This continues the queue-centric design present in the September 18 baseline: use Metal command ordering as the dependency graph and synchronize only where data must genuinely cross back to the CPU.

### CMD3 I/O event gate

`--cmd3-io-gate` is a more consequential overlap optimization. On true expert-cache misses, the runtime can start expert reads asynchronously and encode/commit CMD3 behind a shared-event signal. The GPU command buffer is therefore already queued while disk I/O is in flight. When the read completes, the CPU signals the event and the GPU can proceed.

The goal is not to make storage faster; it is to **hide as much of storage latency as possible behind work that can safely proceed**.

### Temporal expert prefetch

The source adds an expert-prefetch experiment based on recent routing history. It uses a small history window, a confidence/minimum-hit threshold, and a cap on prefetched experts. Importantly, a wrong prediction is discarded rather than promoted into the regular expert cache.

That last detail shows the experiment was designed to limit cache pollution. Prefetch is opportunistic; it does not get to rewrite the cache's evidence about which experts were actually needed.

The current source still presents this mechanism as optional/experimental. It should be documented as a performance tool, not as a semantic requirement of inference.

### Expert-format validation becomes stricter

The same snapshot hardens raw/tiered/LZ4 expert storage:

- tiered manifests are checked against file geometry;
- LZ4 indexes and offsets/sizes are validated;
- incompatible combinations of expert format and cache/predict/prefetch modes are rejected rather than attempted;
- Metal allocation checks are expanded.

### Request-body deadlines

Server socket reads become deadline-aware through `poll`, reducing the chance that a malformed/stalled client leaves the single-process server indefinitely blocked waiting for bytes.

**Development direction:** performance and robustness are no longer separate tracks. The code is increasingly willing to reject an unsafe optimization combination rather than silently run a path whose assumptions are violated.

---

## 7. September 20 17:55 → September 21 14:55: generation semantics, thinking, and UTF-8 correctness

The next transition focuses less on the transformer pipeline and more on what the server emits.

### Automatic thinking policy

The thinking budget becomes policy-driven. `g_think_budget = -1` represents automatic behavior, and the runtime chooses whether/how much thinking to allow based on prompt length and requested generation length. Explicit budget modes remain available.

The exact policy in this snapshot uses different behavior for short prompts, small generation requests, medium requests, and long requests. The important architectural change is that **thinking is no longer a single fixed global budget**.

### Graceful thinking termination

When a budget is exhausted, the runtime no longer simply forces a think-close token with no transition. It injects an internal early-stop handoff sequence and then the Qwen think-end token/newline sequence. That injected control text is not intended as normal user-visible content.

The source is treating the model's reasoning protocol as part of generation state rather than merely clipping output at a token count.

### UTF-8 assembly

A byte-aware token-output path is introduced to prevent multibyte UTF-8 sequences from being emitted piecemeal. This addresses the common failure mode where a token boundary bisects an emoji or other multibyte code point. Invalid residual sequences are handled explicitly rather than accidentally leaking malformed bytes.

### Streaming and non-stream responses

The server begins honoring the incoming `stream` flag and supports both:

- SSE streaming responses; and
- complete non-stream JSON Chat Completions responses.

For non-stream responses, reasoning and normal content are accumulated separately. This lays groundwork for the later OpenAI-compatible tool API, where response framing and finish reasons must be precise.

---

## 8. September 21 14:55 → September 22 00:57: from chat server to native tool-calling runtime

This is the second major architectural transition in the supplied history.

### Qwen-native tool rendering

The runtime gains a tool-aware chat renderer that converts OpenAI-style tool definitions and message history into Qwen3.5's native tool syntax. It renders the tool definitions, native function/parameter call format, historical assistant calls, and tool results.

Historical reasoning is intentionally not reconstructed into the canonical tool conversation. That avoids inventing reasoning content that was not part of the tool-wire state that needs to be replayed.

### Tool schema validation

Rather than pretending to implement arbitrary JSON Schema, the server validates a defined supported subset. Unsupported constructs are rejected explicitly.

The current source still reflects these boundaries:

- `oneOf` and general `anyOf` are rejected;
- schema-valued `additionalProperties` is rejected;
- `tool_choice` supports `auto` and `none`;
- required/forced-function tool choice is not implemented;
- `parallel_tool_calls:false` is not supported.

This approach is important for an agent runtime: a narrow schema implementation that rejects unsupported behavior is safer than accepting a schema and then generating arguments under rules the decoder does not actually enforce.

### Native tool-call parser and constrained output

The runtime parses the model's native tool-call format back into OpenAI-style structured calls and validates arguments against the accepted schema. It also adds constrained-decoding machinery to reduce malformed tool syntax at generation time.

Streaming responses gain structured `tool_calls` deltas and the correct `finish_reason:"tool_calls"` behavior.

### Tool-result/session continuity

A resident continuation is no longer considered reusable merely because the `session_id` matches. The runtime also tracks the tool-context signature and pending tool-call IDs. Tool results must correspond to the expected calls and order before state continuation is accepted.

This is a key correctness change: **resident model state is tied to the exact conversation/tool state that produced it**.

### `ServeStateSnapshot`

Tool calling creates a new performance problem. Large static tool definitions and system prompts can dominate first-use prefill, but the resulting state includes more than a conventional full-attention KV cache because Qwen3.5-35B-A3B mixes full attention and gated linear attention.

`ServeStateSnapshot` is introduced to capture all reusable prefix state:

- per-layer full-attention K/V state;
- linear-attention convolution state;
- linear-attention recurrent/SSM state;
- GPU DeltaNet state and GPU convolution state when the GPU linear-attention path is active.

This snapshot is the bridge between the tool API and the later persistent warm-profile system.

### Exact-prefix in-memory cache

A five-slot prefix cache is added. Entries are matched by:

- tool-context signature;
- rendered-token signature;
- token count.

A startup `--warm-tools` entry can be pinned, and dynamic exact-prefix entries can be captured as traffic arrives. Optional alphabetical tool sorting can canonicalize the tool ordering before rendering so that clients submitting the same tool set in different orders can share one prefix.

At this stage the cache is slot-limited rather than byte-budgeted. That changes in the next snapshot.

---

## 9. September 22 00:57 → September 23 13:39: productionize prefix caching and agent-tool behavior

The September 23 snapshot takes the in-memory tool-prefix system and turns it into something intended to survive real agent traffic and process restarts.

### Dynamic prefix cache gets a memory budget

A five-slot cache alone is not enough when a snapshot can be hundreds of megabytes. The runtime adds a dynamic byte budget, exposed as `--tool-prefix-cache-mb` with a 768 MiB default. The pinned warm entry is excluded from the dynamic budget; non-pinned entries are evicted by LRU when necessary.

Before capturing a new entry, the runtime estimates the expected snapshot size. After capture, it also verifies the actual size fits the budget. This prevents an ostensibly small number of slots from becoming an uncontrolled unified-memory consumer.

### Named DSH and agent-stack warm states

The source adds named warm-profile concepts for DSH and the agent stack. Their source definitions live under the executable/project-relative `warm-tools-cache` directory. The code can build/restore a named static prefix instead of requiring the caller to pay its prefill cost on every process restart.

This snapshot also introduces `warm_state_cache.inc` into `infer.m`.

Because the historical include is not available, we can say with confidence that **persistent warm-state integration exists by this snapshot**, but we cannot establish from the backups whether every current durability/checksum/compatibility feature existed on September 23.

### Cache paths become executable-relative

The tool-set/profile cache directory is resolved from the executable location rather than the current working directory. This is a small change with a large operational benefit: launching `infer` from a different directory no longer silently points it at a different warm cache.

### Requested tool-set persistence

The server records requested OpenAI tool sets for future warm loading. This is create-only/signature-oriented behavior rather than blindly overwriting an existing definition.

### Literal path fidelity

Agent tool calls expose a model behavior that ordinary chat does not: file paths must often be reproduced exactly. The runtime adds narrow path-preservation mechanisms, including an exact read shortcut and token-wire forcing when the desired path is unambiguous.

The implementation is intentionally specialized. It is not a general “copy arbitrary user text into model output” mechanism; it addresses known tool-wire path arguments where token-level drift breaks execution.

### DSH `Write` sanitization

The source adds a DSH-specific guard against speculative sandbox escalation. If the model emits escalation-related fields on a normal `Write` call without a preceding tool result that demonstrates an actual sandbox denial, those fields are removed.

This is a concrete example of separating **model intent** from **executor policy**. The model can request a write, but it cannot manufacture the precondition that would justify elevated handling.

### Malformed-tool recovery

Malformed native tool calls can otherwise strand an agent loop because the server's resident state has advanced but the client has no valid structured call to execute. The server gains explicit compatibility-recovery versus strict-error modes. Recovery responses invalidate the resident session and tell the caller that full history must be resent.

### Repeated failed-call guard

A guard is added for repeated identical failed tool calls. Its purpose is to stop loops in which a stateless or poorly recovering client repeatedly sends the same tool attempt and the model repeatedly produces the same failing call.

### Usage accounting and keepalive behavior

The OpenAI-facing API gains completion usage data and logical prompt-token accounting that includes tokens represented by resident state even when they were not physically re-prefilled during this request. Streaming usage is emitted before `[DONE]`.

Long prefills also gain a valid SSE keepalive mechanism so clients do not interpret a long silent prefill as a dead connection.

By the end of this snapshot, Flash-iOS has moved from “an inference server with tools” toward **a stateful local agent backend with explicit recovery and cache semantics**.

---

## 10. September 23 snapshot → current: generalize profiles and make persistence compatibility deliberate

The current source refines the warm-state system substantially and removes the strongest remaining DSH-specific assumption from its public profile interface.

### `--dsh` becomes `--flash-profile`

The old dedicated DSH profile option is removed. The current interface is generic:

- `--flash-profile NAME` selects a named profile at startup;
- requests can select the profile in JSON or with `X-Flash-Profile`;
- `--flash-profile-recapture NAME` explicitly authorizes replacing that profile source on the next matching capture.

DSH behavior still exists, but is keyed by the `dsh-*` naming convention. This keeps DSH-specific policy where it is needed without making the cache architecture itself DSH-specific.

Profile names are deliberately constrained to lowercase ASCII, digits, dash, and underscore. This avoids ambiguous case/canonicalization behavior in filenames and identities.

### The source definition becomes immutable evidence

A Flash profile stores the system prompt and raw tool definitions, but its effective identity is checked against the **exact rendered token prefix**. The source is only published after the live request is verified. Once a source exists, a mismatching request does not silently replace it.

This is a significant safety property. A profile name such as `main-agent` should mean one stable static prefix, not “whatever happened to be submitted most recently under this label.” Explicit recapture is the mechanism for intentional change.

Because the token signature is computed after rendering/tokenization, irrelevant JSON whitespace or key-order changes do not inherently require a new profile if the rendered prefix remains identical.

### Profile source retention

Current code cleans stale profile-source temporary files and prunes old source definitions by both count and bytes while protecting active/default/recapture sources. The source budget and checkpoint budget are separate concepts: profile JSON is small; serialized inference state can be hundreds of megabytes.

### DSH policies become profile-scoped

The current source narrows DSH-specific behavior rather than applying it to all agents:

- repeated failed-tool-call guard defaults on for `dsh-*` profiles;
- DSH `Write` constrained decoding/sanitization applies in DSH mode;
- ordinary agent-stack/tool users are not forced into those policies unless explicitly configured.

Literal-path handling is also refined so a prior source path stops being forced after a `role=tool` boundary and source/destination path roles are distinguished. This fixes the class of bug where a path read from one file could contaminate a subsequent write destination.

### `session_id` and `flash_profile` are explicitly different identities

The current design separates two kinds of reuse:

- **Flash profile:** a static, reusable prefix (typically system prompt + tool definitions) that may survive process restart through a checkpoint.
- **Session ID:** the identity of the live conversation state currently resident in the process.

A profile can be restored without implying that a prior conversation is resident. Likewise, a session cannot be continued merely because it uses the same profile. This distinction is central to the current server state model.

---

## 11. Current persistent warm-state architecture

Only the current `warm_state_cache.inc` is available, so this section describes the **present endpoint**, not a line-by-line chronology of the include's internal evolution.

### Same state layout in RAM and on disk

The include is deliberately placed after `ServeStateSnapshot` capture/restore code and uses that same state representation. Persistent warm state is therefore not a second independently defined cache format conceptually; it serializes the same prefix state needed for an in-memory restore.

The saved state includes the portions applicable to the configured model/path:

- full-attention K/V contents and lengths;
- CPU linear-attention convolution state;
- CPU recurrent/SSM state;
- GPU DeltaNet and convolution state when GPU linear attention is active.

### Selective compatibility identity

The current code contains an explicit cache correctness contract:

> any inference-math change capable of changing serialized prefix state must alter the execution-mode hash or increment `WARM_STATE_EXECUTION_VERSION`; HTTP/tool/logging/UI-only changes should not cause invalidation.

That policy is a response to an important development constraint: `infer` is rebuilt frequently during active work. Hashing the whole executable would make every unrelated rebuild destroy the value of an expensive prefilled checkpoint.

The current identity therefore combines state-relevant inputs, including:

- model-weight file identity;
- manifest and vocabulary content;
- `shaders.metal` content;
- optional config/tokenizer/tiered-manifest content;
- GGUF overlay/file identities;
- routed-expert layer file identities, including cold tiered files where applicable;
- target/state geometry and KV capacity;
- selected expert-storage/quantization mode;
- native top-K;
- whether GPU DeltaNet state is present;
- GPU-resident MoE;
- output-projection V3;
- tiny-matvec fast path;
- CMD1→CMD2 chain modes;
- GPU/CPU linear-attention execution flags.

A whole-executable hash is present only as a commented conservative alternative, not the current policy.

### Device-independent identity migration

The current “v2” identity intentionally excludes `st_dev`. A legacy compatibility path can validate an older identity that included a device number and, when it matches, migrate the checkpoint to the current identity namespace without recapturing the prefix source.

This prevents a transient filesystem device identifier from invalidating otherwise identical state while still requiring the rest of the model/execution identity to match.

### Format and validation

The header records:

- magic/version/layout version;
- compatibility identity;
- source/token-prefix hash;
- profile hash;
- payload size/hash;
- tool and token signatures;
- token count and position;
- geometry and per-layer KV lengths.

The loader checks these before accepting a snapshot. It also verifies that the calculated payload geometry equals the declared payload size and that the complete file size matches the selected storage format.

For raw checkpoints, the payload is hashed before allocating the checkpoint-sized in-memory snapshot; the payload is hashed again while transferring into the snapshot. This is intentionally defensive against corrupt/truncated state.

For Zstd checkpoints, the compressed section is bounded against `ZSTD_compressBound`, hashed, decompressed to the exact expected size, and then the decompressed payload hash is checked before the state is materialized.

### Atomic publication

The current save path:

1. creates the destination directory if necessary;
2. cleans stale temp files;
3. creates a same-directory temporary file;
4. writes the complete header/payload;
5. `fsync`s the file;
6. closes it;
7. atomically renames it into place;
8. `fsync`s the containing directory.

That structure prevents a normal interrupted save from publishing a partially written checkpoint under the final filename.

### Raw and Zstd namespaces

The current default is Zstd level 1, with raw storage retained as a debugging/alternate format. The loader can fall back to the alternate representation and mark the preferred compressed form for repair.

Compression is explicitly a storage choice, not an execution-compatibility version. A raw and compressed checkpoint of the same state represent the same inference state.

### Retention and safety bounds

The current implementation:

- caps a payload at 2 GiB;
- keeps profile variants under control;
- cleans stale temporary files;
- prunes old state files;
- enforces a 4 GiB warm-state directory budget;
- uses `O_NOFOLLOW` and regular-file checks when loading state.

The synthetic warm-state test suite covers round trips and many failure cases rather than only the happy path.

---

## 12. The architectural progression in one view

Across the available snapshots, the development can be summarized as five overlapping phases.

### Phase A — Measure and reduce decode overhead

The early snapshots add GPU residency, output-projection alternatives, tiny-matvec replay, CMD1 replay, cache telemetry, and shadow-cache simulation. The common thread is replacing intuition with production-path measurement.

### Phase B — Make the target and failure modes explicit

The 35B-A3B pivot introduces loaded configuration, exact target validation, context preflight, manifest/tensor checks, checked execution, and transactional session handling. The runtime becomes less tolerant of implicit assumptions.

### Phase C — Close pipeline bubbles

Pipeline profiling, command-buffer chaining, expert-I/O gating, and temporal prefetch try to overlap work rather than merely accelerate individual kernels. Apple unified memory and serial Metal queues are used as architectural tools, not just implementation details.

### Phase D — Become an agent backend

Thinking policy, UTF-8-safe output, non-stream responses, native Qwen tool rendering/parsing, schema validation, pending-call/session continuity, and tool-specific recovery move the project from a prompt server toward an agent-serving runtime.

### Phase E — Reuse expensive prefixes safely

`ServeStateSnapshot` first makes exact prefix state reusable in memory. Byte-bounded prefix caching makes that manageable. Named warm states make it persistent. Flash profiles then generalize the feature, and the current compatibility identity makes persistence practical during active development without accepting stale inference state.

The result is not simply “an optimized `infer.m`.” The current code is a combined:

- model-specific inference engine;
- Metal pipeline scheduler;
- expert-storage/cache manager;
- OpenAI-compatible local server;
- native Qwen tool protocol adapter;
- single-resident-session state machine;
- in-memory static-prefix cache;
- persistent named-prefix checkpoint system.

---

## 13. Changes that were experiments versus durable architecture

The snapshot series contains both long-lived architecture and instrumentation/experiments. Keeping that distinction helps future maintainers avoid treating every switch as equally fundamental.

### Durable architectural elements visible in the current source

- Qwen3.5-35B-A3B target validation.
- Hybrid full-attention + gated linear-attention state handling.
- Three-command-buffer fused layer structure and deferred/GPU-side combine principles.
- Expert storage abstraction and strict validation.
- OpenAI-compatible chat-completions server.
- Native Qwen tool rendering/parsing and schema validation.
- Resident `session_id` continuity checks.
- `ServeStateSnapshot`.
- Bounded in-memory prefix cache.
- Flash profiles and persistent warm state.
- Selective state-compatibility identity.

### Optional/experimental or profiling-oriented mechanisms

- matvec microbenchmark modes;
- tiny-matvec production replay telemetry;
- CMD1 replay profiler;
- detailed pipeline profiler;
- cache shadow simulations;
- temporal expert prefetch;
- alternate cache eviction policies and diagnostic telemetry;
- explicit fast-path toggles retained for A/B testing.

These mechanisms are valuable, but many exist to answer development questions or permit controlled fallback. They should not be confused with the minimum semantic requirements for correct inference.

---

## 14. Historical gaps and cautions for a future public write-up

Before publishing this reconstruction as a statement about the upstream project, several boundaries should remain explicit:

1. **The project starts September 16, but no September 16–17 source snapshot was supplied.** The clone date and initial goals are documented by the contemporaneous chat record and maintainer-provided folder creation date; the oldest source backup is September 18 and already contains substantial work, so individual code changes from the first two days cannot yet be dated.
2. **No historical `warm_state_cache.inc` was supplied.** The first integration is visible on September 23, but the current include cannot prove the exact feature set of the original include.
3. **Snapshot timestamps are backup metadata, not Git history.** They are sufficient to order these files, but they should not be represented as authored commit times unless a Git history later confirms them.
4. **Rationale should remain tied to source evidence.** Where future conversation notes or benchmark logs are used to enrich this document, they should be distinguished from conclusions recoverable from the source diffs alone.
5. **Current source is target-specific.** Although geometry is loaded at runtime, the current validation intentionally rejects models that do not match Qwen3.5-35B-A3B.

A later GitHub cleanup can convert this source reconstruction into commit-oriented release notes once the repository relationship to upstream is known.

---

## 15. Present development philosophy reflected in the code

The source history repeatedly converges on a small set of principles:

- **Measure production behavior, not only synthetic kernels.** Production-input replay and closed-pipeline profiling were repeatedly added before larger optimization decisions.
- **Use queue ordering to eliminate synchronization.** GPU residency, deferred CMD3, CMD1→CMD2 chaining, and event-gated I/O all rely on explicit dependency reasoning.
- **Reject unsafe combinations.** The runtime increasingly validates model geometry, storage formats, schemas, context sizes, and cache compatibility rather than trying to continue after an assumption fails.
- **Treat reusable inference state as a compatibility-sensitive artifact.** Prefix state is keyed to the rendered token stream and state-producing execution identity, not merely a human profile name.
- **Separate static-prefix reuse from live conversation reuse.** Flash profiles and `session_id` serve different purposes.
- **Keep agent-specific policy scoped.** DSH-specific tool guards remain available without turning them into global behavior for every client.
- **Avoid invalidating expensive state for irrelevant rebuilds.** The current selective compatibility contract is explicitly designed for active inference-engine development.

Those principles provide the clearest through-line from the oldest supplied snapshot to the current implementation.
