# GQA context-gate qualification (2026-10-19)

Status: PASS for isolated integration; NOT approved for production.

Mac mini M4 24GB, Qwen3.5-35B-A3B Flash-MoE, cap-8 GQA context gate at active KV 2048 through 8192. CPU fallback remains after GPU_KV_SEQ.

## Results

The explanation, code and tools runs each had 70/70 performance records marked exact:true: 210/210 total, no failures. These are harness assertions, not fresh HTTP serving qualification.

Across starting active KV 2048, 4096 and 6144, cap8 won all six 64-token pairs per corpus per context: 54/54 wins.

| Starting active KV | Explanation median ms saved | Code median | Tools median |
| --- | ---: | ---: | ---: |
| 2048 | 222 | 317 | 206 |
| 4096 | 464 | 487 | 486 |
| 6144 | 648 | 718 | 712 |

At 8188 and 8192, windows cross the GPU-to-CPU boundary and mixed-window performance is unstable; do not promote these as steady-state improvements.

The initial experimental gate dereferenced null kv pointers in GDN layers. The local test runner was corrected with a kv null guard before successful runs.

## Decision and constraints

GO for isolated integration experiments. NO-GO for production promotion pending session, checkpoint, HTTP and request-path qualification. The live server was not modified.

Evidence locations in synced Google Drive: Flash-iOS/Testing/benchmark-logs/gqa-context-gate-fixed2, gqa-context-gate-code-restored and gqa-context-gate-tools-restored. Original qualification report: v-m2-gqa-cap8-qualification-results-2026-10-18.md.

## Next: 16K GPU attention

Extend Metal KV allocation/stride, scores, cache-mirror writes, restored-cache hydration, attention dispatch bounds, and command-chain guards from 8192 to 16384 consistently. Preserve CPU fallback above cap. Qualify baseline attention first at 8191, 8192, 8193, 12288, 16383, 16384 and 16385, then combine with gated cap8 and validate state, restore, session and HTTP behavior. Doubling KV mirror capacity costs about 160 MiB across 10 full-attention layers plus additional score buffer allocation, depending on configuration.

Never alter production or discard previously qualified cache anchors during these experiments.
