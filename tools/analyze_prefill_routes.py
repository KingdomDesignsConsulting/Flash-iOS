#!/usr/bin/env python3
"""Summarize real Flash-iOS routing traces for contiguous prefill chunks."""

import argparse
import json
import struct
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("tiered_manifest", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.tiered_manifest.read_text())
    layers = manifest["num_layers"]
    k = 8
    record_bytes = 8 + 2048 * 4 + k * 4
    raw = args.trace.read_bytes()
    if len(raw) % record_bytes:
        raise ValueError("routing trace has a partial record")
    records = len(raw) // record_bytes
    if records % layers:
        raise ValueError("routing trace does not contain complete token layers")
    token_count = records // layers
    routes = [[None] * token_count for _ in range(layers)]
    for i in range(records):
        at = i * record_bytes
        layer, count = struct.unpack_from("<ii", raw, at)
        if not 0 <= layer < layers or count != k:
            raise ValueError(f"bad record {i}: layer={layer}, K={count}")
        token = i // layers
        routes[layer][token] = struct.unpack_from("<8i", raw, at + 8 + 2048 * 4)
    if any(row is None for layer in routes for row in layer):
        raise ValueError("trace order or coverage is incomplete")

    result = {"tokens": token_count, "layers": layers, "k": k,
              "trace_bytes": len(raw), "chunks": {}}
    for n in (1, 4, 8, 16, 32, 64):
        totals = Counter()
        group_sizes = Counter()
        for layer in range(layers):
            info = manifest["layers"][str(layer)]["experts"]
            for start in range(0, token_count, n):
                block = routes[layer][start:start + n]
                counts = Counter(expert for row in block for expert in row)
                totals["windows"] += 1
                totals["occurrences"] += sum(counts.values())
                totals["unique"] += len(counts)
                for multiplicity in counts.values():
                    group_sizes[multiplicity] += 1
                for row in block:
                    for expert in row:
                        entry = info[expert]
                        tag = "hot" if entry["bits"] == 4 else "cold"
                        totals[tag + "_occurrences"] += 1
                        totals["occurrence_bytes"] += entry["size"]
                for expert in counts:
                    entry = info[expert]
                    tag = "hot" if entry["bits"] == 4 else "cold"
                    totals[tag + "_unique"] += 1
                    totals["unique_bytes"] += entry["size"]
                for a, b in zip(block, block[1:]):
                    totals["adjacent_pairs"] += 1
                    totals["adjacent_overlap"] += len(set(a) & set(b))
        totals["repeated"] = totals["occurrences"] - totals["unique"]
        totals["ideal_bytes_saved"] = totals["occurrence_bytes"] - totals["unique_bytes"]
        summary = dict(totals)
        summary["mean_unique_per_window"] = totals["unique"] / totals["windows"]
        summary["mean_adjacent_overlap"] = (
            totals["adjacent_overlap"] / totals["adjacent_pairs"]
            if totals["adjacent_pairs"] else 0)
        summary["expert_group_sizes"] = dict(sorted(group_sizes.items()))
        result["chunks"][str(n)] = summary
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
