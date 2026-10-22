#!/usr/bin/env python3
"""Assemble the measured 32K qualification report without running inference."""
import argparse
import csv
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    a = ap.parse_args()
    repo = Path(__file__).resolve().parents[1]
    cases = {name: json.loads((a.root/name/'report.json').read_text()) for name in
             ('initial-16382', 'qualification-24574', 'qualification-32766')}
    assert all(c['result'] == 'PASS' for c in cases.values())
    perf = json.loads((a.root/'performance-matched/results.json').read_text())
    manifest = json.loads((a.root/'performance-matched/manifest.json').read_text())
    assert 'finished' in manifest and len(manifest['runs']) == 12
    accepted = sum(r['accepted'] for r in manifest['runs'])
    out = a.root/'report';out.mkdir(exist_ok=True)
    rows = perf['exploratory']['table']
    fields = ['context', 'arm', 'backend', 'decode_tps', 'token_cv_percent', 'attention_ms_per_layer',
              'physical_mib', 'peak_physical_mib', 'peak_rss_mib', 'metal_view_mib', 'restore_ms']
    values = []
    for r in rows:
        gpu = bool(r['gpu_layers'])
        values.append(dict(context=r['context'], arm=r['arm'], backend='GPU' if gpu else 'CPU',
            decode_tps=r['decode_tps'], token_cv_percent=100*r['token_ms']['cv'],
            attention_ms_per_layer=r['attention_gpu_ms_per_layer' if gpu else 'attention_cpu_ms_per_layer']['median'],
            physical_mib=r['physical_bytes']['median']/2**20, peak_physical_mib=r['peak_physical_bytes']/2**20,
            peak_rss_mib=r['peak_rss_bytes']/2**20, metal_view_mib=r['metal_allocated_bytes']['median']/2**20,
            restore_ms=r['restore_ms']['median']))
    with (out/'performance-exploratory.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(values)
    data = dict(verdict='32K QUALIFIED', qualification=cases, performance=perf,
                timing_confidence='exploratory; competing GPU activity', idle_gated_processes=accepted,
                total_benchmark_processes=len(manifest['runs']))
    (out/'qualification-summary.json').write_text(json.dumps(data,indent=2)+'\n')
    numeric = ['| Comparison / position | Hidden max abs | Logits max abs | KV max abs | GPU recurrent max abs | Worst relative L2 |',
               '|---|---:|---:|---:|---:|---:|']
    for name,c in cases.items():
        for control,candidate in [('lazy16k','lazy32k'),('lazy32k','lazy32k-nochain')]:
            xs=[x for x in c['comparisons'] if x['control']==control and x['candidate']==candidate]
            maxima=[max(x['fields'][f]['max_abs'] for x in xs) for f in ('hidden','logits','kv','gpu-recurrent')]
            rel=max(s['relative_l2'] for x in xs for s in x['fields'].values())
            numeric.append(f"| {control} → {candidate}, {c['pos']} | "+' | '.join(f'{v:.8g}' for v in maxima)+f' | {rel:.8g} |')
    table=['| Active KV | Arm | Backend | Decode tok/s | CV % | Attention ms/layer | Physical MiB | Peak physical MiB | Restore ms |',
           '|---:|---|---|---:|---:|---:|---:|---:|---:|']
    for r in values:
        table.append(f"| {r['context']} | {r['arm']} | {r['backend']} | {r['decode_tps']:.3f} | {r['token_cv_percent']:.2f} | {r['attention_ms_per_layer']:.3f} | {r['physical_mib']:.2f} | {r['peak_physical_mib']:.2f} | {r['restore_ms']:.2f} |")
    lookup={(r['context'],r['arm']):r for r in values}
    ratio32=lookup[(32768,'lazy32k')]['decode_tps']/lookup[(32768,'lazy16k')]['decode_tps']
    ratio24=lookup[(24576,'lazy32k')]['decode_tps']/lookup[(24576,'lazy16k')]['decode_tps']
    boundary=['| Active KV | Arm | Backend | Exploratory tok/s |','|---:|---|---|---:|']
    for r in perf['exploratory']['boundaries']:
        if r['length'] in (16385,32769):boundary.append(f"| {r['length']} | {r['arm']} | {'GPU' if r['gpu_layers'] else 'CPU'} | {1000/r['wall_ms']['median']:.3f} |")
    tail=cases['qualification-32766']['arms']['lazy32k']['tail']
    report=f'''# 32K lazy shared-KV qualification — 2026-10-22

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
| Post-transition save at {tail['saved_pos']}, continuation to {tail['continuation_len']} | Byte-exact state/hidden replay PASS |
| Post-restore continuation token | {tail['token']} in all three arms |
| 12 benchmark processes, three measured repetitions/mode | PASS, all exit 0 and matched tokens |
| Uncontended performance qualification | NOT ESTABLISHED; {accepted}/12 processes passed strict idle gate |
| Long serving/session soak and production integration | NOT RUN |

Full-attention layers: 3, 7, 11, 15, 19, 23, 27, 31, 35, 39.
At lengths 32767/32768 lazy32k reports GPU=1; at 32769/32770/32771 GPU=0.
Chained runs report chain=1 only for GPU rows; unchained runs report chain=0.
All greedy tokens match controls. At 16K, lazy16k/lazy32k are bitwise equal
through length 16384; CPU/GPU differences after that are numerical, not bitwise.

Criteria per field: finite values, identical token IDs, relative L2 <= 1e-4,
max absolute <= 1e-3 + 1e-4 * reference maximum. CPU convolution/recurrent
fields compare exactly. GPU recurrent fields include GDN and convolution.

{chr(10).join(numeric)}

## Memory and performance

**All-data exploratory medians**, including contention; do not interpret small
differences as regressions or speedups. Each position has six primary token
observations across two independently initialized processes; GPU counters use
separate observer passes. CV and complete min/max/p10/p90 are saved in JSON.
Strict idle gating is median <=10% and every sample <30% before/after each
process. Exploratory execution still requires every pre-run sample <30%.

{chr(10).join(table)}

Measured behavior immediately beyond each GPU cap (same contention caveat):

{chr(10).join(boundary)}

Physical and peak physical memory are Mach `phys_footprint` and
`ledger_phys_footprint_peak`; CSV also includes peak RSS and Metal allocation
accounting. Metal no-copy view reservation is **not resident physical memory**.
At a matched context, both variants touch the same CPU-owned KV pages; the
32K view does not create a second physical KV copy.

The all-data ratios are {ratio24:.2f}× at 24K and {ratio32:.2f}× at 32K,
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
'''
    (out/'REPORT.md').write_text(report)
    (repo/'docs/gpu-32k-attention-qualification-2026-10-22.md').write_text(report)
    (repo/'docs/gpu-32k-attention-qualification-2026-10-22.json').write_text(json.dumps(data,indent=2)+'\n')
    print('32K QUALIFIED; report saved to',out)
    print('\n'.join(table))


if __name__=='__main__':main()
