# 32K HTTP serving qualification

Branch: `experiment/gqa-32k-lazy-kv-20261022`.
Starting HTTP-runner revision: `6726ae040dd1e354307f348b6f61cf2c23327c31`.
Numerically qualified attention reference: `44f8c8f6bdbfe78f444e5bbf62b99f1b5d2b0d7d`.

## Scope and repair

The original runner omitted `--tiered`, did not exercise SSE or actual resident
continuations, and accepted empty visible completions. Its apparent PASS was
not sufficient serving evidence. The expanded runner rejects empty output and
checks reasoning-off behavior, response structure, token usage, SSE ordering,
resident continuation, replay, state replacement, and process cleanup.

A real serving defect was reproduced: initial and continuation prompt rendering
hard-coded thinking on even when `reasoning_effort: "off"` selected thinking off.
Short requests could spend their entire completion allowance on hidden reasoning
and return empty content. Both renderer calls now receive
`request_enable_thinking`. The repaired binaries return visible deterministic
answers with empty reasoning for these requests.

A final harness review also found mutable request-history aliasing: appending
client history could change previously recorded request objects and the replay
anchor. `payload()` now takes a deep snapshot of messages. A direct immutability
regression passed; the final short suite also exercises exact resident replays
with this corrected anchor. Earlier request-input arrays should not be treated
as immutable wire captures; their recorded responses, server logs, assertions,
and separate long-session journal remain the authoritative earlier evidence.

Attention arithmetic, shaders, checkpoint format, selective state-compatibility
identity, and production defaults are unchanged. The source additionally exposes
an explicitly enabled HTTP qualification observer and expanded routing traces.
The observer requires `FLASH_HTTP_QUALIFICATION=1` plus
`flash_qual_count_only: true`; it renders/counts without advancing the model.
Optional short-state hashing covers active CPU K/V and CPU/GPU recurrent and
convolution state. It does not claim a long-context byte-exact oracle.

## Test method

- Separate lazy16K and lazy32K experimental executables; production `infer`
  remains untouched.
- Normal tiered experts, default 512-entry malloc cache, and prefetch enabled.
- Three GPU-utilization samples below 30% before each server start. This is
  correctness screening, not an uncontended performance benchmark.
- Noninteractive subprocesses, captured logs, bounded request/startup/shutdown
  timeouts, and intentional SIGTERM shutdown with a closed-listener assertion.
- Native `proc_pid_rusage` records physical footprint, lifetime peak physical
  footprint, and RSS. Conservative stops: 12 GiB physical or 16 GiB RSS.
- One resident conversation is supported. Alternating IDs are accompanied by
  full client history when replacing that resident conversation. No pool of
  conversation KV snapshots was added.
- Resident replay is compared with the same resident replay, not with a
  differently rendered canonical transcript. Qwen rendering can strip historical
  thinking markers, so those two token histories need not be byte-identical.
- Dedicated temporary executable/project location isolates learned profiles and
  ordinary persistent checkpoints from the user's production profiles.

## Completed short and cache checks

The two-round short soak completed 39 requests per implementation, including
12 actual resident continuations per implementation. `/health`, `/v1/models`,
JSON completions, SSE completions, usage before `[DONE]`, alternating
A/B/A/C/B/A sessions, invalid-session-ID recovery, full-history replacement,
and cross-implementation greedy output all passed.

Peak physical footprint was 1.9074 GiB for lazy16K and 1.9023 GiB for lazy32K.
Final-quarter physical-memory medians exceeded the previous quarter by about
12–15 MiB. This is bounded short-run warming evidence, not proof about unlimited
server lifetimes.

After fixing request-history aliasing, a final one-round regression executed
33 requests per implementation, including explicit start/delta replays after
each stateless replacement. Both passed; peak physical footprints were
1.8922 GiB (lazy16K) and 1.8953 GiB (lazy32K). Servers ran sequentially:
16K from 00:37:20 to 00:39:37 PDT and 32K from 00:39:41 to 00:41:41 PDT on
October 23. Both exited with intentional SIGTERM -15 and no orphaned listener.

