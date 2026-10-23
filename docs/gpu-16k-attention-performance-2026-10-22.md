# 16K GPU attention performance screening — 2026-10-22

## Recommendation: PROMOTE 16K for capacity and memory

The qualified 16K GPU path avoids the substantial CPU fallback cost beyond 8192.
At active KV length 16384, lazy shared-KV measured **7.760 tok/s**, legacy 16K
**7.728 tok/s**, and legacy 8K's CPU fallback **2.376 tok/s**: a **3.27×**
lazy-versus-8K improvement. Lazy uses **640.80 MiB less physical footprint**
than legacy 16K at that length (1798.06 versus 2438.86 MiB, **26.3%**).

There is **no established lazy-versus-legacy-16K throughput advantage**.
The observed 0.4% difference at 16K is below the available measurement confidence.
Retaining the existing attention kernels is appropriate; no runtime optimization
or production promotion was performed. `flash-moe-production` and production
`infer` remain unchanged. Qualified reference commit:
`38712216ded9edf298e5cfd91e7b6607c888e795`.

This is a capacity/memory recommendation supported by short checkpoint-assisted
runs, **not a claim of a completed low-noise performance qualification across all
contexts**. A quiet-machine rerun is needed before claiming small throughput
regressions, speedups, or formal equivalence, particularly at 8K.

## Method and limitations

- Apple M4, 10 CPU cores, 24 GiB RAM; macOS 26.7.1 (25G241).
- All three binaries use the same Makefile `INFER_CFLAGS`: `-O2 -Wall -Wextra
  -fobjc-arc -DACCELERATE_NEW_LAPACK`, N128 production/async prefill,
  M4-8row gate/up bitsplit, Metal/Foundation/Accelerate, compression and Zstd.
  Only GPU KV implementation/cap and benchmark instrumentation differ.
- Same model, native K=8, greedy selection, exact same saved checkpoint and
  starting hidden vector per context; fixture and binary SHA-256 recorded.
- Expert malloc cache and expert prefetch disabled identically. Each measurement
  mode has an untimed warm run; OS weight pages are warmed before measurement.
  Results characterize this matched configuration, not a serving expert-cache
  hit-rate study.
- Checkpoint anchors: 2047, 4095, 8191, and 16382. No expensive prefix regenerated.
  Four target steps per restore, three measured repetitions, two independent
  rounds. Arm order rotates/reverses. Counter profiling runs separately from
  throughput so counter sampling is not in the throughput denominator.
- **48 processes**, all exit 0. **1152** recorded decode steps (including separate
  counter passes) and **144** suffix-prefill trials. All decode token IDs and
  suffix next-token IDs agree across arms and repetitions. Warm trials excluded.
- Idle sampling: three readings before/after each process, median <=10%.
  Original collection maximum was <=35%; final analysis additionally requires
  **every sample <30%**. First collection settled 0.4 s after exit; confirmation
  used 2 s to avoid attributing trailing own work to background load. No failed
  gate was retrospectively accepted. **19/48 processes** meet the final gate;
  all 29 others are excluded, retained in raw logs. A concurrent macro-disabled
  build overlapped an already-excluded 8K-context legacy-16K process.
- Low pre/post load does not establish low load throughout a process. GPU
  counters sometimes doubled and decode timing spiked despite passing endpoints.
  These variable observations remain visible, not trimmed to favorable samples.
  During-run utilization includes this benchmark's own work and cannot identify
  competing GPU work. Administrator-only per-process GPU attribution was
  unavailable (`sudo -n powermetrics`: password required).
- Table throughput is 1000 / median per-token wall milliseconds at the indicated
  **active KV length**, not the mixed-backend four-token block average.
  GPU attention latency spans scores, softmax, values, sigmoid gate using Metal
  timestamp counters; CPU fallback latency times the CPU attention/gate loop.
  Latency shown is the average over ten full-attention layers; each individual
  layer is saved in raw logs. CPU and GPU clocks are distinct measurements.
- Physical footprint is `task_vm_info.phys_footprint`; peak physical is
  `ledger_phys_footprint_peak`; peak RSS is Darwin `getrusage.ru_maxrss`.
  These are different metrics. All arms retain the same full anchor oracle in
  RAM; reported absolute footprints include it. This is not a production-server
  memory claim. At anchor 16382 that oracle is 867123200 bytes.
