# Mask63 release procedure — review only, 2026-11-06

No deployment, merge, service stop/restart or production cache modification is authorized by this document. Work A's runtime remains the repaired experimental source frozen from 66adf92e2ea950528917000d1b59b788e1687371. Its testing/draft branch is work/release-mask63-final-qualification. Work B's client changes require separate review.

## Minimal source boundary

Compared with observed local production source 5c26430f2790b84516b7384915eb0500abc5392f, the frozen metal_infer diff is 13 files, 909 additions / 40 removals. This is not the source identity of the installed executable: its provenance is not proven by the checkout. PR #2's remote base is separately 8312a1d0fbf4fa09a14621a51cfe676be98c29b3; that comparison changes 18 files and includes earlier session/transport work. Do not blindly merge either comparison as a minimal production patch.

State-affecting pieces are the repaired infer.m prefill-boundary drain/reset and capture-prefetch exclusion; prefill_nrow_grouped_async.inc dispatch of the opt-in reference attention/combine paths; fe027_attention_reference.inc; fe027_combine_reference.inc; and their selective warm_state_cache.inc identities. Existing fe027_alignment.inc/fe027_q4.inc are dependencies already present in the local baseline. Diagnostic files, hooks, source probes, fault arms and Makefile qualification targets support testing and are not required as enabled product features. Source references must be taken from the same reviewed commit, not piecemeal files from other Work threads.

No runtime source was changed by this Work A closure. It adds only harnesses, watchdog coverage and evidence. Ordinary arithmetic remains the default. The proposal enables FLASH_FE027_NUMERICS=63 explicitly, without changing production defaults.

## Supported envelope and exclusions

Evidence applies to Apple M4 / 24GiB, arm64, macOS26.7.1, Qwen3.5-35B-A3B tiered Q2/Q4, 40 layers, 256 experts, K8, N128, M4-8row gate/up bitsplit, M4-2row down, default GPU-linear/resident-MoE/oproj/tiny-matvec/chaining/prefetch, and lazy shared GPU attention through32768. Other execution modes have only their separately documented short tests. iOS, other devices/weights, long CPU-linear cross-products, concurrent model processes, 64K serving, GUI clients and arbitrary tools are not covered by this qualification.

One heavyweight model process and one evolving resident conversation were tested at a time. Keep the existing five static-prefix slots, pinned-entry policy, 8192 prefix cap and768MiB dynamic-prefix RAM budget. Do not add conversation snapshot pools. Process admission must leave at least6GiB for the OS/other applications; measured diagnostic footprint/RSS/Metal overlap and cannot be summed. Qualification uses16GiB RSS and15% host-availability watchdogs, plus a35% prelaunch availability threshold for performance and three consecutive GPU readings<30%. These are test-controller guards, not newly implemented HTTP product admission controls.

Until separate capacity review, an operator/client must bound total logical prompt plus maximum output to32768 for a proposed GPU-only release. There is no claim that this document adds server-side enforcement of that policy. The engine has a larger CPU context allocation and can route beyond the GPU window; performance observations of that transition are not universal correctness qualification above32768.

## Build and canary proposal

After the Architect approves a final source SHA and feature scope, use a dedicated checkout with its own metal_infer directory. Do not overwrite the installed infer or copy just the executable away from its shader/source dependencies. Pin the reviewed SHA before the build and preserve the build log/compiler/SDK and runtime source hashes.

The exact already-tested performance build form is:

```bash
cd '/Users/knagel/.codex/worktrees/release-mask63-final-qualification/Flash-iOS'
make -C metal_infer release-qualification \
  RELEASE_QUAL_BINARY=infer-mask63-reviewed \
  RELEASE_QUAL_EXTRA_CFLAGS=-UFLASH_SESSION_STATE_DIAGNOSTICS
```

This removes state diagnostics while retaining opt-in FE027 arithmetic and lazy32K flags using the actual Makefile dependencies. A new build requires its own binary fingerprint and bounded smoke/restart checks. It is not automatically authenticated by a matching filename. Code/constant payloads of the already-tested rebuild match after excluding only UUID/ad-hoc-signature bytes; whole-file hashes differ. Never turn that comparison into executable-based cache invalidation.

Proposed foreground canary (only after approval and after three low GPU readings, no other model server, isolated port):

```bash
FLASH_FE027_NUMERICS=63 ./metal_infer/infer-mask63-reviewed \
  --model '/Users/Shared/Main Hard Drive/AI Storage/AI Models/Reasoning/alexintosh/Qwen3.5-35B-A3B-Q4-Tiered-FlashMoE' \
  --tiered --prefill-nrow --flash-profile release-canary-main-agent --serve 11243
```

The new lowercase canary profile deliberately has a separate static-prefix namespace. Capture its actual approved client request, verify prefix match/restart and keep session_id separate. A dedicated checkout's executable-relative caches isolate it from installed production profiles. The FLASH_SESSION_TEST_CACHE_ROOT override belongs to diagnostic builds and must not be assumed to work in this build.

## Checkpoint migration

Keep selective execution/layout/storage versions, runtime/config/artifact identities and exact prefix-token signature. Full executable hashing stays disabled. GPU-N128 ownership epochv2 invalidates the affected old checkpoint class; mask63 also has distinct attention/combine operator identities. Do not hand-edit identities or attempt to force-load old state. Let incompatible prefixes rebuild from their unchanged warm-source definitions. Unaffected scalar/CPU identities remain stable; unrelated rebuilds must not invalidate state.

Before any approved production switch, archive the installed binary, Metal source/dependencies, launch arguments/environment, warm-tools-cache and warm-state directories outside the Drive mirror. Record hashes and verify copies. Maintain free disk space and profile budgets; do not delete old checkpoints merely to test migration. A new candidate may rebuild or prune its own cache, so rollback needs the pre-switch cache copy, not merely an old executable.

## Deployment and rollback preconditions

The actual service launcher, exact PID and its executable mapping must be identified at approval time. Work A has not established a running production process mapping or service manager. Therefore no invented launchctl label, killall, broad process kill, automatic port takeover or concrete command against an assumed production PID is supplied.

Once approved: record a datestamped maintenance window; gracefully stop only the verified owned production process; confirm11241 is free; launch the approved binary from its matching source/dependency directory using the reviewed model/profile settings, FLASH_FE027_NUMERICS=63 and --serve11241; record PID/start/binary/source identity. Run health, an actual client request, resident follow-up and profile restart checks before accepting traffic. Preserve old source/binary/cache backup intact.

If those checks fail: stop only the newly recorded PID; restore the entire old cache/config snapshot while stopped; restart the captured previous executable with its exact previous arguments/environment from its original dependency directory; verify health, a short request and continuation. Never reuse the new resident session_id after restart. The observed old binary SHA256 was7ae16f0a22ca9e871406bb0a9566e366432df6074027c7feeb246a239203bfbb and shaders7067f44056fa947f54ab7095d7461f10c30d507f11c90ca484c09ad5e15aac6b on November4; recheck them at approval time rather than assuming they are still installed.

Exact production start/stop commands remain contingent on verified deployment ownership and the Architect's chosen release configuration. This is an explicit release gate, not permission to infer a service identity. Work A has not changed production, its arithmetic defaults, service or caches.
