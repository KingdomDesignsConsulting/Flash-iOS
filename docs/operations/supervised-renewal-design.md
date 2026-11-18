# Supervised renewal: fail-closed implementation and drain blocker

November17,2026. Contract reviewed at281bd342693a2e2cd50774e02958e358d1d73a5b. Development branch `work/supervised-renewal-20261117`, based on production evidence c2a9cf82fecf20d84cf016a547d984090648e8f3. No production files/processes/approval records touched. No supervisor/native source edits.

## Disposition

**CONDITIONAL — MANUAL RENEWAL REQUIRED (NO RELIABLE DRAIN/IDLE SIGNAL)**

This is working policy/artifact verification tooling and a deterministic transition-kernel prototype, not an installable automatic native launcher. `--run` and `--stop-owned` explicitly fail closed without launching/signaling anything. There is no native backend adapter to circumvent that restriction. `--simulate` runs model-free tests only; no HTTP or model instance. A future qualified adapter must own its supervisor and admission barrier; arbitrary callbacks/plugins cannot be supplied through CLI.

## Source inspection and impossibility of a safe current idle check

Frozen infer.m `serve_loop`, lines20345–20440: synchronous accept, request read/parse, then GET/health returns static status/model. No active-request counter, admission-close command, generation identifier or drain handshake exists. An accepted health response only proves that earlier work on that synchronous loop completed; another connection may already be queued or arrive immediately afterward. Polling health, socket availability, log quietness or a PID cannot establish an atomic admission-close + idle interval.

Existing supervisor `supervise` owns a Popen process group, uses inherited cooperative flock, samples resource/birth identity and terminates at <=21600 monotonic seconds. Its stop Event is an owned control channel, not a drain primitive. Scheduled stop without a barrier can interrupt generation/partial tools. Neither resetting approval expiration nor sleeping until health succeeds fixes that race. The hard six-hour limit remains; it is not a seamless-drain promise.

A native change would change the frozen binary. An external admission proxy requires separately qualified exclusive admission, treatment of direct backend access, connection/body/stream lifetimes, shutdown races, client/session generations and timeout/error semantics. None is silently introduced here. The Architect explicitly permits manual renewal if this signal is absent. No additional exclusive-model window was requested because the prerequisite for a meaningful two-cycle native test fails, and current production must remain intact.

## Implemented files / invariants

`tools/supervised_renewal.py` provides:

- Separate recurring policy kind, explicit approval, owner-held regular0600/no-symlink read, SHA-bound snapshot, maximum24h validity, <=4 launches, >=60s spacing, target<=5h30m, immutable21600s per process, fixed6GiB/16GiB contract, allowed11241/isolated11251 ports. No cutover-plan import, refresh, shell eval, supervisor bypass or arbitrary engine options.
- Streaming checksums of binary, all47 source bindings,49 model files (with per-file stable inode/size/mtime), candidate/model manifests and required recovery archive/selection/profile-source/supervisor/resource-probe assets. No production probes or cache writes. Checkpoints remain runtime-validated mutable state; never hash-edit them or force compatibility. Schema is documentation plus structural machine-readable checks; executable validator is authoritative for filesystem/time/cross-field conditions.
- Exclusive owner0600/O_NOFOLLOW coordinator lock; never unlinks a lock. Existing child cooperative lock remains separate and unchanged. Immutable unique output directories, restrictive umask, state/reason evidence. No policy may run a native process because drain support is false.
- Transition kernel for deterministic tests: reverify before launches/ticks, compare PID+birth/generation, admission-close before idle, defer stop across active request, stop only owned identity, require reap/port/lock release before launch, fresh generation identity, launch cap and latched faults. This kernel is not connected to native processes. Readiness/checkpoint/resource checks are injected mocks, not claims of native qualification. Existing supervisor tests supply real tiny-child lock/lifecycle coverage.

Unsupported/unqualified: native process adapter, authenticated drain barrier, live recurring control channel, persistent generation marker/client notification, crash-recoverable coordinator ownership/journal, live startup/restore/SSE checks in coordinator, production migration. Mock state transitions are not substitutes. Fault logging/full-disk and policy edits need further race/fault qualification before a real launcher. No persistent stop-owned capability is implemented; it refuses rather than signaling a saved PID.

## Operator commands (development only)

From the isolated checkout:

```bash
python3 tools/supervised_renewal.py --build-policy --out /PRIVATE/NEW/template-run
python3 tools/supervised_renewal.py --simulate --out /PRIVATE/NEW/simulation-run
python3 tools/supervised_renewal.py --check-only --policy /PRIVATE/REVIEWED/policy.json --out /PRIVATE/NEW/check-run
```

Use unique nonexistent output directories on local private disk, outside synced Drive. Builder deliberately writes approved=false and invalid placeholder paths/times; it cannot authorize anything. Populate identities with independently verified hashes, never placeholders. No real approved recurring policy has been created. `--check-only` can hash large model/archive files; it is not a serving readiness check. `--run` will return BLOCKED after verification; do not install it as a launcher.

## Setup, disable, emergency stop and recovery

**Install: NOT AUTHORIZED / NOT QUALIFIED.** No LaunchAgent, cron, automation or KeepAlive entry installed. Disable: nothing to uninstall; retain manual foreground supervision. Existing production shutdown remains Control-C in its owned Terminal; never signal a historical PID, killall or port owner inferred by number alone. Do not run development mocks as service supervisors.

If future coordinator faults, it must latch BLOCKED and never retry, auto-rollback, execute partial tools or extend a lifetime. Current prototype cannot own a native child, so has no native emergency-stop behavior to exercise. Existing approved manual historical rollback remains separate and identity-bound; its weaker native context admission is unchanged. Recurring operations policy cannot authorize an older binary.

## Migration plan / remaining qualification

1. Architect approves a separately scoped drain/admission solution; preserve arithmetic/checkpoint identities and independently qualify races. If native control is necessary, re-freeze/requalify its new executable instead of accepting it under old hash.
2. Implement owned native adapter and crash-safe journal/control/generation channel. Reuse `supervise` directly with explicit clean environment, mask63/native admission, inherited single-model lock, telemetry and21600s maximum; no one-time-plan refresh. Block at policy expiry/launch count/rate/resource/failure.
3. Complete remaining fault matrix (journal/full disk/concurrent edits/orphans/listeners/readiness/streams) under normal/-O, then request an exclusive model window with existing production stopped by its owner. Two isolated11251 cycles on copied profile/caches, persistent restore, READY, SSE usage/DONE, resident follow-up and request spanning renewal boundary. Do not launch concurrently with current production or reuse its caches.
4. Record frozen script hashes and private evidence. Obtain **separate operational install/migration authorization** and a real recurring policy. Verify coherent recovery and owner/port, stop old foreground only via owner, confirm exit/lock release, then launch coordinator. No assumption that same-day cutover authorizes recurring restarts.
5. Clients receive explicit generation change, discard resident IDs/resend full history, never blindly retry uncertain external tools. Manual rollback stays separately authorized. No unattended renewal claim until these gates pass.