- Prefill is an **eight-token scalar continuation suffix**, the ordinary
  sub-N128 path, from a restored context. TTFT includes RAM checkpoint restore,
  suffix transformer work, final norm and first-token LM head; it excludes
  process/model startup, disk checkpoint loading, HTTP and client transport.
  **Cold full-prefix prefill and end-to-end API TTFT were not measured**.
  At anchor 8191 the 8K arm executes only the first suffix token on GPU; at
  anchor 16382 both 16K arms execute two suffix tokens on GPU and six on CPU.
  Those mixed timings must not be read as pure 16K GPU prefill throughput.

## Decode, attention and physical footprint

CV is population standard deviation / median token time. Sample count is per
reported active position; processes independently reinitialize the engine.

| Context | Arm | Decode tok/s | CV % | Attention ms/layer | Backend | Physical MiB | Peak physical MiB | Processes / samples |
|---:|---|---:|---:|---:|---|---:|---:|---:|
| 2048 | 8k | 16.966 | 8.42 | 0.996 | GPU | 998.54 | 998.56 | 1 / 3 |
| 2048 | 16k | 17.047 | 0.47 | 1.028 | GPU | 1317.53 | 1317.54 | 1 / 3 |
| 2048 | lazy16k | 17.187 | 21.19 | 0.998 | GPU | 677.24 | 677.96 | 2 / 6 |
| 4096 | 8k | 14.544 | 1.28 | 2.027 | GPU | 1158.41 | 1158.54 | 2 / 6 |
| 4096 | 16k | 14.644 | 1.06 | 1.986 | GPU | 1477.80 | 1477.99 | 2 / 6 |
| 4096 | lazy16k | 14.208 | 33.81 | 2.026 | GPU | 836.64 | 836.76 | 2 / 6 |
| 8192 | 8k | 9.816 | 3.24 | 4.169 | GPU | 1478.13 | 1478.87 | 2 / 6 |
| 8192 | 16k | 8.942 | 7.32 | 5.487 | GPU | 1797.71 | 1797.74 | 1 / 3 |
| 8192 | lazy16k | 11.202 | 11.57 | 4.100 | GPU | 1157.47 | 1158.13 | 2 / 6 |
| 16384 | 8k | 2.376 | 1.78 | 33.316 | CPU | 2118.83 | 2118.90 | 2 / 6 |
| 16384 | 16k | 7.728 | 0.02 | 8.087 | GPU | 2438.86 | 2438.90 | 1 / 3 |
| 16384 | lazy16k | 7.760 | 1.64 | 8.056 | GPU | 1798.06 | 1798.15 | 1 / 3 |

At 16K, legacy and lazy have only one idle-gated independent process each,
with three restored repetitions: token-time CV 0.02% / 1.64%, attention-time
CV 1.07% / 0.42%. This supports a large GPU-vs-CPU benefit and the memory
reduction, but provides low independent-process confidence for a 0.4% difference.
At 4K, the legacy arms have two processes/six samples and ~1% CV; lazy's 33.81%
token CV and 43.28% attention CV prevent claiming its apparent 3% slowdown is
a code regression. At 8K, 16K-legacy has one process and 21.6% attention CV;
its lower reported throughput is contaminated screening data, not evidence
that raising the cap slows the kernels. Exact min/max, p10/p90 and CV are in JSON.

The initial stable 4K matched round measured 14.544 / 14.537 / 14.454 tok/s
(legacy 8K / legacy 16K / lazy), with attention 2.027 / 2.011 / 2.018 ms/layer.
This is screening evidence of similar cost, not an equivalence proof. No
arithmetic/kernel changes are justified by the noisy differences.

## Boundary routing and measured performance

| Active KV | Legacy 8K tok/s | Legacy 16K tok/s | Lazy 16K tok/s | GPU layers: 8K / 16K / lazy |
|---:|---:|---:|---:|---|
| 8192 | 9.816 | 8.942 | 11.202 | 10 / 10 / 10 |
| 8193 | 4.512 | 10.970 | 11.252 | 0 / 10 / 10 |
| 16384 | 2.376 | 7.728 | 7.760 | 0 / 10 / 10 |
| 16385 | 2.344 | 2.409 | 2.383 | 0 / 0 / 0 |

All ten full-attention layers follow the stated route. Lazy preserves the 16K
GPU cap and defined CPU fallback from 16385. The apparent GPU speedup over
8K at 8193 is about 2.49×; those samples have ~13–15% token-time CV, so
confidence is lower than the large 16K result.

## Incremental prefill, warm TTFT and RSS

