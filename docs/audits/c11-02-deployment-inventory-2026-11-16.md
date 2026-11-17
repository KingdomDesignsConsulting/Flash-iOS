# C11-02 deployment inventory

Completed November 16, 2026 (America/Los_Angeles). Workstream D; read-only production access explicitly authorized by the handoff. No inference request, model launch, service operation, installed rebuild, cache mutation or production source edit was performed.

## Revision freeze

Audit branch `audit/c11-02-deployment-provenance-20261116`, independent worktree `/private/tmp/flash-deployment-audit-20261116`, based on `2cb51d98661068b69bf9819b98ea2ae612a0dace`. This base supplies inspection tools/documents, NOT a combined release candidate. Work A/B worktrees and engineering branches were not changed or merged. Final audit commit is supplied by the publication handoff; it cannot embed its own hash.

| Remote branch observed at start | SHA |
|---|---|
| `flash-moe-production` | `8312a1d0fbf4fa09a14621a51cfe676be98c29b3` |
| `work/release-mask63-final-qualification` | `21a073174fb1feb828f2d28762293d1803e66a9a` |
| `fix/audit-c11-01-c11-02-preproduction` | `a50294f2909d5270a173c8c3acda026c113e1e16` |
| `work/c11-resource-closure-20261116` | `2cb51d98661068b69bf9819b98ea2ae612a0dace` |
| `work/agent-prefix-deadline-20261116` | `d2d383e6127e774d80bada9057aeaa6f5a6ff74c` |

Local installed checkout is separately `flash-moe-production` at `5c26430f2790b84516b7384915eb0500abc5392f`, tracked clean, with untracked experimental binaries left untouched; reported 46 commits ahead of its remote-tracking branch. Neither local nor remote HEAD identifies the installed executable's source.

## Ownership map

**UNVERIFIED launcher → UNVERIFIED effective configuration → installed `metal_infer/infer` (bytes verified) → UNVERIFIED deployed model → project cache roots present but binding UNVERIFIED → expected port 11241, no listener observed.**

No inference executable appeared in the scoped `ps` scan and `lsof` found no listener on11241. This is a point-in-time negative observation, not evidence that an installed service does not exist. No service was started to obtain a PID. Live PID, owner, parent/supervisor, executable device/inode mapping, working directory, arguments and environment are unavailable.

Read-only search of user/system LaunchAgents and LaunchDaemons for Flash-iOS/FlashMoE/11241 found no matching plist. `launchctl list` had no Flash entry; Apple's `siriinferenced` is unrelated. Targeted shell startup files, port-specific shell/session history and immediate Desktop/bin/application launcher names did not identify a launcher. These are bounded searches, not a complete inventory of login items, IDEs, external supervisors or all user scripts. The operator supplied the historical October23 manual Terminal command below; the latest launch remains unconfirmed. Automatic restart and absence of competing launchers remain UNVERIFIED.

## Installed artifact identity

Installed path: `/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS/metal_infer/infer`. Regular file, not a symlink, device16777243/inode66802942, uid501/gid0, mode0755. Source metadata was stable across each independent copy. Modification timestamp is recorded in nanoseconds in the JSON companion.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `infer` | 884,104 | `7ae16f0a22ca9e871406bb0a9566e366432df6074027c7feeb246a239203bfbb` |
| `shaders.metal` | 69,853 | `7067f44056fa947f54ab7095d7461f10c30d507f11c90ca484c09ad5e15aac6b` |
| `gguf_iq_shared.h` | 5,828 | `ae46879550de5e3833a2269f65fcc6797603651fe91f75aa42acf56789112f17` |
| `libzstd.1.dylib` | 635,328 | `602d50cbe6fad0f0da6d1b73284ae3f75316015aea482ebd55614b6df2406b43` |
| `infer-candidate-lazy32k` | 900,952 | `497ccfb734e17a7fa7f3369265b739dedf51e8b2cde55fed07e8a77d50db1909` |

Mach-O arm64, UUID `B2B3CE9B-9866-328A-922F-CEC1E7B770D6`; ad-hoc linker-signed, no TeamIdentifier, no bound Info.plist/sealed resources. LC_BUILD_VERSION: minimum macOS26.0, SDK27.0, linker27037.1. These identify metadata, not compiler flags or Git source. No rebuild was performed.

The November4 independent copies of `infer` and `shaders.metal` were rehashed and match the currently installed bytes above. The historical manifest SHA is `a8b1dc009227adca367fbfaf9205ae6d8a49751f300c5da31b8bd65cdde84073`. Historical agreement proves continuity of bytes, not build provenance.

`otool -L` reports Metal, Foundation, Accelerate, CoreFoundation, libSystem, libcompression, libobjc and `/opt/homebrew/opt/zstd/lib/libzstd.1.dylib`. The latter resolves to `/opt/homebrew/Cellar/zstd/1.5.7_1/lib/libzstd.1.5.7.dylib`; the copied dylib hash is above. System frameworks remain tied to macOS26.7.1 build25G241, not portable copied dependencies. No project-root or metal_infer `default.metallib`/`shaders.metallib` was observed in targeted checks; absence elsewhere is not proved.

## Configuration evidence boundaries

| Configuration category | Evidence/status |
|---|---|
| CLI argv, environment, cwd, bind address/port | No running process or configured command established; UNVERIFIED |
| Model/tiered Q2/Q4 identity | Named model directory exists; config.json3809bytes SHA `c0cf317cba802cfb1d2984d4b4afc98ceb3d86450ed757e028383bfb03643964`; candidate location only, deployed binding/weight identity unproved |
| FE027 arithmetic, GPU/CPU context capacities | Effective values UNVERIFIED; current source defaults are not installed-binary proof |
| N128, expert cache/prefetch, resident sessions | Options/settings cannot be established from absent invocation |
| Static/dynamic budgets, active profile | Project cache names exist; do not infer currently selected settings/profile from stale files |
| External supervisor/memory policy | UNVERIFIED; no unrelated app was terminated or reconfigured |

