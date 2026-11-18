# Renewal development qualification — November17,2026

**CONDITIONAL — MANUAL RENEWAL REQUIRED (NO RELIABLE DRAIN/IDLE SIGNAL)**

Native production remains intact. No native binaries, numerical flags, checkpoint identities, supervisor files or operational approval records changed. No model launched/stopped; no production endpoint requests. Contract281bd34 reviewed; basec2a9cf8. Future publication commit identifies tooling, not frozen native source.

## Executed commands

```bash
PYTHONPATH=tools PYTHONPYCACHEPREFIX=/private/tmp/mask63-pycache python3 -m unittest test_supervised_renewal test_c11_supervisor test_production_plan test_historical_recovery_plan
PYTHONPATH=tools PYTHONPYCACHEPREFIX=/private/tmp/mask63-pycache python3 -O -m unittest test_supervised_renewal test_c11_supervisor test_production_plan test_historical_recovery_plan
```

**55 unittest methods PASS in each interpreter**, including subtest matrices (not counted as separate methods). Existing supervisor/one-time/rollback tests remain unchanged. Tests use temp directories/tiny Python processes; no weights/Metal execution.

| Coverage | Evidence / limit |
|---|---|
| Recurring approval absent/expired/replayed/UID/mode/symlink | PASS model-free |
| Frozen binary/source bytes, manifest, model, recovery and profile bytes; wrong artifact location | PASS actual synthetic file hashing/rejection; full production assets NOT accessed, native launch disabled |
| Competing coordinator | PASS real flock refusal |
| Competing cooperating supervisor / inherited lock | PASS existing tiny-child tests; child retains lock after parent FD closes |
| Birth mismatch / stale PID | PASS mock kernel no stop; existing supervisor sampled birth test |
| Two clean renewals / hard21600 per generation | PASS deterministic mocks only, no actual engine cycles |
| Request spans target boundary | PASS mock request active => close admission/defer stop, completion => new generation |
| No idle/barrier | PASS BLOCKED; no blind stop/restart |
| Host/RSS/telemetry failure / unexpected child exit | PASS tiny supervisor and latched kernel tests |
| Checkpoint/health/partial-stream failure | PASS mock readiness failure, no retry; NOT live checkpoint/SSE qualification |
| Foreign listener / orphan lock / unreaped child | PASS mocks no relaunch |
| Policy expiry / policy-check failure / rate and count | PASS deterministic faults |
| Native two isolated cycles + spanning request | NOT RUN: missing required admission/drain barrier; production currently operating |
| Production migration/install | NOT RUN / NOT AUTHORIZED |

Remaining unqualified fault cases include actual native-adapter port race, real concurrent policy mutation during launch, durable journal crash recovery, disk-full evidence failure, generation client notification, native checkpoint failure/partial stream handling. No generic claim that the full contract matrix passed. README/design gives exact next steps and owner-safe manual operating procedure.

No live canary evidence is invented. Under the contract's explicit fallback, lack of trustworthy drain/idle control retains manual renewal rather than attempting an unsafe two-cycle experiment.
