# Token lifecycle trace audit — 2026-10-26

Branch: `experiment/http-resident-prefix-reuse-20261023`
Reviewed HEAD: `99b30b18bd23270ea9a2aeb90e3636d18b6b6c66`
Status: SOURCE REVIEWED; new tracing NOT IMPLEMENTED or LIVE-TESTED.

## Verified from current `metal_infer/infer.m`

- At the HTTP decode loop around line 21568, `generated_token_ids` appends `next_token` before the thinking-budget handoff/substitution at approximately 21650-21670. Consequently the trace represents an *attempted/pre-substitution* token, not necessarily the token forwarded to `run_all_layers_checked`.
- The EOS branch forwards the EOS ID and calls `discard_deferred_experts()`; the normal-token branch forwards the effective `next_token` and calls `complete_deferred_experts()`. In either case `pos++` follows successful calls.
- The JSON trace is emitted after session preservation/invalidation; its `end_pos` is reset to zero for failed or non-reusable sessions, so it cannot represent the last attempted decode position.
- The trace lacks per-token completion, effective forwarded IDs, request start position, and an explicit commit/rollback event.
- A tool/schema failure or SSE disconnect may occur after sampling but before forwarding.

## Minimal next implementation

Under the existing opt-in `FLASH_SESSION_TOKEN_TRACE_DIR`, record per decode attempt an ordered event with sampled ID, effective forwarded ID, input position, reason for substitution, forward_started, forward_completed, deferred_completed, and post-request session acceptance. Capture the effective ID immediately before `embed_lookup` on both EOS and non-EOS branches. Mark completion only after the relevant deferred completion returns successfully and `pos++`; do not infer this from output count. Preserve the legacy `generated_token_ids` meaning and mark it `attempted_pre_substitution` for backwards compatibility.

Keep events private in the test trace directory, disabled by default. No inference mathematics, production binary, checkpoint compatibility or serialized state changes.

## Immediate gate

Existing generated trace commits `16c0f6c` and `32ff71b` have not been shown to compile or pass a live Mac test. First compile and run them on isolated 11243; investigate any observed divergence before adding GPU state fingerprints. The trace above is not sufficient for reconstructing exact effective resident history or claiming KV/GDN/convolution equivalence.
