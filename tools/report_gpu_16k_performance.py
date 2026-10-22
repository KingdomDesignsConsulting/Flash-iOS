#!/usr/bin/env python3
"""Combine saved performance manifests without rerunning inference."""
import argparse
import csv
import json
import pathlib

from benchmark_gpu_16k import idle, summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", nargs="+", type=pathlib.Path)
    parser.add_argument("--out", required=True, type=pathlib.Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    records = []
    for path in args.manifests:
        manifest = json.loads(path.read_text())
        for record in manifest["runs"]:
            record["dataset"] = str(path.parent)
            record["accepted"] = record["accepted"] and idle(record["pre_gpu"]) and idle(record["post_gpu"])
            # This already failed the GPU gate; explicitly record the concurrent
            # macro-disabled build as an additional exclusion reason.
            if "confirmation" in path.parent.name and record["name"] == "round0-8191-16k":
                record["accepted"] = False
                record["exclusion_reason"] = "GPU gate and concurrent build"
            records.append(record)
    for pos in {r["pos"] for r in records}:
        matched = [r for r in records if r["pos"] == pos]
        for step in {s["step"] for r in matched for s in r["data"]["step"]}:
            tokens = {s["token"] for r in matched for s in r["data"]["step"] if s["step"] == step}
            if len(tokens) != 1:
                raise RuntimeError(f"Cross-run decode token mismatch: {pos}, {step}, {tokens}")
        tokens = {p["next_token"] for r in matched for p in r["data"]["prefill"]}
        if len(tokens) != 1:
            raise RuntimeError(f"Cross-run prefill token mismatch: {pos}, {tokens}")
    report = summarize(records)
    report["input_manifests"] = list(map(str, args.manifests))
    report["total_processes"] = len(records)
    report["accepted_processes"] = sum(r["accepted"] for r in records)
    report["decode_and_suffix_tokens_match"] = True
    for row in report["table"]:
        pos = 16382 if row["context"] == 16384 else row["context"] - 1
        row["accepted_processes"] = sum(r["accepted"] and r["pos"] == pos and r["arm"] == row["arm"] for r in records)
    (args.out / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    fields = ["context", "arm", "decode_tps", "token_ms_cv_percent", "attention_ms_per_layer", "backend", "physical_mib", "peak_physical_mib", "peak_rss_mib", "suffix_prefill_tps", "checkpoint_ttft_ms", "processes", "samples", "confidence"]
    rows = []
    for row in report["table"]:
        gpu = row["gpu_layers"] == 10
        rows.append(dict(context=row["context"], arm=row["arm"], decode_tps=round(row["decode_tps"], 3),
            token_ms_cv_percent=round(100 * row["token_ms"]["cv"], 2),
            attention_ms_per_layer=round(row["attention_gpu_ms_per_layer" if gpu else "attention_cpu_ms_per_layer"]["median"], 3),
            backend="GPU" if gpu else "CPU", physical_mib=round(row["physical_bytes"]["median"] / 2**20, 2),
            peak_physical_mib=round(row["peak_physical_bytes"] / 2**20, 2), peak_rss_mib=round(row["peak_rss_bytes"] / 2**20, 2),
            suffix_prefill_tps=round(row["suffix_prefill_tps"]["median"], 3), checkpoint_ttft_ms=round(row["checkpoint_assisted_ttft_ms"]["median"], 3),
            processes=row["accepted_processes"], samples=row["token_ms"]["n"], confidence=row["confidence"]))
    with (args.out / "summary.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    lines = ["| Context | Arm | Decode tok/s | CV % | Attention ms/layer | Backend | Physical MiB | Peak physical MiB | Processes / samples |", "|---:|---|---:|---:|---:|---|---:|---:|---:|"]
    for r in rows:
        lines.append(f"| {r['context']} | {r['arm']} | {r['decode_tps']:.3f} | {r['token_ms_cv_percent']:.2f} | {r['attention_ms_per_layer']:.3f} | {r['backend']} | {r['physical_mib']:.2f} | {r['peak_physical_mib']:.2f} | {r['processes']} / {r['samples']} |")
    (args.out / "table.md").write_text("\n".join(lines) + "\n")
    print(f"Processes: {report['accepted_processes']}/{len(records)} accepted; decode/suffix tokens match")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
