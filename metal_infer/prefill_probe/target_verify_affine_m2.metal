#include <metal_stdlib>
using namespace metal;

// Benchmark-only exact-small-M dense affine Q4 kernel.
// Processes two activation rows while traversing each packed weight once.
// Arithmetic for each row mirrors production dequant_matvec_4bit_v3:
// identical Q4 affine decode, per-lane packed-column order, FP32 FMA accumulation,
// and final simd_sum reduction. Current Qwen3.5 dense verifier inputs are 2048-wide.

static inline float bf16_to_float(ushort x) {
    return as_type<float>(uint(x) << 16);
}

kernel void dense_affine_q4_m2(
    device const uint *weights [[buffer(0)]],
    device const ushort *scales [[buffer(1)]],
    device const ushort *biases [[buffer(2)]],
    device const float *inputs [[buffer(3)]],
    device float *outputs [[buffer(4)]],
    constant uint &out_dim [[buffer(5)]],
    constant uint &in_dim [[buffer(6)]],
    constant uint &group_size [[buffer(7)]],
    constant uint &input_stride [[buffer(8)]],
    constant uint &output_stride [[buffer(9)]],
    uint tg [[threadgroup_position_in_grid]],
    uint lid [[thread_position_in_threadgroup]],
    uint lane [[thread_index_in_simdgroup]],
    uint simd [[simdgroup_index_in_threadgroup]]) {
    if (in_dim > 2048u || group_size != 64u) return;

    const uint row = tg * 8u + simd;
    const uint packed_cols = in_dim / 8u;
    const uint num_groups = in_dim / group_size;

    // Two 2048-float rows = 16 KiB threadgroup memory.
    threadgroup float x_shared[4096];
    for (uint i = lid; i < in_dim; i += 256u) {
        x_shared[i] = inputs[i];
        x_shared[2048u + i] = inputs[input_stride + i];
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);

    if (row >= out_dim) return;

    device const uint *w_row = weights + row * packed_cols;
    device const ushort *s_row = scales + row * num_groups;
    device const ushort *b_row = biases + row * num_groups;

    float acc0 = 0.0f;
    float acc1 = 0.0f;
    for (uint col = lane; col < packed_cols; col += 32u) {
        const uint group = col / 8u;
        const float scale = bf16_to_float(s_row[group]);
        const float bias = bf16_to_float(b_row[group]);
        const uint packed = w_row[col];
        const uint xbase = col * 8u;

        const float x00 = x_shared[xbase + 0u];
        const float x01 = x_shared[xbase + 1u];
        const float x02 = x_shared[xbase + 2u];
        const float x03 = x_shared[xbase + 3u];
        const float x04 = x_shared[xbase + 4u];
        const float x05 = x_shared[xbase + 5u];
        const float x06 = x_shared[xbase + 6u];
        const float x07 = x_shared[xbase + 7u];

        const float x10 = x_shared[2048u + xbase + 0u];
        const float x11 = x_shared[2048u + xbase + 1u];
        const float x12 = x_shared[2048u + xbase + 2u];
        const float x13 = x_shared[2048u + xbase + 3u];
        const float x14 = x_shared[2048u + xbase + 4u];
        const float x15 = x_shared[2048u + xbase + 5u];
        const float x16 = x_shared[2048u + xbase + 6u];
        const float x17 = x_shared[2048u + xbase + 7u];

        acc0 += fma(float((packed >>  0u) & 0xFu), scale * x00, bias * x00);
        acc0 += fma(float((packed >>  4u) & 0xFu), scale * x01, bias * x01);
        acc0 += fma(float((packed >>  8u) & 0xFu), scale * x02, bias * x02);
        acc0 += fma(float((packed >> 12u) & 0xFu), scale * x03, bias * x03);
        acc0 += fma(float((packed >> 16u) & 0xFu), scale * x04, bias * x04);
        acc0 += fma(float((packed >> 20u) & 0xFu), scale * x05, bias * x05);
        acc0 += fma(float((packed >> 24u) & 0xFu), scale * x06, bias * x06);
        acc0 += fma(float((packed >> 28u) & 0xFu), scale * x07, bias * x07);

        acc1 += fma(float((packed >>  0u) & 0xFu), scale * x10, bias * x10);
        acc1 += fma(float((packed >>  4u) & 0xFu), scale * x11, bias * x11);
        acc1 += fma(float((packed >>  8u) & 0xFu), scale * x12, bias * x12);
        acc1 += fma(float((packed >> 12u) & 0xFu), scale * x13, bias * x13);
        acc1 += fma(float((packed >> 16u) & 0xFu), scale * x14, bias * x14);
        acc1 += fma(float((packed >> 20u) & 0xFu), scale * x15, bias * x15);
        acc1 += fma(float((packed >> 24u) & 0xFu), scale * x16, bias * x16);
        acc1 += fma(float((packed >> 28u) & 0xFu), scale * x17, bias * x17);
    }

    const float sum0 = simd_sum(acc0);
    const float sum1 = simd_sum(acc1);
    if (lane == 0u) {
        outputs[row] = sum0;
        outputs[output_stride + row] = sum1;
    }
}
