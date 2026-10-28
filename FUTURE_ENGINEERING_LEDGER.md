# Flash-iOS — Future Engineering Ledger

**Purpose:** The durable, living queue for future Flash-iOS engineering, open release gates, research discoveries, experiment proposals, and work completed. **Source of truth for roadmap status**, not a replacement for detailed experiment reports, raw private results, PR discussion, or `autoresearch/experiments.tsv`.

**Initialized:** 2026-10-28. **Operating model clarified:** 2026-10-28. **Branch:** `experiment/http-resident-prefix-reuse-20261023`. **Production:** `flash-moe-production` unchanged. **PR #2:** draft; promotion not authorized.

## Engineering ownership and execution model

- **Lead Architect (this ChatGPT thread) is the default hands-on engineer.** The Architect investigates, designs and implements individual experiments, commits scripts/source changes on the authorized experimental branch, provides exact Mac commands, and reviews the user's test logs/results. **The user executes Mac-local tests** when this thread lacks direct access. Architectural review and implementation are not separate responsibilities by default.
- **Work engineering thread is optional and reserved for batches of numerous short, sequential experiments** that benefit from unattended automation and minimal moment-by-moment user interaction. Delegate a bounded batch with clear evidence and branch boundaries; do not automatically route a substantial task or every experiment to Work.
- **Research thread** discovers candidate approaches and supplies evidence. Research recommendations are not validated Flash results or implementation assignments until triaged.
- **Owner field describes the current actual implementer**, not merely the reviewer. Use `Architect`, `Work`, `Research`, or `Unassigned`; assign to Work only when explicitly delegated. The existing FE-001–004 Work assignment has now returned results and FE-027 is Architect-owned; future items default to Architect engineering when selected.
- For Architect-developed experiments: inspect code → implement and commit isolated change → give runnable Mac commands → user executes and returns evidence → diagnose/iterate → update ledger/status and reports. Avoid worktree conflicts with concurrent Work batches.

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

## Release gates — completed Work batch and new Architect blocker

| ID | Priority | Status | Owner | Required outcome / current boundary | Evidence / dependencies |
| --- | --- | --- | --- | --- | --- |
| FE-001 | P0 | BLOCKED | Architect | **Confirmed numerical FAIL at completed position 1920**, after pass through 1792. Candidate/state 0.967838436, hidden 0.006615520, logits 0.042357683 exceed unchanged limits. Near-tied layer-9 expert set differs at input position 1829; earlier accumulated drift suspected. Do not escalate 4K+ until localized and corrected | [Release-gates handback](docs/resident-release-gates-2026-10-28.md); [bounded N128 report](docs/n128-resident-state-qualification-2026-10-27.md); FE-027 |
| FE-002 | P0 | QUALIFIED | Work | Named-profile HTTP restart, matched overlapping fingerprints, correct old-session 409, incompatible signature/mode rebuild, unchanged valid profile; CPU-linear profile restart and unrelated-binary rebuild also pass **within observed scope** | [Release-gates handback](docs/resident-release-gates-2026-10-28.md); real different model weights not tested |
| FE-003 | P0 | QUALIFIED | Work | Actual half-close and client timeout, synthetic checked-forward failure, partial temp checkpoint write EIO: invalidation/recreation or safe completion as specified; old sessions rejected; exact recovery. **Only these scenarios qualified** | [Release-gates handback](docs/resident-release-gates-2026-10-28.md); real device/OOM/disk hardware faults unverified; external tool executor N/A |
| FE-004 | P1 | QUALIFIED | Work | Seven **short within-mode** persistent-state comparisons pass, including CPU-linear/profile restart and legacy KV. Bypass is an ablation, not model-quality pass | [Release-gates handback](docs/resident-release-gates-2026-10-28.md); long mode cross-products and cross-mode numerical parity not established |

## Completed or bounded-qualified groundwork

