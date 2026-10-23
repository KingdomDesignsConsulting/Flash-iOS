# Isolated 16K GPU attention experiment

This branch is NOT production-approved and must not overwrite the live `metal_infer/infer` binary.

## Build

On the Mac mini M4, from `metal_infer`:

```sh
make gpu8k-control gpu16k-experiment
```

Both targets produce separate binaries. The only intended difference in the experimental full-attention GPU window is the `FLASH_EXPERIMENTAL_GPU_KV_16K` compile macro, which selects `GPU_KV_SEQ=16384` instead of `8192`. KV buffers, score buffers, per-head strides, mirror writes, CMD1 full-attention chain gating, CPU fallback, and checkpoint GPU mirror hydration all derive from `GPU_KV_SEQ`.

## Initial smoke tests

```sh
MODEL="/Users/Shared/Main Hard Drive/AI Storage/AI Models/Reasoning/alexintosh/Qwen3.5-35B-A3B-Q4-Tiered-FlashMoE"
./infer-gpu8k-control --model "$MODEL" --tiered --no-malloc-cache --no-expert-prefetch --prompt "Explain a photon" --tokens 2 2>&1 | tee /tmp/flash-gpu8k-smoke.log
./infer-gpu16k-experiment --model "$MODEL" --tiered --no-malloc-cache --no-expert-prefetch --prompt "Explain a photon" --tokens 2 2>&1 | tee /tmp/flash-gpu16k-smoke.log
```

Expected startup: 8K control reports `[metal] GPU_KV_SEQ = 8192`, 16K experimental reports `16384`. Neither log alone qualifies 16K attention because these prompts are too short.

## Mandatory qualification (not yet performed)

1. Produce/restored **same native exact states** for control and candidate at prefix 8191 (active 8192), 8192 (active 8193), 12287 (active 12288), 16382 (active 16383), 16383 (active 16384), and 16384 (active 16385).
2. For positions 8193–16384, compare full-attention output with CPU path including token sequence, hidden output, KV cache and GDN state. At 16385 ensure CPU fallback; verify no writes beyond GPU mirror bounds.
3. Exercise sequential decode, checkpoint restoration and resumed decode with prefixes both below and above the old 8192 limit. Include model configurations where `g_kv_seq_len` differs from defaults.
4. Validate that any experimental system-prompt and tool-prefix mirror copies are truncated safely at the new cap and do not expose stale or uninitialized positions.
5. Measure full-token latency and GPU/CPU attention time at 8192, 8193, 12288, 16383, 16384, 16385. Report resident memory and Metal resource allocation.
6. Only after 16K baseline correctness succeeds, port the independently qualified context-gated cap-8 GQA candidate into this branch and repeat exact-state and performance qualification, then HTTP/session tests.

Note: the independently qualified GQA cap-8 implementation is still in experimental artifacts and **is not included** in this branch's baseline `infer.m`. The 16K baseline and combined 16K+GQA are distinct milestones.

## Source synchronization warning

This experiment is based on GitHub `flash-moe-production` at branch creation. Previously, Google Drive's `metal_infer/infer.m` was identified as an authoritative development copy and may differ. Reconcile source differences before production integration; never replace newer Drive code wholesale with an older GitHub snapshot.
