# Drive Testing folder inventory — conservative cleanup candidates (2026-11-04)

**Read-only inventory; no deletion executed.** Folder identifiers and sizes were read from connected Google Drive. This is a *sampled/multi-level* inspection, **not an exhaustive recursive inventory**; the Drive connector limits individual traversals. The totals below are for directly enumerated files only unless explicitly stated. Thus do not infer these sum to total folder size. See [retention policy](testing-drive-retention-policy-2026-11-04.md).

## Priority: large Drive-only binary state

- `Testing/gpu-32k-attention/seed-cache/32766/anchor.state`: **1,538,212,208 B** (folder ID `1l807BHHu4fn9zxnqquyhaXRdPBzmDEs_`).
- `Testing/gpu-32k-attention/seed-cache/31742/anchor.state`: **1,496,269,168 B** (folder ID `1MpVCh6cqQfEzkvDi-xQgep_MWuQd5sOn`).
- `Testing/gpu-32k-attention/seed-cache/24574/anchor.state`: **1,202,667,888 B** (folder ID `1A3CtF8NR_xWSALf7-o3mZIGcIcskO24-`).

Combined **4,237,149,264 bytes (~3.95 GiB)**. These snapshots are **not GitHub-backed**. They are potentially reproducible from the original model and exact history/seed metadata at significant computation cost. **Conditional removal** only after confirming no remaining integration/rollback test requires the exact snapshot, and accepting loss of instant replay. The `seed-cache/history` tree examined at selected positions contains small extension logs/manifests, not the same large anchor bytes. Keep compact history manifests if needed to regenerate.

## Low-risk completed-run subfolders

These were examined at least one level and contained logs/reports/diagnostic summaries rather than the big binary state identified above. **Candidate REMOVE after confirming no job references the path and accepting loss of raw run logs** (GitHub typically retains sanitized summaries, not exact raw logs):

- `gpu-32k-attention/integration-gate-01` (ID `1mLnzpsuz7RTYw35PNuce8MQ8Mp_cjEDg`) — one 345-byte direct result.
- `gpu-32k-attention/integration-gate-02` (ID `1i9lgUMyEeRNJapTsDk_lkZ9iRPHKGwef`) — direct small metadata; nested HTTP test results, not yet exhaustively traversed.
- `gpu-32k-attention/http-initial` (ID `1xNfM8ZU4QuJ83L3Karm4q5nejj2ZtuH8`) — three direct log/summary files, 99,005 bytes.
- `gpu-32k-attention/performance-matched` (ID `1E3a0DVjfT6zMulG2I4EirAK1jnztOymq`) — 14 direct files, 952,169 bytes; retain source-level performance report in GitHub.
- `gpu-32k-attention/qualification-32766` (ID `1v2o3shyflI_ZrsfhTDMlvd_cLEI2N1OO`) — 5 direct files, 71,001 bytes; report and logs, **not** the separate large `seed-cache/32766` anchor.
- `gpu-32k-attention/qualification-24574` (ID `1zYJUxnP9xknWOMwxNd2NQAQvcaptOASN`) — 5 direct files, 64,667 bytes.
- `gpu-32k-attention/initial-16382` (ID `1iONoa1ahfOILtuwCCcZAKt7wckhNR9JI`) — 7 direct files, 115,029 bytes.
- `HTTP-Prefix-Reuse/2026-10-23` (ID `1cEUA_eqWPdmGkyMShGHhQTa2IiR3GRPh`) — server log + two generated JSON records, 14,420 bytes.
- `HTTP-Prefix-Reuse/2026-10-24` (ID `1Rc8klKFDHzIXZ0sQOkinTCx0Q8t4NajN`) — 12 direct files, 524,097 bytes; confirm no unique original test corpus before removing.
- `HTTP-Prefix-Reuse/2026-10-25-client-hardening` (ID `1QOfZ4igdtP3IqK76Pupu-cawlqLZtsi5`) — 5 direct files, 98,214 bytes.
- `HTTP-Prefix-Reuse/2026-10-26` (ID `1cju1U0tGLVkgPoSzUyj6PBXLYUlqLHd3`) — small direct metadata and nested token-trace folders: **conditional**, not yet proven fully redundant.
- `HTTP-Prefix-Reuse/2026-11-02-mask63-release/model-free` (ID `1q7dyVf95CfwSzw8yib_lOXutLakmMSnF`) — six small model-free regression output logs, total 2,983 bytes; corresponding test source committed.

## Keep / do not wholesale-remove

- `gpu-32k-attention/seed-cache` (ID `1LjDPWGNiNOQg-Hmd-yvwhRz_75IpFsK4`) — contains the three large state anchors and other history. Not on GitHub. Deleting this recovers space but destroys stored checkpoint replay.
- `gpu-32k-attention/http-long-serving`, `http-repaired`, `http-final-replay` — archived experiments with nested inputs/logs; not all subfolders independently audited.
- `HTTP-Prefix-Reuse/2026-10-27-n128-state-equivalence` (ID `1vGs_eRM_NdoGeJcKvOq13aezJj9wfhiR`) — nested `disk-01` contains a checkpoint; preserve until compatibility witness reviewed.
- `HTTP-Prefix-Reuse/2026-10-28-fe027` (ID `1ELZXh0zO0cPKo8UM_u4JcpDR5qaqDszG`) — original failing histories and mask-15 checkpoints. Example `http-mask15` has original two-slab HTTP token-history subfolders; `disk-mask15/checkpoint` stores checkpoint material. Preserve a minimal reproduction set.
- `HTTP-Prefix-Reuse/2026-10-28-fe027-full-attention` (ID `1z2c4IRKPfgF-7XLsEkdOenALD1tQtR5X`) — old mask15 checkpoint file **67,380,091 B**; disk31 checkpoint **67,376,487 B**. These are not GitHub files, and have historical compatibility-test value.
- `HTTP-Prefix-Reuse/2026-10-29-fe027-combine` (ID `1CYGTgZViC00NMlDrqOilZoAADYMyhpf5`) — contains exact-cause operator traces and `expansion/disk63` old-state checks; sanitized combine report is committed, but raw checkpoints are not. Retain critical regression seed/compatible checkpoint.
- `HTTP-Prefix-Reuse/2026-11-02-mask63-release` (ID `1IGUqGVE7WTh8Sp9QJxIZowvr78QINcZ4`) — the most recent FE-038/039 production-readiness failure, ownership-repair validation, 16K/32K proof and private exact histories. **Keep** until PR #2 is accepted and reproduction/rollback requirements are settled.
- `HTTP-Prefix-Reuse/2026-10-28-release-gates` and `2026-10-27-state-equivalence` — many nested tests; no unconditional removal without deeper inspection of saved-state witnesses.

## Next cleanup action

Start with the small, verified completed-run folders to establish a safe procedure; meaningful storage recovery requires making a deliberate keep/delete decision on the three ~4.24 GB `anchor.state` files and any other large checkpoints. Before deleting those, verify provenance and current test dependencies and whether model+seed+history permit regeneration, then obtain explicit user authorization. Do not treat GitHub commits as a backup for the binary bytes.
