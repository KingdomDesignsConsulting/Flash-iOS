# Compact exact-M2 verifier state bank — 2026-10-07

## Representation

The isolated verifier now retains one compact post-candidate bank. For every full-attention layer it stores the single K and V slot appended by row 0 plus the resulting KV length. It stores the mutable CPU convolution/recurrent arrays when those exist, the GPU DeltaNet and convolution buffers when GPU linear attention is active, and the row-0 hidden vector. The bank records copied Metal-buffer bytes and its total allocated footprint, including metadata.

The anchor remains a full `ServeStateSnapshot` in the validation harness. It is the rollback oracle for row-0 rejection and a convenient way to repeat deterministic tests. A production decode path already has the live anchor state and should avoid making an extra full-prefix snapshot merely for each speculative pair.

Row 1 does not need a second bank: after its transformer forward, the state and hidden vector remain live. The exact M2 LM-head reads normalized copies of the two hidden rows and does not modify model state.

## Transaction

1. Restore the anchor for the isolated trial.
2. Run candidate 0 through ordinary serial transformer code and capture the compact row-0 bank.
3. Run candidate 1 through ordinary serial transformer code, leaving row-1 state live.
4. Evaluate both LM-head rows with the exact M2 kernel.
5. On row-0 rejection, restore anchor; on row-1 rejection, restore the compact row-0 bank; on full acceptance, keep live row-1 state.
6. Advance any target fallback token once from the selected committed state. Accepted candidates are never replayed.

The compact restore validates all bank sections before it mutates state. For a full-attention layer it restores only the appended CPU K/V slot and the matching GPU mirror slot when present, then sets the KV length. It copies the saved recurrent/convolution state and hidden vector. The existing full snapshot path remains in the benchmark as a byte-exact oracle; all three acceptance cases run both implementations.

## Draft provider and isolation

`TargetVerifyDraftProvider` is a callback taking caller context and position and returning two candidate token IDs. An explicit `enabled` argument disables it without invoking the callback. The short harness uses a deterministic fixed provider to test both enabled and disabled behavior. No draft model is selected and no request/serving decode path calls the verifier yet. The compile-time `TARGET_VERIFY_EXACT_M2_INTEGRATION` guard remains required.

`FLASH_TARGET_VERIFY_PROMPT_TOKENS=/path/to/tokens.bin` can select a token fixture for the isolated benchmark. Without that environment variable the existing short built-in prompt is used. This does not alter normal serving.

## Validation and limits

The short test compares compact results with the full-snapshot oracle for full acceptance, row-0 rejection, and row-1 rejection, including logits, committed state/hidden, and fallback state/hidden. It prints per-case bank bytes, Metal-buffer copy bytes, capture/commit/rollback timings, and whether an additional GPU synchronization was needed. The reference bank footprint is 376.13 MiB for two full post-candidate snapshots.

The 2026-10-07 short run passed on both the live Drive build and the Git checkout build. Each reported `lm_bitwise=496640/496640`, `lm_max_abs=0`, `compact_oracle exact=yes` for accepted counts 2, 0, and 1, exact commit/fallback state and hidden values, coherent CPU/GPU KV mirrors, `continuation_after_full_accept exact=yes` after one more target step, and `RESULT: PASS`. The fixed provider passed both enabled and disabled checks. Accepted-token replay remained zero.

| Measure | Two full post-row snapshots | Compact row-0 bank |
| --- | ---: | ---: |
| Allocated bytes | 394,403,840 | 196,168,744 |
| MiB | 376.13 | 187.081 |
| Reduction | — | 50.26% |
| Capture, warmed Drive cases | 10.06–10.37 ms for two | 4.99–5.57 ms for one |
| Capture, initial Drive case | 55.94 ms | 16.12 ms |
| Reject row 0 restore, Drive | 5.05 ms | 4.77 ms (anchor restore) |
| Reject row 1 restore, Drive | 5.17 ms | 4.78 ms |
| Full accept restore, Drive | 19.50 ms | 0 ms; row 1 remains live |

