# C11-01 release admission and resource policy — November16,2026

Base reviewed Architect revision: `a50294f2909d5270a173c8c3acda026c113e1e16`; numerically qualified inference lineage21a0731. This opt-in engineering branch is `work/c11-resource-closure-20261116`. No production/Work B/PR2/PR3 change or promotion is authorized. C11-02 remains OPEN.

## Contract and mechanism

Unset `FLASH_SERVE_QUALIFIED_GPU_ONLY` retains legacy capacity, startup and inference behavior. Every explicitly supplied value except exact `1`, including an empty string, rejects HTTP inference admission. The existing normal inference Makefile dependency now includes the admission header; its timestamp regression passes.

In mode1, HTTP admission occurs before resident session replacement/restoration. Required logical position + incoming token count + maximum requested generation must be nonnegative and <=min(32768,GPU window,engine allocation). Widened arithmetic rejects overflow-sized input. Host free+inactive must be >=6GiB; the sample must succeed. Own-process RSS must be measured and <16GiB. Availability and RSS are distinct overlapping observations, never added as independent physical allocations. CPU allocation remains65536; GPU-only admission restricts the supported envelope rather than reducing allocations or changing attention arithmetic.

During an admitted request, a request-scoped, sticky resource guard samples at the next checked inference boundary after250ms: scalar/decode layer boundaries and existing N128 layer poll callbacks. The same6GiB and16GiB policies apply. Host/RSS telemetry failure also latches an abort. A final pre-publication poll prevents successful publication after a detected resource fault. The guard is disabled for ordinary requests, CLI generation, startup warmup and non-HTTP numerical oracles. The paired external supervisor covers startup and stalls. No background native thread, signal protocol, arithmetic, routing, template, checkpoint identity/version or conversation snapshot pool is introduced.

Detected failure goes through the existing checked-forward abort path. Pending GPU work is completed/discarded through existing lifetime fences; the partial session identity is invalidated and cannot be resumed. Buffered response is an explicit HTTP500 with session_invalidated/resend_full_history; SSE emits an error plus DONE without a successful finish/tool call. Disconnected clients receive no synthetic successful completion. This is invalidation, not restoration of the failed turn. A fresh request can recover after telemetry/pressure recovers; repeated pre-admission rejections preserve the prior completed session unchanged.

## External bound and exclusive operating envelope

Use `tools/supervise_qualified_serve.py` for any future qualified launch. It accepts only a separately named candidate binary in its own checkout, never installed `infer`, and forbids production port11241 or an engine port override. The operator must explicitly attest that other heavyweight models are stopped; this tool does not inventory production or other applications.

A fixed per-user `/private/tmp/flash-ios-qualified-model-UID.lock` prevents two cooperating qualified launchers. It is securely opened with no-follow/type/UID checks and never unlinked. The child inherits the lock descriptor, so a supervisor exit alone does not release it while that child remains alive. This is not a host-global arbiter of other users or manually launched/unmanaged models: the operator restriction is part of the supported envelope. Do not claim otherwise.

Before launch, host telemetry must pass and three GPU samples must be below30%. The new session/process group is owned by the supervisor. Every0.5s it reads host availability plus ONLY its child's RSS and creation identity via the separately built probe; no generic process inventory. Host below6GiB, own RSS>=16GiB, unavailable telemetry, changed child identity, operator cancellation or lifetime deadline stops only this process group. SIGTERM is followed after3s by SIGKILL if required. No auto-restart or retry. Maximum server lifetime21600s (six hours) is explicit, not an inference-request idle timeout.

The native guard may deliver an explicit request error first and leave the process usable if a transient fault clears. An external stop is nonrecoverable: the socket closes/EOF, no successful finish/DONE is fabricated, all resident IDs die with the process, and restart requires complete history/new sessions. Strict clients must treat an unfinished stream as failure and never execute partial tools. The supervisor does not proxy/rewrite HTTP or pretend it can deliver a JSON error after killing a process.

Neither sampled guard reserves memory nor provides a zero-latency OOM guarantee. A long GPU operation, I/O wait, output write or checkpoint operation can delay a native poll. External termination is the coarse bound; measurement subprocesses have3s timeouts. OS suspension, supervisor SIGKILL and unrelated allocation spikes remain limitations. If the Architect requires stronger guarantees or transparent preservation of a failed conversation, that needs further design review rather than silently broadening native transactions.

## Executed evidence

