# C11-02 future deployment and rollback runbook

Reviewed November16,2026. **ALL OPERATIONAL COMMANDS BELOW ARE NOT EXECUTED. This is not deployment authorization.** Current status PARTIAL: latest owner/launcher/environment and complete recovery package remain unresolved. No service was stopped, started or reconfigured during this audit.

## Mandatory decision record — stop before deployment

The Architect/operator must supply and approve all these fields in a private maintenance record, with a sanitized public manifest. Unknown values are deliberately mandatory; do not infer them from a filename or port:

- `APPROVED_RECOVERY_EXECUTABLE`: choose the actual prior runtime, with evidence. `infer` SHA7ae16f… and historically launched `infer-candidate-lazy32k` SHA497ccf… are distinct artifacts. Do not silently swap them.
- Exact original launcher/owner, executable absolute path, cwd, argv array, explicit and inherited relevant environment, HOME, model identity, profile/cache roots, supervisor restart behavior. The October23 manual command in the inventory is a historical template only.
- Actual owned PID **plus start time, UID and executable device/inode/hash mapping** at the maintenance window. Never act on a saved PID alone. If no process exists, record that and skip stopping; do not start merely for inspection.
- `APPROVED_CANDIDATE_SHA`, candidate executable SHA, matching shader/header/dependencies, source manifest, toolchain/SDK/build flags, runtime resource policy and explicit mask63 setting. No combined candidate SHA is chosen by this audit. Numerical candidate21a073… and resource branch2cb51d… are separate lineages.
- Exact authorized owner-specific stop/start argument arrays or supervised foreground procedure, resource/emergency-stop owner and restart suppression. A launchd command must not be invented when no job has been identified.
- Backup destination, verified full snapshot manifest and private secret-config handling, disk margin, model/process exclusivity and resource gates. Preserve at least6GiB host headroom per approved policy; satisfy candidate's actual admission guard, not only a benchmark controller. Performance/qualification tests require three GPU readings<30%; no GPU test was run here.
- Explicit Architect acceptance of unresolved old build provenance if opaque authenticated binaries are the recovery policy. No such acceptance currently exists.

Until all are complete, **DO NOT DEPLOY**. Exact executable start command for the latest deployment cannot honestly be supplied while its identity/environment is unresolved. No guessed kill/launchctl/eval command is supplied. Historical command is recorded in the inventory, not approved for execution.

## Pre-switch backup: reviewed command template

Only in a separately authorized maintenance window, after the verified owner has stopped/quiesced the appropriate runtime and all writers to these roots are confirmed stopped. Do not use `killall`, a port-only PID, or another thread's process. Recheck PID/start/executable identity immediately before any targeted stop; reused PID => abort. Capture the owner-specific exact stop/start command in the approved record first.

The following snapshots the **known project roots only**. It is incomplete until all actual external configuration/state roots and the chosen launcher/model/dependency manifest are added. Choose a fresh private destination outside production/Drive; preferably a separate encrypted volume. Mode/owner/ACL/xattr/link manifests and stable before/after inventories are required independently of archive creation.

