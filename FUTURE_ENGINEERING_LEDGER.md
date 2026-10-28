# Flash-iOS — Future Engineering Ledger

**Purpose:** The durable, living queue for future Flash-iOS engineering, open release gates, research discoveries, experiment proposals, and work completed. **Source of truth for roadmap status**, not a replacement for detailed experiment reports, raw private results, PR discussion, or `autoresearch/experiments.tsv`.

**Initialized:** 2026-10-28. **Branch:** `experiment/http-resident-prefix-reuse-20261023`. **Production:** `flash-moe-production` unchanged. **PR #2:** draft; promotion not authorized.

## How to maintain this ledger

- Give each item an immutable ID (`FE-###`) and an **owner** (`Work`, `Architect`, `Research`, or `Unassigned`). Do not reuse IDs or silently delete history; mark superseded and link successor.
- **State:** `PROPOSED` (research candidate), `TRIAGED` (scoped/awaiting capacity), `ACTIVE` (engineer assigned), `BLOCKED` (explicit dependency), `QUALIFIED` (acceptance gate met within documented scope), `DONE` (completed action, no remaining acceptance scope), `REJECTED`, or `SUPERSEDED`. `QUALIFIED` is not synonymous with production-approved.
- **Evidence:** Cite a source issue/PR, research-doc section and, once executed, commit/report/results. Clearly distinguish upstream author claims from Flash Mac measurements. Never promote a proposal to PASS based on upstream results.
- **Priority:** P0 production correctness/release blocker; P1 near-term user/agent reliability; P2 useful optimization or hardening; P3 exploratory/deferred. Assignments and priorities can change with results; add a dated decision note when they do.
- Prefer **one item per independently verifiable outcome**. Cross-reference related entries. Mark checkboxes only for actually executed/qualified work; use nested follow-on IDs for additional scope.
- Raw prompts, token traces, float dumps and checkpoint files remain private (Drive); only sanitized metrics, reproducer code and links belong on GitHub.
- Update ledger whenever a research finding is accepted/rejected, an experiment starts/finishes, or priorities change. Update linked PR/docs as relevant. A research watch entry alone does not create a test obligation.
- Avoid parallel experiments changing the same production-sensitive session paths without explicit coordination. Only authorized experimental branch; do not merge without Architect review.

