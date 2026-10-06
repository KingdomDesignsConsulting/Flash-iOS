# Archived experiment: routed-down M4-2row Q4/Q2 bitsplit

Date: 2026-10-06  
Branch: `flash-moe-production`  
Status: **closed / not promoted**

## Goal

Test whether replacing the accepted routed-down M4-2row dynamic-bit kernel with dedicated Q4 and Q2 M4-2row pipelines improves N128 prefill performance for the tiered Q4/Q2 Qwen3.5-35B-A3B Flash-MoE model.

The candidate preserved the accepted M4-2row geometry: 64-thread threadgroup, two SIMD groups, one output row per SIMD, M=4 tile, the same FP32 accumulation order, and the same reduction/output layout. Only the weight unpack path was specialized by quantization width.

## Candidate

Benchmark-only kernels:

- `grouped_tiered_projection_m4_2row_q4`
- `grouped_tiered_projection_m4_2row_q2`

Benchmark target:

- `make n128downbits`
- output: `infer-n128-down-m4-2row-bitsplit-bench`

Control target:

- `make n128gateup8bits`
- routed down: accepted dynamic-bit M4-2row
- gate+up: production M4-8row Q4/Q2 bitsplit

Production `infer` was never switched to the routed-down bitsplit candidate.

## Correctness

Across candidate and control runs:

- `hidden_max = 1.0490417e-05`
- `logits_max = 1.3828278e-05`
- next token: `1752/1752`
- `state_equal = 1`

These are comfortably inside the experiment thresholds:

- hidden max <= 1e-3
- logits max <= 1e-2
- same next token
- state equality required

The 1K benchmark did not emit a separate `decode_match` field.

## Instrumentation correction

An early candidate run used `FLASH_PREFILL_NROW_DOWN_BIT_TIMING`, which partitions routed-down work into separate Q4 and Q2 command buffers. The ordinary control used one routed-down command buffer, so that first wall-clock A/B was not comparable.

The benchmark setup was corrected in commit:

- `261983ee5678952fa546a40a2d7c9e84b13dd515`
- `experiment: separate down bitsplit perf and bit diagnostics`

Primary performance targets now use matching single-buffer routed-down submission. Separate diagnostic-only targets retain Q4/Q2 timing when needed.

## Matched clean-state results

### Dynamic-bit M4-2row control

Run 1:

- `nrow_ms = 40702.624`
- `nrow_tps = 25.158`
- `expert_ms = 8668.799`
- `expert_stage_ms = 3627.510`
- `expert_gate_up_gpu_ms = 4250.858`
- `expert_down_gpu_ms = 4060.084`

Run 2:

- `nrow_ms = 40590.417`
- `nrow_tps = 25.228`
- `expert_ms = 8665.253`
- `expert_stage_ms = 3379.009`
- `expert_gate_up_gpu_ms = 4259.064`
- `expert_down_gpu_ms = 4063.739`

Mean routed-down GPU time: **4061.912 ms**

### Q4/Q2 bitsplit candidate

Run 1:

- `nrow_ms = 38929.747`
- `nrow_tps = 26.304`
- `expert_ms = 8644.469`
- `expert_stage_ms = 2042.482`
- `expert_gate_up_gpu_ms = 4262.318`
- `expert_down_gpu_ms = 4062.868`

Run 2:

- `nrow_ms = 39421.859`
- `nrow_tps = 25.975`
- `expert_ms = 8818.303`
- `expert_stage_ms = 1619.323`
- `expert_gate_up_gpu_ms = 4319.045`
- `expert_down_gpu_ms = 4109.510`

Mean routed-down GPU time: **4086.189 ms**

## Conclusion

The fixed Q4/Q2 routed-down specialization did **not** produce a meaningful performance gain.

Compared with the clean-state dynamic M4-2row control, the candidate mean routed-down GPU time was about **0.60% slower** (4086.189 ms vs. 4061.912 ms). The difference is small enough to be near run-to-run GPU noise, but there is no evidence of a useful positive effect.

Large end-to-end differences between individual runs were dominated by memory residency / expert staging, not the routed-down shader. `expert_stage_ms` varied by seconds while the routed-down GPU phase remained near 4.06-4.11 s.

## Decision

- Keep **dynamic-bit M4-2row** as the production routed-down kernel.
- Do **not** promote routed-down Q4/Q2 bitsplit.
- Retain the bitsplit implementation and benchmark targets as archived experimental code/reference.
- Future routed-down work should target higher-leverage areas such as memory/input reuse, expert staging, cache residency, or useful work per weight load rather than bit-unpack specialization.
