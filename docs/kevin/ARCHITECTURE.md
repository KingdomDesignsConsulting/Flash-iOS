# Flash-iOS Runtime Architecture

## Overview

The current Flash-iOS `infer` runtime is a model-specific Qwen3.5 inference engine and local agent-serving backend for Apple Silicon. It combines Metal compute, CPU-side orchestration and expert I/O, OpenAI-compatible HTTP serving, native Qwen tool calling, resident conversation state, reusable static-prefix snapshots, and persistent named warm profiles.

The implementation is concentrated in:

- `metal_infer/infer.m` — inference, model validation, Metal orchestration, expert loading/cache behavior, tokenization/generation, HTTP/API/tool handling, resident sessions, in-memory prefix caching, and Flash-profile orchestration.
- `metal_infer/warm_state_cache.inc` — persistent serialization, compatibility identity, integrity validation, atomic checkpoint publication, compression selection, retention, and warm-state self-tests.

The current design is **not a generic arbitrary-model runtime**. Model geometry is loaded from configuration/manifest data, but `validate_target_architecture()` intentionally requires the Qwen3.5-35B-A3B geometry supported by this build.

### Project provenance and design target

This working codebase began on **September 16, 2026** as a clone of `Anemll/Flash-iOS`. The initial practical goal was narrower than the architecture that exists today: run the tiered Qwen3.5-35B-A3B model efficiently on the Mac mini M4 and retain the CLI's `--serve` path so the model could act as an OpenAI-compatible backend for the user's local agent stack.

That origin explains several present-day design choices. The runtime remains deliberately model-specific, focuses heavily on sparse-expert I/O and Apple-Silicon synchronization costs, and treats HTTP/session/tool/prefix-state behavior as part of the inference system rather than as a separate generic serving layer. The current architecture is the result of extending that original backend into a persistent agent-serving runtime.

---

## 1. High-level structure

```text
OpenAI-compatible client / local agent
                │
                ▼
      HTTP request + optional
      session_id / flash_profile
                │
                ▼
        Request/tool validation
                │
                ▼
      Qwen-native prompt renderer
                │
       ┌────────┴─────────┐
       │                  │
       ▼                  ▼
Flash-profile /       Resident session
prefix lookup         continuation check
       │                  │
       └────────┬─────────┘
                ▼
       Prefill missing tokens
                │
                ▼
        Qwen3.5-35B-A3B
        Metal/CPU pipeline
                │
                ▼
          Token generation
                │
       ┌────────┴─────────┐
       │                  │
       ▼                  ▼
normal text /        native Qwen
reasoning            tool-call parser
       │                  │
       └────────┬─────────┘
                ▼
     OpenAI-compatible response
                │
                ▼
      updated resident state
      + optional prefix capture
      + optional disk checkpoint
```

There are two distinct kinds of state reuse:

1. **Resident session state** — live conversation state already present in the running process and identified by `session_id`.
2. **Flash-profile prefix state** — a reusable static prefix, usually system prompt plus tool definitions, identified by `flash_profile` and optionally persisted across process restarts.

They are deliberately separate identities.

---

## 2. Supported model architecture

### Runtime configuration

`ModelConfig` is populated from model configuration/manifest data and contains the dimensions needed by both CPU and Metal paths. Compile-time `MAX_*` values exist for static array bounds; the active dimensions come from `g_cfg`.

The current build validates the following Qwen3.5-35B-A3B geometry:

| Property | Current target |
|---|---:|
| Hidden dimension | 2048 |
| Layers | 40 |
| Attention heads | 16 |
| KV heads | 2 |
| Head dimension | 256 |
| Vocabulary | 248,320 |
| Routed experts | 256 |
| Native experts/token | 8 |
| Routed MoE intermediate | 512 |
| Shared-expert intermediate | 512 |
| Full-attention interval | 4 |
| Full-attention layers | 10 |
| Linear-attention layers | 30 |
| Linear value heads | 32 |
| Linear key heads | 16 |
| Linear key/value dimension | 128 |
| Linear conv kernel | 4 |
| Group size | 64 |
| RoPE theta | 10,000,000 |
| Partial rotary fraction | 0.25 |

The fallback values exist to keep partial configuration parsing deterministic, but a real supported configuration must be loaded; the target validator rejects a mismatching model.

### Context capacity

The source distinguishes several limits:

