# Mask63 pre-production release gates

Completed November11,2026. Candidate21a073174fb1feb828f2d28762293d1803e66a9a; Work B01ae9976f541c384dd83905fc006da196971bdb2. Recommendation only; production excluded.

| Gate | Audit disposition | Evidence / required owner action |
|---|---|---|
|Source freeze and executable binding|PASS|45 candidate/frozen hashes and saved binary/manifest independently checked|
|Repaired native32K numerical result|PASS within recorded scope|256 endpoints, state0, hidden4.76837158203125e-7, logits5.7220458984375e-6, exact greedy/fingerprints|
|Actual candidate GPU routing|PASS within recorded scope|All ten layers at six specified boundaries through32768|
|Six-expert ownership repair|PASS static + bounded historical evidence|Capture exclusion, prefill-boundary drain/reset, selective ownership-v2|
|KV/GDN/conv snapshots and corruption rejection|PASS scoped|Source inspection,37 synthetic PASS markers; saved profile/EOS trace reanalysis|
|Cancellation and restore hardware fault coverage|BOUNDED|Historical checked failure/disconnect tests; actual device reset/OOM not established|
|Selective checkpoint identity|PASS present envelope|No full-binary hash;8192 prefix bound makes supported>=8192 window changes safe; future-change guard|
|32K total serving context policy|OPEN P1 C11-01|Native default65536 allocation admission accepts beyond qualified32K; Work A/Architect enforce reviewed envelope|
|Host resource admission|OPEN P1 C11-01|Controller guards do not establish native service reserve enforcement; Architect choose enforceable policy|
|Long-context latency/performance acceptance|OPEN P1 C11-05|n=1, cross-date confounds, scalar32K warm interrupted; Architect explicit disposition, not ordinary-N128 promotion|
|Work B mock protocol tests|PASS|Independent44/44 and TypeScript build; no native source overlap|
|Work B long-prefill deadline|OPEN P1 C11-03 if supported|600s total not refreshed by keepalive; reproduce scaled with fetch-only mock|
|Native thinking/post-tool semantics|LIMITED|53 resolution cases; unsupported controls ignored/post-tool text rejected; contract/exclusion required|
|Actual current LM Studio GUI/live tools|NOT RUN, C11-04 if claimed|Historical GUI observations are not current B qualification|
|Actual MCP Gateway registry/pagination/dispatch|NOT RUN, C11-04 if claimed|Only fixture endpoints qualified; external implementation unavailable here|
|Responses API|UNSUPPORTED|Only Chat Completions in inspected adapter contract|
|Deployment source/launcher ownership and rollback|OPEN P1 C11-02|Future separately authorized operator must establish exact mapping/commands and verify complete backup|
|Optimized Python evidence validation|OPEN P2 C11-06|Normal rejects synthetic error, -O accepts; actual recorded evidence independently passes|
|Checkpoint directory durability reporting|OPEN P2 C11-07|File fsync/close/rename checked; directory open/fsync errors ignored|
|Production authorization|NOT GRANTED|No service inventory, operation, merge, production files/cache access or deployment performed|

A restricted native-only canary is a possible future Architect decision, after mandatory admission/provenance/rollback/latency prerequisites. It is not authorized by this matrix. Excluding GUI/MCP/adapter features must be explicit rather than relabeling their tests PASS.

**AUDIT CONDITIONAL PASS — SPECIFIC REMEDIATIONS REQUIRED**
