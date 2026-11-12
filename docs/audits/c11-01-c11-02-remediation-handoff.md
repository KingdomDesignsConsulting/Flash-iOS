# C11-01 / C11-02 pre-production remediation handback

**Scope:** Proposed experimental mask63 candidate only. **Not production auditing, inventory or deployment.** Starting candidate: `21a073174fb1feb828f2d28762293d1803e66a9a`. Work A, Work B, audit branch, PR #2/#3 and `flash-moe-production` remain unchanged.

## C11-01 — new opt-in serving admission

`metal_infer/flash_serve_admission.h` defines a bounded GPU-only serving contract:

- `FLASH_SERVE_QUALIFIED_GPU_ONLY=1` activates it; unset preserves old behavior; any other explicit value causes HTTP admission failure. Set only in a separately tested candidate canary, **not production**.
- Before resident-state invalidation/restoration, rejects `current_position + incoming_tokens + max_generation > min(32768, GPU_KV_SEQ, engine_KV_cap)`, including continuation requests. Uses widened unsigned arithmetic and fails closed on invalid negative values.
- Samples macOS host free + inactive page bytes using `host_statistics64` and refuses new requests if the sample is unavailable or less than 6 GiB. This is intentionally a conservative *admission* sample. The tool/test memory-availability percentage is a separate metric.
- Existing 65536-token engine allocation and CLI/default serving remain unchanged. Existing HTTP rejected-request error text was broadened.
- This does **not** implement continuously supervised mid-request memory intervention, a GPU-utilization gate, multi-process global enforcement or any proof of M4 behavior. Serial `serve_loop` only admits one request at a time in the inspected process.

### Required Work model-free tests

Run from the candidate checkout:

```sh
clang -std=c11 -Wall -Wextra -Werror -I metal_infer \
  tools/test_qualified_serve_admission.c -o /tmp/flash-admission-test
/tmp/flash-admission-test
```

Run native build and existing self-tests on the *new* opt-in branch. Confirm neither compiler behavior nor default settings regress. Inspect source-order evidence that rejected requests preserve the previous resident session. Test invalid env modes, negative/overflow accounting, current+input+generation 32768/32769 boundaries and default 8192 GPU cap. Additional instrumented, no-weight tests must confirm the live `context_preflight` integration as opposed to only the isolated helper.

For a separately authorized non-production, isolated candidate server, verify:

1. 32768 total context (including requested generation) admitted if host sample passes.
2. 32769 rejected with a client error before resident mutation.
3. Continuation at the boundary rejected without destroying prior resident conversation.
4. Memory failure/unavailable sample rejected without ending existing session.
5. The previous unset/default mode is unaffected.
6. Mid-request memory risk is independently bounded by a documented supervisor or an explicit operational restriction, since request-time reserve checks are not continuous.

**Do not claim C11-01 fully closed** until native build, integrated tests, and an enforceable post-admission resource policy are accepted.

## C11-02 — future deployment-provenance verification package

`tools/verify_release_provenance.py` checks a pre-supplied *offline manifest* and SHA256 of explicitly named artifacts. It neither discovers a launcher nor examines a running service; it does not create backups or execute any start/stop commands.

A separately authorized deployment operator will need to capture, verify and provide:

- Actual launcher/owner and complete launch arguments/environment, including deployed arithmetic mode/profile.
- Exact installed executable mapping, matching dependency/shader files, model identity and checked source/build SHA.
- Independent, verified backups of both state/cache roots and original configuration/binaries.
- Candidate/rollback commands tied to the actual launcher identity.
- Offline rollback restoration test, new-session behavior, health checks and stop criteria.
- Frozen canary configuration and explicit supported capacity and latency envelope.

### Example structure (placeholder, not actual production facts)

