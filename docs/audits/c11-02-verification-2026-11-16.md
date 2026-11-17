# C11-02 independent verification

Completed November16,2026, America/Los_Angeles. Dedicated audit branch `audit/c11-02-deployment-provenance-20261116`, start `2cb51d98661068b69bf9819b98ea2ae612a0dace`. Final commit is provided in the Git publication handoff. No engineering branch merged, Work A/B worktree modified, running service controlled or inference request sent.

## Executed checks

| Check | Result | Scope / evidence |
|---|---|---|
| Remote/source freeze | PASS | Five branch pins in inventory/JSON; no unified candidate invented |
| Read-only production checkout | PASS | HEAD5c26430…, tracked clean; untracked binaries untouched |
| Process/listener inspection | NO MATCH OBSERVED | Scoped ps scan, lsof11241; no network connection or server start |
| launchd/shell/project launcher inspection | UNRESOLVED | No matching job or script in scoped searches; not proof no external launcher exists |
| Historical launch identification | VERIFIED HISTORICAL ONLY | User's October23 Terminal command names infer-candidate-lazy32k; current launch/env unproved |
| Installed infer identity | PASS | SHA7ae16f…, matches independently rehashed Nov4 copy; source unknown |
| Historical candidate identity | PASS | SHA497ccf… matches saved gate02 report; recorded clean-tree source3a87663… and full build command found |
| Shader/header/Zstd byte identities | PASS | Four-artifact record plus historical candidate preserved; source shader/header agree at3a87663… |
| Model metadata | PARTIAL | Candidate config hashed; active deployment and weights identity unproved |
| Cache/config snapshot | NOT VERIFIED | Read-only counts/sizes; no payload read/new checkpoint/cache writes |
| First small copied-artifact restore | PASS |4files1,595,113bytes; hashes/modes; archive SHA375bb7… |
| Expanded copied-artifact restore | PASS |5files2,496,065bytes; archive2,508,800bytes SHA d155f2bb7b8b066e605988fa321cabd1fce702d6b167373d91d26c2269cff9db |
| Actual partial package complete gate | REJECTED AS REQUIRED | Both versions missing required recovery dependency roles |
| Existing validator on actual partial fields | REJECTED AS REQUIRED | Exit1; absent source/launcher/config/model/cache/rollback records |
| Adversarial unit checks |25/25 PASS | Synthetic fixtures only; no inference/model/process APIs |
| Full recovery package / ownership ACL/xattr restore | NOT RUN | No complete package; small rehearsal intentionally does not claim this |
| Production stop/start/rollback/health/functional check | NOT RUN | Prohibited by assignment |

## Commands and methods actually used

- Read-only Git: `git ls-remote origin` with exact branch refs; `git rev-parse HEAD`, `git status --short --branch`, `git show REV:PATH`, targeted `git log`. Production status examined without changing tracked files; subsequent reads use optional-lock suppression where applicable.
- `ps -axo pid=,ppid=,uid=,comm=` with Python filtering for named inference binaries; `lsof -nP -iTCP:11241 -sTCP:LISTEN -FpcLn`; `launchctl list` filtered for Flash/infer names. No signals, HTTP calls or global environment dump.
- Python plist parsing of named LaunchAgent/LaunchDaemon roots; relevant-line shell config/history searches; bounded root launcher filename scans; `rg` for `infer-candidate-lazy32k|11241` in project script/plist files and candidate build records. These are bounded inspections; login items and external launchers remain unexcluded.
- Python hashlib/stat/resolve of named artifacts, `file`, `dwarfdump --uuid`, `codesign -dv --verbose=2`, `otool -L`, Mach-O load-command/initial-symbol data inspection using `nm`, binary string-presence checks. None executes the binary. `sw_vers`, `uname -m`, disk usage metadata identify host context.
- Read-only gate01/gate02 report and build.log examination; `git show 3a87663…:metal_infer/Makefile`, infer.m and runner logic. No historic PASS was rerun. Gate02 hashes actual binary bytes after building; it is unsigned historical evidence, not a reproducible-build attestation. No implication that 3a87663 is source of separate infer.
- `python3 tools/audit/test_c11_recovery.py`:25tests PASS (final captured run before publication; raw output private). Tests cover wrong binary/shader/model hashes, missing executable/launcher/cache role, symlink/archive links, corrupt/incomplete archive, path traversal, duplicate path, checkpoint/environment/conflicting-launcher/source/PID-recheck/rollback declaration gaps, disk shortage, partial-restore failure, destination overlay and unsafe permission rejection.
- Existing `python3 tools/verify_release_provenance.py --manifest /Users/knagel/Flash-iOS-Work-D/2026-11-16-c11-02/legacy-partial-manifest.json`: exit1 expected. All four listed copies hash correctly; incomplete role/config fields prevent even its limited field validation from passing. Its checks alone do not bind installed_executable/runtime_dependencies/cache_backups to files[], resolve source uncertainty, or verify archives.
- Offline Python driver used `shutil.copy2` of named files, stable pre/post inode/size/mtime and source/copy SHA checks; `tarfile` creation with explicit relative members; `c11_recovery.restore` to new private disposable directories; `verify(..., complete=True)` expected ValueError. Expanded driver added only the historically named candidate and historical report/build-log copies. No production payload changed.

