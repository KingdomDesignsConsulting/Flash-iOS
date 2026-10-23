# 32K lazy shared-KV qualification — 2026-10-22

## Verdict: 32K QUALIFIED

Correctness and measured memory fit pass on the Mac mini M4 (24 GiB, macOS
26.7.1). Production is unchanged. The 16K baseline remains available.
Performance numbers below are **exploratory**, not a low-noise performance win.

Recommend integrating 32K directly as the next **opt-in** production candidate,
retaining the 16K fallback, rather than doing an intermediate 16K-only rollout.
Do not change the production default before serving/session memory-budget and
long-session validation. This assignment did not perform production integration.

## Implemented repairs and safeguards

- Removed an unused scalar grid argument from the benchmark-only
  `grouped_tiered_gate_up_m1_q4x4` kernel. Its mismatch with a vector grid
  declaration prevented the entire N128 shader library from compiling; it
  silently fell back to scalar prefill. Kernel arithmetic is unchanged.
- Increased the **qualification-only** fixture persistence ceiling from 16384
  to 32771. The first >16K fixture save exposed this limit and returned 27;
  the serving prefix-cache limit remains 8192 and the five-slot design is unchanged.
- Fixture loader now recognizes both historical active-GDN payloads and current
  complete-GPU-state payloads, using the production validator for current files.
- Added deterministic, resumable N128 fixture extension, 1024 tokens per
  subprocess; atomic directory publication after checksums, full-state reload,
  hidden-file fsync and completion metadata. Keep two recent recovery points
  and the 24K landmark; archive small logs while pruning older large payloads.
- GPU admission checks require three samples below 30%. Bounded contention
  waits stop safely with a usable resume point. Generation actually resumed
  after GPU-load stops at positions 20478 and 21502.
- State execution version is explicitly 2 because restored N128 availability
  can change the prefix computation path relative to the old scalar fallback.
  Full-binary invalidation remains disabled; unrelated rebuilds do not change
  the selective compatibility identity.
- Reused the separate observer/throughput performance harness for lazy16k and
  lazy32k, with matched anchors, flags, expert-cache settings and deterministic
  tokens. Benchmark-only changes do not enable speculative decode or new caches.

## Actual validation

| Check | Result |
|---|---|
| Separate 32K normal and qualification builds | PASS; no production infer overwritten |
| Metal shader compilation, accepted N128 runtime initialization | PASS |
| Saved 16382 anchor: five arms, five target steps | PASS |
| 24574 anchor: lazy16k CPU control, lazy32k, unchained lazy32k | PASS |
| 32766 anchor: all three arms, five steps through 32771 | PASS |
| GPU routing through 32768, CPU fallback from 32769 | PASS, all ten layers |
| Prefix KV immutability and finite numerical comparison fields | PASS |
| Ownership: retained no-copy views during queued GPU work, repeated destruction | PASS |
| Original checkpoint restore, malformed restore rejection, error-latch recovery | PASS |
| Production save/load roundtrip, first-step rollback/replay | Byte-exact PASS |
| Post-transition save at 32771, continuation to 32772 | Byte-exact state/hidden replay PASS |
| Post-restore continuation token | 248046 in all three arms |
| 12 benchmark processes, three measured repetitions/mode | PASS, all exit 0 and matched tokens |
| Uncontended performance qualification | NOT ESTABLISHED; 0/12 processes passed strict idle gate |
| Long serving/session soak and production integration | NOT RUN |

Full-attention layers: 3, 7, 11, 15, 19, 23, 27, 31, 35, 39.
At lengths 32767/32768 lazy32k reports GPU=1; at 32769/32770/32771 GPU=0.
Chained runs report chain=1 only for GPU rows; unchained runs report chain=0.
All greedy tokens match controls. At 16K, lazy16k/lazy32k are bitwise equal
through length 16384; CPU/GPU differences after that are numerical, not bitwise.

Criteria per field: finite values, identical token IDs, relative L2 <= 1e-4,
max absolute <= 1e-3 + 1e-4 * reference maximum. CPU convolution/recurrent
fields compare exactly. GPU recurrent fields include GDN and convolution.