- `MAX_SEQ_LEN = 262144` — native/compile-time context ceiling used by the runtime.
- `g_kv_seq_len = 65536` by default — practical CPU KV allocation limit.
- `GPU_KV_SEQ = 8192` — GPU mirror size used for the GPU full-attention path.

`context_preflight()` checks the required position against the actual runtime KV capacity before state is mutated.

---

## 3. Weight and expert storage

### Non-expert weights

The main non-expert weight store is memory-mapped at startup. The runtime also supports model components supplied through GGUF-backed overlays/paths where configured.

The architecture relies heavily on Apple unified memory: CPU-visible allocations can often be wrapped by Metal rather than copied into a separate discrete-GPU memory domain.

### Routed experts

Routed experts are stored separately by layer and loaded on demand. The current source contains support for several expert representations, including:

- raw packed 4-bit experts;
- 2-bit experts;
- hybrid Q3/GGUF expert paths;
- tiered hot/cold 4-bit/2-bit experts;
- LZ4-compressed expert storage.

The runtime resolves the active storage mode before cache setup and validates its metadata/file geometry. Unsafe combinations are rejected. For example, LZ4 expert storage is not silently combined with cache/prediction/prefetch modes whose assumptions do not hold.

### Expert caching

The current runtime can use a malloc-backed expert cache, with zero-copy Metal wrappers around its preallocated buffers. The code supports multiple eviction policies, including scan, list-LRU, and clock behavior.

The default source configuration favors the malloc-backed cache and disables the older Metal LRU cache when the malloc cache is active.

Cache telemetry can report more than a simple hit rate: development instrumentation includes layer attribution, eviction behavior, reuse information, and shadow-cache simulations.

### Expert prefetch

An optional temporal prefetch mechanism uses recent routing history to predict a small number of likely experts. It is confidence-gated and deliberately avoids promoting incorrect predictions into the normal cache. This should be treated as an optimization experiment rather than an inference-semantic requirement.

---

## 4. Per-layer inference pipeline

The central optimized path is `fused_layer_forward`.

### Three-command-buffer structure

The source documents the normal layer as three Metal command buffers with CPU work between them:

```text
Input
  │
  ▼
CMD1
  attention/linear-attention input projections
  │
  ▼
attention-side computation/state update
  │
  ▼
CMD2
  output projection
  residual update
  normalization
  router
  shared-expert gate/up preparation
  │
  ▼
CPU router softmax + top-K
expert cache lookup / expert I/O
  │
  ▼
CMD3
  routed expert forwards
  shared expert
  MoE combine
  residual
  next-layer normalization where possible
  │
  ▼
Next layer
```

The current native model routes to up to `MAX_K=8`, matching Qwen3.5-35B-A3B's native top-8 configuration by default.

### Deferred CMD3 and GPU-side combine

CMD3 can be committed without an immediate wait. For non-last layers, it also performs the MoE combination, residual update, and next layer's input normalization into the buffer consumed by the next CMD1.

Because Metal command buffers on the queue are serialized, the next CMD1 can be submitted behind the previous CMD3 without a CPU wait solely to establish ordering.

This removes a class of per-layer CPU round trips and is one of the core performance principles of the runtime.

### CMD1→CMD2 chaining

Two controls allow the CPU to remove additional synchronization boundaries:

- `--cmd12-chain` for the linear-attention path;
- `--cmd12-full-chain` for full-attention layers.

Full-attention chaining includes GPU-side preparation and synchronization back to CPU KV state only when the CPU needs an authoritative copy.

### CMD3 expert-I/O event gate

With `--cmd3-io-gate`, true cache-miss expert reads can proceed asynchronously while CMD3 is encoded and committed. CMD3 waits on a shared-event gate; the CPU signals the event after the required expert data is ready.

The purpose is to overlap disk latency with command submission/other work rather than leave the GPU queue empty until all expert I/O has completed.

---

## 5. Hybrid attention state

Qwen3.5-35B-A3B mixes conventional full attention with gated linear/DeltaNet attention. That makes reusable prefix state more complex than a standard KV-only transformer.

### Full-attention state

Full-attention layers maintain CPU KV caches. The GPU path also uses a bounded GPU-side KV mirror for active computation.

### Linear-attention state

Linear-attention layers maintain convolution and recurrent/SSM state. When GPU linear attention is active, the Metal context also owns per-linear-layer DeltaNet and convolution buffers.

### Why this matters for snapshots

A reusable prefix must capture whichever state actually determines the next token. Saving only full-attention KV would produce an invalid continuation because the linear-attention recurrence would be missing.