The compact capture reads 130,252,800 bytes from Metal shared buffers; restoring row 0 writes 130,293,760 bytes including the appended GPU KV slots. It introduces no extra GPU synchronization beyond the existing completed transformer forward. These are short single-run timings, not stable throughput measurements. The Git checkout also passed; its warmed captures were 5.13–7.86 ms compact versus 9.69–9.97 ms full.

The optional fixture path also passed with an eight-token file and the same oracle/continuation checks. No multi-thousand-token run was performed.

The full-attention prefix is assumed immutable during the two speculative forwards; the production forward appends exactly one K/V slot per row. Recurrent/GDN and convolution state still require full-state copies, so the compact bank is expected to remain substantial. Timing is a short-run diagnostic and not a serving throughput result.

Before production enablement: validate a long context on Kevin's Mac, integrate a real draft producer, wire the verifier into serving with an explicit runtime disable path, and compare end-to-end ordinary versus speculative decode under the same workload. No long-context or production performance claim is made here.

## Kevin's deferred long-context check

Run these commands only when GPU utilization is below 30%. They are intentionally not part of this short validation.

```bash
cd "/Users/knagel/My Drive/Flash-iOS/metal_infer"
clang -O2 -Wall -Wextra -fobjc-arc -DACCELERATE_NEW_LAPACK \
  -I/opt/homebrew/include -DFLASH_PREFILL_NROW_PRODUCTION \
  -DFLASH_PREFILL_NROW_ASYNC \
  -DFLASH_PREFILL_NROW_GATEUP_M4_8ROW_BITSPLIT \
  -DTARGET_VERIFY_EXACT_M2_INTEGRATION \
  -framework Metal -framework Foundation -framework Accelerate \
  -lpthread -lcompression -L/opt/homebrew/lib -lzstd \
  infer.m -o "../Testing/Temporary Testing Files/Apps/infer-target-verify-exact-m2-compact"
```

Create a deterministic 4096-token stress fixture by repeating the existing 1024-token fixture. This tests state length and rollback identity; it is not a linguistic quality sample.

```bash
cd "/Users/knagel/My Drive/Flash-iOS"
python3 - <<'PY'
from pathlib import Path
import struct
source = Path('Testing/Temporary Testing Files/Resources/prefill-1k-1024.bin')
target = Path('Testing/Temporary Testing Files/Resources/prefill-4k-4096-from-1k.bin')
data = source.read_bytes()
assert struct.unpack_from('<I', data)[0] == 1024 and len(data) == 4100
target.write_bytes(struct.pack('<I', 4096) + data[4:] * 4)
print(target, target.stat().st_size)
PY
```

```bash
cd "/Users/knagel/My Drive/Flash-iOS/metal_infer"
FLASH_TARGET_VERIFY_PROMPT_TOKENS="../Testing/Temporary Testing Files/Resources/prefill-4k-4096-from-1k.bin" \
  "../Testing/Temporary Testing Files/Apps/infer-target-verify-exact-m2-compact" \
  --model "/Users/Shared/Main Hard Drive/AI Storage/AI Models/Reasoning/alexintosh/Qwen3.5-35B-A3B-Q4-Tiered-FlashMoE" \
  --tiered --no-malloc-cache --no-expert-prefetch \
  --bench-target-verifier-batched \
  2>&1 | tee "../benchmark-logs/exact-m2-compact-4k-$(date +%Y%m%d-%H%M%S).log"
```

Send the complete log, especially `compact_oracle`, `full_accept`, `reject0`, `reject1`, `state_bank_reference_mib`, `compact_bank_bytes`, timing/copy fields, and final `RESULT`. A genuine ordinary-serving versus speculative-serving A/B command does not yet exist because no real draft source is connected to HTTP decode; the isolated verifier benchmark is not a production throughput substitute.