| Comparison / position | Hidden max abs | Logits max abs | KV max abs | GPU recurrent max abs | Worst relative L2 |
|---|---:|---:|---:|---:|---:|
| lazy16k → lazy32k, 16382 | 1.4305115e-05 | 0.00010108948 | 0.00018167496 | 0.00012791157 | 9.5910171e-06 |
| lazy32k → lazy32k-nochain, 16382 | 6.6757202e-06 | 1.9550323e-05 | 7.6293945e-06 | 2.2888184e-05 | 1.1712421e-06 |
| lazy16k → lazy32k, 24574 | 9.0122223e-05 | 0.00021648407 | 0.0005273819 | 0.00047540665 | 2.3561441e-05 |
| lazy32k → lazy32k-nochain, 24574 | 2.8610229e-06 | 9.7751617e-06 | 1.8596649e-05 | 1.6987324e-05 | 9.353746e-07 |
| lazy16k → lazy32k, 32766 | 9.7751617e-05 | 0.00030231476 | 0.00033092499 | 0.00050354004 | 3.4462789e-05 |
| lazy32k → lazy32k-nochain, 32766 | 2.8610229e-06 | 7.1525574e-06 | 4.529953e-06 | 9.5367432e-06 | 5.8745035e-07 |

## Memory and performance

**All-data exploratory medians**, including contention; do not interpret small
differences as regressions or speedups. Each position has six primary token
observations across two independently initialized processes; GPU counters use
separate observer passes. CV and complete min/max/p10/p90 are saved in JSON.
Strict idle gating is median <=10% and every sample <30% before/after each
process. Exploratory execution still requires every pre-run sample <30%.

| Active KV | Arm | Backend | Decode tok/s | CV % | Attention ms/layer | Physical MiB | Peak physical MiB | Restore ms |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 16384 | lazy16k | GPU | 7.363 | 2.98 | 8.128 | 1800.34 | 1802.70 | 20.89 |
| 16384 | lazy32k | GPU | 7.444 | 3.42 | 8.188 | 1798.10 | 1798.21 | 22.88 |
| 24576 | lazy16k | CPU | 1.614 | 0.85 | 53.069 | 2439.42 | 2441.73 | 29.01 |
| 24576 | lazy32k | GPU | 5.662 | 2.48 | 12.021 | 2438.26 | 2438.31 | 29.31 |
| 32768 | lazy16k | CPU | 1.234 | 0.39 | 71.302 | 3082.19 | 3082.20 | 38.23 |
| 32768 | lazy32k | GPU | 4.614 | 1.82 | 16.408 | 3079.42 | 3079.51 | 36.78 |

Measured behavior immediately beyond each GPU cap (same contention caveat):

| Active KV | Arm | Backend | Exploratory tok/s |
|---:|---|---|---:|
| 16385 | lazy16k | CPU | 2.328 |
| 16385 | lazy32k | GPU | 7.361 |
| 32769 | lazy16k | CPU | 1.230 |
| 32769 | lazy32k | CPU | 1.260 |

Physical and peak physical memory are Mach `phys_footprint` and
`ledger_phys_footprint_peak`; CSV also includes peak RSS and Metal allocation
accounting. Metal no-copy view reservation is **not resident physical memory**.
At a matched context, both variants touch the same CPU-owned KV pages; the
32K view does not create a second physical KV copy.

The all-data ratios are 3.51× at 24K and 3.74× at 32K,
relative to the 16K path's CPU fallback. These are observed exploratory ratios,
not reliable low-noise speedup claims. The ~1% 16K throughput difference is noise.
At 16K, Metal allocation accounting increases from 3116.36 to 3757.36 MiB
(+641 MiB), while measured physical footprint remains about 1.76 GiB in both
variants. The larger shared view is not another resident KV allocation.

Absolute footprints include an identical retained full checkpoint oracle per
process and are not a production-server memory prediction. At 32766 the saved
fixture is 1538212208 bytes; file/header overhead differs from live snapshot
accounting. The generation and qualification processes successfully ran on the
24-GiB machine. Full production expert-cache configurations were not measured.

