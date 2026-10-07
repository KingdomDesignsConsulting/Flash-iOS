#include <metal_stdlib>
using namespace metal;

// Benchmark-only exact-small-M dense affine Q4 kernel.
// Processes four activation rows while traversing each packed weight once.
// Arithmetic for each row mirrors production dequant_matvec_4bit_v3:
// identical Q4 affine decode, per-lane packed-column order, FP32 FMA accumulation,
// and final simd_sum reduction. Current Qwen3.5 dense verifier inputs are 2048-wide.

static inline float bf16_to_float(ushort x) {
    return as_type<float>(uint(x) << 16);
}

kernel void dense_affine_q4_m4(
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

    // Four 2048-float rows = 32 KiB threadgroup memory.
    threadgroup float x_shared[8192];
    for (uint i = lid; i < in_dim; i += 256u) {
        x_shared[i] = inputs[i];
        x_shared[2048u + i] = inputs[input_stride + i];
        x_shared[4096u + i] = inputs[2u * input_stride + i];
        x_shared[6144u + i] = inputs[3u * input_stride + i];
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);

    if (row >= out_dim) return;

    device const uint *w_row = weights + row * packed_cols;
    device const ushort *s_row = scales + row * num_groups;
    device const ushort *b_row = biases + row * num_groups;

    float acc0 = 0.0f;
    float acc1 = 0.0f;
    float acc2 = 0.0f;
    float acc3 = 0.0f;

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

        const float x20 = x_shared[4096u + xbase + 0u];
        const float x21 = x_shared[4096u + xbase + 1u];
        const float x22 = x_shared[4096u + xbase + 2u];
        const float x23 = x_shared[4096u + xbase + 3u];
        const float x24 = x_shared[4096u + xbase + 4u];
        const float x25 = x_shared[4096u + xbase + 5u];
        const float x26 = x_shared[4096u + xbase + 6u];
        const float x27 = x_shared[4096u + xbase + 7u];

        const float x30 = x_shared[6144u + xbase + 0u];
        const float x31 = x_shared[6144u + xbase + 1u];
        const float x32 = x_shared[6144u + xbase + 2u];
        const float x33 = x_shared[6144u + xbase + 3u];
        const float x34 = x_shared[6144u + xbase + 4u];
        const float x35 = x_shared[6144u + xbase + 5u];
        const float x36 = x_shared[6144u + xbase + 6u];
        const float x37 = x_shared[6144u + xbase + 7u];

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

        acc2 += fma(float((packed >>  0u) & 0xFu), scale * x20, bias * x20);
        acc2 += fma(float((packed >>  4u) & 0xFu), scale * x21, bias * x21);
        acc2 += fma(float((packed >>  8u) & 0xFu), scale * x22, bias * x22);
        acc2 += fma(float((packed >> 12u) & 0xFu), scale * x23, bias * x23);
        acc2 += fma(float((packed >> 16u) & 0xFu), scale * x24, bias * x24);
        acc2 += fma(float((packed >> 20u) & 0xFu), scale * x25, bias * x25);
        acc2 += fma(float((packed >> 24u) & 0xFu), scale * x26, bias * x26);
        acc2 += fma(float((packed >> 28u) & 0xFu), scale * x27, bias * x27);

        acc3 += fma(float((packed >>  0u) & 0xFu), scale * x30, bias * x30);
        acc3 += fma(float((packed >>  4u) & 0xFu), scale * x31, bias * x31);
        acc3 += fma(float((packed >>  8u) & 0xFu), scale * x32, bias * x32);
        acc3 += fma(float((packed >> 12u) & 0xFu), scale * x33, bias * x33);
        acc3 += fma(float((packed >> 16u) & 0xFu), scale * x34, bias * x34);
        acc3 += fma(float((packed >> 20u) & 0xFu), scale * x35, bias * x35);
        acc3 += fma(float((packed >> 24u) & 0xFu), scale * x36, bias * x36);
        acc3 += fma(float((packed >> 28u) & 0xFu), scale * x37, bias * x37);
    }

    const float sum0 = simd_sum(acc0);
    const float sum1 = simd_sum(acc1);
    const float sum2 = simd_sum(acc2);
    const float sum3 = simd_sum(acc3);
    if (lane == 0u) {
        outputs[row] = sum0;
        outputs[output_stride + row] = sum1;
        outputs[2u * output_stride + row] = sum2;
        outputs[3u * output_stride + row] = sum3;
    }
}
