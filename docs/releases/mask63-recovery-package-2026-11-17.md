# Recovery package — November17,2026

Private root `/Users/knagel/Flash-iOS-Release/2026-11-17/recovery-03`. Source reads only; no installed service/cache modifications. The final archive is **1,151,814,144bytes**, SHA `f584e449610caa4d091209dc67e60ebb80bba698651e33e96de262bb09779563`. It restores85entries into a disposable tree. Source inventories before/after and lsof checks found no visible users of the two cache roots and discovered HOME state. This is a point-in-time coherent-copy check, not host-global exclusion against future writers.

| Role | Entries including directories | Payload bytes |
|---|---:|---:|
| warm-state | 6 | 1,114,319,038 |
| warm-tools-cache | 13 | 95,176 |
| old-infer | 1 | 884,104 |
| historical-candidate | 1 | 900,952 |
| shader | 1 | 69,853 |
| shared-header | 1 | 5,828 |
| zstd | 1 | 635,328 |
| home-state | 4 | 1,019 |

Additional archive contents: original source-to-absolute-path role manifests, all small model metadata/tokenizers, tracked checkout reference sources, historical candidate report/build log, proposed manual recovery configuration. Current checkout references are not claimed as either old executable's build source. Metadata/source manifests remain private because cache paths may reveal private information. No prompt/session payload is published.

## Actual offline results

Independent Python streaming inventories compare every directory/file/link and hash each regular file in1MiBchunks;65MiBsynthetic test passes. Missing/unexpected entries, bytes, modes, uid/gid, mtime, flags, xattr hashes and ACLs are checked. Unsafe symlinks/special files reject. BSD tar archives are screened for traversal and escaping links before extraction into a fresh isolated destination. After extraction, captured permitted metadata is applied only to the private restored tree; independent full-tree comparison passes. No production path is an extraction target.

First attempts failed rather than silently accepting metadata loss. They are retained in recovery-01/recovery-02 and recovery-03 previous-attempt reports. macOS added/changed protected com.apple.provenance, staging groups changed, and tar omitted UF_TRACKED, an allowed group and root timestamp. The private restore repaired the latter three. Original ownership/provenance intent is retained in manifests; **original source metadata is not byte-for-byte reproduced in staging**. In explicitly recorded staging mode only uid/gid and OS-controlled provenance are exceptions; no other xattrs/content/membership are ignored. Exact restored-package comparison includes its stored ownership. This is not proof of privileged restoration of original gid0 or exact original OS-provenance values. That policy/controlled metadata rehearsal remains OPEN.

The verifier does not load nested model data into RAM; individual payloads stream. Model-free12tree tests cover membership, changes, permissions, links, >64MiB, owner mismatch and narrow provenance handling. Archive creation/extraction is handled by native tar, verified independently by Python inventories. Original artifacts are retained on failure. The tool uses filesystem copies/metadata writes only in the private package; production remains read-only.

## Model and dependencies

Portable weight supplement `/Users/knagel/Flash-iOS-Release/2026-11-17/model-weight-identities.json`, SHA `dfe16862bbb3f53bd379136812ebe056770f17d14b7cee94ba86c86cd19bebf4`:49files, 13,423,646,070bytes, each content-hashed once, with per-file stable stat checks during hashing. Supplement binds the recovery archive SHA above. The candidate manifest publishes only names/sizes/hashes, not weights. Weights remain in the original model directory; **independent model backup is NOT SATISFIED**. Exact reinstall can be checked against these hashes, but repository availability/reinstallation was not tested. Explicit acceptance of that limitation is required.

Both old executable hashes remain unchanged: infer7ae16f… (opaque build provenance), historical candidate497ccf… (saved clean-tree source association3a87663…). Shader/header/Zstd are copied; Zstd original resolution path and system framework/OS dependencies must be retained or deliberately requalified. Historical Terminal launch is documented but latest inherited environment/automatic-supervisor ownership remain unproved.

## Remaining recovery gates

- Operator/Architect selects the historical candidate manual configuration or accepts authenticated opaque infer recovery; no silent default selection.
- Approve reconstructed explicit environment/launcher policy or identify latest actual launcher. No launchd label was invented.
- Approve or complete original-owner/OS-metadata restoration handling; archive intent alone is insufficient to claim it tested.
- Accept same-disk/local backup and external model dependency, or provide separate encrypted physical backup and independently restored model.
- Full process restart/live rollback remains NOT RUN; requires later authorization and capacity.

Result: complete **discovered runtime/cache tree backup and stored-package restore PASS**, complete approved operational/disaster recovery **PARTIAL**. Do not confuse this with the previous five-artifact2.5MB test or with C11-02 closure.
