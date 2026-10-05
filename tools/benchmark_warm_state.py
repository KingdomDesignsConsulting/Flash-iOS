#!/usr/bin/env python3
"""Isolated, read-only-source benchmark for Flash-iOS warm-state checkpoints."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import statistics
import struct
import subprocess
import time
import uuid

HEADER_BYTES = 368
KV_LEN_OFFSET = 108
MAX_LAYERS = 64
BLOCK_BYTES = 1 << 20


def inspect_checkpoint(path: Path):
    size = path.stat().st_size
    with path.open("rb") as handle:
        head = handle.read(HEADER_BYTES)
    if len(head) != HEADER_BYTES or head[:8] != b"FWSTATE1":
        raise ValueError("not a Flash warm-state checkpoint")
    version, header_bytes, layout_version = struct.unpack_from("<III", head, 8)
    payload_bytes = struct.unpack_from("<Q", head, 48)[0]
    token_count, pos, layers, kv_dim, conv_bytes, ssm_bytes, gpu_layers = (
        struct.unpack_from("<7I", head, 80)
    )
    kv_len = struct.unpack_from(f"<{MAX_LAYERS}i", head, KV_LEN_OFFSET)
    if header_bytes != HEADER_BYTES or size != header_bytes + payload_bytes:
        raise ValueError("checkpoint header or file length mismatch")
    if not (0 < layers <= MAX_LAYERS and token_count == pos and
            all(n >= 0 for n in kv_len[:layers])):
        raise ValueError("checkpoint geometry is invalid")
    regions = []
    offset = header_bytes
    by_type = {}

    def add(kind, length):
        nonlocal offset
        if length < 0 or length % 4:
            raise ValueError(f"{kind} is not an FP32-sized region")
        regions.append((offset, length, kind))
        by_type[kind] = by_type.get(kind, 0) + length
        offset += length

    for layer in range(layers):
        if kv_len[layer]:
            length = kv_len[layer] * kv_dim * 4
            add("full_attention_k", length)
            add("full_attention_v", length)
        else:
            add("linear_conv", conv_bytes)
            add("linear_ssm", ssm_bytes)
    for _ in range(gpu_layers):
        add("gpu_delta", 64 * 128 * 128 * 4)
        add("gpu_conv", 3 * 12288 * 4)
    if offset != size:
        raise ValueError(f"serialized regions end at {offset}, file ends at {size}")
    return {
        "path": str(path), "bytes": size, "header_bytes": header_bytes,
        "payload_bytes": payload_bytes, "version": version,
        "layout_version": layout_version, "token_count": token_count,
        "layers": layers, "gpu_layers": gpu_layers, "regions": regions,
        "region_bytes": by_type,
    }


def bitshuffle_bytes(data: bytes, regions, inverse=False):
    import numpy as np

    output = bytearray(data)
    for offset, length, _ in regions:
        end = offset + length
        for start in range(offset, end, BLOCK_BYTES):
            stop = min(start + BLOCK_BYTES, end)
            block = np.frombuffer(data, dtype=np.uint8, count=stop - start,
                                  offset=start)
            words = (stop - start) // 4
            if inverse:
                bits = np.unpackbits(block, bitorder="little").reshape(32, words).T
                output[start:stop] = np.packbits(
                    bits, axis=1, bitorder="little").tobytes()
            else:
                bits = np.unpackbits(block.reshape(words, 4),
                                     axis=1, bitorder="little")
                output[start:stop] = np.packbits(
                    bits.T.reshape(-1), bitorder="little").tobytes()
    return bytes(output)


def commands(codec):
    if codec == "none":
        return None, None
    if codec == "lz4":
        return ["lz4", "-1", "-z", "-q", "-c"], ["lz4", "-d", "-q", "-c"]
    if codec.startswith("zstd"):
        level = int(codec[4:])
        return ["zstd", "-q", "-T1", f"-{level}", "-c"], ["zstd", "-d", "-q", "-c"]
    if codec == "xz6":
        return ["xz", "-T1", "-6", "-c"], ["xz", "-d", "-c"]
    if codec == "gzip6":
        return ["gzip", "-6", "-c"], ["gzip", "-d", "-c"]
    raise ValueError(f"unknown codec: {codec}")


def run_command(command, data):
    result = subprocess.run(command, input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise RuntimeError(f"{' '.join(command)} failed: {result.stderr.decode(errors='replace')}")
    return result.stdout


def benchmark(args, layout):
    start = time.perf_counter()
    source = args.source.read_bytes()
    source_read_s = time.perf_counter() - start
    original_hash = hashlib.sha256(source).hexdigest()
    if len(source) != layout["bytes"]:
        raise ValueError("source changed during inspection")
    shuffled = args.codec.startswith("bitshuffle-")
    codec = args.codec.removeprefix("bitshuffle-")
    encode, decode = commands(codec)
    args.workdir.mkdir(parents=True, exist_ok=True)
    rounds = []
    for index in range(args.repeats):
        start = time.perf_counter()
        transformed = bitshuffle_bytes(source, layout["regions"]) if shuffled else source
        shuffle_s = time.perf_counter() - start
        start = time.perf_counter()
        compressed = run_command(encode, transformed) if encode else transformed
        compress_s = time.perf_counter() - start
        output = args.workdir / f"{args.codec}-{uuid.uuid4().hex}.bin"
        try:
            start = time.perf_counter()
            with output.open("xb") as handle:
                handle.write(compressed)
                handle.flush()
                os.fsync(handle.fileno())
            write_s = time.perf_counter() - start
            start = time.perf_counter()
            disk_bytes = output.read_bytes()
            read_s = time.perf_counter() - start
            start = time.perf_counter()
            restored = run_command(decode, disk_bytes) if decode else disk_bytes
            decompress_s = time.perf_counter() - start
            start = time.perf_counter()
            recovered = bitshuffle_bytes(restored, layout["regions"], inverse=True) \
                if shuffled else restored
            unshuffle_s = time.perf_counter() - start
            start = time.perf_counter()
            match = hashlib.sha256(recovered).hexdigest() == original_hash
            hash_s = time.perf_counter() - start
            if not match or recovered != source:
                raise ValueError(f"round trip failed for {args.codec}")
            rounds.append({
                "compressed_bytes": len(disk_bytes), "shuffle_s": shuffle_s,
                "compress_s": compress_s, "write_fsync_s": write_s,
                "read_s": read_s, "decompress_s": decompress_s,
                "unshuffle_s": unshuffle_s, "hash_s": hash_s,
                "save_s": shuffle_s + compress_s + write_s,
                "restore_s": read_s + decompress_s + unshuffle_s + hash_s,
                "sha256_match": match,
            })
        finally:
            output.unlink(missing_ok=True)
        print(f"[{args.codec}] round {index + 1}/{args.repeats}: "
              f"{rounds[-1]['compressed_bytes']} bytes, "
              f"save {rounds[-1]['save_s']:.3f}s, "
              f"restore {rounds[-1]['restore_s']:.3f}s", flush=True)
    warm = rounds[1:] if len(rounds) > 1 else rounds
    metric = {key: statistics.median(row[key] for row in warm)
              for key in ("shuffle_s", "compress_s", "write_fsync_s", "read_s",
                          "decompress_s", "unshuffle_s", "hash_s", "save_s",
                          "restore_s")}
    compressed_bytes = rounds[-1]["compressed_bytes"]
    result = {
        "codec": args.codec, "source": str(args.source),
        "original_bytes": len(source), "compressed_bytes": compressed_bytes,
        "ratio": len(source) / compressed_bytes,
        "space_saved_pct": 100 * (1 - compressed_bytes / len(source)),
        "source_sha256": original_hash, "source_read_s": source_read_s,
        "commands": {"compress": encode, "decompress": decode},
        "warm_median": metric, "first_round": rounds[0], "rounds": rounds,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    with args.jsonl.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "codec", "original_bytes", "compressed_bytes", "ratio",
        "space_saved_pct", "peak_rss_bytes")}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--codec")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--jsonl", type=Path)
    args = parser.parse_args()
    layout = inspect_checkpoint(args.source)
    if args.inspect:
        print(json.dumps({key: value for key, value in layout.items()
                          if key != "regions"}, indent=2, sort_keys=True))
        return
    if not args.codec or not args.workdir or not args.jsonl or args.repeats < 1:
        parser.error("--codec, --workdir, --jsonl, and a positive --repeats are required")
    benchmark(args, layout)


if __name__ == "__main__":
    main()