```bash
# NOT EXECUTED. Mandatory operator-provided path; unset => fail closed.
: "${APPROVED_BACKUP_ROOT:?set a fresh private non-production non-Drive destination}"
PRODUCTION_ROOT='/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS'
# Run only after owner-verified quiescence and adequate free space.
test ! -e "$APPROVED_BACKUP_ROOT" || exit 1
umask 077
mkdir -m 700 "$APPROVED_BACKUP_ROOT" || exit 1
/usr/bin/ditto --rsrc --extattr --acl "$PRODUCTION_ROOT/warm-state" "$APPROVED_BACKUP_ROOT/warm-state" || exit 1
/usr/bin/ditto --rsrc --extattr --acl "$PRODUCTION_ROOT/warm-tools-cache" "$APPROVED_BACKUP_ROOT/warm-tools-cache" || exit 1
/usr/bin/ditto --rsrc --extattr --acl "$PRODUCTION_ROOT/metal_infer/infer" "$APPROVED_BACKUP_ROOT/infer" || exit 1
/usr/bin/ditto --rsrc --extattr --acl "$PRODUCTION_ROOT/metal_infer/infer-candidate-lazy32k" "$APPROVED_BACKUP_ROOT/infer-candidate-lazy32k" || exit 1
/usr/bin/ditto --rsrc --extattr --acl "$PRODUCTION_ROOT/metal_infer/shaders.metal" "$APPROVED_BACKUP_ROOT/shaders.metal" || exit 1
/usr/bin/ditto --rsrc --extattr --acl "$PRODUCTION_ROOT/metal_infer/gguf_iq_shared.h" "$APPROVED_BACKUP_ROOT/gguf_iq_shared.h" || exit 1
/usr/bin/ditto --rsrc --extattr --acl '/opt/homebrew/Cellar/zstd/1.5.7_1/lib/libzstd.1.5.7.dylib' "$APPROVED_BACKUP_ROOT/libzstd.1.5.7.dylib" || exit 1
/usr/bin/shasum -a 256 "$APPROVED_BACKUP_ROOT/infer" "$APPROVED_BACKUP_ROOT/infer-candidate-lazy32k" "$APPROVED_BACKUP_ROOT/shaders.metal" "$APPROVED_BACKUP_ROOT/gguf_iq_shared.h" "$APPROVED_BACKUP_ROOT/libzstd.1.5.7.dylib"
```

These commands alone neither prove cache completeness nor supply model/dependency relocation. Validate every cache/config entry against a quiescent source inventory, including directory metadata and links. Snapshot private HOME/system prompt/session roots only after confirming actual dependencies and protecting prompt contents. Preserve Homebrew symlink resolution/install-name or independently qualify relocation; copying a dylib into an arbitrary directory is not enough to launch Mach-O successfully. Authenticate model metadata and weight identities separately. Do not overwrite existing backups or hand-edit checkpoints.

The new small-package verifier is deliberately capped at64MiB and rejects links. It is **not** a full1.1GiB cache archiver/restorer. Full cache snapshots need an appropriately bounded streaming verifier and platform-metadata-aware extraction, plus independent rehearsal. This is a remaining gate, not an implied capability of the small tool.

## Offline verification commands (model-free)

Commands actually tested with real copied artifacts are described in the verification report. For another **new disposable destination**, using the audit checkout:

```bash
# NOT EXECUTED with this new destination. Never point restore-to at production.
python3 tools/audit/test_c11_recovery.py
python3 tools/audit/c11_recovery.py \
  --manifest '/Users/knagel/Flash-iOS-Work-D/2026-11-16-c11-02/partial-package-v2.json' \
  --archive '/Users/knagel/Flash-iOS-Work-D/2026-11-16-c11-02/partial-runtime-artifacts-v2.tar'
# Expected exit1: this actual package is incomplete, despite valid copied bytes.
python3 tools/audit/c11_recovery.py \
  --manifest '/Users/knagel/Flash-iOS-Work-D/2026-11-16-c11-02/partial-package-v2.json' \
  --archive '/Users/knagel/Flash-iOS-Work-D/2026-11-16-c11-02/partial-runtime-artifacts-v2.tar' \
  --require-complete
```

A zero exit without `--require-complete` authenticates listed byte/mode preservation only. `--require-complete` also enforces required role names and affirmative gates, but those declarations require independent evidence. It does not inspect processes, validate secrets, prove model identity or audit archive inventories inside another archive. Do not use it as automatic release authorization.

## Future switch procedure — ordered, not executed