Private evidence root `/Users/knagel/Flash-iOS-Work-D/2026-11-16-c11-02/`: artifact-copies.json, copied-artifacts/, partial-package[-v2].json, partial-runtime-artifacts[-v2].tar, offline-restored[-v2]/, offline-results[-v2].json, legacy-partial-manifest.json, legacy-validator.txt, adversarial-tests.txt, historical-report.json, historical-build.log. No cache/prompt payload was copied into this set. Host copies share the production disk; not disaster-recovery isolation. Published JSON contains nonsecret hashes and scope, not transcripts/secrets.

## Verifier guarantees and limitations

New audit-only `tools/audit/c11_recovery.py` leaves existing Work A tool/runtime untouched. It binds role/path/size/mode/hash to exact regular archive members, rejects duplicates/unlisted files/links/traversal, validates before writing, stages into a new directory, reads back bytes, and publishes only after all listed files succeed. Injected failure removes staging and leaves destination absent. No subprocesses or fsync/fullfsync are used by this tool; `os.rename` publishes staging and `shutil.rmtree` removes failed temporary files only. This verifies logical copying, not crash durability or live service rollback. It assumes an exclusive trusted offline directory, not a concurrently hostile filesystem. Manifest authenticity is an independent prerequisite.

Memory/size cap64MiB restricts this tool to small offline rehearsals. POSIX mode preservation was checked; uid/gid/ACL/xattrs/install-name resolution were not restored. Complete-mode booleans are **declarations checked for missing/false values**, not independent proofs: tests called stale-PID/environment/conflicting-launcher/cache-identity show fail-closed missing-record handling, not a live PID/model/checkpoint-semantic verifier. Nested cache archive completeness is not implemented. No synthetic case is evidence that the real deployment is backed up. The mandatory full-package gate remains open.

## Findings and remediation owners

| ID | Severity/status | Evidence and release impact | Minimal action / owner |
|---|---|---|---|
| D-01 | P1 confirmed evidence gap | Historical manual launch documented, latest owned launcher/argv/env and restart policy absent; cannot target safe stop/restart | Capture current configured launcher privately/read-only or at approved maintenance window, including identity rechecks; operator/Architect |
| D-02 | P1 confirmed evidence gap | infer bytes stable but build source unknown; candidate has historical source association, not latest deployment mapping | Preserve both; obtain source/build evidence or explicitly accept opaque-artifact recovery policy; Architect |
| D-03 | P1 confirmed recovery gap | No full authenticated quiescent cache/config/model dependency backup; small bytes-only restore insufficient | Complete snapshot/inventories and independent isolated full restoration, metadata/link/dependency checks; operator + Work D |
| D-04 | P1 confirmed configuration gap | Deployed model/env/profiles/budgets/limits not established by current source or cache names | Bind actual invocation to model/config/dependency manifest and final reviewed resource policy; operator + Work A/Architect |
| D-05 | P2 tool limitation | Legacy generic field/hash validator has no role/archive proof; new small tool also cannot qualify full service | Retain explicit scope; qualify streaming full-package validator/rehearsal before using any automated release gate; future engineering |

No confirmed runtime defect or unsafe rollback execution was induced. These are release prerequisites, not a claim that the installed service is faulty. Historical candidate association narrows D-02 but does not close separate infer provenance or recovery-target selection. Unrelated rebuild invalidation remains disabled; no state-identity policy change recommended or implemented.

Remote refs were rechecked immediately before publication and all five audited heads were unchanged. No newer engineering source was silently substituted. An initial `py_compile` attempt could not write Python’s default user-cache path; rerunning with `PYTHONPYCACHEPREFIX=/private/tmp/c11-d-python-cache` passed. AST parsing, final25tests and actual v2 archive verification also passed. This cache-path issue did not involve production.

## Acceptance gates still open

1. Identify latest launcher/owner/config and choose authenticated previous-runtime target; capture argv/env/cwd and supervisor restart control.
2. Architect selects final source and resource/admission launch policy; Work A/B lineages stay separate until reviewed.
3. Authenticate active model/dependencies and accept or resolve old source uncertainty.
4. Create coherent complete private backup; verify source-to-copy inventories, metadata, links and actual archive bytes. Rehearse full restoration into isolated storage, not just small runtime artifacts.
5. Review exact owner-specific stop/start/publish commands after those facts exist. Later authorized live validation must cover bounded health/client/session/tool/capacity behavior and rollback, with all resident IDs refreshed.

No update to shared engineering ledger or draft PRs was made. Proposed scoped ledger delta: “C11-02 remains open: two local executable identities authenticated; historical lazy32K source/launch association recovered;25model-free checks and5-artifact byte/mode restore pass; latest launcher/env, chosen rollback target and full cache/config/model recovery package remain mandatory.”

**C11-02 PARTIAL — SPECIFIC PROVENANCE OR RECOVERY GAPS REMAIN**
