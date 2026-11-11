# Audit commands and reproduction

Executed November11,2026, from `/private/tmp/flash-ios-audit-mask63-20261110`, unless specified. All commands concern Git source, private experimental evidence or model-free fixtures. No model, real client/Gateway, production endpoint or heavyweight benchmark ran.

## Isolation/provenance

```sh
git ls-remote origin refs/heads/work/release-mask63-final-qualification refs/heads/work/agent-mcp-protocol-reliability refs/heads/experiment/http-resident-prefix-reuse-20261023 refs/heads/flash-moe-production
git worktree add -b audit/mask63-preproduction-readiness-20261110 /private/tmp/flash-ios-audit-mask63-20261110 21a073174fb1feb828f2d28762293d1803e66a9a
git diff --stat 5c26430f2790b84516b7384915eb0500abc5392f HEAD -- metal_infer
git diff --numstat 8312a1d0fbf4fa09a14621a51cfe676be98c29b3 HEAD -- metal_infer
git diff work/release-mask63-final-qualification...01ae9976f541c384dd83905fc006da196971bdb2 -- clients tools docs
```

Source inspection used targeted `rg`, `sed`, `cat`, `git show`, `git log` and diff reads in the independent checkout. Private evidence enumeration was limited to the recorded experimental root. No installed production directories/processes/cache were enumerated. GitHub connector `get_pr_info` and `fetch_pr_comments` read PR2/PR3; `fetch_pr` read ggml-org/llama.cpp PR31688. Git remote verification repeated before publication. Captured metadata: `evidence/github-review.json`.

## Existing evidence recomputation (read-only)

```sh
python3 docs/audits/verify_mask63_evidence.py \
  --evidence /Users/knagel/Flash-iOS-Work-A/2026-11-04-mask63-release \
  --out docs/audits/evidence/independent-native-evidence.json
python3 tools/check_work_a_eos.py \
  --profile-root /Users/knagel/Flash-iOS-Work-A/2026-11-04-mask63-release/profile \
  --out docs/audits/evidence/saved-eos-review.json
python3 -m unittest discover -s tools -p 'test_work_a_*.py'
```

The EOS output uses exclusive creation; choose a new audit output filename to rerun. An inline Python recomputation parsed the first128 `[prefill-nrow-profile` records of each recorded `0-mask63/server.log` under `performance-resume-20261106-32768` and `performance-missing-20261110-111928`, summed each `key=value` counter with the recorded parser expression, and compared the four staging/attention/grouped totals against `matched-prefix-staging-anomaly.json` within0.001ms. `evidence/staging-recomputation.json` records results and both whole-log hashes. No log or original evidence was changed.

## Native model-free build/tests

```sh
make -C metal_infer release-qualification RELEASE_QUAL_BINARY=infer-audit-model-free
./metal_infer/infer-audit-model-free --self-test-tools
./metal_infer/infer-audit-model-free --self-test-api
./metal_infer/infer-audit-model-free --self-test-warm-state /private/tmp/flash-ios-audit-warm-synthetic-20261111
python3 docs/audits/test_runtime_capacity.py
python3 docs/audits/test_gate_optimization.py
```

Separate audit binary only, never `infer`. No model argument or server flag. Native self-test dispatch exits before model/Metal initialization. Warm tests create/delete synthetic checkpoint files only in the new temporary test directory (including checked writes/fsync/rename/unlink), with no pre-existing checkpoint mutation. The test removes its directory on completion; choose a fresh directory for any future run. Capacity test compiles actual-source C with eight synthetic cases. Gate test uses temporary JSON/log fixtures and both normal/-O Python.

## Work B isolated export/build/tests

Actual export: Python `subprocess.check_output(['git','archive', '01ae9976f541c384dd83905fc006da196971bdb2', 'clients/lmstudio-documents', 'tools/qualify_agent_controls.py', 'tools/qualify_agent_render.py'])`, extracted with `tarfile` into `/private/tmp/flash-ios-audit-work-b-20261110`. No B worktree edits or merge. Then:

```sh
cd /private/tmp/flash-ios-audit-work-b-20261110/clients/lmstudio-documents
npm ci --ignore-scripts --no-audit --no-fund
npm run build
npm test
```

Initial sandbox test run:10 passes/34 localhost-listen EPERM failures. Authorized outside-sandbox fixture-only rerun:44 passes/0 failures. The successful TAP log is retained; environmental failure is explicitly recorded here rather than called a product failure.

```sh
cd /private/tmp/flash-ios-audit-mask63-20261110
node docs/audits/test_adapter_total_deadline.cjs \
  /private/tmp/flash-ios-audit-work-b-20261110/clients/lmstudio-documents/dist/transport.js
```

Deadline test replaces fetch; it does not open sockets. It scales idle/total to40/100ms and streams comments every5ms, proving the independent total timeout. The actual B control-resolution script was copied to `/private/tmp/flash-audit-controls.py` with only its `ROOT` changed to the candidate audit checkout, then run:

```sh
python3 /private/tmp/flash-audit-controls.py --out docs/audits/evidence/native-controls.json
```

That compiles extracted native resolution statements against Foundation, without HTTP/model activity.53 cases characterize behavior, including ignored controls; they do not turn unsupported behavior into compatibility PASS.

## Final artifact checks

```sh
python3 -m json.tool docs/audits/mask63-audit-findings-2026-11-10.json >/dev/null
git diff --check
```

All generated report paths are under `docs/audits/`; the only compiled executable is ignored in the independent audit checkout. Product runtime source is unchanged. Git publication is restricted to the audit branch; PRs and production/engineering branches stay untouched. The publication commit can be recovered with `git log -1 audit/mask63-preproduction-readiness-20261110`.
