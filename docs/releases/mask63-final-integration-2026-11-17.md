# Final mask63 integration — November17,2026

Execution/completion November17,2026 America/Los_Angeles. Branch `release/mask63-supervised-integration-20261117`; isolated worktree `/private/tmp/flash-mask63-release-20261117`. Production checkout, branch, port11241 and installed binaries were not changed or operated.

## Frozen candidate

Source `e58cc0d95ad9f49d87fe8a5c553e7575e63fbd83`; binary SHA `9f6ffea0ea70de6409e51978381968d57df9c2ee158a42bef3a35c063ce08da4`, 918,960bytes; `UUID: 361E0BE3-096A-3D6E-B362-2C81819FD33D (arm64) /private/tmp/flash-mask63-release-20261117/metal_infer/infer-mask63-supervised-20261117`. The manifest binds47runtime files. Build uses Apple clang21.0.0(2100.4.1.1), macOS SDK27.2 on26.7.1/25G241. Private exact build log SHA `a179f3acdf09bd5ebfa66fd0bab918d2ae404ec280a3d17fbbc10bce41a8b1e8`. Subsequent recovery/supervisor/report commits do not alter those47runtime inputs; their final publication SHA is supplied in the handoff. The binary was built from the frozen source, not relabeled as a later documentation commit.

## Source-selection matrix

| Selection | Revision / handling | Rationale |
|---|---|---|
| Numerical runtime and ownership repair | Base21a073174fb1feb828f2d28762293d1803e66a9a, includesac06b920… | Preserve256-endpoint qualification |
| C11-01 admission/supervision | Reviewed focused commits9c8b97d through2cb51d9, cherry-picked with provenance; final admitted runtime matches2cb51d9 before narrow durability change | No branch merge; pre-mutation capacity/reserve, sticky failure, owned external supervision |
| C11-06 |31d09eb, explicit ValueError checks in5evidence modules, adapted tests | Cannot disappear under python-O; no numerical threshold changes |
| C11-07 |e58cc0d, new warm_checkpoint_durability.h and caller check | Directory open/fsync/close failure returns failure and suppresses pruning; rename visibility is not undone |
| Clean build |e58cc0d, new mask63-supervised-release target | Explicit FE027 and lazy32K flags, no session diagnostics; refuses existing output and infer name |
| Work B |d2d383e… inspected, NOT imported | Native-only initial contract; adapter/GUI/MCP claims excluded |
| GDN research |9524b591… evidence retained, NOT imported | No GDN arithmetic/diagnostic filename changes |
| Work D audit |1e68fab… used as evidence, NOT merged | Extended actual backup beyond five small artifacts |

Remote start refs matched nominated heads: Work A21a0731, admission2cb51d9, Work Bd2d383e. No newer source was silently substituted. Both original engineering branches remain untouched. Native-only and optional adapter contracts are distinguished in the machine-readable contract: the optional adapter needs finite configured deadlines and separate combined live acceptance; its70isolated tests do not qualify this build.

## Numerical/source proof and focused review

42of45original runtime inputs are byte-identical to21a0731. Changed original files are only infer.m (reviewed admission/abort guards, no FP arithmetic), Makefile (dependencies and separate target), warm_state_cache.inc (save durability). Two headers are added. Attention/combine/GDN/conv kernels, expert routing/prefetch arithmetic, tensor layouts, serializer format and selective compatibility identities are unchanged. No Qwen template change, tolerance relaxation or whole-binary cache invalidation. The42unchanged paths are retained in private numerical-binding.json.

The original32768gate was revalidated under normal and optimized Python:256endpoints, exact persistent fingerprints, all required ten-layer GPU boundaries. This authenticates historical evidence, NOT a new full-model integrated qualification. Accepted historical maxima remain state0, hidden4.76837158203125e-7, logits5.7220458984375e-6. No complete oracle was rerun because no arithmetic dependency changed.

Separate detached review checkout `/private/tmp/flash-mask63-final-review-20261117` at e58cc0d verified all47hashes, admission ordering before resident continuation and durability failure return before pruning. This is a separate-checkout review by the same engineer, not an independent human reviewer. Final Architect review remains required.

## Diagnostic audit

Build command `make -C metal_infer mask63-supervised-release serve-resource-probe`. Effective inference flags: `-O2 -Wall -Wextra -fobjc-arc -DACCELERATE_NEW_LAPACK -I/opt/homebrew/include -DFLASH_PREFILL_NROW_PRODUCTION -DFLASH_PREFILL_NROW_ASYNC -DFLASH_PREFILL_NROW_GATEUP_M4_8ROW_BITSPLIT -DFLASH_FE027_NUMERICS -DFLASH_EXPERIMENTAL_LAZY_SHARED_GPU_KV_32K`; normal Foundation/Metal/Accelerate,pthread,compression,Zstd links. No FLASH_SESSION_STATE_DIAGNOSTICS or qualification-only macro. Resource-arm, test-system-prompt and test-cache-root strings are absent. Existing model-free self-test entry points remain intentionally available.

C11-07 changes neither checkpoint format nor compatibility version. fsync failure after rename means the new file is visible but directory durability unconfirmed; the function returns0 without profile/budget pruning. It does not restore a prior same-path target, promise hardware power-loss durability, or redesign transactions. Eight deterministic syscall-fault cases pass; no intentional power-failure test was done.
