# N128 prefetch ownership repair — 2026-11-02

Short repair qualification PASS; overall release qualification remains open. Production/defaults remain unchanged and PR #2 remains draft. Starting published progress HEAD: `24d6cc4cef2c8b852b63f4d3af3dcf55b30090c6`.

The live SDK smoke exposed a second-stateless-request defect missed by the independent fresh-process histories. The first request matches scalar exactly. In the second, the completed N128 slab at 128 matches, then active state diverges at 129. Fresh scalar replay reproduces all 208 scalar HTTP observations; the candidate first differs at 129. The earlier 16K/32K single-history results remain valid for their measured paths and do not establish multi-request safety.

An authenticated producer-ordered layer-0 capture proves that mid-state, shared expert output, expert order and the first two routed expert outputs match. The other six expert outputs are stale and their combine weights are zero. Maximum active persistent-state error at 129 is **18.87463927268982**, well above the unchanged `<1e-3` limit; this is not harmless rounding. The original state fingerprints reproduce with diagnostics enabled. Existing `--no-expert-prefetch` restores exact state at all 81 candidate observations through 207, isolating the scheduling dependency.

Decode-only prefetch remained enabled across requests. An N128 attention-capture call could launch a short temporal prefetch, then return before the expert-read consumption path. That leaves an unrelated short read in the global async slot. A later scalar-tail wait can apply its short validity array to the eight routed experts, zeroing six weights after provisional CMD3 gating. Successful later I/O does not repair dispatches already encoded without those experts.

The narrow repair drains old async scratch writes and resets decode-only prediction/prefetch flags after request admission, before restoring or mutating model state. Capture-only N128 calls also cannot launch temporal prefetch. Default decode prefetch remains enabled. No kernels, routing/tie policy, template, sampling rules or numerical limits change; no state rebasing, pools or new checkpoint format.

Eligible tiered GPU N128 now hashes the explicit **`nrow-prefetch-ownership-v2`** execution marker. Old identities aliased prefetch on/off, so the entire affected class is invalidated once, including its currently disabled-prefetch variant. Scalar and CPU-linear identities retain their prior policy. Global execution version 3, storage/layout versions and disabled full-executable hashing remain unchanged. This is a state-correctness invalidation, not rebuild invalidation. Affected profiles require one rebuild when this repair is eventually approved for use; subsequent unrelated rebuilds remain compatible.

The diagnostic extension is opt-in: `FLASH_SESSION_STATE_DUMP_COMPONENT=active`, a single position (all-active dumping capped at 512) and optional trace identity select private native float32 captures. An ordered blit records actual combine operands/output after the producer without an early fence or state writes. Captures are authenticated against original observations before interpretation. Unused combine padding is excluded.

## Executed evidence

| Test | Result |
| --- | --- |
| Original SDK two-request state | FAIL at 129; first request exact |
| Independent fresh scalar | Exact to scalar HTTP at all 208 positions |
| Prefetch disabled isolation | PASS: 81 exact candidate observations, through 207 |
| Repaired default-prefetch capture | PASS: all active tensors and all eight expert/combine vectors byte-exact; max error 0 at 129 |
| Three stateless turns | PASS against separate fresh scalar histories |
| Three resident turns with N128 deltas | PASS through 174, 325, 476 against independent scalar replay |
| Cache synthetic tests | PASS, including selective-marker/unaffected-identity property |
| Post-repair live checkpoint/long HTTP/performance | Pending; not inferred from the short repair |

The original SDK wording asks for a new literal on turn two but both scalar and candidate return the original literal. Native request IDs and full history are correctly forwarded. That negative model-behavior observation is preserved separately; matching text did not override the numerical failure. Installed GUI behavior is not claimed qualified.

## Reproduction

Use a new private output directory for every invocation. Three consecutive GPU readings below 30%, owned-process RSS/timeout and host-memory guards are enforced by the focused driver.

```bash
cd '/Users/knagel/.codex/worktrees/http-session-validation/Flash-iOS'
make -C metal_infer release-qualification RELEASE_QUAL_BINARY=infer-release-prefetch-fixed
PRIVATE_OUT="/Users/knagel/My Drive/Flash-iOS/Testing/HTTP-Prefix-Reuse/prefetch-rerun-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$PRIVATE_OUT"
python3 tools/qualify_prefetch_phase.py --binary "$PWD/metal_infer/infer-release-prefetch-fixed" --turns 3 --out "$PRIVATE_OUT/stateless"
python3 tools/qualify_prefetch_phase.py --binary "$PWD/metal_infer/infer-release-prefetch-fixed" --resident --turns 3 --out "$PRIVATE_OUT/resident"
```

Raw requests, tokens, tensor captures and reference binaries are private under `/Users/knagel/My Drive/Flash-iOS/Testing/HTTP-Prefix-Reuse/2026-11-02-mask63-release/final-safety/`. Logs are in the project-root `benchmark-logs/mask63-release-adapter-*.log` and `mask63-release-prefetch-*.log`. Sanitized measurements: `docs/results/prefetch-n128-ownership-2026-11-02.json`.