Read-only Mach-O symbol/data inspection found initial values GPU-linear/resident-MoE/oproj-v3/tiny-matvec/Zstd=1 and linear bypass/CMD12 flags/prefetch/N128/sort-tools=0. **These are file initializers, not effective startup settings:** BSS may be updated by initialization/CLI. They do not establish runtime configuration. `g_kv_seq_len` was not recovered. String-presence inspection found no `FLASH_FE027_NUMERICS` or `FLASH_SERVE_QUALIFIED_GPU_ONLY`; this is not proof of arithmetic/admission behavior or complete feature absence. `--flash-profile`, `--prefill-nrow`, shader/header names and prefix-budget option strings were present. The binary was never executed, including for help output.

## Cache metadata only

Project `warm-state`: five0600 uid501 files totaling1,114,319,038bytes. Named source/profile variants include main-agent, dsh-default-kevin and dsh-restore-audit, raw/id2/zstd-id2 naming. `warm-tools-cache`:12entries totaling95,176bytes including `.DS_Store`, named sources and learned JSON files. Root directories uid501/gid0 mode0755. Prompt/checkpoint contents were not read or published. File naming alone does not prove format correctness or active use.

`~/.flash-moe` contains sessions/history; no system.md was observed there. No content was published, and active dependency status remains unknown. Free disk observed640,627,056,640bytes; this is a measurement, not future backup-space approval. All inspected roots were on the same filesystem, so a local copy is not an independent-disk disaster backup.

The configuration gaps prevent an exact start/stop command from being authenticated. See the fail-closed future runbook; none of its operations were executed.

## Historical manual launcher and second executable (operator follow-up)

The operator identified the October23 manual Terminal launch, with confirmed endpoint at that time:

```bash
# HISTORICAL RECORD ONLY — NOT EXECUTED BY THIS AUDIT
cd '/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS/metal_infer'
./infer-candidate-lazy32k \
  --model '/Users/Shared/Main Hard Drive/AI Storage/AI Models/Reasoning/alexintosh/Qwen3.5-35B-A3B-Q4-Tiered-FlashMoE' \
  --tiered --serve 11241 --prefill-nrow --timing
```

This is historical evidence of a manual Terminal launcher, NOT confirmation of the latest launch, inherited environment, user ownership or automatic supervisor. Do not substitute `./infer` for this executable in a rollback recipe.

Current candidate: regular900,952-byte arm64 executable, uid501/gid0 mode0755, device16777243/inode70505932, UUID `E0459911-B6FE-3DFB-AE94-A4F85A76F114`, ad-hoc linker-signed, SHA `497ccfb734e17a7fa7f3369265b739dedf51e8b2cde55fed07e8a77d50db1909`. Its linked library paths match infer, including Homebrew Zstd. It was independently copied and restored without execution.

`Testing/gpu-32k-attention/integration-gate-02/report.json` SHA `5d769b3bbac5d26f05ef32595ced214f01ec2aae8da494c1ba8581452b97b08b` records PASS, clean tracked source check, HEAD `3a87663a72c6c88922dbd7fd9f82842e588a5dc6`, the exact current candidate SHA, and unchanged separate infer SHA. Its runner at that commit checks tracked cleanliness before building; `http/build.log` records the command below. This is a useful independently matched historical source association, not a new build reproduction or cryptographically attested toolchain. Gate01 failed before building because of cleanliness; that failed record was preserved, not discarded.

```text
clang -O2 -Wall -Wextra -fobjc-arc -DACCELERATE_NEW_LAPACK -I/opt/homebrew/include -DFLASH_PREFILL_NROW_PRODUCTION -DFLASH_PREFILL_NROW_ASYNC -DFLASH_PREFILL_NROW_GATEUP_M4_8ROW_BITSPLIT -DFLASH_EXPERIMENTAL_LAZY_SHARED_GPU_KV_32K -framework Metal -framework Foundation -framework Accelerate -lpthread -lcompression -L/opt/homebrew/lib -lzstd infer.m -o infer-candidate-lazy32k
```

At that recorded source, `metal_infer/infer.m` SHA is `5354277b4a744e4852cfae128dd670d602fa20e751e75a7728f443bbb842623f`; Makefile SHA `75ccd87f40f3362d177930f0c454629db9fdbc2924bbb37295d646b6ef46eae6`. Shader/header hashes at that source match the current copied files. Source anchors: infer.m4595–4652 shader/header resolution,16599–16609 executable-relative tools cache,19077+ HOME system prompt,19318+ warm-state paths; Makefile `integration-kv-candidates`; tools/verify_gpu_32k_integration.py clean-tree/report logic. These inspected paths support project cache binding for the historical command, subject to executable resolution and unrecorded environment. They do not establish latest operating configuration.

The source associated with that build selects GPU cap32768, initial CPU allocation65536 and production N128 flags; startup may adapt allocations and the effective environment is absent. Treat these as historical build/source facts, not measured current capacities. No `--flash-profile` appears in the historical command; present profile files do not prove which request-selected profiles were used. Source loads HOME/.flash-moe/system.md if present; current absence cannot reconstruct its October contents.

A targeted read-only search of project shell/zsh/command/plist files found no matching candidate/port launcher definition. Existing Python qualification controllers are test launchers, not evidence of the user's production supervisor. Login-item/external automation completeness remains unproved. No further operator reconstruction was required.