Throughput is 1000 / median target-step wall ms at the specified active KV
length, not the mixed GPU/CPU four-token block average. CPU and GPU attention
latencies use CPU wall and calibrated Metal timestamp counters respectively,
averaged across ten layers; individual layers are in raw logs.

Same Makefile -O2 optimization flags, native K=8, model and greedy tokens,
`--tiered --no-malloc-cache --no-expert-prefetch`. Each mode has an untimed
warm pass; OS weight pages warm before measurement. Restore is from a RAM
snapshot, excluding disk fixture loading. No timing claim is based on compiler
activity or comparison with differently warmed expert caches. Cold prefill,
end-to-end HTTP latency and long-session sustained throughput were not measured.

## Reproduce

Run from `/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS` on branch
`experiment/gqa-32k-lazy-kv-20261022`. Existing state inputs are read-only.
Output directories below must be fresh.

```bash
make -C metal_infer lazy32k-experiment gpu-kv-qualification gpu-kv-qualification-32k gpu-kv-performance gpu-kv-performance-32k
python3 tools/qualify_gpu_32k.py --out '/Users/knagel/My Drive/Flash-iOS/Testing/gpu-32k-attention/reproduce-32766' --anchor '/Users/knagel/My Drive/Flash-iOS/Testing/gpu-32k-attention/seed-cache/32766/anchor.state' --pos 32766 --arms lazy16k,lazy32k,lazy32k-nochain
python3 tools/benchmark_gpu_16k.py --out '/Users/knagel/My Drive/Flash-iOS/Testing/gpu-32k-attention/performance-quiet-rerun' --contexts 16382,24574,32766 --arms lazy16k,lazy32k --anchor-root '/Users/knagel/My Drive/Flash-iOS/Testing/gpu-32k-attention/seed-cache' --rounds 2 --repeats 3 --steps 4 --suffix 2
```

The actual performance collection used those same matrix arguments plus
`--idle-wait 60 --post-settle 2 --exploratory`; all failed strict idle gates
remain excluded from the reliable results table.

Resumable fixture generation, if needed (does no new generation when complete):

```bash
python3 tools/extend_gpu_kv_fixture.py --root '/Users/knagel/My Drive/Flash-iOS/Testing/gpu-32k-attention/seed-cache' --anchor '/Users/knagel/My Drive/Flash-iOS/Testing/gpu-16k-attention/boundary-16384/seed-cache/explanation/16382/anchor.state' --target 32766 --idle-wait 120
```

This extends the validated 16382 anchor by 16384 deterministic tokens:
`1000 + (absolute_position * 73) % 1000`. It does not regenerate the first
16K tokens. Chunks are <=1024 tokens and use the accepted N128/M4 prefill path.
The 24K and 32K fixture content is synthetic; no broad prompt-corpus or long
serving soak is implied by this boundary qualification.

## Evidence and changed files

Drive: `Flash-iOS/Testing/gpu-32k-attention/`: `initial-16382/`,
`qualification-24574/`, `qualification-32766/`, `performance-matched/`,
`seed-cache/` (states and small history), and `report/` (this report, CSV,
combined numerical JSON, scripts/build logs/source hashes/evidence bundle).
Array dumps are compared before deletion; numerical results and hashes remain.
The saved 24K and 32K states remain for future tests. Failed initial extension
logs are retained; old redundant checkpoint payloads are pruned.

Engineering files changed relative to the supplied 32K branch:
`metal_infer/infer.m`, `metal_infer/Makefile`,
`metal_infer/gpu_kv_qualification.inc`, `metal_infer/warm_state_cache.inc`,
`metal_infer/prefill_probe/chunk_kernels.metal`,
`tools/extend_gpu_kv_fixture.py`, `tools/qualify_gpu_32k.py`,
`tools/benchmark_gpu_16k.py`, `tools/report_gpu_16k_performance.py`,
`tools/report_gpu_32k.py`, plus this report and its numerical JSON.

No new attention arithmetic, production default, production branch, model,
or production infer binary was changed. No pool of conversation KV snapshots
was added; full snapshots here are test-only correctness oracles.
