# Flash-iOS research reconciliation — October 8–15 and November 2–4, 2026

**Source:** canonical Google Drive `Flash-iOS/docs/kevin/Research Discoveries.md` (ID `197wH1GgOC-7eaddF_Bv-B2W7vSmOsQgn`), observed modified 2026-11-04T22:14:01.595Z and 902,594 connector text characters. This document is a scoped research *triage*, not proof that an upstream issue affects Flash or a claim of independent replication on base M4. Research timestamps are preserved as provided; no dates invented. **Production remains unchanged; PR #2 draft; FE-038 still NO-GO.**

## October 8–15 backfill — missing explicit source coverage

The canonical archive has only dated headings for October 8, October 9 and October 15 in this interval, totaling **seven third-level discovery entries** (the October 15 entries each group multiple sources). Do not invent daily findings for October 10–14; do not mislabel the October 22 review of an October 11 preprint as a contemporaneous October 11 research report.

| Source | Documented finding | Action, priority, and disposition |
| --- | --- | --- |
| [MLX #4621](https://github.com/ml-explore/mlx/issues/4621) (Oct 8 log) | For dense MLX long-prefill Q4, pre-dequantized BF16 projection can win at high M, while small-M favors quantized kernel; M2 Max results do not project to tiered base M4. | **P3, proposed**: only bounded active-layer dequant-vs-fused Q2/Q4 prefill crossover + memory benchmark if FE-038 is closed. No full-model BF16 expansion; associate FE-024/FE-031. |
| [llama.cpp PR #30065](https://github.com/ggml-org/llama.cpp/pull/30065) | Merged generic few-row low-bit Metal MMA, distinct from unmerged sparse routed-MoE PR #30047. | **P3, proposed**: inspect dequant/dispatch for Q2/Q4 M=2/4/8/16; do not assume verifier or speculative speedup. Fold into FE-024/FE-021. |
| [Unsloth PR #13016](https://github.com/unslothai/unsloth/pull/13016) | Apple MLX decision backend and limited Clef/Laya training/calibration; Kev 4B inference support does not validate custom pointer-head weights. | **P3, separate agent decision workstream**, not Flash core; measure p50/p95, calibrated routing, memory arbitration before replacement. No model migration. |
| [llama.cpp PR #30139](https://github.com/ggml-org/llama.cpp/pull/30139) | Guarded in-place recurrent-state view can avoid copy; rollback/remap/zero-state cases retain gather. | **P2, triaged**: profile actual Flash GDN read/gather/copy; if already in-place, close without change; otherwise exact alias/rollback-safe microprobe. Related FE-019/FE-029. |
| [MLX-LM PR #1957](https://github.com/ml-explore/mlx-lm/pull/1957) | Malformed tool arguments could yield `finish_reason=tool_calls` without actual tool calls; proposed parser retains rejected text. | **P1, triaged**: test malformed/partial mixed calls, streamed/buffered, fail-closed execution; related FE-011/FE-028/FE-034. No claim Flash has bug. |
| [MLX-VLM PR #2525](https://github.com/Blaizzy/mlx-vlm/pull/2525), [Splash #434](https://github.com/incoai/splash/pull/434), [MLX-VLM #2527](https://github.com/Blaizzy/mlx-vlm/pull/2527) (Oct 15 grouped entry) | Cache lifecycle, short-prefill scheduling and numerical parity; the archive explicitly lacks detailed code-level evidence/benchmarks. | **P3, watch/reverify upstream before engineering**. No measured Flash gain or assigned port. |
| [SGLang #43514](https://github.com/sgl-project/sglang/issues/43514) (Oct 15) | Grammar-constrained required tools + concurrent long prefill + speculative serving caused token-zero/zero acceptance on NVIDIA H20. | **P3, blocked by FE-021**: add grammar/concurrent-prefill reproducibility when speculation becomes viable, not now. |

October 9 also notes [llama.cpp #30141](https://github.com/ggml-org/llama.cpp/pull/30141) as a **related watch item**, not another independently recommended integration. Preserve that distinction.

## November 2–4 incremental findings

| Source | Distinct Flash-relevant hypothesis / action | Priority / track |
| --- | --- | --- |
| [vLLM #65112](https://github.com/vllm-project/vllm/issues/65112) | Batch-order drift can confound hybrid checkpoint replay testing; use one-request batch-stable controls and compare accepted-state fingerprints. | P1 test-method addition to FE-038/FE-002; CUDA issue not a Flash defect |
| [vLLM #65114](https://github.com/vllm-project/vllm/issues/65114) | Conflicting thinking/reasoning controls can change exact prompt tokenization without error; establish precedence, prompt identity and stream/nonstream parity. | P1 FE-012/FE-017, release-relevant client semantics |
| [vLLM #65073](https://github.com/vllm-project/vllm/issues/65073) | Duplicate MCP names can cross-wire displayed tool schema and execution URL. | P1 separate Gateway registration validation |
| [vLLM #65074](https://github.com/vllm-project/vllm/issues/65074) | MCP `tools/list` pagination may silently truncate tool catalog. | P1 separate Gateway pagination and identity validation |
| [SGLang #47916](https://github.com/sgl-project/sglang/issues/47916) | Vectorized GDN state slot copy transiently allocates n × state size, causing burst OOM even when steady state fits. | P1 FE-035/FE-029: test bounded multi-slot copies and peak admission, not CUDA port |
| [SGLang #47896](https://github.com/sgl-project/sglang/issues/47896) | Derived fused GDN projection cache may remain on wrong device after offload. | P1 FE-016/FE-036: validate derived tensor residency/version/metadata across remap |
| [vLLM #65131](https://github.com/vllm-project/vllm/issues/65131) | KV load-failure fallback can desynchronize output accounting and crash. | P1 FE-003/FE-034: transactional recompute including stream tokens and recurrent state |
| [vLLM #65139](https://github.com/vllm-project/vllm/issues/65139) | First speculative verify invokes unwarmed attention shape and crashes in CUDA. | P3 blocked FE-021, cold-shape verifier testing, no Metal bug inferred |
| [MLX Swift LM #753](https://github.com/ml-explore/mlx-swift-lm/issues/753) | A single GDN recurrence pass may emit both accepted checkpoint and final state, avoiding second pass in MTP verification. | P3 FE-021 prerequisite; no drafter enablement or M4 speed projection |
| [llama.cpp PR #31638](https://github.com/ggml-org/llama.cpp/pull/31638) (Nov 4) | Proposed Responses tool-event ordering and truncated `max_output_tokens` incomplete-result fix; follow-up to issue #30773, not a new independent defect. | P1 FE-011/FE-034: complete versus truncated tools, streaming/buffered test oracle |

The November 2 watch also lists vLLM #65034, Ollama #19458, SGLang #47830 and vLLM #65035; **already captured** as FE-036, FE-034, FE-035 and FE-037 respectively. Do not create duplicate engineering tickets.

## Recommended order

1. **Keep FE-038 production gate first**: repaired binary full 32K, long performance/HTTP decode, and unexplained literal-change behavior. No change to release NO-GO.
2. **Near-term agent reliability tests**: conflicting thinking controls, malformed and truncated tools, duplicate MCP names, cursor pagination; these may affect user agent functionality without touching kernel math.
3. **Bounded memory/state hardening**: transient GDN copy allocation, derived weight residency, checkpoint failure accounting.
4. **Deferred research**: long-M dequant/BF16 crossover, generic Metal MMA, speculative verifier GDN one-pass, decision-model backend. Evaluate only under isolated M4 resource budgets and after release blockers.

This reconciliation explicitly covers all seven research headings dated October 8–15, plus November 2–4 additions, while preserving reported source certainty. No changes to Qwen weights, templates, production inference or active checkpoints are authorized.
