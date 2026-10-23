# Current-engine GPU full-attention 16K qualification, 2026-10-22

Verdict: **16K QUALIFIED for the tested current-engine configuration and fixtures.** The implementation remains opt-in on `experiment/gqa-16k-attention-20261019`. This is neither a production promotion nor a 32K/64K qualification. Starting revision: `66674cab0e503b4d2465b70ab1d12e359c9927e7`.

## Corrections

- Lazy shared KV now uses a 16384-token GPU view and retains the larger CPU mapping for fallback from active KV length 16385. The default CPU capacity remains 65536; this does not mean 64K GPU attention is enabled.
- Each lazy KV cache owns its Metal views. A Metal deallocator releases the complete mmap only after the final resource reference disappears, including references retained by in-flight command buffers. Freeing an older cache clears a global slot only if it still refers to that cache, so it cannot detach a newer session's view. Partial wrapping failures release successfully adopted mappings through their owner and directly unmap only unadopted mappings.
- The attention score stride is derived from the actual allocated score buffer, rather than the compile-time GPU cap. This prevents out-of-bounds indexing when runtime context allocation is smaller than the GPU cap.
- Snapshot capture completes deferred GPU work before reading state. Restore waits for actual pending GPU work independently of the forward-error latch, then validates the entire snapshot before changing any layer. It can therefore recover a valid anchor after a latched inference error and rejects malformed later-layer state transactionally.
- Optional boundary diagnostics now report every full-attention layer and use real newline framing.

No attention arithmetic or Metal kernel was rewritten. Existing checked CMD1/CMD2 waits and serial-queue dependencies remain the synchronization boundary for CPU/GPU visibility; shared memory is not used as a substitute for command completion. Mmap supplies zero-initialized backing. GPU access is limited to the view; CPU fallback retains the tail of the same allocation.

## Current-source harness

`metal_infer/gpu_kv_qualification.inc` is compiled only with `FLASH_GPU_KV_QUALIFICATION`. It uses the actual current engine, snapshot functions, warm-state save/load, and transformer forwards. `tools/qualify_gpu_16k.py` launches subprocesses with `stdin=DEVNULL`, captured logs, explicit exit checks and a 240-second timeout per arm. Every output directory must be fresh. It retains manifests, source and binary SHA256 hashes, fixture hashes, command lines, logs, and machine-readable numeric reports. Temporary numeric dumps are removed after comparisons; immutable fixtures are never overwritten.

Historical checkpoints contain the model's active 2-MiB GPU GDN state per layer, whereas this current revision snapshots the full fixed 4-MiB GPU allocation. The qualification-only importer validates the original format, identity constants, geometry, file length and payload checksum, copies the active bytes exactly, and zero-pads the unused allocation tail. It does not relax production checkpoint validation. The current 4-MiB representation is then saved, loaded and compared exactly through the current persistence functions. Hidden files have independent SHA256 identities and the same starting hidden is used in every arm.

Each boundary arm performs five greedy forwards plus an exact first-step rollback/replay. It verifies all ten KV lengths, CPU/Metal coherence, unchanged prefix KV bytes, and exact persistence recovery. A deliberately changed early snapshot K value combined with an invalid later KV length must reject without any early-layer mutation. A latched forward-error recovery must still restore exactly. Lazy-cache lifetime testing performs three allocate/replace/free cycles while a Metal fill command still retains the older view, verifies GPU output after cache destruction and checks that freeing the old cache preserves the newer global view.

All recurrent arrays are compared: CPU convolution and GDN, plus all 30 GPU convolution and GDN buffers. K/V numerical dumps cover the appended positions; the entire pre-existing prefix is separately required to remain byte-identical to the loaded anchor.

## Results

The final lower suite used active KV lengths 8192–8196. The final upper suite used 16383–16387. Arms were 8K control, legacy 16K, lazy 16K, and lazy 16K with full-attention CMD12 chaining disabled. All processes exited 0. A final two-arm upper regression confirmed the strengthened malformed-restore assertion.