The focused lazy32K cache/state test passed:

- An invalid session-ID request preserved the resident state hash.
- Replaying the same first turn and continuation after stateless replacement
  produced the same output and complete active-state hash
  `d7b00512fa2e87f9` at position 55, with all ten KV lengths equal to 55.
- Six distinct prefixes exercised the existing five-slot prefix cache. The
  original profile was recovered through the ordinary persistent-state path.
- A real production-format compressed checkpoint (62,552,468 stored bytes) was
  deliberately corrupted in the isolated test project. Normal startup rejected
  it, rebuilt the short prefix, and served correctly.
- Another restart restored the valid rebuilt checkpoint and reused its prefix.

## Real long HTTP session

The long runner builds context through ordinary streamed HTTP requests with
resident deltas. It targets exact logical lengths 8,191, 16,383, 24,576, and
32,767, and records routing at neighboring decode positions. Qualification-only
fixtures are never imported into serving. The first run was deliberately
interrupted after a durable 4,098-token checkpoint in the client journal; resume
replayed ordinary HTTP history before continuing. The journal is a transcript,
not a raw KV checkpoint: resuming requires normal prefill and can be expensive.

The resumed server ran from **2026-10-22 23:18:27 PDT** to
**2026-10-23 00:10:31 PDT** and passed. Completed logical prompt lengths were
2,048; 4,098; 6,146; 8,191; 10,241; 12,291; 14,341; 16,383; 18,433; 20,483;
22,533; 24,576; 26,626; 28,676; 30,726; and 32,767. Each returned visible `OK`,
with two completion tokens and all ten KV lengths equal to prompt length + 2.
The first two lengths were completed before the deliberate interruption.

| Actual active KV length | Observed backend | Full-attention layers checked | Result |
| --- | --- | --- | --- |
| 8,192 / 8,193 | GPU / GPU | 10 / 10 | PASS |
| 16,384 / 16,385 | GPU / GPU | 10 / 10 | PASS |
| 24,576 | GPU | 10 | PASS |
| 32,767 / 32,768 | GPU / GPU | 10 / 10 | PASS |
| 32,769 | CPU | 10 | PASS |

At position 32,769, a continuation whose prompt plus requested generation
exceeded the actual CPU KV capacity returned HTTP 400. Position and all ten KV
lengths remained 32,769. The next valid resident continuation succeeded. This
test checks rejection metadata/state lengths and continued usability; it does
not claim a bytewise hash of the entire 32K state across rejection.

Replacing the long conversation with the original short request reproduced
`ORBIT` and the exact original active KV/recurrent/convolution hash
`884a49621d7d809a` at position 34. All ten KV lengths were 34 before and after.

Peak physical footprint was **3,757,781,736 bytes (3.500 GiB)**; maximum sampled
RSS was **8,626,077,696 bytes (8.034 GiB)**. There were 3,081 native memory
samples during the resumed server lifetime. Physical footprint at shutdown
retained the high-water allocation; resetting a session does not unmap the
engine's reusable global KV/buffer arenas. Metal allocation accounting rose
from 3,796,795,392 to 4,307,910,656 bytes as long-prefill workspaces were used;
this is allocation accounting, not an additional physical-footprint total.
No memory safety threshold was reached. Short repeated session replacement
remained near 1.9 GiB. Together these are bounded-run evidence; an indefinite
soak is not claimed.

The expert cache remained at 512 entries, with prefetch enabled. Its final
logged cumulative totals were 82,342 hits and 299,938 misses (21.54% hit rate),
with per-request eviction and per-layer telemetry retained in the full log.
The prefix-cache eviction test used six prefixes against five slots, then
recovered the original through the ordinary validated persistent cache.

