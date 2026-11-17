# C11-02 rollback dependency matrix

Completed November16,2026. No complete recovery package verified. Private independent artifact copies are under `/Users/knagel/Flash-iOS-Work-D/2026-11-16-c11-02/`, outside production and synchronized Drive. Their paths/hashes are in the JSON companion. Copying did not execute any binary.

| Dependency | Current evidence | Exact / functional rollback | Backup status |
|---|---|---|---|
| Installed infer | SHA, UUID, metadata independently verified | Essential | Current copied bytes and historical Nov4 copy agree; small restore passed |
| shaders.metal | SHA independently verified | Essential if runtime compiles it | Copied/restored |
| gguf_iq_shared.h | Presence, SHA; binary contains name | Preserve reconstruction/runtime dependency until proven unnecessary | Copied/restored |
| Compiled shaders | No named metallib in inspected roots | Preserve if actual launcher uses one | Full discovery unresolved |
| Homebrew Zstd | Dylib resolved and hashed | Essential linked dependency | Copied/restored bytes; install-name/symlink graph relocation NOT rehearsed |
| System frameworks/OS | Linked paths; macOS26.7.1/25G241 | Compatible host essential | Not backed up by this package; OS recovery separate |
| Source/build manifest | Installed source/flags unproven | Essential to reproducible reconstruction; optional for explicitly accepted opaque-binary recovery | No authoritative build-source manifest |
| Launcher, service owner, cwd | Unknown | Essential to correct stop/start/restart ownership | Missing verified record |
| Arguments/environment/config | Unknown, no secrets dumped | Essential | Missing verified record |
| Model weights/metadata | Candidate config hashed, no deployment binding/full weights identity | Essential | No verified model recovery manifest or independent model backup |
| warm-state | Five files1,114,319,038bytes metadata only | Exact rollback essential; rebuild may give functional rollback at cost | No complete authenticated pre-switch archive |
| warm-tools-cache |12entries95,176bytes metadata only | Exact profile/prefix recovery essential | No complete authenticated pre-switch archive |
| External ~/.flash-moe or other state | Present, active server dependency unresolved | Conditional, inventory first | No validated complete backup |
| launchd/login-item/external supervisor definition | No matching job established | Conditional but must resolve actual owner | Not captured |
| Resident RAM sessions | No process observed | Not durably restorable | Invalidate/reseed session IDs after every restart |

The current4-artifact archive contains1,595,113bytes of payload (archive1,607,680bytes), SHA `375bb7a8e60f77ca3469802c473a29fca8b9224ce6a9af80ff55652d5fb31510`. Restoring bytes and POSIX modes into a new disposable directory passed. Ownership, ACLs/xattrs, links, full cache trees, model and service startup were NOT rehearsed. A synthetic manifest is never evidence of actual backups.

## Required complete snapshot

After launcher/configuration discovery and a separately authorized quiescent maintenance window, capture the two whole cache directories, all actual external state/configuration roots, executable, shaders, dependency tree, launcher definitions and redacted public/private split configuration. Use restrictive backup permissions and a non-Drive destination, inventory every relative path/type/size/mode/uid/gid/link target/xattrs as applicable, hash actual stored regular-file bytes, and bind each role to its original absolute location. Store secret environment/config material privately and securely; publish only nonsecret identities. Record OS/Homebrew identities and retain original dependency resolution paths or a tested relocation plan. Capture a model manifest with weight identities without repeatedly hashing tens of gigabytes at every launch.

Reconcile live metadata before/after snapshot; any change invalidates a coherent snapshot claim. Empty directories and required symlinks belong in the inventory, not only files. Verify archive expansion before publishing a complete backup claim. Cache bytes can contain private prompts and must not be committed to GitHub or Drive evidence folders. Prefer an encrypted independent backup volume for disaster recovery; present local copies share a disk.

GPU-N128 ownership epochv2 and mask63 operator identities may invalidate affected prefixes. Do not force compatibility or edit identities. Candidate cache pruning/rebuilding can destroy old rollback state, so isolate candidate caches or preserve/rehearse the full pre-switch snapshot while stopped. Preserve selective state identity and leave whole-executable hashing disabled; artifact authentication here is deployment provenance, not a proposed checkpoint-key change.

Owner: operator/Architect for launcher and recovery policy, Work A for final candidate/dependency manifest, Work D for independent offline package verification. Source uncertainty can only be resolved by build evidence or an explicit Architect-approved opaque-artifact recovery policy; no such acceptance was observed.

## Historical launch artifact added

The operator's historical manual command names `infer-candidate-lazy32k`, not infer. Both are now authenticated independently and must remain distinct roles until the maintenance-window recovery target is approved. The candidate has a saved clean-tree report/source association described in the inventory; infer's source remains unproved. No arbitrary choice between them is authorized.

A second preserved archive `partial-runtime-artifacts-v2.tar` contains all five artifacts:2,496,065payload bytes,2,508,800archive bytes, SHA `d155f2bb7b8b066e605988fa321cabd1fce702d6b167373d91d26c2269cff9db`. Independent disposable restoration again passed byte/mode checks. The first archive is retained. Neither archive includes complete caches, launcher/environment, model or OS recovery. Complete-package validation rejects both.