**Research intake:** [Research Discoveries.md (Drive)](https://drive.google.com/file/d/197wH1GgOC-7eaddF_Bv-B2W7vSmOsQgn/view). Reference material may evolve independently; record source date/revision when implementing.

## Active release gates — Work engineering assignment

| ID | Priority | Status | Owner | Required outcome / current boundary | Evidence / dependencies |
| --- | --- | --- | --- | --- | --- |
| FE-001 | P0 | ACTIVE | Work | Long-context and many-slab N128 numerical accumulation, including 2K/4K/8K and bounded escalation; actual matched positions, state/hidden/logits tolerances, greedy tokens, KV geometry | [Architect gates](docs/architect-release-gates-2026-10-28.md); [bounded N128 report](docs/n128-resident-state-qualification-2026-10-27.md) |
| FE-002 | P0 | ACTIVE | Work | Named-profile HTTP save → clean restart → restore → continuation, including wrong identity/metadata rejection and unchanged valid state | Native serializer restart qualified; HTTP profile lifecycle not yet |
| FE-003 | P0 | ACTIVE | Work | Additional failure and rollback: half-close, timeout, interrupted streaming, bounded executor/Metal injection, disk-fault handling; no tainted reuse | Actual TCP RST prefill/decode covered in FE-006 |
| FE-004 | P1 | ACTIVE | Work | Inventory and qualify supported CPU-linear, bypass, legacy GPU KV and other reachable execution modes, plus mode identity switches | Do not label unsupported modes PASS |

## Completed or bounded-qualified groundwork

| ID | Status | Scope actually supported | Evidence |
| --- | --- | --- | --- |
| FE-005 | [x] QUALIFIED | Short scalar matched-token resident state across seven cases; repair stale CPU shadow upload overwriting GPU system prefix at position 13. Exact active component fingerprints, not full-memory identity | [Report](docs/resident-state-equivalence-2026-10-27.md); repair `dc77d12c` |
| FE-006 | [x] QUALIFIED | **Bounded** short N128 numerical parity (not bit-exact to scalar), HTTP candidate-to-native fingerprints, prefill/decode/EOS/continuation, real TCP RST invalidation and exact fresh recovery | [Report](docs/n128-resident-state-qualification-2026-10-27.md); `b3cc330` |
| FE-007 | [x] QUALIFIED | Native Zstd state checkpoint from prefix 141, restart and 64-position exact continuation; wrong-prefix and opposite-mode rejection. Named-profile HTTP path remains FE-002 | [N128 report](docs/n128-resident-state-qualification-2026-10-27.md) |
| FE-008 | [x] DONE | Selective identity advanced to execution v3 for corrected GPU-prefix state and includes N128/scalar runtime switch; full executable hashing remains disabled | `dc77d12c`, `0b49e08` |
| FE-009 | [x] DONE | Four-token difference explained by empty thinking wrapper retained in resident history; canonical reconstructed history omits it. Qwen template deliberately unchanged | [Scalar report](docs/resident-state-equivalence-2026-10-27.md) |
| FE-010 | [x] DONE | GUI Regenerate not available in inspected LM Studio interface. This **does not** qualify all other GUI behavior | [Architect gates](docs/architect-release-gates-2026-10-28.md) |

## Research-derived candidate queue — not demonstrated Flash defects

| ID | Priority | State | Candidate test / decision trigger | Origin / overlap |
| --- | --- | --- | --- | --- |
| FE-011 | P1 | TRIAGED | Lossless demultiplexing of raw output, reasoning, answer and tool arguments; streamed vs buffered, every split-marker boundary, answer→tool→answer, malformed envelopes | Rapid-MLX #5281; complement FE-012/013; separate agent-protocol test stream |
| FE-012 | P1 | TRIAGED | Thinking-off streaming timely first visible delta; explicit/implicit markers, thinking on/off, tools, resident continuation and no leakage | Rapid-MLX #5280; test fake engine before live Qwen |
| FE-013 | P1 | TRIAGED | Correct decoded-content stop handling across alternate token decompositions, network chunks, reasoning/tool channels, streamed/nonstreamed finish reasons | SGLang #47059; vLLM #64088/#64062 |
| FE-014 | P1 | TRIAGED | Tool schema losslessness and validation across JSON Schema regex/GBNF and adapters; required arguments, nested schemas, malformed escape failures | llama-cpp-turboquant #408; kagent #3387 |
| FE-015 | P1 | TRIAGED | Long-agent summary survives repeated truncation; atomic tool-call/result pairs, checkpoint/continuation | Strands #5565; depends on context manager design |
| FE-016 | P1 | TRIAGED | Tiered Q2/Q4 per-layer/per-expert packing, shape, revision and manifest ownership validated fail-closed; streamed checkpoint rollback preserves original weights/state | vLLM #63990/#63991; SGLang #46924; intersects FE-002/003 but distinct model loader |
| FE-017 | P2 | TRIAGED | System/developer prefix metadata, actual token IDs and checkpoint identity agree after model/session switch, clear, restore and tool continuation | Ollama #19341; may fold into FE-002/004 |
| FE-018 | P2 | TRIAGED | Verify log-sum-exp base and deterministic split/prefix-attention merge parity **if such merge paths exist**; unchanged correct kernels | SGLang #46793; may fold into FE-001 |
| FE-019 | P2 | TRIAGED | Profile/checkpoint ownership tracks all dependent KV/GDN/conv/token identity; reject evicted/incomplete state rather than silently reuse | SGLang #47057/#47058; partially overlaps FE-002 |
| FE-020 | P3 | PROPOSED | Whole-model multi-agent eviction policy: smallest sufficient victim, reload economics, session pinning and measured 24GB residency | Ollama #19326; not routed-expert cache policy |
| FE-021 | P3 | BLOCKED | Speculative verifier/drafter program: genuinely sublinear grouped target Q2/Q4 small-M verification and exact provisional KV/GDN/conv commit/rollback; only then investigate DFlash/DSpark and draft-KV sliding windows | Serial N4 **194.1 ms**, layer-major N4 **~247.8 ms** controls; HYHPING DFlash2 wrong fine-tune, vLLM #64109, SGLang #47057/#47058. Not a deployment candidate |
| FE-022 | P3 | TRIAGED | Per-run request-weighted speculative accepted-tokens and wall-clock measurements; prevent prior-run/warmup counter contamination | SGLang #46960; prerequisite if FE-021 unblocks |
| FE-023 | P3 | PROPOSED | Speculative target/draft/KV/GDN/conv allocation ledger incl. lookahead and exact rollback before 24GB admission | SGLang #46756; FE-021 dependency |
| FE-024 | P3 | PROPOSED | Bounded M4 simdgroup multi-row Q2/Q4 experiment (M2/M4 vs M6/M8), dispatch and expert weight sharing; no direct M5+ NAX port | MLX #4781; dependent on FE-021 viability |
| FE-025 | P2 | TRIAGED | Additional live LM Studio GUI install, cancellation and attachment behavior for actual SDK integration; do not confuse SDK/mock controller tests with full GUI qualification | PR #2; Regenerate item FE-010 closed |
| FE-026 | P2 | PROPOSED | Checkpoint compression/persistence tuning only if measured end-to-end startup savings justify CPU/memory overhead; preserve current Zstd baseline | Research baseline 224.42MB → 88.27MB; no new optimizer claim |

## Next disposition queue

1. **Work:** Own and report FE-001 through FE-004. Incorporate FE-017/018/019/016 test patterns where relevant but do not turn this into uncontrolled scope expansion. Update statuses and attach measured results.
2. **Architect:** Review FE-001–004 evidence for production gates; coordinate independent agent protocol FE-011–015 after correctness baseline, rather than interrupting active N128 runs.
3. **Research:** File new discoveries as proposed candidate entries with source, date, applicability, testable hypothesis, blockers and expected benefit, explicitly stating whether Apple M4 was tested.
4. **Verifier:** Keep FE-021 blocked until a bounded M4 design beats serial end-to-end with exact hybrid-state rollback. Microbenchmarks, acceptance length and off-target draft models alone do not unblock it.

## Decision log

- **2026-10-28:** Ledger established. Existing qualified short-scalar/N128/lifecycle findings recorded as bounded, and four active release gates identified. Research findings triaged without claiming current Flash bugs. No production promotion.
