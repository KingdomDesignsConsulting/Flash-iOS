# Flash-iOS

For the current development baseline, build targets, accepted production
configuration, benchmark candidates, warm-state design, and Git workflow, see
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

Few tweaks for [@alexintosh](https://github.com/Alexintosh) (macOS, iOS memory and Fanout)

Based on: https://github.com/Alexintosh/flash-moe/tree/feature/ios-app/FlashMoE-iOS

## Changes from upstream

- **macOS compatibility** — `#if os(iOS)` / `#if os(macOS)` guards for platform-specific APIs (UIKit colors, toolbar placement, memory queries, `os_proc_available_memory`)
- **iOS memory entitlements** — `extended-virtual-addressing` + `increased-memory-limit` for running large MoE models on iPhone
- **Fanout I/O** — Ported chunked pread from desktop engine: split each expert read into N page-aligned chunks for parallel SSD reads. Configurable via UI (Off / 2 / 4 / 8 chunks)
- **Race condition fix** — Async pread uses GCD `dispatch_group` (not pthread pool) to eliminate generation counter conflicts
- **Tiered validation fix** — `async_pread_wait` validates each chunk against its own size (not uniform 4-bit size), fixing silent cold expert skipping
- **No mmap on iOS** — Expert layer files use pread-only path, saving virtual address space
- **Model reload fix** — Full cleanup on unload (weight file, layer cache, tracking arrays, tensor hash table) so switching models doesn't crash
- **iOS storage protection** — Model files marked `isExcludedFromBackup` to prevent iOS from purging them
- **Models & Settings** — Menu button to return to model list / I/O settings from chat
- **Copy script** — `copy_model_to_iphone.sh` to push models to device over USB cable with auto-detect, ETA, and per-file progress

## Copy model to iPhone

Connect your iPhone via USB cable, then:

```bash
# Auto-detects connected device
./copy_model_to_iphone.sh /path/to/model-directory

# Or specify device UDID
./copy_model_to_iphone.sh /path/to/model-directory <device-udid>
```

The script copies all model files (config, weights, vocab, expert layers) file-by-file to the app's Documents container, with transfer speed and ETA display.

## Desktop inference profiles

Start the local inference server with `--flash-profile NAME --serve 11436`. The
first matching API request captures its effective system prompt and tools if the
profile does not exist yet. Requests may select a profile with the JSON field
`"flash_profile":"NAME"` or the `X-Flash-Profile` header; the JSON field wins.
`session_id` remains a separate conversation identifier.
Profile names use 1–64 lowercase ASCII letters, digits, `-`, or `_`.

DSH profiles use names such as `dsh-default-kevin`:

```bash
./metal_infer/infer --model "/path/to/model" --flash-profile dsh-default-kevin --sort-tools-alpha --serve 11436
```

`--dsh` has been removed. The `dsh-` profile name enables DSH Write handling
and the default repeated-failure guard, including when selected by a request.
To explicitly replace a profile source from its next matching request, start
with `--flash-profile-recapture NAME` (optionally alongside the same
`--flash-profile NAME`). Stored sources are named
`warm-tools-cache/flash-NAME-warm.json`; checkpoints are named
`warm-state/id2-flash-NAME-<prefix-hash>.state`. Existing
`warm-state/flash-NAME-<prefix-hash>.state` files use the earlier compatibility
identity. A matching legacy checkpoint can be fully validated and copied into
the new identity namespace without rewriting the original. The new identity
omits transient filesystem device IDs while retaining model, source, runtime
mode, inode, size, timestamp, and content-derived inputs. Completed checkpoints share a
4 GiB disk budget; the oldest other profiles are removed after a successful
save when the directory exceeds it.
Flash warm-source files are capped at 128 files and 64 MiB total; the startup
profile, active session profile, and current capture are protected from eviction.

Warm-state checkpoints use Zstd level 1 by default and store a separate
`warm-state/zstd-id2-<original-checkpoint-filename>` sidecar. The existing raw
checkpoint remains readable and is not rewritten. A versioned header identifies
the compressed representation: the stored bytes and the decompressed serialized
payload each have their own checksum. A compatible raw restore can create its
compressed sidecar without running another warmup. The current selective state
compatibility identity is independent of the storage representation. Use
`--warm-state-compression raw` to save and prefer the legacy uncompressed format
for debugging. `--warm-state-compression zstd` explicitly selects the default.
Both formats remain readable; a valid checkpoint in the other format can be
restored without recapturing the prefix.
For an isolated startup measurement without generating tokens, set
`FLASH_WARM_STATE_RESTORE_PROBE=1`; it times copying the loaded snapshot into
CPU/Metal state and reports peak process resident memory before and after.

## Production N-row prefill

Desktop `metal_infer/infer` now builds with the accepted production N-row
prefill geometry enabled by default:

```text
slab rows                     128
top-K                         8
routed assignments/slab       1024
gate+up kernel                grouped M4-8row
routed-down kernel            grouped M4-2row
expert staging slots          256 on the current 256-expert model
```

The normal Makefile `infer` target defines `FLASH_PREFILL_NROW_PRODUCTION` and
`FLASH_PREFILL_NROW_ASYNC`; the accepted N128/M4-8row/M4-2row geometry is the
default selected by `infer.m`. `--no-prefill-nrow` retains the established
scalar prefill path as an immediate runtime fallback. Decode behavior is
unchanged.

The promoted geometry passed scalar-vs-N-row hidden/logit/next-token/state
checks plus deterministic continuation validation. In serving-path tests it
also improved prefill performance over the former N64/M4-2row production
geometry. Representative aligned results:

```text
4099-token prefill:
  N64   202.424 s, 20.250 tok/s
  N128  185.576 s, 22.088 tok/s

5895-token DSH-scale prefill:
  N64   311.808 s, 18.906 tok/s
  N128  296.349 s, 19.892 tok/s   (production ./infer verification)
```

The server progress label still says `N64 prefill progress` for historical
reasons; the authoritative runtime geometry is reported by the startup lines
such as `slab_rows=128` and `production runtime ready N=128`.
