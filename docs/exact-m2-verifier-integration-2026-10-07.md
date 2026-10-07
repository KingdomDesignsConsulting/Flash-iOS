# Exact M2 two-candidate verifier integration — 2026-10-07

Status: **compact state bank validated in short Drive and Git runs; production serving remains unchanged. Long-context validation is deferred to Kevin.**


## Compact-bank update (2026-10-07)

The original `target_verify_exact_m2_pair(...)` and its two full `ServeStateSnapshot` banks remain inside the isolated harness as a correctness oracle. The new `target_verify_exact_m2_pair_compact(...)` keeps only one post-row bank: the appended full-attention K/V slot and length for row 0, mutable CPU/GPU recurrent and convolution state, and the row-0 hidden vector. Row-1 state stays live on full acceptance. The harness runs both implementations for full accept, reject row 0, and reject row 1, then compares logits, committed state, hidden, and CPU/GPU KV mirrors byte for byte. Fallback advancement remains the ordinary serial forward and accepted rows are not replayed.

Both short model runs (Drive source and Git checkout) passed: `496640/496640` exact LM-head logits, `lm_max_abs=0`, exact state/hidden after commit and fallback, all three `compact_oracle exact=yes` cases, and one additional deterministic continuation step after full acceptance. The compact bank is `196,168,744` bytes (`187.081 MiB`) versus `394,403,840` bytes (`376.13 MiB`) for the two full reference banks, a `50.26%` reduction. Warmed Drive capture was `4.99–5.57 ms` for one compact bank versus `10.06–10.37 ms` for two full snapshots; compact row-1 restore was `4.78 ms`, row-0 anchor rollback `4.77 ms`, and full acceptance needed no restore. Capture copies `130,252,800` bytes from Metal shared buffers; row-0 restore writes `130,293,760` bytes including appended GPU KV. No extra GPU synchronization was introduced. These single-run timings are diagnostic only.

A generic two-token draft-provider callback is present and independently disableable. The harness tests it with fixed deterministic candidates. No real draft model or serving decode integration is active. The benchmark accepts an optional `FLASH_TARGET_VERIFY_PROMPT_TOKENS` fixture path for Kevin's later long-context run. See `docs/compact-m2-state-bank-2026-10-07.md` for representation, limits, and exact manual commands. The following full-snapshot design sections document the historical oracle path.

## Why this path

The exact-affine experiments established two separate facts:

1. The Q4 M2 kernel is bitwise identical to current Flash M1 for the tested ordinary affine shapes.
2. The much faster M8 `simdgroup_matrix` family cannot reproduce current M1 bits once per-element/per-lane accumulation has been collapsed to coarse group partials. Experiments 3–6 reconstructed the MMA dot-product steps exactly, but all tested scale/bias/group-accumulation hybrids remained non-exact.

Therefore the current exact verifier should build on M2, while the M8 work remains a separate future-arithmetic research path.

## Integration boundary

The new path is guarded by:

```text
TARGET_VERIFY_EXACT_M2_INTEGRATION
```

The current isolated validation reuses the historical batched-verifier CLI:

```text
--bench-target-verifier-batched
```

when `TARGET_VERIFY_EXACT_M2_INTEGRATION` is defined. The compile-time guard redirects that benchmark entrypoint to the exact-M2 transaction. A dedicated CLI name can be added later as cleanup; it is not required for the validated integration.

The reusable core is `target_verify_exact_m2_pair(...)` in:

```text
metal_infer/target_verify_exact_m2_integration.inc
```

The existing exact shader remains:

```text
metal_infer/prefill_probe/target_verify_affine_m2.metal
```

Normal serving does not compile/execute the integration unless the macro is enabled.

## Two-candidate transaction

Inputs are:

- an exact anchor `ServeStateSnapshot` and matching anchor hidden vector;
- two draft candidate token IDs;
- the ordinary production transformer/state machinery;
- the exact Q4 M2 LM-head projection.

Execution is deliberately conservative:

