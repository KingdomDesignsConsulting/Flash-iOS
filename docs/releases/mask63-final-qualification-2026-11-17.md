# Final qualification — November17,2026

Candidate source `e58cc0d95ad9f49d87fe8a5c553e7575e63fbd83`, binary `9f6ffea0ea70de6409e51978381968d57df9c2ee158a42bef3a35c063ce08da4`. No production operations. All large/private evidence under `/Users/knagel/Flash-iOS-Release/2026-11-17/`; benchmark-logs subdirectory holds build/native/canary logs. No logs/checkpoints/model data committed.

| Test | Actual result | Scope |
|---|---|---|
| Clean candidate + native probe build | PASS | Separate names; no installed infer overwritten |
| Native tools/API/warm-state | PASS, exits0/0/0 |45/29/36PASS log lines respectively; log lines are not asserted independent test counts |
| C11 pure admission / resource C tests |19cases /20checks PASS | No model |
| Actual-source preflight extraction |40cases PASS |8K/32K; synthetic resident bytes unchanged |
| Actual-source abort/cleanup extraction |18checks PASS | Deterministic model/transport stubs |
| Directory durability |8fault combinations PASS | Real helper, fake open/fsync/close; not power-loss durability |
| Combined Python unit suite normal |72test executions PASS | Includes inherited/reused fixtures; not72new independent scenarios |
| Same suite python-O |72test executions PASS | Same rejection behavior;9selected gate modules contain no removable assert |
| Tree verifier |12tests included in above | Includes65MiBfile and explicit metadata exceptions |
| Production-plan validator + existing supervisor |12+11 included above | Synthetic authorization records/tiny owned children; no production authorization issued |
| Header-only dependency |PASS |make-n-Wflash_serve_admission.h schedules normal rebuild; NOT executed infer target |
| Original32768numerical evidence revalidation |256endpoints PASS under normal and-O | Historical; no expensive rerun or threshold changes |
| Separate checkout static review |PASS bounded checks |47source hashes, admission/durability ordering; same reviewer |
| Full local archive restoration |PASS stored package |1.15GB/85entries; original-owner/provenance limitations explicitly open |
| Final live canary |BLOCKED_RESOURCE |Real startup only, no readiness or inference |

## Canary attempt and cleanup

GPU preflight[0,0,0] and host available8,166,588,416bytes passed; supervisor sampled7,909,523,456bytes immediately before launch. Owned PID38125 started **2026-11-17T01:45:17.567748-08:00**; stopped **01:45:20.865319-08:00**, exit-15 after seven samples. Host minimum6,397,526,016bytes was below required6,442,450,944; own RSS peak980,156,416bytes. Stop reason `host_reserve`. Process was reaped by its supervisor; no automatic retry or unrelated app termination. This demonstrates the external startup guard, not live native request-failure behavior.

Cold health, streamed/buffered completion, scalar-vs-mask63short comparison, resident continuation, named-profile capture/restart, EOS/follow-up, stale-session rejection, exact32768request admission,32769request rejection with real resident preservation, decode cancellation, injected resource interruption, finish/DONE/usage ordering, reset/restart, live complete tool emission and short/moderate performance are **NOT RUN on this final binary**. Earlier qualified source results remain separately labeled historical; no similar test was substituted for a final live PASS.

Remaining live command, only after capacity recovers and an exclusive window is reconfirmed:

```bash
cd '/private/tmp/flash-mask63-release-20261117'
PYTHONPYCACHEPREFIX=/private/tmp/mask63-pycache python3 tools/qualify_mask63_final.py \
 --out '/Users/knagel/Flash-iOS-Release/2026-11-17/canary-02' --operator-exclusive-model
```

The runner rechecks threeGPU<30readings, source/binary identity,6GiBreserve and16GiBRSS supervisor. It has a600sowned lifetime, strict timeouts and cleanup, no production port. Do not run blindly after failure. Do not lower thresholds; additional startup headroom is required. The current runner covers a bounded subset (health, usage, resident rejection/continuation, exact-budget decode cancellation/stale/fresh recovery). Passing that subset will still require the remaining profile/restart/EOS/tool/numerical checks above before complete canary closure.

## Exact model-free reproduction

```bash
cd '/private/tmp/flash-mask63-release-20261117'
PYTHONPATH=tools PYTHONPYCACHEPREFIX=/private/tmp/mask63-pycache python3 -m unittest test_work_a_gate test_work_a_missing_validation test_macho_rebuild test_work_a_summary test_release_binding test_recovery_tree test_production_plan test_c11_supervisor
PYTHONPATH=tools PYTHONPYCACHEPREFIX=/private/tmp/mask63-pycache python3 -O -m unittest test_work_a_gate test_work_a_missing_validation test_macho_rebuild test_work_a_summary test_release_binding test_recovery_tree test_production_plan test_c11_supervisor
clang -std=c11 -Wall -Wextra -Werror -I metal_infer tools/test_checkpoint_durability.c -o /private/tmp/mask63-directory-test
/private/tmp/mask63-directory-test
```

Do not rerun the build into the existing frozen binary name. For a justified new build use a new MASK63_RELEASE_BINARY name and create its own manifest/qualification. Model-free extraction scripts have legacy docs/results output defaults; prior original evidence was restored unchanged, with this run's new extracted results preserved privately. A new binary is not authenticated by a reused filename.
