# Verified software recovery and future operating commands

Completed November 17, 2026. **No production cutover or production endpoint access occurred.** This supplement supersedes the earlier NOT RUN / unselected recovery statements. Native runtime source and candidate binary are unchanged.

## Evidence

- Recovery archive SHA256 `f584e449610caa4d091209dc67e60ebb80bba698651e33e96de262bb09779563`, 1,151,814,144 bytes: PASS against published manifest.
- Fresh extraction: all 85 logical entries and 85 associated metadata records checked; stored-tree contents/metadata PASS. Original group/OS-provenance normalization remains explicitly recorded; no forensic original-metadata equivalence claimed.
- All 49 model files, 13,423,646,070 bytes: content hashes PASS. Zstd installed dependency and archived copy match. Shader/header/N128 kernel match historical source association `3a87663a72c6c88922dbd7fd9f82842e588a5dc6`. macOS 26.7.1/25G241 system frameworks remain external dependencies.
- Selected recovery executable is **infer-candidate-lazy32k**, SHA256 `497ccfb734e17a7fa7f3369265b739dedf51e8b2cde55fed07e8a77d50db1909`. Separate opaque-provenance `infer` is retained, not selected.
- Isolated operational restore: **PASS**, November 17 11:30:36–11:30:39 PST, port 11250, restored working directory, explicit clean environment, GPU admission 17/16/22 percent, supervisor PID 62105. Health 200; content `READY`, finish `stop`, usage 27 prompt + 2 completion = 29. Six resource samples. Operator-requested supervised shutdown/reap, exit -15. No running restored model remains. First relocated smoke at 11:28:29–11:28:35 also passed; the targeted repeat verified the historical working directory explicitly.
- 31 controller/authorization model-free tests PASS; 8 historical authorization cases also PASS under Python -O.

Private evidence: `/Users/knagel/Flash-iOS-Release/2026-11-17/operational-restore-01/` contains `verification.json`, `selected-recovery.json`, fresh extraction/runtime/cache generation, `live-exact-cwd/result.json`, server logs/telemetry, `backup-checksums.sha256`, and successful `checksum-verification.txt`. Logs also reside in the release root's `benchmark-logs/`. Public sanitized results: [JSON](mask63-operational-recovery-2026-11-17.json).

Checksum manifest SHA256: `c6e869f2306dad0589089d1ba0b9a3a8ad14a0ccce7ac59c72df62895df48368`. Selection SHA256: `73dd74016ef1fbe77506ec758f76ce0a211ed19ddee16850e03d0e97c0ed1d21`.

## Operating envelope and remaining decisions

User selected the historical manual recovery configuration and same-disk **software rollback** purpose. This is not independent disk-failure recovery; model weights/system libraries are external. Functional same-user restoration passed; privileged original group/provenance restoration was not performed. The new candidate remains one supervised cooperating model, native 32,768 logical-context maximum, 6-GiB available-memory reserve, 16-GiB RSS ceiling, mask63 opt-in, finite six-hour supervisor lifetime. Sampling is not a hard memory reservation; the lock cannot prevent unrelated model programs.

Historical recovery is deliberately not relabeled: it predates native qualified-32K request admission (engine allocation cap 65,536, GPU window 32,768). It uses the external one-model/6-GiB/16-GiB supervisor, but **does not provide the new native request-budget guard**. A future rollback requires explicit acknowledgement; if the same native admission guarantee is mandatory for fallback, keep traffic closed rather than launch this legacy binary. The restored short request does not requalify historical numerics, long contexts or every recovered profile checkpoint.

The user acknowledged long-running inference: historical exploratory warm prefill approximately 1,180 s at 16K and 5,084 s at 32K, not responsive-interactive guarantees. No new performance claim, adapter/GUI/MCP qualification, source-identity change or production authorization follows.

## Exact future commands — NOT EXECUTED

These are reviewable commands, not permission to run them. Both private plan templates deliberately contain false authorization flags and expiry zero. After final explicit approval, owner-held bound plans must be reviewed, given a fresh expiry no later than six hours and required explicit true decisions; do not merely rename an invalid template. Check no unexpected owner/listener or cache writer exists before any switch; take a new coherent backup if the protected generation changed.