`ServeStateSnapshot` therefore stores:

```text
per full-attention layer:
    K snapshot
    V snapshot
    KV length

per CPU linear-attention layer:
    convolution state
    recurrent/SSM state

when GPU linear attention is active:
    GPU DeltaNet state
    GPU convolution state
```

The same state layout is used by the in-memory prefix cache and persistent warm-state system.

---

## 6. Generation and thinking behavior

The generation layer supports Qwen reasoning output and normal assistant content.

### Thinking budget

The default thinking policy is automatic rather than a single global fixed budget. Explicit `--think-budget` control remains available.

When the runtime terminates a thinking budget, it uses a controlled internal handoff/think-end sequence rather than simply truncating arbitrary reasoning bytes.

### UTF-8 output assembly

Decoded token bytes are assembled into complete UTF-8 sequences before emission. This prevents a multibyte code point from being broken across streaming writes merely because the tokenizer split it across token boundaries.

### Streaming versus non-streaming

`POST /v1/chat/completions` supports both:

- streaming SSE responses; and
- non-stream JSON responses.

Reasoning content and normal assistant content are tracked separately where required by the response format.

---

## 7. HTTP server

The built-in server binds to loopback (`127.0.0.1`) and exposes:

- `POST /v1/chat/completions`
- `GET /v1/models`
- `GET /health`

CORS response headers allow `Content-Type`, `Authorization`, and `X-Flash-Profile`.

Request-body reads are deadline-aware rather than allowing an incomplete client body to block indefinitely.

The server is stateful: the model's KV/recurrent state is reused between compatible requests instead of rebuilding every turn.

---

## 8. Native Qwen tool protocol

### Input side

The server accepts OpenAI-style `tools` and compatible message history, validates the supported schema subset, and renders the tool context into Qwen3.5's native format.

The renderer handles:

- function tool definitions;
- assistant historical `tool_calls`;
- tool results;
- system/user/assistant message content;
- Qwen native tool-call markers and parameter syntax.

### Supported schema boundary

The runtime deliberately rejects schema behavior it cannot faithfully constrain. Current limitations visible in the source include:

- `oneOf` rejected;
- general `anyOf` rejected;
- schema-valued `additionalProperties` rejected;
- `tool_choice` limited to `auto` and `none`;
- required/forced-function modes not implemented;
- `parallel_tool_calls:false` not supported.

This is a correctness boundary, not merely an API omission: unsupported schema features are rejected rather than silently treated as if they were enforced.

### Output side

Native Qwen tool-call text is parsed into structured OpenAI-style calls. Arguments are validated against the accepted schema. Streaming responses emit structured tool-call deltas and finish with `finish_reason:"tool_calls"` when appropriate.

### Constrained tool-wire generation

The current runtime contains tool-wire constrained decoding and additional fidelity logic for exact arguments such as file paths. DSH-style profiles also have a narrower `Write` policy that suppresses speculative sandbox-escalation fields until a tool result actually establishes the relevant failure condition.

---

## 9. Resident session state

`session_id` identifies a live conversation continuation.

The resident model state is the real source of truth; the string ID is only valid if it describes that state. The server therefore treats state transitions transactionally:

- incompatible/new requests invalidate the previous reusable identity before mutation;
- a continuation identity is published only after successful prefill/update;
- failures clear the resident identity;
- tool-result continuation checks include pending tool-call IDs/order and tool-context identity.

This prevents a client from reusing a `session_id` after the server's internal state has diverged from the conversation history implied by that ID.

Only one active resident conversation state is represented by the main model buffers at a time. Flash profiles do not change that; they accelerate reconstruction of the static beginning of a conversation.

---

## 10. In-memory static-prefix cache

### `ServeStateSnapshot`

The in-memory prefix cache stores `ServeStateSnapshot` objects along with:

- tool signature;
- rendered token signature;
- token count;
- LRU timestamp;
- pinned flag.

A cache hit requires all relevant signatures/counts to match exactly.

### Capacity

Current constants define:

- 5 prefix-cache slots;
- maximum capturable prefix: 4096 tokens;
- default dynamic memory budget: 768 MiB.

The pinned warm slot is treated separately from the dynamic budget. Dynamic entries are evicted by LRU as required to fit the next expected snapshot.

The 4096-token capture ceiling is an intentional practical constraint of the current implementation; a larger static prompt simply is not captured by this prefix cache.

---