The final request's suffix prefill was 332.29 seconds and generation was
1,109.81 ms for two completion tokens spanning the CPU fallback. Earlier
resumed requests used different prefix histories/cache warmth; these numbers
are diagnostic wall times, not a matched throughput comparison or production
performance claim.

## Results and integration verdict

| Check | Result |
| --- | --- |
| Separate lazy16K/lazy32K builds | PASS |
| Health/models, nonstream JSON, SSE and usage ordering | PASS |
| Short 16K/32K greedy output agreement | PASS |
| Repeated A/B/A/C/B/A replacement and resident continuation | PASS |
| Exact short resident replay after stateless replacement | PASS |
| Five-slot prefix eviction and validated persistent restore | PASS |
| Corrupted persistent checkpoint rejection and recovery | PASS |
| Real HTTP 8K/16K/24K/32K routing and saved-state lengths | PASS |
| 32,769 CPU fallback and subsequent continuation | PASS |
| Capacity rejection preserves resident position/KV lengths | PASS |
| Post-long reset restores exact short active-state hash | PASS |
| Bounded observed memory and closed listeners after shutdown | PASS |
| Prior standalone numerical qualification | RETAINED; no arithmetic changes |
| Uncontended performance / indefinite soak | NOT RUN; not claimed |

**Verdict: 32K SERVING QUALIFIED. GO for controlled production integration,**
retaining the qualified 16K fallback. This report does not itself promote or
merge production. The attention numerical oracle was not needlessly repeated:
attention arithmetic, buffer ownership implementation and checkpoint semantics
remain those of the already-qualified reference; the relevant HTTP regressions
were executed with the repaired renderer and routing diagnostics.

The fix and runners are committed as
`554f38b185076033fbaebf262ad6242ce2dfbc67`. A subsequent documentation commit
records this completed evidence. The production branch and executable were not
modified. Every owned test server was stopped; expected SIGTERM exit was -15,
with no forced SIGKILL and no orphaned listener.

## Reproduction

From the project root, with an idle-enough GPU:

```bash
make -C metal_infer lazy16k-experiment lazy32k-experiment
python3 tools/soak_gpu_32k_http.py --out "$HOME/My Drive/Flash-iOS/Testing/gpu-32k-attention/http-short-new" --rounds 2
python3 tools/serve_gpu_32k_long.py --out "$HOME/My Drive/Flash-iOS/Testing/gpu-32k-attention/http-long-new"
```

Resume an interrupted long run using its existing output directory:

```bash
python3 tools/serve_gpu_32k_long.py --out "$HOME/My Drive/Flash-iOS/Testing/gpu-32k-attention/http-long-new" --resume
```

The isolated temporary project referenced by `progress.json` must still exist.
The runners print timestamped server starts/stops and leave their servers
stopped on completion or handled errors. SIGTERM exit `-15` is intentional;
it is not reported as an engine's graceful exit status zero.

## Evidence locations

Under `Testing/gpu-32k-attention/` in the local Drive mirror:

- `http-initial/`: original runner's vacuous empty-completion evidence.
- `http-repaired/{lazy16k,lazy32k}/`: completed short-soak logs, full request and
  response JSON, native memory samples, process commands, executable hashes.
- `http-final-replay/{lazy16k,lazy32k}/`: final corrected immutable request
  snapshots, exact resident replay regression, responses and memory records.
- `http-long-serving/cache-state-report.json`: exact short-state replay and
  normal persistent-checkpoint validation evidence.
- `http-long-serving/cache-{capture,invalid-recovery,valid-restore}/`: logs and
  request/response/memory records for the cache tests.
- `http-long-serving/progress.json` and `long*/`: durable transcript, actual
  long-session API usage/timings, per-layer routing, memory, and server logs.
- `http-serving-summary.json`, `http-serving-contexts.csv`, and
  `http-serving-source-sha256.json`: aggregate machine-readable evidence and
  exact source identities.

Full engine source is published to GitHub. The Drive evidence bundle contains
test drivers, reports, logs, JSON and source hashes rather than engine binaries
or complete runtime-source copies.
