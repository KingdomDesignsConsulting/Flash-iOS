# Flash-iOS Google Drive testing-artifact retention policy (2026-11-04)

**Purpose:** Recover space in Google Drive's `Testing/gpu-32k-attention` and `Testing/HTTP-Prefix-Reuse` without misrepresenting GitHub's contents or destroying unique release evidence. This policy authorizes **inventory and recommendations only**, not deletion.

## Ground rules

- GitHub contains committed code, engineering reports, bounded sanitized matrices, and reproduction commands. It does **not** contain arbitrary raw token histories, binary `anchor.state`, saved checkpoint bytes, full per-run traces, raw tensors, caches, or private test worktrees.
- A GitHub **summary** is not an identical backup of raw input, checkpoint, manifest, failed-run evidence, or replayable state.
- Classify each Drive subtree using direct and recursively nested file metadata. A folder's size is **not** the sum of its immediate file sizes if it has descendants.
- **REMOVE** only if all unique contents are demonstrably reproducible from GitHub/public fixtures with no unresolved regression dependency, or are truly redundant; **CONDITIONAL** if unique raw data would be lost but owner accepts loss of replayability; **KEEP** if it contains a non-regenerable checkpoint/fixture, unique failure reproduction, model provenance, or data required by an open FE-038/039 release gate.
- Prefer deleting outputs of passing rerunnable tests before removing unique failed-case evidence. Preserve the minimal set of compatibility checkpoints for old arithmetic masks and the repaired prefetch identity. Keep at least one exact original problem input/history and corresponding hashes when later regressions depend on it.
- Do not move to another folder inside synchronized Google Drive as an 'archive': this does not save Drive storage. If local offline preservation is desired, use a genuinely non-synced destination and verify copies/hashes first; otherwise accept irrecoverable raw-evidence loss explicitly.
- GitHub SHA/provenance and private Drive raw data have different retention purposes. Do not upload multi-GB state or sensitive raw token dumps to the repo simply to enable deletion.
- Before deleting any Drive subtree, ensure no active job references its local synced path, confirm other users do not require it, and beware Drive Desktop's local mirroring. Trash may continue to count toward quota until emptied; avoid permanent deletion without owner approval.
- Release state: PR #2 remains draft; FE-038 production readiness NO-GO and FE-039 prefetch ownership repaired in a bounded scope. Missing native repaired-build 32K repeat, intended-capacity performance, and client behavior remain relevant to retention.
- Record a dated manifest identifying folder ID, size, child count, preservation justification, and action. This document does not certify that uninspected raw files have GitHub equivalents.

## Audit workflow

1. Enumerate each requested folder recursively using Google Drive's canonical folder IDs and child metadata, recording incomplete listings.
2. Group by actual release-evidence dependencies, not just age or filename. Distinguish `anchor.state`, `checkpoint*.zst`, original token fixtures, input/history IDs, raw numerical traces, copied source, build logs and generated summaries.
3. Cross-check report/sanitized-result paths in GitHub; identify unique originals even when summaries have been committed.
4. Return a folder-level recommendation in the categories REMOVE, CONDITIONAL, KEEP, with recoverable bytes clearly separated from uncertain bytes.
5. Request explicit deletion authorization only after review. Never equate 'committed report' with 'committed raw artifact'.

Related: `docs/mask63-production-readiness-2026-11-02.md`, `docs/fe027-moe-combine-alignment-2026-10-29.md`, and `FUTURE_ENGINEERING_LEDGER.md`.