Reverify the frozen backup before switching:

```bash
/usr/bin/shasum -a 256 -c '/Users/knagel/Flash-iOS-Release/2026-11-17/operational-restore-01/backup-checksums.sha256'
```

Candidate start (separate installed candidate, not overwritten `infer`):

```bash
cd '/Users/knagel/Flash-iOS-Release/2026-11-17/candidate-source/metal_infer'
/usr/bin/env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin HOME=/Users/knagel LANG=en_US.UTF-8 PYTHONPYCACHEPREFIX=/private/tmp/mask63-pycache \
 /usr/bin/python3 ../tools/supervise_qualified_serve.py \
 --binary "$PWD/infer-mask63-supervised-20261117" \
 --probe "$PWD/flash-serve-resource-probe" \
 --model '/Users/Shared/Main Hard Drive/AI Storage/AI Models/Reasoning/alexintosh/Qwen3.5-35B-A3B-Q4-Tiered-FlashMoE' \
 --out '/Users/knagel/Flash-iOS-Release/2026-11-17/production-approved-01' \
 --port 11241 --max-seconds 21600 --operator-exclusive-model \
 --production-plan '/Users/knagel/Flash-iOS-Release/2026-11-17/production-plan.approved.json' \
 --authorize-production-cutover -- --flash-profile main-agent
```

`main-agent` uses a byte-identical source JSON from the verified backup, staged only in the private candidate directory. No old checkpoint identity is forced to pass; incompatible state rebuilds normally. This exact new production launch/profile combination has NOT RUN. Existing bounded candidate canary/profile tests remain the release evidence. Candidate runtime bindings are frozen in `candidate-runtime-binding.json`; tooling updates did not change the 47 runtime inputs.

Stop the newly launched candidate with **Control-C in that foreground supervisor's Terminal**; retain its PID/start/executable receipt and confirm it reaped its owned child before rollback. Do not use broad kill/port-based termination. If any pre-existing production owner must be stopped, identify and record that owner's actual stop procedure first; no historical PID or guessed launchd label is sufficient. No command to stop an unknown existing service is authorized by this document.

Historical rollback start from the separately restored cache/runtime generation:

```bash
/usr/bin/env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin HOME=/Users/knagel LANG=en_US.UTF-8 PYTHONPYCACHEPREFIX=/private/tmp/mask63-pycache \
 /usr/bin/python3 '/Users/knagel/Flash-iOS-Release/2026-11-17/candidate-source/tools/launch_historical_recovery.py' \
 --selection '/Users/knagel/Flash-iOS-Release/2026-11-17/operational-restore-01/selected-recovery.json' \
 --selection-sha256 73dd74016ef1fbe77506ec758f76ce0a211ed19ddee16850e03d0e97c0ed1d21 \
 --probe '/Users/knagel/Flash-iOS-Release/2026-11-17/candidate-source/metal_infer/flash-serve-resource-probe' \
 --out '/Users/knagel/Flash-iOS-Release/2026-11-17/production-rollback-01' \
 --port 11241 --operator-exclusive-model \
 --production-rollback-plan '/Users/knagel/Flash-iOS-Release/2026-11-17/rollback-plan.approved.json' \
 --authorize-production-rollback
```

The rollback controller verifies the selected manifest/runtime/dependencies and recent full model verification's size/inode/mtime records, uses restored `runtime/metal_infer` as cwd, isolated restored HOME/cache generation and explicit environment. Re-run full checksums after model changes. The original installation is not overlaid or deleted. All resident session IDs are lost across either process; clients resend full history. Failed/possibly executed tools must not be blindly retried. Any verification/resource/startup failure leaves traffic closed, preserves evidence and requires an operator decision; no automatic retry.

Final cutover approval, current owner-specific stop facts and the historical fallback admission acknowledgement remain prerequisites. No approved true plan has been created. This report closes the missing checksum and short operational software-restore evidence, not those future authorization steps.
