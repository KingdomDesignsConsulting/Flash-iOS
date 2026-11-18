# Flash-iOS safe production renewal — implementation contract (2026-11-17)

**Status: ARCHITECT DESIGN / ENGINEERING HANDOFF — NOT IMPLEMENTED, NOT DEPLOYED.** Baseline: release evidence `c2a9cf82fecf20d84cf016a547d984090648e8f3`; native source `e58cc0d95ad9f49d87fe8a5c553e7575e63fbd83`; executable SHA256 `9f6ffea0ea70de6409e51978381968d57df9c2ee158a42bef3a35c063ce08da4`. Do not alter running supervisor PID84890/model PID84895, port11241, production caches, or existing approval files. The first supervised six-hour lifetime ends 2026-11-18 02:20:01 PST.

## Architectural decision

Provide **one owner-managed launch coordinator** wrapping repeated instances of the existing `supervise_qualified_serve.py`, not a daemonized inference child and not removal/extension of the tested 21600-second supervisor limit. Preserve opt-in mask63, 32768 prompt+maximum-output native admission, 6GiB host reserve, <16GiB own RSS, 3 GPU readings <30%, cooperative single-model lock, atomic tool publication, and session fail-closed semantics.

Do not self-generate `production_cutover_authorized` from an expired, historic record. The current `validate_production_plan` explicitly requires authorization expiry <=6h; simply refreshing `expires_unix` or copying true booleans is **not permitted**. A new **separately user-approved recurring operations policy** with explicit validity window, approved binary/source/model/cache/recovery hashes, identity-bound service owner, maximum restart count/frequency, approved port, and hard-stop conditions is required. This record authorizes only identical binary restarts, never arbitrary future deployments or rollbacks. Its builder should be an operator-facing CLI and must not silently mark user approval true.

## Required source review

- `tools/supervise_qualified_serve.py`: `supervise` creates one owned process group, child inherits flock lock, samples resource every0.5s, terminates on stop or max_seconds<=21600. `validate_production_plan` accepts a one-time bound record; its main() requires `--production-plan` for port11241. No scheduled renewal exists.
- `tools/launch_historical_recovery.py`: fallback is separate, requires its own approval and cannot be silently invoked by renewal.
- `docs/releases/mask63-production-final-2026-11-17.md`: production foreground supervisor starts20:20PST and expires02:20PST; renewal manually authorized; resident RAM sessions lost on restart; checkpoint restored691 tokens in425ms.
- `docs/releases/mask63-operational-recovery-2026-11-17.md`: source/binary/recovery and explicit env known; do not change historical fallback's weaker native context guard.

## Core invariant and state machine

Coordinator states: `PREPARED -> AUTHORIZED -> STARTING -> READY -> RUNNING -> DRAINING -> STOPPED -> VERIFYING -> READY`; any fault enters `BLOCKED` and requires operator action (not automatic retry). An unexpected subprocess exit is a fault, not a restart signal.

1. Create a private owner-only state and run directory outside production and synced Drive. Open an exclusive advisory lock; inspect owner/mode and *never unlink* an active lock. No second coordinator may start. Retain the existing child's lock semantics.
2. Before *each* cycle, validate the currently approved source/binary/model and stable 47-source manifest hashes; exact production port and no unknown listener; current recovery manifest; authorization policy expiry; resource admission. Do not mutate old cache/profile state, and do not accept a changed binary by same filename.
3. Start exactly one supervised child via existing subprocess ownership and telemetry logic, with a fresh unique run directory, no inherited unsafe environment, and no fixed archived authorization file copied into a new run. Record PID + birth identity + executable SHA/UID, profile and timestamps.
4. Health, readiness, and one bounded no-side-effect request after each start; verify response completion, usage, model identity, and profile restore; never treat `GET /health` alone as acceptance. If it fails, no repeated auto-launch; leave service down, retain logs and notify operator.
5. Draining/renewal **must not interrupt active requests or partially executable tool calls**. Verify whether the native server exposes a reliable inflight-request count / readiness-to-drain endpoint and whether a graceful close to admission exists. If absent, add *separately qualified* minimal drain/idle coordination or **do not automatically renew**: stop at the six-hour bound and leave service down rather than blind restarting. Current `serve_loop` is synchronous, but port free/health does not prove idle. Do not infer idleness from inactivity on stdout alone.
6. Target renewal well before 21600s (e.g. 5h30m), but only after a verified idle/drained interval, within the separate recurring authorization and with enough margin for startup. The six-hour hard deadline is never extended; if idle cannot be verified, no forced renewal disguised as seamless.
7. Request graceful stop through **only the child supervisor's owned control channel**; verify process exit, inherited lock release, port exit, and absence of active writers. No `killall`, unknown PID, stale PID, or port-based kill. Reuse the currently reviewed termination policy; escalation only to its verified own process group.
8. Repeat fresh launch admission and restore `main-agent` checkpoint subject to exact source/operator identity. Publish a new service generation; old resident session IDs are invalid. Clients must resend full history and never retry uncertain external tools. Persist a generation marker for clients/health responses or explicit restart notification, without leaking session or prompt contents.
9. On resource violation, telemetry failure, mismatch, restart storm, missing backup, unknown owner, expired authorization, failed checkpoint or malformed stream: BLOCK, never automatic rollback to older executable (requires distinct recovery authorization). Preserve diagnostics.