- Supplied19 admission assertions PASS (the Architect corrected the displayed count).
-40 actual-source integrated admission cases PASS, at8K/32K capacities; explicit empty now rejects; synthetic resident positions8190/32766 and turn7 remain unchanged across rejects.
-20 pure resource-guard checks PASS: below/equal/above reserve, failed host/RSS samples, RSS ceiling, sampling interval, sticky abort and explicit new-request recovery; disabled policy bypass preserved.
-18 actual-source checked-forward/error/cleanup checks PASS with model and transport stubs: resource abort after five layer stubs, deferred cleanup, prefill/decode invalidation, client disconnect, HTTP500/SSE error+DONE and clean fresh-request recovery.
-11 supervisor process tests PASS, using only tiny Python sleep/no-op children: prelaunch rejection, running telemetry failure, low host, RSS, cancellation, lifetime, changed birth identity, cooperating lock and inherited-lock lifetime. An unrelated fixture child survives; no real application is targeted.
-An actual macOS probe plus owned tiny Python child completed normally with six telemetry samples; no model or production process was used.
-12 synthetic offline provenance CLI cases PASS. These do not authenticate a real service, dependency role, backup archive or rollback.
-Native release target/probe builds PASS; tools/API/warm-state self-tests PASS. The isolated synthetic checkpoint test exercises ordinary checked writes/fsync/rename/unlink, not a live cache.
-Header-only `make -n -W flash_serve_admission.h` triggers a normal inference rebuild (PASS).

Preserved binary/synthetic artifacts: `/Users/knagel/My Drive/Flash-iOS/Testing/2026-11-16-c11-gdn-work/` (archive receipt binds admission code commitb8b3f16 and separate GDN commitda6a823).

Logs: project-root `benchmark-logs/c11-20261116/`; sanitized JSON in `docs/results/c11-20261116-*.json`. Compiler logs and native source/build hashes are retained. The46-file source freeze includes the new header. An initial extraction harness accidentally included the following newly added resource wrapper; its end marker was corrected without modifying the tested preflight. Another extractor initially selected a forward declaration; it now selects the actual error function definition. A Python bytecode-cache sandbox denial was resolved by putting pycache under/private/tmp. These are test-infrastructure corrections, not relaxed product assertions.

## Reproduction and separately gated live work

```sh
make -C metal_infer serve-resource-probe release-qualification RELEASE_QUAL_BINARY=infer-c11-resource-test
clang -std=c11 -Wall -Wextra -Werror -I metal_infer tools/test_qualified_serve_admission.c -o /private/tmp/c11-admission-test
/private/tmp/c11-admission-test
clang -std=c11 -Wall -Wextra -Werror -I metal_infer tools/test_c11_resource_guard.c -o /private/tmp/c11-resource-test
/private/tmp/c11-resource-test
python3 tools/test_c11_native_integration.py
python3 tools/test_c11_abort_paths.py
python3 tools/test_c11_provenance_offline.py
PYTHONPATH=tools PYTHONPYCACHEPREFIX=/private/tmp/c11-pycache python3 -m unittest test_c11_supervisor
```

Future operator-confirmed, safeguarded isolated model launch (NOT RUN here):

```sh
python3 tools/supervise_qualified_serve.py \
 --binary "$PWD/metal_infer/infer-c11-resource-test" \
 --probe "$PWD/metal_infer/flash-serve-resource-probe" \
 --model '/Users/Shared/Main Hard Drive/AI Storage/AI Models/Reasoning/alexintosh/Qwen3.5-35B-A3B-Q4-Tiered-FlashMoE' \
 --out "$PWD/benchmark-logs/c11-live-$(date +%Y%m%d-%H%M%S)" \
 --port 11248 --operator-exclusive-model -- --flash-profile c11-isolated-validation
```

The operator attestation is a real prerequisite, not a flag to supply speculatively. Native32768/32769 HTTP acceptance plus actual resident KV preservation, live cancellation and injected telemetry/resource loss remain NOT RUN. They need no broad16K/32K benchmark or256-endpoint repeat; count-only/render diagnostics and a short real conversation can target admission. Current host samples alone do not prove an exclusive model window or enough incremental model memory. No installed production investigation was used to infer one.

## Status

**C11-01: PARTIAL.** The two previous code issues are resolved and the implemented opt-in resource policy passes bounded model-free/build tests. Actual live state/transport validation and Architect acceptance of the explicit supervision/operating limitations remain gates. C11-02 stays OPEN pending separately authorized actual deployment provenance and rollback evidence. GDN research has a separate branch/result and cannot close either gate.
