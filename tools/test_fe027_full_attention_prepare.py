#!/usr/bin/env python3
"""FE-027: source-guarded model-free scalar/N128 full-attention Q/K preparation test.

Checks the *actual checked-out source* has the intended shared Q/K normalization
and RoPE contracts and executes a synthetic float32 comparison over 128 rows.
It does NOT compare QKV projection kernels, actual model inputs, Metal attention,
or o-projection; a PASS must never be interpreted as N128 numerical qualification.
"""
import argparse
import json
import math
import pathlib
import re
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCALAR = ROOT / "metal_infer/infer.m"
NROW = ROOT / "metal_infer/prefill_nrow_grouped_async.inc"


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def source_contract(scalar, nrow):
    # These source guards intentionally fail closed when implementation changes;
    # update them only after reviewing the new scalar/N128 semantics.
    checks = {
        "scalar_sumsq": r"sum_sq\s*\+=\s*qh\[i\]\s*\*\s*qh\[i\]",
        "nrow_sumsq": r"ss\s*\+=\s*qh\[d\]\s*\*\s*qh\[d\]",
        "scalar_qnorm": r"qh\[i\]\s*=\s*qh\[i\]\s*\*\s*inv_rms\s*\*\s*bf16_to_f32\(qnorm_w\[i\]\)",
        "nrow_qnorm": r"qh\[d\]\s*=\s*qh\[d\]\s*\*\s*inv\s*\*\s*bf16_to_f32\(lc->q_norm_w\[d\]\)",
        "scalar_knorm": r"kh\[i\]\s*=\s*kh\[i\]\s*\*\s*inv_rms\s*\*\s*bf16_to_f32\(knorm_w\[i\]\)",
        "nrow_knorm": r"kh\[d\]\s*=\s*kh\[d\]\s*\*\s*inv\s*\*\s*bf16_to_f32\(lc->k_norm_w\[d\]\)",
        "scalar_rope": r"apply_rotary_emb\(q,\s*k_out,\s*pos,\s*NUM_ATTN_HEADS,\s*NUM_KV_HEADS,\s*HEAD_DIM,\s*ROTARY_DIM\)",
        "nrow_rope": r"apply_rotary_emb\(q,\s*k,\s*base_pos\s*\+\s*row,\s*NUM_ATTN_HEADS,\s*NUM_KV_HEADS,\s*HEAD_DIM,\s*ROTARY_DIM\)",
    }
    texts = {k: scalar if k.startswith("scalar_") else nrow for k in checks}
    return {k: bool(re.search(pattern, texts[k])) for k, pattern in checks.items()}


def norm(vec, weights, eps):
    # Mirror left-to-right float32 evaluation, without NumPy or host f64 sums.
    ss = f32(0)
    for x in vec:
        ss = f32(ss + f32(x * x))
    inv = f32(1 / f32(math.sqrt(f32(f32(ss / len(vec)) + eps))))
    return [f32(f32(x * inv) * w) for x, w in zip(vec, weights)]


def run_synthetic(rows, heads, head_dim, eps):
    if rows <= 0 or heads <= 0 or head_dim <= 0:
        raise ValueError("positive geometry required")
    maximum = 0.0
    different = 0
    tested = 0
    # Deliberately identical operands test arithmetic/row slicing only. No
    # assertion about real QKV projection, attention outputs or Metal kernels.
    for row in range(rows):
        for head in range(heads):
            vec = [f32(math.sin((row + 1) * (head + 3) * (d + 5) * .007)
                       * (0.01 if d % 17 == 0 else 1.0)) for d in range(head_dim)]
            weights = [f32(1.0 + (d % 7) / 32) for d in range(head_dim)]
            scalar_result = norm(vec, weights, eps)
            nrow_result = norm(vec[:], weights[:], eps)
            for a, b in zip(scalar_result, nrow_result):
                maximum = max(maximum, abs(a - b))
                different += a != b
                tested += 1
    return {"rows": rows, "heads": heads, "head_dim": head_dim,
            "floats": tested, "different": different, "max_abs": maximum}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path)
    parser.add_argument("--rows", type=int, default=128)
    parser.add_argument("--heads", type=int, default=16)
    parser.add_argument("--head-dim", type=int, default=128)
    args = parser.parse_args()
    source = source_contract(SCALAR.read_text(), NROW.read_text())
    synthetic = run_synthetic(args.rows, args.heads, args.head_dim, 1e-6)
    passed = all(source.values()) and synthetic["different"] == 0
    result = {
        "test": "FE027 full-attention preparation source and synthetic parity",
        "passed": passed, "source_contract": source, "synthetic": synthetic,
        "scope": "identical synthetic operands, Q/K RMSNorm arithmetic only; RoPE shared-call source guard",
        "not_tested": ["actual QKV projection", "actual model operand identity",
                       "RoPE output values", "Metal attention kernel", "o-projection",
                       "within-slab full model state", "resident HTTP", "1920/2304/303 failures"],
    }
    output = json.dumps(result, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output)
    print(output, end="")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