## Coordination with ongoing foreground production

**Never touch the current foreground supervisor.** New coordinator development/tests run only isolated mock/tiny children, and then an isolated nonproduction port with separate profile/cache if operator grants an exclusive model window. Installation of a LaunchAgent/scheduled task and migration of existing 11241 ownership requires a *distinct explicit operational approval*. The current foreground service must first be gracefully stopped by its owner, with no unexpected listener and current coherent backup reverified. No concurrent automatic launcher while the foreground server is active.

## Preferred implementation

- A Python coordinator + declarative owner-only JSON policy, built against existing supervisor APIs; CLI supports `--check-only`, `--simulate`, `--run` and `--stop-owned` with strictly separate authorization gates. No shell `eval`.
- Either a user LaunchAgent or an explicitly foreground coordinator selected later; **do not install/enable launchd by default**. LaunchAgent must not use `KeepAlive` to defeat fail-closed blocked state or cause restart storms.
- Never store passwords/tokens in a public manifest; private policy is 0600 and owned by the expected UID. Local clock changes should not extend an already running cycle; use monotonic lifetime timing and wall-clock validity only for explicit approval records.
- Existing `--max-seconds 21600` stays in the supervisor; the coordinator must not add an unqualified bypass.
- Optional alerts: local operator-visible log/status/notification for upcoming expiration, successful renewal, resource refusal, unexpected exit and failed readiness; avoid external network notification unless separately configured and approved.

## Deterministic model-free test matrix

At minimum test:
- Authorization absent, expired, wrong owner, world/group writable, changed candidate binary, wrong source/manifest/model, wrong port, same-binary record replay after policy expiry => all reject.
- Competing coordinator, competing cooperating supervisor, child lock inheritance, stale PID, PID reuse/birth mismatch, unexpected 11241 listener => reject/no signals to unrelated processes.
- Timed normal renewal at idle under synthetic monotonic clock; before expiry but no idle => safe BLOCK/STOP rather than active-request interruption; restart limited to policy count/rate.
- Total supervised child max lifetime <=21600 every generation; no uncontrolled retry after unexpected child exit, telemetry unavailable, low host reserve, RSS ceiling, failed readiness, partial HTTP response, checkpoint failure.
- Crash between stop and next start, process startup with port conflict, supervisor unexpected termination and orphan child lock, concurrent policy edit, log write failure/full disk.
- Preserves old/foreign tool-call non-retry semantics and native session invalidation across restart.
- Archive/recovery package unchanged; source hash checks and native context admission remain enabled.
- Tests under normal and `python -O`; release-critical validations must not rely on assertions.

## Live staged qualification (only after model-free passes, explicit exclusive window)

1. Isolated port, separate copied/staged profile and caches; no production process/11241 interactions.
2. Two full coordinator cycles each with authenticated actual model, health, bounded `READY`, streamed usage before DONE, resident follow-up, checkpoint save and subsequent restore. Shortened **coordinator renewal interval only in test configuration**, never shorten production supervision safeguards or skip approval. Test no active-request interruption with a deliberately slow/no-side-effect request. If no reliable drain mechanism, expected NO-GO automatic renewal.
3. Fault-injection on one owned isolated child, without real OOM, after response progress; verify no automatic execution of partial tools or restart storm.
4. Verify expected unique run directories, log hashes, supervisor PID and child birth identity, no model remaining after cleanup.
5. Final independent source/diff review, frozen script SHA and tests. Do **not** replay 32K oracle or modify Metal/GDN arithmetic for coordinator-only changes.

## Success criteria and deliverables

Create a separate branch such as `work/supervised-renewal-20261117` from verified current release tooling, not the production branch. Publish `docs/operations/supervised-renewal-design.md`, `docs/operations/supervised-renewal-test-results.md`, policy schema with **unauthorized example only**, model-free tests, staged canary evidence, exact install/uninstall/rollback instructions and a migration plan from current foreground supervisor. Describe the policy's allowed duration/restart rate explicitly; no unlimited evergreen authorization by default.

Report one of:
- `RENEWAL IMPLEMENTATION QUALIFIED — AWAITING SEPARATE OPERATIONAL INSTALL AUTHORIZATION`
- `CONDITIONAL — MANUAL RENEWAL REQUIRED (NO RELIABLE DRAIN/IDLE SIGNAL)`
- `NO-GO — SAFETY OR AUTHORIZATION FAILURE`

**Current production deployment stays unchanged until a separately reviewed and authorized migration.** The current service has already been accepted for the restricted six-hour supervised envelope; renewal is a new operational feature, not permission to retrofit a running process.