| ID | Status | Scope actually supported | Evidence |
| --- | --- | --- | --- |
| FE-005 | [x] QUALIFIED | Short scalar matched-token resident state across seven cases; repair stale CPU shadow upload overwriting GPU system prefix at position 13. Exact active component fingerprints, not full-memory identity | [Report](docs/resident-state-equivalence-2026-10-27.md); repair `dc77d12c` |
| FE-006 | [x] QUALIFIED | **Bounded** short N128 numerical parity (not bit-exact to scalar), HTTP candidate-to-native fingerprints, prefill/decode/EOS/continuation, real TCP RST invalidation and exact fresh recovery | [Report](docs/n128-resident-state-qualification-2026-10-27.md); `b3cc330` |
| FE-007 | [x] QUALIFIED | Native Zstd state checkpoint from prefix 141, restart and 64-position exact continuation; wrong-prefix and opposite-mode rejection. Named-profile HTTP path remains FE-002 | [N128 report](docs/n128-resident-state-qualification-2026-10-27.md) |
| FE-008 | [x] DONE | Selective identity advanced to execution v3 for corrected GPU-prefix state and includes N128/scalar runtime switch; full executable hashing remains disabled | `dc77d12c`, `0b49e08` |
| FE-009 | [x] DONE | Four-token difference explained by empty thinking wrapper retained in resident history; canonical reconstructed history omits it. Qwen template deliberately unchanged | [Scalar report](docs/resident-state-equivalence-2026-10-27.md) |
| FE-010 | [x] DONE | GUI Regenerate not available in inspected LM Studio interface. This **does not** qualify all other GUI behavior | [Architect gates](docs/architect-release-gates-2026-10-28.md) |

## Confirmed defect requiring Architect-led engineering

| ID | Priority | State | Owner | Next discriminating experiment and exit criterion | Evidence |
| --- | --- | --- | --- | --- | --- |
| FE-027 | P0 | ACTIVE | Architect | **Locate earliest accumulated N128/scalar divergence preceding hard MoE route flip.** Inspect the exact 1792→1920 oracle, layer-9 router tie at input 1829, and earlier state drift. Use narrowly instrumented same-input route-score margins and per-layer state-delta tracing across slab endpoints; identify where numerical paths differ enough to alter top-K. Test targeted arithmetic/accumulation fixes on isolated experimental paths only; require unchanged numerical limits across many-slab and long-context cases, greedy equality, correct KV, finite state and repeatability. Scalar-anchor reset is a diagnostic counterfactual, not a serving fix. Preserve routing policy and Qwen template unless separate explicit decision | [Work report](docs/resident-release-gates-2026-10-28.md) at `ba11bd38`, implementation/probes `120e993`. At 1920: state 0.967838436, hidden 0.006615520, logits 0.042357683. Last measured pass 1792; first observed expert-set flip layer 9 / position 1829; exact anchor at 1792 prevents jump. |

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

1. **Architect:** Own FE-027 as the next implementation-and-user-run investigation. FE-001 is blocked on its resolution; do not reclassify failure as pass based on greedy agreement. Work's FE-002/003/004 bounded handback is recorded, with untested sub-scopes explicitly preserved.
2. **Architect:** Implement experiments and give the user Mac commands; review exact outputs and revise FE-027 as evidence dictates. Once numerical drift is corrected, reopen FE-001 for 2K/4K/8K and extended contexts. Keep FE-011–015 as later Architect-led agent protocol work.
3. **Research:** File new discoveries as proposed candidate entries with source, date, applicability, testable hypothesis, blockers and expected benefit, explicitly stating whether Apple M4 was tested.
4. **Verifier:** Keep FE-021 blocked until a bounded M4 design beats serial end-to-end with exact hybrid-state rollback. Microbenchmarks, acceptance length and off-target draft models alone do not unblock it.

## Decision log

- **2026-10-28 (Work handback / architectural triage):** FE-001 long N128 FAIL at 1920 (state 0.967838436 versus <1e-3). FE-002, FE-003 and FE-004 qualified only within bounded executed scopes. Created FE-027 Architect investigation of near-tied MoE route flip with inherited numerical drift; no production promotion.\n- **2026-10-28 (operating-model amendment):** Lead Architect is also the default experiment implementer; user runs local Mac tests. Work is used selectively for many short experiments that can run unattended. Existing FE-001–004 batch delegation retained.
- **2026-10-28:** Ledger established. Existing qualified short-scalar/N128/lifecycle findings recorded as bounded, and four active release gates identified. Research findings triaged without claiming current Flash bugs. No production promotion.