1. Freeze approved candidate and dependencies; retain source/build log and hash manifest. Build only in its separate reviewed checkout, never overwrite installed infer during preparation. Candidate resource supervisor on the inspected branch intentionally refuses11241; a proposed production launch needs a separately reviewed equivalent policy, not bypassing that guard.
2. Record maintenance timestamp, owner-specific launcher and process mapping; suspend traffic and automatic retries. Obtain exclusivity and disk/memory admission. Verify approved recovery package and offline rehearsal before stopping anything.
3. Run **only the recorded authorized stop procedure**, rechecking ownership/start/device/inode at action time. Confirm process exit and no listener11241, without assuming any listener belongs to Flash. Unexpected listener => abort; do not take over the port.
4. Complete the quiescent backup and independent full snapshot verification above. If it fails, remain stopped or restart the unchanged old runtime through its recorded launcher only with operator direction; do not partially deploy.
5. Launch the approved candidate from its matching dependency directory with exact reviewed argv/env. Candidate enablement requires `FLASH_FE027_NUMERICS=63` and approved capacity/resource policy, not merely the option string. Use isolated candidate profiles/caches; preserve previous state separately. Verify actual executable mapping, PID/start/owner and bound endpoint.
6. After separate authorization, perform short health, bounded real-client streaming/nonstreaming, usage, resident follow-up, capacity rejection without state mutation, tool completion and profile restart checks. This audit performed none. Reject malformed/unfinished tool streams; no external action from partial arguments. Do not replay a possibly executed tool without idempotency evidence.
7. Record accepted source/binary/shader/dependency/config identities and functional evidence. No automatic promotion from a health response. Only Architect authorization accepts release traffic.

## Rollback scenarios — all NOT RUN

| Trigger | Detection | Required action / expected state | Verification / remaining risk |
|---|---|---|---|
| Candidate fails startup | Exit/error/no approved health readiness | Keep traffic closed; stop only mapped candidate if still alive; restore exact previous runtime/config/cache package while stopped | Hash/mode/path check; restart via approved original launcher; dependency/model/owner gaps currently prevent rehearsal |
| Candidate fails health | Bounded timeout/error or wrong executable identity | Stop owned candidate, preserve logs, restore full prior state | Recheck old PID/binary then authorized short health/client check |
| Numerical/resident-state failure | Mismatch, tainted continuation or unexplained session invalidation | Stop candidate; never reuse its RAM session IDs; restore untouched old cache/config | New full-history sessions; no checkpoint identity editing |
| Checkpoint invalidation/damage | Compatibility/rebuild failure or corrupted state | Restore complete pre-switch roots while all writers stopped; retain failed candidate evidence separately | Full manifest equality including missing/extra files, permissions and links; no overlay of mixed generations |
| Resource excess | Approved admission/watchdog breach | Use recorded emergency procedure targeting verified owned candidate only; suppress its configured restart loop | Wait for exit/resource recovery; no broad signals or unrelated app termination |
| Malformed/incomplete tools | Missing finish/DONE, invalid schema or publication | Close client execution gate; fail request, preserve evidence; rollback if systemic | Never execute partial tool call or blind retry possibly executed action |
| Rollback copy/start failure | Checksum/extraction/metadata error, missing dependency, health failure | **Remain stopped, traffic closed, no automatic retry/relaunch; preserve original backup and failed staging** | Operator intervention; do not run a partly restored tree |

## Exact rollback ordering after later authorization

- Recheck candidate PID/start/owner/executable mapping; invoke approved stop argv. Confirm exit and absence of writers. **Command unresolved pending launcher ownership.**
- Verify complete backup against trusted manifest. Restore into fresh staging, verify all files/directories/links/owners/ACLs/xattrs and original absolute role mapping; do not overlay live cache roots. Preserve rejected candidate artifacts in a separate evidence directory.
- Publish the entire reviewed previous runtime/config/cache generation while stopped, with operator-controlled atomic swaps appropriate to the filesystem. Preserve its linked library resolution and OS compatibility. A generic tar extraction into production is not approved.
- Invoke recorded original launcher with original cwd/argv/environment and selected authenticated old executable. **Latest-launch argv/environment unresolved; October23 command is historical, not a substitute.**
- Confirm PID/start/owner/executable identity and then authorized health/bounded functional/continuation checks. Discard all pre-restart resident IDs; resend complete histories. Keep maintenance state until explicit acceptance.

Concrete stop/start/swap commands cannot be truthfully finalized until missing launcher/configuration and full package are resolved. This explicit limitation prevents C11-02 closure; it is preferable to executable guesses. No production operation was attempted to fill those gaps.
