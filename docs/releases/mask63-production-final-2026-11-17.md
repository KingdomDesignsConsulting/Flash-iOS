# Production cutover completion — November 17, 2026

**PRODUCTION DEPLOYED — POST-DEPLOYMENT QUALIFICATION PASS**

Restricted native-only deployment authorized by the user, executed in the user's visible foreground Terminal, verified against actual running processes and bounded requests. No Work B/GUI/MCP integration or production branch merge. Legacy binaries and original cache generations were not replaced. Source e58cc0d95ad9f49d87fe8a5c553e7575e63fbd83; executable SHA2569f6ffea0ea70de6409e51978381968d57df9c2ee158a42bef3a35c063ce08da4. Operational tooling publication is separate from frozen runtime provenance.

## Actual operating record

- Candidate root `/Users/knagel/Flash-iOS-Release/2026-11-17/candidate-source`, executable `metal_infer/infer-mask63-supervised-20261117`.
- Endpoint `http://127.0.0.1:11241/v1`, model qwen3.5; configured Qwen3.5-35B-A3B-Q4-Tiered-FlashMoE at the approved model path.
- Foreground supervisor PID84890, child84895, UID501, start20:20:01PST; listener and process executable mapping verified. Former83650/83644 no longer present after user Control-C.
- Launch/environment: exact approved runbook command, fresh output `production-approved-03`, main-agent profile, mask63/native qualified admission set by frozen supervisor. Runtime log confirms GPU_KV_SEQ32768. One cooperating supervised model,6GiB host reserve,16GiB RSS ceiling retained.
- Six-hour process lifetime expires **November18,02:20:01PST**. At20:20:44 approximately5h59m remained. Authorization records expire01:51PST; they do not renew automatically or extend a process lifetime.

## Acceptance matrix

| Check | Result/evidence |
|---|---|
| Frozen binary / actual process / endpoint | PASS actual SHA/process/lsof; approved source binding previously rechecked |
| Buffered completion, usage, natural EOS | PASS READY/stop; attempt02 |
| SSE finish, usage before DONE | PASS attempt02 |
| Resident follow-up / correct continuation | PASS attempt02; including tool-result resident continuation |
| Exact32768 logical+reserved generation admission | PASS short READY request, not32768-token execution |
| Exact32769 rejection and preserved resident state | PASS HTTP400 then streamed resident OK |
| Profile capture / match / mismatch protection | PASS new synthetic source capture/reuse; changed tools logged mismatch with source unchanged |
| Harmless complete tool envelope | PASS echo(payload=alpha), no external executor invoked |
| Incomplete tool arguments | PASS no executable call, session_invalidated/resend_full_history |
| Persistent main-agent checkpoint restore | PASS actual restart valid zstd1 snapshot691tokens,425ms |
| Post-restore health/model/request | PASS health200/modelqwen3.5, READY/stop; logical713,cached691,prefill22,completion2,total715 |
| Supervision / memory | PASS continuing telemetry within6GiB/16GiB; exact snapshot in final JSON |
| Startup/checkpoint/Metal errors | No unexplained errors in inspected startup/request logs; normal profile-mismatch fallback during changed-tool test |

Attempt01 resource stop remains a real preserved failure, not erased. Attempt02 passed10bounded cases then was deliberately stopped by user for restart. Attempt03 confirms persistent restoration and actual prefix reuse without repeating the full suite. Earlier isolated numerical/lifecycle evidence remains its separately bounded historical evidence; no new hidden/KV/32K performance claim.

Private evidence: release-root `production-approved-01`, `production-approved-02/acceptance`, `production-approved-03/restore-acceptance`, each supervisor child log/result/telemetry. Exact request drivers preserved in `benchmark-logs/production_acceptance02.py` and `benchmark-logs/verify_production_restore03.py`. Only sanitized result summaries published. [Final JSON](mask63-production-final-2026-11-17.json).

## Recovery and operation

Recovery-03 archive f584e449610caa4d091209dc67e60ebb80bba698651e33e96de262bb09779563 and selected manifest73dd74016ef1fbe77506ec758f76ce0a211ed19ddee16850e03d0e97c0ed1d21 were freshly verified before cutover. Additional ZIP48718e48d226f3f53082de2578592038a049f954957b57dccb3db5b46e798e73 passed integrity. Model49files rehashed and protected caches unchanged/quiescent before launch. Exact recovery/runbook commands remain in the operational recovery report. Same-disk software rollback is not disk-failure recovery; weights/frameworks external, original metadata normalization explicit. Historical fallback lacks modern native32K admission and requires restricted clients plus external supervision; no fallback launch occurred.

Keep the owned Terminal open. Control-C stops the supervisor and its owned child. No daemon/unattended restart is installed. A renewal needs fresh authorization, exclusive/resource checks and a new log directory; all resident session IDs are lost on restart. Long16K/32K prefills remain long-running inference, not interactive latency guarantees. Resource readings are sampled, not hard reservations. Do not use broad kill commands or alter checkpoint identities. Keep tools gated until a complete valid envelope is received; no blind retry of possibly executed actions.

This completion supplements earlier conditional reports and blocked-attempt records without rewriting failed evidence. Shared engineering ledger and production branch remain unchanged.