```json
{
  "authorized_inventory": false,
  "source_commit": "REPLACE_WITH_ACTUAL_PREVIOUS_BUILD_SOURCE",
  "release_commit": "REPLACE_WITH_APPROVED_CANDIDATE_SOURCE",
  "launcher_owner": "REPLACE_WITH_VERIFIED_OWNER",
  "launcher_definition": "REPLACE_WITH_VERIFIED_SERVICE_DEFINITION",
  "installed_executable": "REPLACE_WITH_VERIFIED_ABSOLUTE_PATH",
  "startup_argv": ["REPLACE_WITH_ACTUAL_COMMAND"],
  "startup_environment": {"FLASH_FE027_NUMERICS": "REPLACE_WITH_ACTUAL_VALUE"},
  "runtime_dependencies": ["REPLACE_WITH_ALL_VERIFIED_SHADERS_AND_LIBRARIES"],
  "model_identity": "REPLACE_WITH_MODEL_MANIFEST_HASH",
  "cache_backups": ["REPLACE_WITH_FIRST_VERIFIED_BACKUP", "REPLACE_WITH_SECOND_VERIFIED_BACKUP"],
  "rollback_argv": ["REPLACE_WITH_PREVIOUS_COMMAND"],
  "rollback_environment": {"REPLACE_WITH_PREVIOUS_VARIABLE": "VALUE"},
  "rollback_test_plan": "REPLACE_WITH_ACTUAL_RESTORE_TEST_AND_STOP_CRITERIA",
  "files": [{"path": "/absolute/path/to/pre-captured/artifact", "sha256": "actual_lowercase_sha256"}]
}
```

```sh
python3 tools/verify_release_provenance.py --manifest /path/to/operator-captured-manifest.json
```

The manifest MUST remain unauthorized and therefore fail until a separate, explicitly approved operator captures real data. A passing offline manifest does **not** verify the running process, create/verify entire cache archives, or prove restart/rollback works. Never fabricate those claims.

## Release conditions and ownership

- No production process, source checkout, running service, port, launcher or live cache was inspected.
- No modifications to mask63 arithmetic, routing, checkpoint identities or frozen native numerical test tolerances.
- New runtime source **requires** source/binary re-freeze and focused re-audit, even though the change occurs before numerical inference.
- Work A tests C11-01 admission; the eventual deployment operator resolves C11-02 only after separate authorization.
- P1 C11-02 remains **OPEN** until actual deployment provenance and rollback testing exist.
- No merge, deployment or canary authorization is implied.


## November 11 verification follow-up — V-01/V-02 fixes

Verification source: [independent Work test report](https://github.com/KingdomDesignsConsulting/Flash-iOS/blob/2e7105ddaf82cf845de4816dcac0660bb7b87b36/docs/audits/c11-01-c11-02-verification-2026-11-11.md).

- **V-01 resolved in source:** `metal_infer/Makefile` now includes `flash_serve_admission.h` in shared `INFER_DEPS`, which is a prerequisite for normal `$(INFER_TARGET)` and the existing experimental targets that reference it. A header-only timestamp change must now rebuild the normal inference target. Verify this with a dry-run incremental-dependency test.
- **V-02 resolved in source:** `flash_serve_policy_mode(NULL)==0` (unset retains legacy behavior), `flash_serve_policy_mode("1")==1`, and *all explicitly supplied values other than literal "1", including empty string,* are rejected with -1. Unit tests now cover empty and whitespace.
- **Existing verification evidence:** native build/self-tests PASS, 40 extracted-source model-free integration cases PASS, 12 synthetic provenance tests PASS at original remediation commit `337b5a1`. These results precede the V-01/V-02 fixes and **do not qualify the updated commit**. Re-run the existing tests and dependency regression on the updated branch.
- **C11-01 remains PARTIAL**: opt-in request-time host reserve does not provide continuous post-admission memory protection or real live-session qualification. Do not represent source-level corrections as complete serving-resource admission acceptance.
- **C11-02 remains OPEN**: offline provenance tool cannot establish actual deployment launcher, executable mapping, verified full backups or rollback; these require a separately authorized operator. The verification report also notes its role-binding limitation. Do not claim that passing synthetic manifests closes C11-02.

No runtime arithmetic, checkpoint version, production default, installed service or cache was changed. Keep PRs draft. All release-specific follow-on tests must use a new authenticated source/binary manifest.