1. Restore the anchor and copy the anchor hidden vector.
2. Save the anchor hidden as LM row 0.
3. Teacher-force candidate 0 through the ordinary one-token production forward at `pos`.
4. Capture `state-after-row0` and its hidden vector.
5. Save that hidden as LM row 1.
6. Teacher-force candidate 1 through the ordinary one-token production forward at `pos+1`.
7. Capture `state-after-row1` and its hidden vector.
8. Apply final norm to copies of the two saved rows.
9. Project both rows in one exact M2 LM-head dispatch.
10. Compare target predictions against the two draft candidates and accept the longest exact prefix.

The transformer/state portion is still serial. This is intentional: the older layer-major multi-position experiment changed floating-point/state ordering and was not byte-exact. The present integration first establishes exact transaction semantics before any deeper multirow transformer refactor.

## Longest-prefix commit

The state bank is:

```text
anchor
state-after-row0
state-after-row1
```

with matching hidden vectors for each point.

Commit rules:

```text
pred0 != candidate0
    accepted = 0
    restore anchor
    fallback = pred0

pred0 == candidate0 && pred1 != candidate1
    accepted = 1
    restore state-after-row0
    fallback = pred1

pred0 == candidate0 && pred1 == candidate1
    accepted = 2
    restore state-after-row1
    no fallback from these two rows
```

Accepted candidates are never replayed.

On a rejection, the caller must advance the target fallback token once from the committed state before continuing generation. That forward is required target work and is not replay of an accepted draft row.

## Hidden state matters too

`ServeStateSnapshot` stores KV/recurrent state but not the current hidden vector. The verifier therefore banks:

```text
anchor_hidden
hidden_after_row0
hidden_after_row1
```

and restores the hidden vector corresponding to the selected state bank. A state-only rollback would be incorrect because the next LM-head prediction consumes the committed hidden vector.

## Exact M2 LM head

`target_verify_exact_m2_lm_pair(...)` loads the existing `dense_affine_q4_m2` shader and evaluates two normalized hidden rows against the resident Q4 LM-head tensors in one dispatch.

Contract:

- Q4 packed weights
- group size 64
- BF16 scale/bias
- FP32 input/output
- `HIDDEN_DIM == 2048`
- current Flash per-row FMA order and `simd_sum`

The validation requires all `2 * VOCAB_SIZE` logits to match two ordinary M1 LM-head calls bit-for-bit.

The integration intentionally rejects the GGUF Q6_K LM-head path because this exact M2 shader is for the resident affine Q4 format.

## Validation mode

`--bench-target-verifier-batched` in an isolated `TARGET_VERIFY_EXACT_M2_INTEGRATION` build reuses the existing deterministic target-verifier prompt and generated full-accept candidate sequence. It then checks three cases.

### Full accept

Use the two target-generated candidates unchanged.

Required:

- `accepted=2`
- M2 logits bitwise equal to two production M1 LM-head outputs
- committed snapshot exactly equal to serial state-after-row1
- committed hidden exactly equal to serial hidden-after-row1

### Reject row 0

Perturb candidate 0 so it cannot equal the target prediction.

Required:

- `accepted=0`
- fallback equals the serial target prediction for row 0
- committed state equals anchor exactly
- committed hidden equals anchor hidden exactly
- after advancing the fallback once, state and hidden exactly equal the serial reference after the correct row-0 token

### Reject row 1

Keep candidate 0 exact and perturb candidate 1.

Required:

- `accepted=1`
- fallback equals the serial target prediction for row 1
- committed state/hidden equal serial state-after-row0 exactly
- no accepted-token replay
- after advancing the fallback once, state and hidden exactly equal the serial two-token reference

The test prints:

```text
[target-exact-m2] RESULT: PASS
```

only if every check succeeds.

## Suggested verification build

Build an isolated binary; do not replace production `infer`:

```bash
cd "/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS/metal_infer"

clang -O2 -Wall -Wextra -fobjc-arc \
  -DACCELERATE_NEW_LAPACK \
  -I/opt/homebrew/include \
  -DFLASH_PREFILL_NROW_PRODUCTION \
  -DFLASH_PREFILL_NROW_ASYNC \
  -DFLASH_PREFILL_NROW_GATEUP_M4_8ROW_BITSPLIT \
  -DTARGET_VERIFY_EXACT_M2_INTEGRATION \
  -framework Metal \
  -framework Foundation \
  -framework Accelerate \
  -lpthread -lcompression \
  -L/opt/homebrew/lib -lzstd \
  infer.m -o infer-target-verify-exact-m2
```