| Check | Result |
| --- | --- |
| Makefile builds: control, legacy16K, lazy16K, qualification arms | PASS, no compiler warnings |
| Lazy16K vs legacy16K, hidden/logits/KV/CPU+GPU recurrent | PASS, all SHA256 identities equal; max_abs=0, RMS=0 |
| Greedy token agreement across all four arms | PASS at all ten sampled positions |
| All ten full-attention layers GPU through KV 16384 | PASS |
| All ten layers CPU at KV 16385–16387 | PASS |
| CMD12 full-attention enabled and disabled | PASS under numerical criteria |
| Original fixture integrity and exact current-format disk round trip | PASS |
| Exact rollback/replay including recurrent state and hidden | PASS |
| Malformed later-layer restore leaves early live state unchanged | PASS |
| Restore with latched forward error | PASS |
| Lazy mapping lifetime and old/new cache ownership | PASS |
| NaN/Inf in compared hidden/logits/KV/recurrent arrays | None |
| 128-token runtime score allocation, Metal API validation, normal CLI shutdown | PASS |
| 32K/64K GPU rollout, serving throughput, prolonged multi-session HTTP soak | NOT RUN; outside this qualification |

Greedy sequences:

- KV 8192–8196: `248068, 271, 248069, 271, 760`.
- KV 16383–16387: `11177, 310, 7604, 5307, 26847`.
- The 65-token short fixture reports subsequent sampled IDs `279, 696, 87` in all 8K/16K/lazy arms, with runtime capacity 128 and the lazy baseline at 65536. The ordinary CLI reports three subsequent IDs for four requested tokens; the boundary harness explicitly reports all five sampled tokens.

Numerical criteria were set before comparisons: lazy vs legacy16K must be bitwise exact; CPU/GPU or chained/unchained comparisons require identical greedy tokens, no nonfinite values, relative L2 <= 1e-4, and max_abs <= 1e-3 + 1e-4 * reference_max for every field at every step. These are explicit acceptance criteria for this finite qualification, not a proof of equivalence for every prompt or future generation length.

Maximum absolute differences across the five steps of each CPU8K-vs-GPU16K comparison:

| Field | Lower boundary | Upper boundary |
| --- | ---: | ---: |
| Hidden | 4.22000885e-05 | 3.19480896e-05 |
| Logits | 7.77244568e-05 | 3.76939774e-04 |
| Appended K/V | 1.85966492e-05 | 3.18527222e-04 |
| CPU recurrent | 0 | 0 |
| GPU recurrent | 5.34057617e-05 | 9.05990601e-04 |

Maximum relative L2 was 2.20187942e-05. Chained vs unchained lazy16K stayed below max_abs 2.28881836e-05 and relative L2 1.48217828e-06. Every comparison met the predeclared criteria. CPU fallback comparisons are numerical agreement, not bitwise equality. No speed conclusion is drawn from these potentially contended runs.

## Saved evidence and reproduction

Drive root: `/Users/knagel/My Drive/Flash-iOS/Testing/gpu-16k-attention/`.

- `current-qualification-20261022-final-lower/{manifest,report}.json` and four arm logs.
- `current-qualification-20261022-final-upper/{manifest,report}.json` and four arm logs.
- `current-qualification-20261022-transaction-regression/` contains the final strengthened two-arm upper regression.
- `current-qualification-20261022-small-context/` contains Metal-validation CLI logs and report.
- Build logs: Drive `benchmark-logs/gpu16k-qualification-build-20261022.log` and `gpu16k-final-build-20261022.log`.

Build from the experimental checkout:

```sh
cd '/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS'
make -C metal_infer gpu-kv-qualification lazy16k-experiment gpu16k-experiment gpu8k-control
```

Reproduce the final upper boundary with a fresh output name:

```sh
python3 tools/qualify_gpu_16k.py \
  --out '/Users/knagel/My Drive/Flash-iOS/Testing/gpu-16k-attention/recheck-upper-20261022' \
  --anchor '/Users/knagel/My Drive/Flash-iOS/Testing/gpu-16k-attention/boundary-16384/seed-cache/explanation/16382/anchor.state' \
  --pos 16382
```

For the lower boundary use `--pos 8191` and anchor `/Users/Shared/Main Hard Drive/AI Storage/Apps/gqa-qual-20261018/cache/explanation/8191/anchor.state`. Run `python3 tools/qualify_gpu_kv_small_context.py --out FRESH_DIRECTORY` for the small runtime-context regression. No required local test remains for the scope above. Longer generation, additional corpora and HTTP soak are reasonable later expansion gates, not results claimed here.