| Context | Arm | Eight-token suffix tok/s | Checkpoint-assisted TTFT ms | Restore ms | Peak RSS MiB |
|---:|---|---:|---:|---:|---:|
| 2048 | 8k | 18.015 | 456.08 | 8.25 | 2576.94 |
| 2048 | 16k | 18.721 | 439.50 | 8.47 | 2575.58 |
| 2048 | lazy16k | 15.448 | 530.72 | 6.55 | 2495.98 |
| 4096 | 8k | 15.760 | 524.13 | 12.65 | 2800.27 |
| 4096 | 16k | 15.769 | 523.49 | 12.26 | 2799.02 |
| 4096 | lazy16k | 15.263 | 538.03 | 8.81 | 2637.95 |
| 8192 | 8k | 4.859 | 1672.74 | 20.72 | 3266.98 |
| 8192 | 16k | 8.612 | 959.48 | 25.87 | 3265.64 |
| 8192 | lazy16k | 11.917 | 687.76 | 12.46 | 2946.09 |
| 16384 | 8k | 2.368 | 3413.59 | 28.27 | 4542.16 |
| 16384 | 16k | 2.893 | 2809.40 | 36.36 | 4895.22 |
| 16384 | lazy16k | 2.880 | 2804.63 | 20.68 | 4255.58 |

These measurements carry the same contention caveats as the decode table.
At 16K, lazy's RAM restore median is 20.68 ms versus legacy's 36.36 ms,
consistent with avoiding redundant GPU KV copies; the experiment is too small
to attribute that difference exclusively to copying. It is not cold-start TTFT.

## Engineering and validation

| Check | Result |
|---|---|
| Three separate benchmark binaries, identical optimization flags | PASS |
| Ordinary macro-disabled 8K, 16K and lazy builds | PASS; production infer untouched |
| 48 process exits / finite positive counter timings | PASS |
| Cross-arm/repeat greedy tokens and suffix next token | PASS |
| Ten-layer routing at 8192/8193 and 16384/16385 | PASS |
| Previous numerical/checkpoint correctness qualification | Retained at 38712216; not unnecessarily repeated |
| Python syntax and diff whitespace checks | PASS |
| Fully uncontended repeated independent runs at every context | NOT ESTABLISHED |
| Cold full-prefix prefill / end-to-end API TTFT | NOT RUN |
| Runtime optimization / production behavior change | None justified or applied |

New instrumentation is compile-guarded by `FLASH_GPU_KV_PERFORMANCE`. Production
arithmetic, selective checkpoint identity/version contract, KV ownership,
attention kernels and state restoration are unchanged. The only fixes are to
benchmark methodology: separate observer passes, bounded GPU-idle gating,
a longer post-exit settle interval, and preserving high-variance measurements
with explicit confidence limits.

## Reproduce with one command

```bash
cd '/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS'
python3 tools/benchmark_gpu_16k.py --build   --out '/Users/knagel/My Drive/Flash-iOS/Testing/gpu-16k-attention/performance-quiet-rerun'
```

The output directory must not already exist. Native Metal access is required.
The runner builds only `infer-perf-{8k,16k,lazy16k}`, uses DEVNULL stdin,
300-second process timeouts, bounds each idle wait to 60 seconds, and saves
partial results on a contention stop. It does not start an API server.
Use `--exploratory` only to deliberately collect labelled contended screening
data; such processes remain excluded when the idle gate fails.

Actual collection commands used two output directories, first with
`--rounds 2 --repeats 3 --suffix 8 --steps 4 --exploratory` and then the same
matrix with strict gating and `--idle-wait 60 --post-settle 2`. Exact per-binary
commands, fixture/binary hashes, utilization samples and parsed records are
in each `manifest.json`; exact historical runner copies are archived alongside.

Combine without rerunning inference:

```bash
python3 tools/report_gpu_16k_performance.py   '/Users/knagel/My Drive/Flash-iOS/Testing/gpu-16k-attention/performance-matched-20261022/manifest.json'   '/Users/knagel/My Drive/Flash-iOS/Testing/gpu-16k-attention/performance-confirmation-20261022/manifest.json'   --out '/Users/knagel/My Drive/Flash-iOS/Testing/gpu-16k-attention/performance-report-20261022'
```

## Evidence locations

Drive working mirror: `Flash-iOS/Testing/gpu-16k-attention/`:

- `performance-matched-20261022/`: first 24 processes, logs and hashes.
- `performance-confirmation-20261022/`: second 24 processes with 2 s settle.
- `performance-report-20261022/`: combined JSON/CSV/Markdown, source hashes,
  build logs, this report, scripts and compressed evidence bundle.
- `performance-pilot-exploratory-20261022/`: preliminary upper-boundary probe;
  excluded from the 48-process table.

Send `summary.json`, `summary.csv` and this report for architectural review.
For a further quiet run send its manifest, results JSON and all per-arm logs;
no need to send checkpoint/model payloads.