Run:

```bash
./infer-target-verify-exact-m2 \
  --model "/Users/Shared/Main Hard Drive/AI Storage/AI Models/Reasoning/alexintosh/Qwen3.5-35B-A3B-Q4-Tiered-FlashMoE" \
  --tiered \
  --no-malloc-cache \
  --no-expert-prefetch \
  --bench-target-verifier-batched
```

After the isolated verifier passes, also rebuild the normal configuration and run `./infer --self-test-api` before pushing.

## Validation result — PASS

The integration was compiled with `TARGET_VERIFY_EXACT_M2_INTEGRATION` and executed on the Apple M4 against the Qwen3.5-35B-A3B tiered model. The exact M2 shader was loaded from the live Drive working tree.

Measured result:

```text
[target-exact-m2] full_accept accepted=2/2
    lm_bitwise=496640/496640
    lm_max_abs=0
    state_exact=yes
    hidden_exact=yes

[target-exact-m2] reject0 accepted=0
    fallback=248068 expected=248068
    commit_state_exact=yes
    commit_hidden_exact=yes
    fallback_state_exact=yes
    fallback_hidden_exact=yes
    replayed_accepted=0

[target-exact-m2] reject1 accepted=1
    fallback=271 expected=271
    commit_state_exact=yes
    commit_hidden_exact=yes
    fallback_state_exact=yes
    fallback_hidden_exact=yes
    replayed_accepted=0

[target-exact-m2] state_bank_reference_mib=376.13
    transformer_rows=serial_exact
    lm_head_rows=M2_exact
    serving_enabled=no
    draft_source=not_wired

[target-exact-m2] RESULT: PASS
```

This establishes all intended transaction invariants:

- both LM-head rows are bitwise identical to separate production M1 evaluation;
- full acceptance commits exact state/hidden after row 1;
- row-0 rejection restores the anchor exactly and advancing the target fallback reproduces the serial reference exactly;
- row-1 rejection commits exact state/hidden after row 0 and advancing its fallback reproduces the serial two-token reference exactly;
- no accepted draft token is replayed.

The original full-snapshot transaction is therefore correctness-validated. The compact update above validates the reduced representation against it; serving integration remains open.

## Historical baseline: correctness-first state banks

The original oracle deliberately uses complete `ServeStateSnapshot` captures for both post-candidate banks. This proved transaction semantics before the compact representation was added.

A full snapshot copies:

- prefix KV for every full-attention layer;
- CPU convolution/recurrent state when present;
- GPU DeltaNet state;
- GPU convolution state.

For long contexts, copying full prefix KV per speculative row is unacceptable and can erase the M2 arithmetic gain. The validated two-bank reference footprint is approximately **376.13 MiB**. This confirms that full snapshots are unsuitable for the production speculative-decode path.

The compact path now banks the state required for row-0 rollback:

- row 0's appended K/V slot and length rather than the whole prefix;
- the mutable recurrent/GDN and convolution state after row 0;
- the matching row-0 hidden vector.

Row 1 remains live on full acceptance, preserving the same commit rules without replay or a second post-row bank.

## Serving status

The normal HTTP decode loop still has no draft-token producer. Therefore this change does **not** enable speculative decoding in production serving and does not alter production token generation.

The remaining implementation sequence is:

1. run Kevin's long-context compact-state correctness check;
2. connect a real draft-token source to the existing provider interface;
3. call the compact verifier from decode when two candidates are available;
4. emit accepted draft tokens plus the target fallback when required;
5. preserve ordinary one-token decode as the fallback/disable path;
6. benchmark end-to-end decode rather than only affine kernels.

## Promotion status

The isolated exact-M2 transaction validation passed. This checkpoint is safe to version because the integration remains compile-time isolated and production serving is unchanged.

Promotion into the normal decode path is a separate decision and remains blocked on long-context validation, a real draft-token provider, and guarded serving integration.