## 11. Flash profiles

Flash profiles attach a stable human-selected name to one reusable static prefix.

### Selection

A profile can be selected by:

- startup option `--flash-profile NAME`;
- request JSON field `flash_profile`;
- HTTP header `X-Flash-Profile: NAME`.

A request-level selector takes precedence over a default startup profile where applicable.

Profile names are restricted to lowercase ASCII letters, digits, dash, and underscore, up to 64 characters.

### Source files

When `infer` is located in the expected `metal_infer` directory, the cache root is resolved relative to the executable's project directory:

```text
<project>/warm-tools-cache/
```

A generic Flash-profile source is named:

```text
warm-tools-cache/flash-<name>-warm.json
```

The source records the system prompt and raw tool definitions needed to reconstruct the prefix.

### Token-level identity

The profile source is not trusted merely because its JSON file exists. The source is rendered/tokenized and matched by its exact token signature and count. The persistent state also carries the tool/token signatures.

This means a profile is ultimately an identity for a **rendered model prefix**, not merely a JSON blob.

### Capture and recapture

A source is published only after the live request's effective system/tool prefix has been verified. Existing source files are immutable under normal capture.

Intentional replacement uses:

```text
--flash-profile-recapture NAME
```

This prevents an accidental request from silently changing the meaning of a long-lived profile name.

### Retention

Current source definitions are bounded by:

- maximum 128 Flash-profile source files;
- 64 MiB profile-source budget;
- oldest-first pruning while protecting selected sources;
- stale temporary-file cleanup.

These small JSON source files have a separate retention policy from the much larger serialized model-state checkpoints.

---

## 12. Persistent warm-state checkpoints

`warm_state_cache.inc` serializes a fully prefilled `ServeStateSnapshot` so a named profile can be restored after `infer` restarts.

### State location

The logical raw checkpoint path generated for a Flash profile is under the sibling project directory:

```text
<project>/warm-state/flash-<profile>-<token-signature>.state
```

The current compatibility namespace prepends `id2-` to the checkpoint basename, and the Zstd storage namespace prepends `zstd-` to that identity filename. These prefixes are implementation details of the current storage layer; callers use the logical profile path and the warm-state layer resolves the selected representation.

### Header identity

A checkpoint header contains enough information to reject stale state before restoration:

- format and layout versions;
- compatibility identity;
- exact prefix/source hash;
- profile hash;
- payload size/hash;
- tool signature;
- token signature and token count;
- position;
- active geometry;
- per-layer KV lengths.

### Raw storage

For raw checkpoints, the state payload is written directly after the header. The loader verifies the payload checksum before allocating the full restored snapshot and verifies it again during the actual transfer.

### Zstd storage

The current default is Zstd level 1. The compressed format stores both:

- compressed/stored byte count and checksum; and
- uncompressed payload byte count and checksum.

The loader bounds compressed size against the expected Zstd limit, verifies the stored bytes, decompresses to the exact expected payload length, and then verifies the decompressed state hash.

Compression changes storage representation only; it is not considered a different inference execution identity.

### Atomic save

Checkpoint publication follows:

```text
serialize to same-directory temp file
        │
        ▼
      fsync(file)
        │
        ▼
      close(file)
        │
        ▼
   atomic rename
        │
        ▼
    fsync(directory)
```

The final filename therefore should not refer to a half-written normal save.

### Retention

The current warm-state layer:

- removes stale temp files;
- prunes obsolete profile variants;
- prunes oldest checkpoint files to a 4 GiB directory budget;
- caps a single serialized payload at 2 GiB.

---

## 13. State-compatibility identity

Persistent model state is only valid if the code/configuration that **produces that state** is compatible with the code/configuration restoring it.

The current implementation intentionally does not hash the entire `infer` executable. Doing so would invalidate a costly profile checkpoint after an unrelated rebuild, such as an HTTP logging change.

Instead, the compatibility identity incorporates state-relevant inputs.

### Model/storage inputs

The identity includes, as applicable:

- primary model-weight file identity;
- model manifest content;
- vocabulary content;
- `config.json`;
- tokenizer data;
- tiered manifest;
- `shaders.metal` content;
- configured GGUF backing-file identities;
- each routed-expert layer file and cold tiered file.

### Execution-mode inputs

`warm_execution_mode_hash()` includes state-relevant runtime geometry/modes such as:

