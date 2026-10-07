# Exact M2 two-candidate verifier integration — 2026-10-07

Status: **validated on Apple M4. Production serving remains unchanged.**

## Decision

The current exact speculative verifier should use the Q4 M2 affine kernel. M2 is bitwise identical to current Flash M1 on the tested affine shapes. The faster M8 simdgroup-matrix family remains a separate future-arithmetic path because the tested MMA/hybrid formulations could not reproduce current M1 rounding exactly.

## Integration

The compile-time guard is:

`TARGET_VERIFY_EXACT_M2_INTEGRATION`

The reusable verifier implementation is:

`metal_infer/target_verify_exact_m2_integration.inc`

The validation entrypoint currently reuses `--bench-target-verifier-batched` when the compile-time guard is enabled. Normal serving builds do not execute this path.

The two-candidate transaction keeps:

- the anchor state/hidden;
- state/hidden after candidate 0;
- state/hidden after candidate 1.

Commit semantics are:

```text
row 0 rejected     -> restore anchor
row 0 accepted     -> commit state-after-row0
both accepted      -> commit state-after-row1
```

Accepted candidates are never replayed. On rejection, advancing the target fallback token is required target work, not accepted-token replay.

## Validation result

The isolated integration test passed:

```text
full_accept accepted=2/2
lm_bitwise=496640/496640
lm_max_abs=0
state_exact=yes
hidden_exact=yes

reject0 accepted=0
commit_state_exact=yes
commit_hidden_exact=yes
fallback_state_exact=yes
fallback_hidden_exact=yes
replayed_accepted=0

reject1 accepted=1
commit_state_exact=yes
commit_hidden_exact=yes
fallback_state_exact=yes
fallback_hidden_exact=yes
replayed_accepted=0

state_bank_reference_mib=376.13
transformer_rows=serial_exact
lm_head_rows=M2_exact
serving_enabled=no
draft_source=not_wired

RESULT: PASS
```

This validates the transaction invariants: exact two-row LM-head evaluation, exact longest-prefix state/hidden commit, exact rollback, exact fallback continuation, and zero accepted-token replay.

## Current limitation

The correctness reference uses two complete `ServeStateSnapshot` banks. Their measured combined footprint is approximately **376.13 MiB**, so they are not suitable for production speculative decoding.

The next implementation should bank only mutable speculative state:

- appended KV positions/lengths rather than copied prefix KV;
- dual recurrent/GDN state;
- dual convolution-tail state;
- matching hidden vectors.

## Serving status

No draft-token producer is wired into the normal HTTP decode loop yet. Production token generation is unchanged.

Next steps:

1. replace full snapshots with compact mutable-state banks;
2. validate the same accept/reject invariants with those compact banks;
3. add a draft-token provider;
4. wire the exact-M2 verifier into decode when two candidates are available;
5. retain ordinary one-token decode as the disable/fallback path;
6. benchmark end-to-end decode.