- number of layers, KV heads, head dimensions, and linear-attention dimensions;
- runtime KV capacity;
- tiered/2-bit/Q3/LZ4 expert mode;
- routed top-K;
- availability/use of GPU DeltaNet state;
- GPU-resident MoE;
- output-projection V3;
- tiny-matvec fast mode;
- CMD1→CMD2 chain modes;
- GPU versus bypassed linear-attention path.

### Correctness contract

The include documents the developer rule directly:

> If an inference-math change can alter serialized prefix state, update a value represented by the execution-mode hash or increment `WARM_STATE_EXECUTION_VERSION`.

Conversely, HTTP, tool UI, logging, and other code that cannot alter the serialized inference state should not invalidate the checkpoint merely because `infer` was rebuilt.

### Legacy device-ID migration

Current identity generation excludes the filesystem device ID. A guarded legacy path can validate an older checkpoint identity that included `st_dev`, then migrate it into the current namespace without recapturing the profile source.

---

## 14. Tool failure and recovery policy

Tool output is model-generated data crossing into an executor boundary, so the server has several policy layers.

### Malformed model tool calls

The current default can return a compatibility recovery response instead of leaving the client with unusable structured output. Such recovery invalidates the resident session and indicates that the client should resend full history.

Strict provider-error behavior remains selectable.

### Repeated failed calls

A retry guard can stop a repeated identical failed tool call. Current defaults scope this behavior primarily to `dsh-*` profiles; it can be explicitly enabled or disabled.

### Literal path preservation

The runtime contains targeted handling to preserve exact file paths through tool generation. Current code distinguishes source and destination path contexts and stops carrying old path forcing across a tool-result boundary where it would become unsafe.

These are agent-facing policy layers. They are separate from the core transformer state and therefore should generally not participate in warm-state compatibility unless they change the rendered prefix itself.

---

## 15. Usage accounting

The server reports prompt/completion usage in OpenAI-compatible responses.

When resident state avoids physically replaying some prompt tokens, prompt usage is still treated logically: tokens represented by the existing conversation/prefix remain part of the request's logical prompt even though the model did not recompute all of them during that HTTP call.

Streaming mode can emit final usage information before `[DONE]`.

---

## 16. Diagnostics and self-tests

The source retains extensive instrumentation because the project is still actively optimized.

Notable diagnostic modes include:

- `--timing` — phase-level inference timing;
- `--pipeline-profile` — closed decode pipeline timeline and dependency gaps;
- `--cmd1-profile` — production-input CMD1 replay;
- tiny-matvec telemetry/benchmarking;
- cache telemetry and shadow cache analysis;
- expert-prefetch diagnostics.

Notable self-tests include:

- tool API/tool-wire tests;
- API/session/recovery tests;
- Flash-profile tests;
- synthetic warm-state persistence/corruption tests.

The warm-state self-test exercises the disk format without needing a live model/Metal device and includes negative tests such as corruption, truncation, incompatible identity, invalid geometry, and compressed-format damage.

---

## 17. Important invariants for future development

### Inference-state changes must invalidate persistence

Any change to attention math, recurrent-state interpretation, state-producing Metal kernels, quantization behavior that affects results, snapshot layout, or relevant execution mode must change the warm-state execution identity/version.

### Non-state server changes should not invalidate persistence

HTTP formatting, logs, diagnostics, unrelated UI/tool presentation, and other non-state-producing changes should not require expensive recapture solely because the executable was rebuilt.

### Profile source must not drift silently

A named profile has stable meaning. Prefix mismatch should be rejected/rebuilt under explicit operator control, not silently overwrite the source.

### `session_id` is not `flash_profile`

A profile represents reusable static prefix state; a session represents a live conversation continuation. They must remain independent.

### Prefix cache hits require exact identity

Tool signature, rendered-token signature, and token count must match the state being restored. Human-readable profile naming is not sufficient proof of compatibility.

### Capture limits are real resource limits

The in-memory/persistent prefix path currently caps profile capture at 4096 tokens. Larger static prefixes are outside this cache design unless the implementation is intentionally changed.

### Failed state transitions must not remain reusable

If prefill, restore, tool parsing, or a state update fails in a way that makes resident state ambiguous, invalidate the session rather than preserving a stale continuation identity.

---

## 18. Architectural boundaries

The current runtime combines several responsibilities in one executable, but they remain conceptually separable:

```text
┌──────────────────────────────────────────────────────────────┐
│                    OpenAI-compatible API                     │
│ request parsing • SSE/JSON • usage • error/recovery policy  │
├──────────────────────────────────────────────────────────────┤
│                     Tool protocol layer                      │
│ schema validation • Qwen rendering • parser • constraints   │
├──────────────────────────────────────────────────────────────┤
│                    State reuse layer                         │
│ session_id • prefix cache • Flash profiles • persistence    │
├──────────────────────────────────────────────────────────────┤
│                   Generation/runtime                         │
│ tokenizer • thinking policy • UTF-8 • sampling/argmax       │
├──────────────────────────────────────────────────────────────┤
│                Transformer execution pipeline                │
│ CMD1/CMD2/CMD3 • attention • MoE routing • shared expert    │
├──────────────────────────────────────────────────────────────┤
│               Expert storage/cache/I/O layer                 │
│ raw/2-bit/Q3/tiered/LZ4 • cache • async reads • prefetch    │
├──────────────────────────────────────────────────────────────┤
│                      Apple Metal                             │
│ unified buffers • kernels • serial queue • shared events    │
└──────────────────────────────────────────────────────────────┘
```

This layering is useful when deciding compatibility and ownership. A change in the API layer should not automatically invalidate transformer state; a change in the transformer/state layer usually must.

---

## 19. Current known scope boundaries

The source itself establishes several current limits that should be documented rather than hidden:

- The build is validated for Qwen3.5-35B-A3B, not arbitrary Qwen geometries.
- The runtime uses one primary resident conversation state at a time.
- Tool schema support is intentionally narrower than full JSON Schema/OpenAI tool-choice semantics.
- Static-prefix snapshot capture is limited to 4096 tokens.
- Some performance paths remain selectable/experimental for A/B testing rather than being unconditional requirements.
- Historical implementation details of the first `warm_state_cache.inc` cannot be reconstructed from the supplied backups because only the current include was available.

These boundaries are part of the architecture and should remain visible as the project is prepared for public sharing.

---

## 20. Summary

The present Flash-iOS design is built around three ideas:

1. **Keep the decode pipeline moving.** Metal queue ordering, GPU-resident state, command-buffer chaining, asynchronous expert I/O, and selective synchronization minimize bubbles between model stages.
2. **Treat agent context as reusable model state.** Native tool prefixes and system prompts can be captured as the complete hybrid-attention state they produce, reused in memory, and persisted as named Flash profiles.
3. **Make reuse strict enough to be safe.** Exact token/tool signatures, transactional session handling, model/execution compatibility hashes, checksummed checkpoint formats, atomic publication, and explicit recapture prevent stale or mismatched state from being silently accepted.

That combination is what differentiates the current runtime from a simple stateless model server.


## N64 Production Prompt Prefill (2026-10-01/02)

The normal `infer` build now includes the accepted N-row prompt-prefill path and
uses N64 by default. The build defines:

```text
FLASH_PREFILL_NROW_PRODUCTION
FLASH_PREFILL_NROW_ASYNC
```

Production geometry:

```text
slab rows                  64
top-K                       8
routed assignments/slab    512
gate+up                     grouped_tiered_gate_up_m4_2row
routed down                 grouped_tiered_projection_m4_2row
tile                        M=4
threadgroup                 64 threads / 2 SIMD groups
```

Complete 64-token prompt chunks use N64. Any remainder smaller than 64 remains
on the established scalar prefill path. Decode is unchanged.

Routed-expert staging is allocated by unique-expert capacity rather than route
count:

```text
stage_slots = min(g_cfg.num_experts, PREFILL_NROW_ASSIGNMENTS)
```

For Qwen3.5-35B-A3B this is 256 staging slots at N64. The N64 workspace is
persistent for the process and reused across requests.

Runtime controls:

```text
--prefill-nrow       explicitly enable N64
--no-prefill-nrow    disable N64 and use scalar prefill
```

N64 is the production default; the scalar switch is retained as an immediate
fallback.

Validation completed before promotion:

- exact hidden/logit/next-token/state match on the controlled 1024-token gate;
- production single-command-buffer arithmetic passed twice;
- real HTTP serving exercised N64 plus scalar remainder;
- warmed 211-token prefill improved from 15.612 s / 13.515 tok/s scalar to
  8.443 s / 24.990 tok/s N64;
- an N64-created session state was reused by a later continuation
  (`session_reused=1`), with scalar control matching continuation behavior.

N96/N128 and larger-M / matrix-multiply expert kernels remain experimental and
should be evaluated against N64 as the production baseline.
