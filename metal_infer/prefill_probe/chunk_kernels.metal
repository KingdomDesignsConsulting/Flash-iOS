#include <metal_stdlib>
using namespace metal;

// Benchmark-only Qwen3.5 GDN recurrence. A thread owns one value/state row.
// The chunk kernel keeps its 128-element recurrent row local across known
// prompt positions, preserving causal order while avoiding per-token state I/O.
static inline void gdn_step(thread float s[128], uint head, uint vi, uint t,
    device const float *q, device const float *k, device const float *v,
    device const float *decay, device const float *beta,
    device float *out) {
    const uint kh = head / 2;
    const float g = decay[t * 32 + head];
    const float b = beta[t * 32 + head];
    float mem = 0.0f;
    for (uint j = 0; j < 128; j++) {
        s[j] *= g;
        mem += s[j] * k[t * 2048 + kh * 128 + j];
    }
    const float delta = (v[t * 4096 + head * 128 + vi] - mem) * b;
    for (uint j = 0; j < 128; j++)
        s[j] += k[t * 2048 + kh * 128 + j] * delta;
    float value = 0.0f;
    for (uint j = 0; j < 128; j++)
        value += s[j] * q[t * 2048 + kh * 128 + j];
    out[t * 4096 + head * 128 + vi] = value;
}

kernel void gdn_scalar(device float *state [[buffer(0)]],
    device const float *q [[buffer(1)]], device const float *k [[buffer(2)]],
    device const float *v [[buffer(3)]], device const float *decay [[buffer(4)]],
    device const float *beta [[buffer(5)]], device float *out [[buffer(6)]],
    constant uint &t [[buffer(7)]], uint tid [[thread_position_in_grid]]) {
    if (tid >= 4096) return;
    const uint head = tid / 128, vi = tid % 128;
    const uint base = head * 16384 + vi * 128;
    float s[128];
    for (uint j = 0; j < 128; j++) s[j] = state[base + j];
    gdn_step(s, head, vi, t, q, k, v, decay, beta, out);
    for (uint j = 0; j < 128; j++) state[base + j] = s[j];
}

kernel void gdn_chunk(device float *state [[buffer(0)]],
    device const float *q [[buffer(1)]], device const float *k [[buffer(2)]],
    device const float *v [[buffer(3)]], device const float *decay [[buffer(4)]],
    device const float *beta [[buffer(5)]], device float *out [[buffer(6)]],
    constant uint &count [[buffer(7)]], uint tid [[thread_position_in_grid]]) {
    if (tid >= 4096) return;
    const uint head = tid / 128, vi = tid % 128;
    const uint base = head * 16384 + vi * 128;
    float s[128];
    for (uint j = 0; j < 128; j++) s[j] = state[base + j];
    for (uint t = 0; t < count; t++)
        gdn_step(s, head, vi, t, q, k, v, decay, beta, out);
    for (uint j = 0; j < 128; j++) state[base + j] = s[j];
}

// Matches the production depthwise convolution's kernel=4, row-major
// three-token tail, BF16 weights, SiLU output, and causal tail update.
static inline void conv_step(thread float tail[3], uint channel, uint t,
    device const float *input, device const ushort *weights,
    device float *output) {
    const uint w = channel * 4;
    float x = input[t * 8192 + channel];
    float acc = tail[0] * as_type<float>(uint(weights[w]) << 16);
    acc += tail[1] * as_type<float>(uint(weights[w + 1]) << 16);
    acc += tail[2] * as_type<float>(uint(weights[w + 2]) << 16);
    acc += x * as_type<float>(uint(weights[w + 3]) << 16);
    output[t * 8192 + channel] = acc / (1.0f + exp(-acc));
    tail[0] = tail[1]; tail[1] = tail[2]; tail[2] = x;
}

kernel void conv_scalar(device float *state [[buffer(0)]],
    device const float *input [[buffer(1)]],
    device const ushort *weights [[buffer(2)]],
    device float *output [[buffer(3)]],
    constant uint &t [[buffer(4)]], uint c [[thread_position_in_grid]]) {
    if (c >= 8192) return;
    float tail[3] = {state[c], state[8192 + c], state[16384 + c]};
    conv_step(tail, c, t, input, weights, output);
    state[c] = tail[0]; state[8192 + c] = tail[1]; state[16384 + c] = tail[2];
}

kernel void conv_chunk(device float *state [[buffer(0)]],
    device const float *input [[buffer(1)]],
    device const ushort *weights [[buffer(2)]],
    device float *output [[buffer(3)]],
    constant uint &count [[buffer(4)]], uint c [[thread_position_in_grid]]) {
    if (c >= 8192) return;
    float tail[3] = {state[c], state[8192 + c], state[16384 + c]};
    for (uint t = 0; t < count; t++) conv_step(tail, c, t, input, weights, output);
    state[c] = tail[0]; state[8192 + c] = tail[1]; state[16384 + c] = tail[2];
}

// Keep the production QKV layout in the convolution output while presenting
// contiguous per-component rows to the already validated GDN chunk kernel.
kernel void split_qkv(device const float *qkv [[buffer(0)]],
    device float *q [[buffer(1)]], device float *k [[buffer(2)]],
    device float *v [[buffer(3)]], constant uint &count [[buffer(4)]],
    uint tid [[thread_position_in_grid]]) {
    if (tid >= count * 8192) return;
    uint row = tid / 8192, col = tid % 8192;
    if (col < 2048) q[row * 2048 + col] = qkv[tid];
    else if (col < 4096) k[row * 2048 + col - 2048] = qkv[tid];
    else v[row * 4096 + col - 4096] = qkv[tid];
}

static inline float bf16_to_float(ushort x) {
    return as_type<float>(uint(x) << 16);
}

// One workgroup owns one output row of one real tiered expert. Each packed
// weight is decoded once and accumulated into up to 64 input rows. Both the
// 4-bit and 2-bit formats use their native affine scales/biases in the kernel.
kernel void grouped_tiered_projection(
    device const uint *weights [[buffer(0)]],
    device const ushort *scales [[buffer(1)]],
    device const ushort *biases [[buffer(2)]],
    device const float *inputs [[buffer(3)]],
    device float *outputs [[buffer(4)]],
    constant uint &in_dim [[buffer(5)]],
    constant uint &out_dim [[buffer(6)]],
    constant uint &count [[buffer(7)]],
    constant uint &bits [[buffer(8)]],
    uint row [[threadgroup_position_in_grid]],
    uint lane [[thread_position_in_threadgroup]]) {
    if (row >= out_dim || lane >= 32) return;
    const uint values_per_word = 32 / bits;
    const uint packed_cols = in_dim / values_per_word;
    const uint groups = in_dim / 64;
    float acc[64];
    for (uint m = 0; m < count; m++) acc[m] = 0.0f;
    for (uint col = lane; col < packed_cols; col += 32) {
        const uint group = col / (64 / values_per_word);
        const float scale = bf16_to_float(scales[row * groups + group]);
        const float bias = bf16_to_float(biases[row * groups + group]);
        const uint packed = weights[row * packed_cols + col];
        for (uint j = 0; j < values_per_word; j++) {
            const float w = float((packed >> (j * bits)) & ((1u << bits) - 1u)) * scale + bias;
            const uint xcol = col * values_per_word + j;
            for (uint m = 0; m < count; m++)
                acc[m] += w * inputs[m * in_dim + xcol];
        }
    }
    for (uint m = 0; m < count; m++) {
        const float sum = simd_sum(acc[m]);
        if (lane == 0) outputs[m * out_dim + row] = sum;
    }
}

// V12A small-M diagnostic: fixed M=4 routed-down tile inspired by the
// verifier shape used by dflash-mlx.  One 32-thread SIMD workgroup owns one
// output row for up to four routed activations of a single expert.  Each packed
// weight is decoded once per four-row tile and reused across those activations.
// Groups larger than four rows are split into multiple tiles; groups smaller
// than four use a single partial tile.  Arithmetic order within each row is
// intentionally the same as grouped_tiered_projection_acc32.
kernel void grouped_tiered_projection_m4(
    device const uint *weights [[buffer(0)]],
    device const ushort *scales [[buffer(1)]],
    device const ushort *biases [[buffer(2)]],
    device const float *inputs [[buffer(3)]],
    device float *outputs [[buffer(4)]],
    constant uint &in_dim [[buffer(5)]],
    constant uint &out_dim [[buffer(6)]],
    constant uint &count [[buffer(7)]],
    constant uint &bits [[buffer(8)]],
    uint3 tg [[threadgroup_position_in_grid]],
    uint3 tid [[thread_position_in_threadgroup]]) {
    const uint row = tg.x;
    const uint base = tg.y * 4u;
    const uint lane = tid.x;
    if (row >= out_dim || lane >= 32 || base >= count) return;

    const uint values_per_word = 32 / bits;
    const uint packed_cols = in_dim / values_per_word;
    const uint groups = in_dim / 64;
    const bool v1 = base + 1u < count;
    const bool v2 = base + 2u < count;
    const bool v3 = base + 3u < count;
    float a0 = 0.0f;
    float a1 = 0.0f;
    float a2 = 0.0f;
    float a3 = 0.0f;

    for (uint col = lane; col < packed_cols; col += 32) {
        const uint group = col / (64 / values_per_word);
        const float scale = bf16_to_float(scales[row * groups + group]);
        const float bias = bf16_to_float(biases[row * groups + group]);
        const uint packed = weights[row * packed_cols + col];
        for (uint j = 0; j < values_per_word; j++) {
            const float w = float((packed >> (j * bits)) & ((1u << bits) - 1u)) * scale + bias;
            const uint xcol = col * values_per_word + j;
            a0 += w * inputs[(base + 0u) * in_dim + xcol];
            if (v1) a1 += w * inputs[(base + 1u) * in_dim + xcol];
            if (v2) a2 += w * inputs[(base + 2u) * in_dim + xcol];
            if (v3) a3 += w * inputs[(base + 3u) * in_dim + xcol];
        }
    }

    const float s0 = simd_sum(a0);
    const float s1 = simd_sum(a1);
    const float s2 = simd_sum(a2);
    const float s3 = simd_sum(a3);
    if (lane == 0) {
        outputs[(base + 0u) * out_dim + row] = s0;
        if (v1) outputs[(base + 1u) * out_dim + row] = s1;
        if (v2) outputs[(base + 2u) * out_dim + row] = s2;
        if (v3) outputs[(base + 3u) * out_dim + row] = s3;
    }
}

// V12C occupancy midpoint: same fixed M=4 arithmetic as V12A, with one
// 64-thread workgroup carrying two independent 32-lane SIMD groups. Each
// SIMD group owns one output row and consumes the same four-activation tile.
// This isolates 2-SIMD threadgroup packing between V12A (1) and V12B (4).
// Benchmark-only exact-small-M dense affine Q4 kernel.
// Processes two activation rows while traversing each packed weight once.
// Arithmetic for each row mirrors production dequant_matvec_4bit_v3:
// identical Q4 affine decode, per-lane packed-column order, FP32 FMA accumulation,
// and final simd_sum reduction. Current Qwen3.5 dense verifier inputs are 2048-wide.
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
    // The verifier prototype is intentionally limited to the production
    // hidden width and group-size-64 MLX affine layout.
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

kernel void grouped_tiered_projection_m4_2row(
    device const uint *weights [[buffer(0)]],
    device const ushort *scales [[buffer(1)]],
    device const ushort *biases [[buffer(2)]],
    device const float *inputs [[buffer(3)]],
    device float *outputs [[buffer(4)]],
    constant uint &in_dim [[buffer(5)]],
    constant uint &out_dim [[buffer(6)]],
    constant uint &count [[buffer(7)]],
    constant uint &bits [[buffer(8)]],
    uint3 tg [[threadgroup_position_in_grid]],
    uint3 tid [[thread_position_in_threadgroup]]) {
    const uint simd = tid.x >> 5;
    const uint lane = tid.x & 31u;
    const uint row = tg.x * 2u + simd;
    const uint base = tg.y * 4u;
    if (simd >= 2u || row >= out_dim || base >= count) return;
    const uint values_per_word = 32 / bits;
    const uint packed_cols = in_dim / values_per_word;
    const uint groups = in_dim / 64;
    const bool v1 = base + 1u < count;
    const bool v2 = base + 2u < count;
    const bool v3 = base + 3u < count;
    float a0 = 0.0f, a1 = 0.0f, a2 = 0.0f, a3 = 0.0f;
    for (uint col = lane; col < packed_cols; col += 32) {
        const uint group = col / (64 / values_per_word);
        const float scale = bf16_to_float(scales[row * groups + group]);
        const float bias = bf16_to_float(biases[row * groups + group]);
        const uint packed = weights[row * packed_cols + col];
        for (uint j = 0; j < values_per_word; j++) {
            const float w = float((packed >> (j * bits)) & ((1u << bits) - 1u)) * scale + bias;
            const uint xcol = col * values_per_word + j;
            a0 += w * inputs[(base + 0u) * in_dim + xcol];
            if (v1) a1 += w * inputs[(base + 1u) * in_dim + xcol];
            if (v2) a2 += w * inputs[(base + 2u) * in_dim + xcol];
            if (v3) a3 += w * inputs[(base + 3u) * in_dim + xcol];
        }
    }
    const float s0 = simd_sum(a0), s1 = simd_sum(a1);
    const float s2 = simd_sum(a2), s3 = simd_sum(a3);
    if (lane == 0) {
        outputs[(base + 0u) * out_dim + row] = s0;
        if (v1) outputs[(base + 1u) * out_dim + row] = s1;
        if (v2) outputs[(base + 2u) * out_dim + row] = s2;
        if (v3) outputs[(base + 3u) * out_dim + row] = s3;
    }
}

// Fixed Q4 specialization of the accepted M4-2row routed-down kernel.
kernel void grouped_tiered_projection_m4_2row_q4(
    device const uint *weights [[buffer(0)]],
    device const ushort *scales [[buffer(1)]],
    device const ushort *biases [[buffer(2)]],
    device const float *inputs [[buffer(3)]],
    device float *outputs [[buffer(4)]],
    constant uint &in_dim [[buffer(5)]],
    constant uint &out_dim [[buffer(6)]],
    constant uint &count [[buffer(7)]],
    constant uint &_bits_unused [[buffer(8)]],
    uint3 tg [[threadgroup_position_in_grid]],
    uint3 tid [[thread_position_in_threadgroup]]) {
    const uint simd = tid.x >> 5;
    const uint lane = tid.x & 31u;
    const uint row = tg.x * 2u + simd;
    const uint base = tg.y * 4u;
    if (simd >= 2u || row >= out_dim || base >= count) return;
    const uint packed_cols = in_dim / 8u;
    const uint groups = in_dim / 64u;
    const bool v1 = base + 1u < count;
    const bool v2 = base + 2u < count;
    const bool v3 = base + 3u < count;
    float a0 = 0.0f, a1 = 0.0f, a2 = 0.0f, a3 = 0.0f;
    for (uint col = lane; col < packed_cols; col += 32u) {
        const uint group = col / 8u;
        const float scale = bf16_to_float(scales[row * groups + group]);
        const float bias = bf16_to_float(biases[row * groups + group]);
        const uint packed = weights[row * packed_cols + col];
        for (uint j = 0; j < 8u; j++) {
            const float w = float((packed >> (j * 4u)) & 0xFu) * scale + bias;
            const uint xcol = col * 8u + j;
            a0 += w * inputs[(base + 0u) * in_dim + xcol];
            if (v1) a1 += w * inputs[(base + 1u) * in_dim + xcol];
            if (v2) a2 += w * inputs[(base + 2u) * in_dim + xcol];
            if (v3) a3 += w * inputs[(base + 3u) * in_dim + xcol];
        }
    }
    const float s0 = simd_sum(a0), s1 = simd_sum(a1);
    const float s2 = simd_sum(a2), s3 = simd_sum(a3);
    if (lane == 0) {
        outputs[(base + 0u) * out_dim + row] = s0;
        if (v1) outputs[(base + 1u) * out_dim + row] = s1;
        if (v2) outputs[(base + 2u) * out_dim + row] = s2;
        if (v3) outputs[(base + 3u) * out_dim + row] = s3;
    }
}

// Fixed Q2 specialization of the accepted M4-2row routed-down kernel.
kernel void grouped_tiered_projection_m4_2row_q2(
    device const uint *weights [[buffer(0)]],
    device const ushort *scales [[buffer(1)]],
    device const ushort *biases [[buffer(2)]],
    device const float *inputs [[buffer(3)]],
    device float *outputs [[buffer(4)]],
    constant uint &in_dim [[buffer(5)]],
    constant uint &out_dim [[buffer(6)]],
    constant uint &count [[buffer(7)]],
    constant uint &_bits_unused [[buffer(8)]],
    uint3 tg [[threadgroup_position_in_grid]],
    uint3 tid [[thread_position_in_threadgroup]]) {
    const uint simd = tid.x >> 5;
    const uint lane = tid.x & 31u;
    const uint row = tg.x * 2u + simd;
    const uint base = tg.y * 4u;
    if (simd >= 2u || row >= out_dim || base >= count) return;
    const uint packed_cols = in_dim / 16u;
    const uint groups = in_dim / 64u;
    const bool v1 = base + 1u < count;
    const bool v2 = base + 2u < count;
    const bool v3 = base + 3u < count;
    float a0 = 0.0f, a1 = 0.0f, a2 = 0.0f, a3 = 0.0f;
    for (uint col = lane; col < packed_cols; col += 32u) {
        const uint group = col / 4u;
        const float scale = bf16_to_float(scales[row * groups + group]);
        const float bias = bf16_to_float(biases[row * groups + group]);
        const uint packed = weights[row * packed_cols + col];
        for (uint j = 0; j < 16u; j++) {
            const float w = float((packed >> (j * 2u)) & 0x3u) * scale + bias;
            const uint xcol = col * 16u + j;
            a0 += w * inputs[(base + 0u) * in_dim + xcol];
            if (v1) a1 += w * inputs[(base + 1u) * in_dim + xcol];
            if (v2) a2 += w * inputs[(base + 2u) * in_dim + xcol];
            if (v3) a3 += w * inputs[(base + 3u) * in_dim + xcol];
        }
    }
    const float s0 = simd_sum(a0), s1 = simd_sum(a1);
    const float s2 = simd_sum(a2), s3 = simd_sum(a3);
    if (lane == 0) {
        outputs[(base + 0u) * out_dim + row] = s0;
        if (v1) outputs[(base + 1u) * out_dim + row] = s1;
        if (v2) outputs[(base + 2u) * out_dim + row] = s2;
        if (v3) outputs[(base + 3u) * out_dim + row] = s3;
    }
}

// V12B occupancy diagnostic: same fixed M=4 arithmetic as V12A, but one
// 128-thread workgroup carries four independent 32-lane SIMD groups. Each
// SIMD group owns one output row; all four consume the same activation tile.
// This changes only threadgroup packing/dispatch occupancy, not per-row math.
kernel void grouped_tiered_projection_m4_4row(
    device const uint *weights [[buffer(0)]],
    device const ushort *scales [[buffer(1)]],
    device const ushort *biases [[buffer(2)]],
    device const float *inputs [[buffer(3)]],
    device float *outputs [[buffer(4)]],
    constant uint &in_dim [[buffer(5)]],
    constant uint &out_dim [[buffer(6)]],
    constant uint &count [[buffer(7)]],
    constant uint &bits [[buffer(8)]],
    uint3 tg [[threadgroup_position_in_grid]],
    uint3 tid [[thread_position_in_threadgroup]]) {
    const uint simd = tid.x >> 5;
    const uint lane = tid.x & 31u;
    const uint row = tg.x * 4u + simd;
    const uint base = tg.y * 4u;
    if (simd >= 4u || row >= out_dim || base >= count) return;
    const uint values_per_word = 32 / bits;
    const uint packed_cols = in_dim / values_per_word;
    const uint groups = in_dim / 64;
    const bool v1 = base + 1u < count;
    const bool v2 = base + 2u < count;
    const bool v3 = base + 3u < count;
    float a0 = 0.0f, a1 = 0.0f, a2 = 0.0f, a3 = 0.0f;
    for (uint col = lane; col < packed_cols; col += 32) {
        const uint group = col / (64 / values_per_word);
        const float scale = bf16_to_float(scales[row * groups + group]);
        const float bias = bf16_to_float(biases[row * groups + group]);
        const uint packed = weights[row * packed_cols + col];
        for (uint j = 0; j < values_per_word; j++) {
            const float w = float((packed >> (j * bits)) & ((1u << bits) - 1u)) * scale + bias;
            const uint xcol = col * values_per_word + j;
            a0 += w * inputs[(base + 0u) * in_dim + xcol];
            if (v1) a1 += w * inputs[(base + 1u) * in_dim + xcol];
            if (v2) a2 += w * inputs[(base + 2u) * in_dim + xcol];
            if (v3) a3 += w * inputs[(base + 3u) * in_dim + xcol];
        }
    }
    const float s0 = simd_sum(a0), s1 = simd_sum(a1);
    const float s2 = simd_sum(a2), s3 = simd_sum(a3);
    if (lane == 0) {
        outputs[(base + 0u) * out_dim + row] = s0;
        if (v1) outputs[(base + 1u) * out_dim + row] = s1;
        if (v2) outputs[(base + 2u) * out_dim + row] = s2;
        if (v3) outputs[(base + 3u) * out_dim + row] = s3;
    }
}

// V11 midpoint diagnostic: identical baseline routed down arithmetic with
// float acc[32]. Routed group count remains <= 16, so this changes only the
// compiler-visible accumulator array extent versus acc[64]/acc[16].
kernel void grouped_tiered_projection_acc32(
    device const uint *weights [[buffer(0)]],
    device const ushort *scales [[buffer(1)]],
    device const ushort *biases [[buffer(2)]],
    device const float *inputs [[buffer(3)]],
    device float *outputs [[buffer(4)]],
    constant uint &in_dim [[buffer(5)]],
    constant uint &out_dim [[buffer(6)]],
    constant uint &count [[buffer(7)]],
    constant uint &bits [[buffer(8)]],
    uint row [[threadgroup_position_in_grid]],
    uint lane [[thread_position_in_threadgroup]]) {
    if (row >= out_dim || lane >= 32 || count > 16) return;
    const uint values_per_word = 32 / bits;
    const uint packed_cols = in_dim / values_per_word;
    const uint groups = in_dim / 64;
    float acc[32];
    for (uint m = 0; m < count; m++) acc[m] = 0.0f;
    for (uint col = lane; col < packed_cols; col += 32) {
        const uint group = col / (64 / values_per_word);
        const float scale = bf16_to_float(scales[row * groups + group]);
        const float bias = bf16_to_float(biases[row * groups + group]);
        const uint packed = weights[row * packed_cols + col];
        for (uint j = 0; j < values_per_word; j++) {
            const float w = float((packed >> (j * bits)) & ((1u << bits) - 1u)) * scale + bias;
            const uint xcol = col * values_per_word + j;
            for (uint m = 0; m < count; m++)
                acc[m] += w * inputs[m * in_dim + xcol];
        }
    }
    for (uint m = 0; m < count; m++) {
        const float sum = simd_sum(acc[m]);
        if (lane == 0) outputs[m * out_dim + row] = sum;
    }
}

// V10 diagnostic candidate: baseline routed down arithmetic with the local
// accumulator constrained to the actual maximum routed group count (16).
// This is intentionally identical to grouped_tiered_projection otherwise, so
// an A/B build isolates compiler/register/occupancy effects of acc[64] vs
// acc[16].  Host code guarantees count <= 16 before dispatch.
kernel void grouped_tiered_projection_acc16(
    device const uint *weights [[buffer(0)]],
    device const ushort *scales [[buffer(1)]],
    device const ushort *biases [[buffer(2)]],
    device const float *inputs [[buffer(3)]],
    device float *outputs [[buffer(4)]],
    constant uint &in_dim [[buffer(5)]],
    constant uint &out_dim [[buffer(6)]],
    constant uint &count [[buffer(7)]],
    constant uint &bits [[buffer(8)]],
    uint row [[threadgroup_position_in_grid]],
    uint lane [[thread_position_in_threadgroup]]) {
    if (row >= out_dim || lane >= 32 || count > 16) return;
    const uint values_per_word = 32 / bits;
    const uint packed_cols = in_dim / values_per_word;
    const uint groups = in_dim / 64;
    float acc[16];
    for (uint m = 0; m < count; m++) acc[m] = 0.0f;
    for (uint col = lane; col < packed_cols; col += 32) {
        const uint group = col / (64 / values_per_word);
        const float scale = bf16_to_float(scales[row * groups + group]);
        const float bias = bf16_to_float(biases[row * groups + group]);
        const uint packed = weights[row * packed_cols + col];
        for (uint j = 0; j < values_per_word; j++) {
            const float w = float((packed >> (j * bits)) & ((1u << bits) - 1u)) * scale + bias;
            const uint xcol = col * values_per_word + j;
            for (uint m = 0; m < count; m++)
                acc[m] += w * inputs[m * in_dim + xcol];
        }
    }
    for (uint m = 0; m < count; m++) {
        const float sum = simd_sum(acc[m]);
        if (lane == 0) outputs[m * out_dim + row] = sum;
    }
}

// V8 benchmark candidate for routed down projection only.
// Two SIMD groups share one 64-thread workgroup.  Each SIMD group owns one
// output row and executes exactly the same 32-lane reduction/order as
// grouped_tiered_projection.  The intended change is scheduling geometry only:
// halve threadgroup count for the 512 -> 2048 down projection without changing
// quantization, accumulation order, SwiGLU, routing weights, or output layout.
kernel void grouped_tiered_projection_2row(
    device const uint *weights [[buffer(0)]],
    device const ushort *scales [[buffer(1)]],
    device const ushort *biases [[buffer(2)]],
    device const float *inputs [[buffer(3)]],
    device float *outputs [[buffer(4)]],
    constant uint &in_dim [[buffer(5)]],
    constant uint &out_dim [[buffer(6)]],
    constant uint &count [[buffer(7)]],
    constant uint &bits [[buffer(8)]],
    uint row_pair [[threadgroup_position_in_grid]],
    uint tid [[thread_position_in_threadgroup]]) {
    if (tid >= 64) return;
    const uint simd = tid >> 5;
    const uint lane = tid & 31u;
    const uint row = row_pair * 2u + simd;
    if (row >= out_dim) return;

    const uint values_per_word = 32 / bits;
    const uint packed_cols = in_dim / values_per_word;
    const uint groups = in_dim / 64;
    float acc[64];
    for (uint m = 0; m < count; m++) acc[m] = 0.0f;

    for (uint col = lane; col < packed_cols; col += 32) {
        const uint group = col / (64 / values_per_word);
        const float scale = bf16_to_float(scales[row * groups + group]);
        const float bias = bf16_to_float(biases[row * groups + group]);
        const uint packed = weights[row * packed_cols + col];
        for (uint j = 0; j < values_per_word; j++) {
            const float w =
                float((packed >> (j * bits)) & ((1u << bits) - 1u)) *
                scale + bias;
            const uint xcol = col * values_per_word + j;
            for (uint m = 0; m < count; m++)
                acc[m] += w * inputs[m * in_dim + xcol];
        }
    }

    for (uint m = 0; m < count; m++) {
        const float sum = simd_sum(acc[m]);
        if (lane == 0) outputs[m * out_dim + row] = sum;
    }
}

// V9 benchmark candidate for routed down projection only.
// Two output rows share one 64-thread workgroup as in V8, but the workgroup
// first cooperatively copies this routed expert group's activation slab into
// threadgroup memory.  Both SIMD groups then consume the same cached activation
// values while retaining the V8/baseline weight decode, lane mapping, FP32
// accumulation order, reductions, quantization, and output layout.
//
// Dynamic threadgroup storage is count * in_dim floats.  For routed down,
// in_dim is 512 and count <= 16, so the worst case is 32 KiB; typical grouped
// counts are much smaller.  This isolates activation-read reuse from further
// scheduling/row-packing changes.
kernel void grouped_tiered_projection_2row_coop(
    device const uint *weights [[buffer(0)]],
    device const ushort *scales [[buffer(1)]],
    device const ushort *biases [[buffer(2)]],
    device const float *inputs [[buffer(3)]],
    device float *outputs [[buffer(4)]],
    constant uint &in_dim [[buffer(5)]],
    constant uint &out_dim [[buffer(6)]],
    constant uint &count [[buffer(7)]],
    constant uint &bits [[buffer(8)]],
    threadgroup float *cached_inputs [[threadgroup(0)]],
    uint row_pair [[threadgroup_position_in_grid]],
    uint tid [[thread_position_in_threadgroup]]) {
    if (tid >= 64) return;

    const uint cache_values = count * in_dim;
    for (uint i = tid; i < cache_values; i += 64)
        cached_inputs[i] = inputs[i];
    threadgroup_barrier(mem_flags::mem_threadgroup);

    const uint simd = tid >> 5;
    const uint lane = tid & 31u;
    const uint row = row_pair * 2u + simd;
    if (row >= out_dim) return;

    const uint values_per_word = 32 / bits;
    const uint packed_cols = in_dim / values_per_word;
    const uint groups = in_dim / 64;
    float acc[64];
    for (uint m = 0; m < count; m++) acc[m] = 0.0f;

    for (uint col = lane; col < packed_cols; col += 32) {
        const uint group = col / (64 / values_per_word);
        const float scale = bf16_to_float(scales[row * groups + group]);
        const float bias = bf16_to_float(biases[row * groups + group]);
        const uint packed = weights[row * packed_cols + col];
        for (uint j = 0; j < values_per_word; j++) {
            const float w =
                float((packed >> (j * bits)) & ((1u << bits) - 1u)) *
                scale + bias;
            const uint xcol = col * values_per_word + j;
            for (uint m = 0; m < count; m++)
                acc[m] += w * cached_inputs[m * in_dim + xcol];
        }
    }

    for (uint m = 0; m < count; m++) {
        const float sum = simd_sum(acc[m]);
        if (lane == 0) outputs[m * out_dim + row] = sum;
    }
}




// V6 benchmark candidate: compute routed gate and up projections together.
// The two projections retain independent quantized weights/scales/biases and
// independent FP32 accumulation order; only the input load and dispatch/loop
// machinery are shared. SwiGLU and down projection remain separate.
kernel void grouped_tiered_gate_up(
    device const uint *gate_weights [[buffer(0)]],
    device const ushort *gate_scales [[buffer(1)]],
    device const ushort *gate_biases [[buffer(2)]],
    device const uint *up_weights [[buffer(3)]],
    device const ushort *up_scales [[buffer(4)]],
    device const ushort *up_biases [[buffer(5)]],
    device const float *inputs [[buffer(6)]],
    device float *gate_outputs [[buffer(7)]],
    device float *up_outputs [[buffer(8)]],
    constant uint &in_dim [[buffer(9)]],
    constant uint &out_dim [[buffer(10)]],
    constant uint &count [[buffer(11)]],
    constant uint &bits [[buffer(12)]],
    uint row [[threadgroup_position_in_grid]],
    uint lane [[thread_position_in_threadgroup]]) {
    if (row >= out_dim || lane >= 32) return;
    const uint values_per_word = 32 / bits;
    const uint packed_cols = in_dim / values_per_word;
    const uint groups = in_dim / 64;
    float gate_acc[64];
    float up_acc[64];
    for (uint m = 0; m < count; m++) {
        gate_acc[m] = 0.0f;
        up_acc[m] = 0.0f;
    }
    for (uint col = lane; col < packed_cols; col += 32) {
        const uint group = col / (64 / values_per_word);
        const float gate_scale = bf16_to_float(gate_scales[row * groups + group]);
        const float gate_bias = bf16_to_float(gate_biases[row * groups + group]);
        const float up_scale = bf16_to_float(up_scales[row * groups + group]);
        const float up_bias = bf16_to_float(up_biases[row * groups + group]);
        const uint gate_packed = gate_weights[row * packed_cols + col];
        const uint up_packed = up_weights[row * packed_cols + col];
        for (uint j = 0; j < values_per_word; j++) {
            const uint mask = (1u << bits) - 1u;
            const float wg = float((gate_packed >> (j * bits)) & mask) * gate_scale + gate_bias;
            const float wu = float((up_packed >> (j * bits)) & mask) * up_scale + up_bias;
            const uint xcol = col * values_per_word + j;
            for (uint m = 0; m < count; m++) {
                const float x = inputs[m * in_dim + xcol];
                gate_acc[m] += wg * x;
                up_acc[m] += wu * x;
            }
        }
    }
    for (uint m = 0; m < count; m++) {
        const float gate_sum = simd_sum(gate_acc[m]);
        const float up_sum = simd_sum(up_acc[m]);
        if (lane == 0) {
            gate_outputs[m * out_dim + row] = gate_sum;
            up_outputs[m * out_dim + row] = up_sum;
        }
    }
}


// V13B: fixed M=4 routed gate+up with the accepted V12C 2-SIMD / 64-thread
// threadgroup geometry.  Each SIMD owns one output row and computes gate and
// up for up to four routed activations.  Gate/up packed weights are decoded
// once per M4 tile and reused across those four activations.  This removes the
// dynamic gate_acc[64]/up_acc[64] arrays that regress when N32 creates larger
// per-expert routed groups, while preserving per-row arithmetic/reduction order.
kernel void grouped_tiered_gate_up_m4_2row(
    device const uint *gate_weights [[buffer(0)]],
    device const ushort *gate_scales [[buffer(1)]],
    device const ushort *gate_biases [[buffer(2)]],
    device const uint *up_weights [[buffer(3)]],
    device const ushort *up_scales [[buffer(4)]],
    device const ushort *up_biases [[buffer(5)]],
    device const float *inputs [[buffer(6)]],
    device float *gate_outputs [[buffer(7)]],
    device float *up_outputs [[buffer(8)]],
    constant uint &in_dim [[buffer(9)]],
    constant uint &out_dim [[buffer(10)]],
    constant uint &count [[buffer(11)]],
    constant uint &bits [[buffer(12)]],
    uint3 tg [[threadgroup_position_in_grid]],
    uint3 tid [[thread_position_in_threadgroup]]) {
    const uint simd = tid.x >> 5;
    const uint lane = tid.x & 31u;
    const uint row = tg.x * 2u + simd;
    const uint base = tg.y * 4u;
    if (simd >= 2u || row >= out_dim || base >= count) return;

    const uint values_per_word = 32 / bits;
    const uint packed_cols = in_dim / values_per_word;
    const uint groups = in_dim / 64;
    const bool v1 = base + 1u < count;
    const bool v2 = base + 2u < count;
    const bool v3 = base + 3u < count;

    float g0 = 0.0f, g1 = 0.0f, g2 = 0.0f, g3 = 0.0f;
    float u0 = 0.0f, u1 = 0.0f, u2 = 0.0f, u3 = 0.0f;

    for (uint col = lane; col < packed_cols; col += 32) {
        const uint group = col / (64 / values_per_word);
        const float gate_scale = bf16_to_float(gate_scales[row * groups + group]);
        const float gate_bias = bf16_to_float(gate_biases[row * groups + group]);
        const float up_scale = bf16_to_float(up_scales[row * groups + group]);
        const float up_bias = bf16_to_float(up_biases[row * groups + group]);
        const uint gate_packed = gate_weights[row * packed_cols + col];
        const uint up_packed = up_weights[row * packed_cols + col];
        const uint mask = (1u << bits) - 1u;

        for (uint j = 0; j < values_per_word; j++) {
            const float wg =
                float((gate_packed >> (j * bits)) & mask) * gate_scale + gate_bias;
            const float wu =
                float((up_packed >> (j * bits)) & mask) * up_scale + up_bias;
            const uint xcol = col * values_per_word + j;

            const float x0 = inputs[(base + 0u) * in_dim + xcol];
            g0 += wg * x0; u0 += wu * x0;
            if (v1) {
                const float x1 = inputs[(base + 1u) * in_dim + xcol];
                g1 += wg * x1; u1 += wu * x1;
            }
            if (v2) {
                const float x2 = inputs[(base + 2u) * in_dim + xcol];
                g2 += wg * x2; u2 += wu * x2;
            }
            if (v3) {
                const float x3 = inputs[(base + 3u) * in_dim + xcol];
                g3 += wg * x3; u3 += wu * x3;
            }
        }
    }

    const float gs0 = simd_sum(g0), us0 = simd_sum(u0);
    const float gs1 = simd_sum(g1), us1 = simd_sum(u1);
    const float gs2 = simd_sum(g2), us2 = simd_sum(u2);
    const float gs3 = simd_sum(g3), us3 = simd_sum(u3);

    if (lane == 0) {
        gate_outputs[(base + 0u) * out_dim + row] = gs0;
        up_outputs[(base + 0u) * out_dim + row] = us0;
        if (v1) {
            gate_outputs[(base + 1u) * out_dim + row] = gs1;
            up_outputs[(base + 1u) * out_dim + row] = us1;
        }
        if (v2) {
            gate_outputs[(base + 2u) * out_dim + row] = gs2;
            up_outputs[(base + 2u) * out_dim + row] = us2;
        }
        if (v3) {
            gate_outputs[(base + 3u) * out_dim + row] = gs3;
            up_outputs[(base + 3u) * out_dim + row] = us3;
        }
    }
}


// V15C benchmark candidate: fixed M=4 routed gate+up with 4-SIMD / 128-thread
// threadgroup packing. Arithmetic, quantization and per-SIMD accumulator width are
// identical to accepted V13B M4-2row; only output-row packing changes from two
// rows per threadgroup to four. This isolates dispatch/occupancy effects at N128.
kernel void grouped_tiered_gate_up_m4_4row(
    device const uint *gate_weights [[buffer(0)]],
    device const ushort *gate_scales [[buffer(1)]],
    device const ushort *gate_biases [[buffer(2)]],
    device const uint *up_weights [[buffer(3)]],
    device const ushort *up_scales [[buffer(4)]],
    device const ushort *up_biases [[buffer(5)]],
    device const float *inputs [[buffer(6)]],
    device float *gate_outputs [[buffer(7)]],
    device float *up_outputs [[buffer(8)]],
    constant uint &in_dim [[buffer(9)]],
    constant uint &out_dim [[buffer(10)]],
    constant uint &count [[buffer(11)]],
    constant uint &bits [[buffer(12)]],
    uint3 tg [[threadgroup_position_in_grid]],
    uint3 tid [[thread_position_in_threadgroup]]) {
    const uint simd = tid.x >> 5;
    const uint lane = tid.x & 31u;
    const uint row = tg.x * 4u + simd;
    const uint base = tg.y * 4u;
    if (simd >= 4u || row >= out_dim || base >= count) return;

    const uint values_per_word = 32 / bits;
    const uint packed_cols = in_dim / values_per_word;
    const uint groups = in_dim / 64;
    const bool v1 = base + 1u < count;
    const bool v2 = base + 2u < count;
    const bool v3 = base + 3u < count;

    float g0 = 0.0f, g1 = 0.0f, g2 = 0.0f, g3 = 0.0f;
    float u0 = 0.0f, u1 = 0.0f, u2 = 0.0f, u3 = 0.0f;

    for (uint col = lane; col < packed_cols; col += 32) {
        const uint group = col / (64 / values_per_word);
        const float gate_scale = bf16_to_float(gate_scales[row * groups + group]);
        const float gate_bias = bf16_to_float(gate_biases[row * groups + group]);
        const float up_scale = bf16_to_float(up_scales[row * groups + group]);
        const float up_bias = bf16_to_float(up_biases[row * groups + group]);
        const uint gate_packed = gate_weights[row * packed_cols + col];
        const uint up_packed = up_weights[row * packed_cols + col];
        const uint mask = (1u << bits) - 1u;

        for (uint j = 0; j < values_per_word; j++) {
            const float wg =
                float((gate_packed >> (j * bits)) & mask) * gate_scale + gate_bias;
            const float wu =
                float((up_packed >> (j * bits)) & mask) * up_scale + up_bias;
            const uint xcol = col * values_per_word + j;

            const float x0 = inputs[(base + 0u) * in_dim + xcol];
            g0 += wg * x0; u0 += wu * x0;
            if (v1) {
                const float x1 = inputs[(base + 1u) * in_dim + xcol];
                g1 += wg * x1; u1 += wu * x1;
            }
            if (v2) {
                const float x2 = inputs[(base + 2u) * in_dim + xcol];
                g2 += wg * x2; u2 += wu * x2;
            }
            if (v3) {
                const float x3 = inputs[(base + 3u) * in_dim + xcol];
                g3 += wg * x3; u3 += wu * x3;
            }
        }
    }

    const float gs0 = simd_sum(g0), us0 = simd_sum(u0);
    const float gs1 = simd_sum(g1), us1 = simd_sum(u1);
    const float gs2 = simd_sum(g2), us2 = simd_sum(u2);
    const float gs3 = simd_sum(g3), us3 = simd_sum(u3);

    if (lane == 0) {
        gate_outputs[(base + 0u) * out_dim + row] = gs0;
        up_outputs[(base + 0u) * out_dim + row] = us0;
        if (v1) {
            gate_outputs[(base + 1u) * out_dim + row] = gs1;
            up_outputs[(base + 1u) * out_dim + row] = us1;
        }
        if (v2) {
            gate_outputs[(base + 2u) * out_dim + row] = gs2;
            up_outputs[(base + 2u) * out_dim + row] = us2;
        }
        if (v3) {
            gate_outputs[(base + 3u) * out_dim + row] = gs3;
            up_outputs[(base + 3u) * out_dim + row] = us3;
        }
    }
}


// V15D benchmark candidate: fixed M=4 routed gate+up with 8-SIMD / 256-thread
// threadgroup packing. Arithmetic, quantization and per-SIMD accumulator width are
// identical to accepted M4 kernels; only output-row packing changes from four
// rows per threadgroup to eight. This isolates whether the N128 gate+up win from
// 4-row packing continues at a larger threadgroup without increasing M.
kernel void grouped_tiered_gate_up_m4_8row(
    device const uint *gate_weights [[buffer(0)]],
    device const ushort *gate_scales [[buffer(1)]],
    device const ushort *gate_biases [[buffer(2)]],
    device const uint *up_weights [[buffer(3)]],
    device const ushort *up_scales [[buffer(4)]],
    device const ushort *up_biases [[buffer(5)]],
    device const float *inputs [[buffer(6)]],
    device float *gate_outputs [[buffer(7)]],
    device float *up_outputs [[buffer(8)]],
    constant uint &in_dim [[buffer(9)]],
    constant uint &out_dim [[buffer(10)]],
    constant uint &count [[buffer(11)]],
    constant uint &bits [[buffer(12)]],
    uint3 tg [[threadgroup_position_in_grid]],
    uint3 tid [[thread_position_in_threadgroup]]) {
    const uint simd = tid.x >> 5;
    const uint lane = tid.x & 31u;
    const uint row = tg.x * 8u + simd;
    const uint base = tg.y * 4u;
    if (simd >= 8u || row >= out_dim || base >= count) return;

    const uint values_per_word = 32 / bits;
    const uint packed_cols = in_dim / values_per_word;
    const uint groups = in_dim / 64;
    const bool v1 = base + 1u < count;
    const bool v2 = base + 2u < count;
    const bool v3 = base + 3u < count;

    float g0 = 0.0f, g1 = 0.0f, g2 = 0.0f, g3 = 0.0f;
    float u0 = 0.0f, u1 = 0.0f, u2 = 0.0f, u3 = 0.0f;

    for (uint col = lane; col < packed_cols; col += 32) {
        const uint group = col / (64 / values_per_word);
        const float gate_scale = bf16_to_float(gate_scales[row * groups + group]);
        const float gate_bias = bf16_to_float(gate_biases[row * groups + group]);
        const float up_scale = bf16_to_float(up_scales[row * groups + group]);
        const float up_bias = bf16_to_float(up_biases[row * groups + group]);
        const uint gate_packed = gate_weights[row * packed_cols + col];
        const uint up_packed = up_weights[row * packed_cols + col];
        const uint mask = (1u << bits) - 1u;

        for (uint j = 0; j < values_per_word; j++) {
            const float wg =
                float((gate_packed >> (j * bits)) & mask) * gate_scale + gate_bias;
            const float wu =
                float((up_packed >> (j * bits)) & mask) * up_scale + up_bias;
            const uint xcol = col * values_per_word + j;

            const float x0 = inputs[(base + 0u) * in_dim + xcol];
            g0 += wg * x0; u0 += wu * x0;
            if (v1) {
                const float x1 = inputs[(base + 1u) * in_dim + xcol];
                g1 += wg * x1; u1 += wu * x1;
            }
            if (v2) {
                const float x2 = inputs[(base + 2u) * in_dim + xcol];
                g2 += wg * x2; u2 += wu * x2;
            }
            if (v3) {
                const float x3 = inputs[(base + 3u) * in_dim + xcol];
                g3 += wg * x3; u3 += wu * x3;
            }
        }
    }

    const float gs0 = simd_sum(g0), us0 = simd_sum(u0);
    const float gs1 = simd_sum(g1), us1 = simd_sum(u1);
    const float gs2 = simd_sum(g2), us2 = simd_sum(u2);
    const float gs3 = simd_sum(g3), us3 = simd_sum(u3);

    if (lane == 0) {
        gate_outputs[(base + 0u) * out_dim + row] = gs0;
        up_outputs[(base + 0u) * out_dim + row] = us0;
        if (v1) {
            gate_outputs[(base + 1u) * out_dim + row] = gs1;
            up_outputs[(base + 1u) * out_dim + row] = us1;
        }
        if (v2) {
            gate_outputs[(base + 2u) * out_dim + row] = gs2;
            up_outputs[(base + 2u) * out_dim + row] = us2;
        }
        if (v3) {
            gate_outputs[(base + 3u) * out_dim + row] = gs3;
            up_outputs[(base + 3u) * out_dim + row] = us3;
        }
    }
}


// N128 benchmark candidate: accepted M4-8row geometry with fixed Q4
// decode. This removes runtime bit-width arithmetic from the routed gate+up
// inner loop while preserving M=4, eight-SIMD packing, FP32 accumulation order,
// quantization semantics, reductions, and output layout.
kernel void grouped_tiered_gate_up_m4_8row_q4(
    device const uint *gate_weights [[buffer(0)]],
    device const ushort *gate_scales [[buffer(1)]],
    device const ushort *gate_biases [[buffer(2)]],
    device const uint *up_weights [[buffer(3)]],
    device const ushort *up_scales [[buffer(4)]],
    device const ushort *up_biases [[buffer(5)]],
    device const float *inputs [[buffer(6)]],
    device float *gate_outputs [[buffer(7)]],
    device float *up_outputs [[buffer(8)]],
    constant uint &in_dim [[buffer(9)]],
    constant uint &out_dim [[buffer(10)]],
    constant uint &count [[buffer(11)]],
    constant uint &_bits_unused [[buffer(12)]],
    uint3 tg [[threadgroup_position_in_grid]],
    uint3 tid [[thread_position_in_threadgroup]]) {
    const uint simd = tid.x >> 5;
    const uint lane = tid.x & 31u;
    const uint row = tg.x * 8u + simd;
    const uint base = tg.y * 4u;
    if (simd >= 8u || row >= out_dim || base >= count) return;

    const uint packed_cols = in_dim / 8u;
    const uint groups = in_dim / 64u;
    const bool v1 = base + 1u < count;
    const bool v2 = base + 2u < count;
    const bool v3 = base + 3u < count;

    float g0 = 0.0f, g1 = 0.0f, g2 = 0.0f, g3 = 0.0f;
    float u0 = 0.0f, u1 = 0.0f, u2 = 0.0f, u3 = 0.0f;

    for (uint col = lane; col < packed_cols; col += 32u) {
        const uint group = col / 8u;
        const float gate_scale = bf16_to_float(gate_scales[row * groups + group]);
        const float gate_bias = bf16_to_float(gate_biases[row * groups + group]);
        const float up_scale = bf16_to_float(up_scales[row * groups + group]);
        const float up_bias = bf16_to_float(up_biases[row * groups + group]);
        const uint gate_packed = gate_weights[row * packed_cols + col];
        const uint up_packed = up_weights[row * packed_cols + col];

        for (uint j = 0; j < 8u; j++) {
            const float wg =
                float((gate_packed >> (j * 4u)) & 0xFu) * gate_scale + gate_bias;
            const float wu =
                float((up_packed >> (j * 4u)) & 0xFu) * up_scale + up_bias;
            const uint xcol = col * 8u + j;

            const float x0 = inputs[(base + 0u) * in_dim + xcol];
            g0 += wg * x0; u0 += wu * x0;
            if (v1) {
                const float x1 = inputs[(base + 1u) * in_dim + xcol];
                g1 += wg * x1; u1 += wu * x1;
            }
            if (v2) {
                const float x2 = inputs[(base + 2u) * in_dim + xcol];
                g2 += wg * x2; u2 += wu * x2;
            }
            if (v3) {
                const float x3 = inputs[(base + 3u) * in_dim + xcol];
                g3 += wg * x3; u3 += wu * x3;
            }
        }
    }

    const float gs0 = simd_sum(g0), us0 = simd_sum(u0);
    const float gs1 = simd_sum(g1), us1 = simd_sum(u1);
    const float gs2 = simd_sum(g2), us2 = simd_sum(u2);
    const float gs3 = simd_sum(g3), us3 = simd_sum(u3);

    if (lane == 0) {
        gate_outputs[(base + 0u) * out_dim + row] = gs0;
        up_outputs[(base + 0u) * out_dim + row] = us0;
        if (v1) {
            gate_outputs[(base + 1u) * out_dim + row] = gs1;
            up_outputs[(base + 1u) * out_dim + row] = us1;
        }
        if (v2) {
            gate_outputs[(base + 2u) * out_dim + row] = gs2;
            up_outputs[(base + 2u) * out_dim + row] = us2;
        }
        if (v3) {
            gate_outputs[(base + 3u) * out_dim + row] = gs3;
            up_outputs[(base + 3u) * out_dim + row] = us3;
        }
    }
}

// N128 benchmark candidate: accepted M4-8row geometry with fixed Q2
// decode. This removes runtime bit-width arithmetic from the routed gate+up
// inner loop while preserving M=4, eight-SIMD packing, FP32 accumulation order,
// quantization semantics, reductions, and output layout.
kernel void grouped_tiered_gate_up_m4_8row_q2(
    device const uint *gate_weights [[buffer(0)]],
    device const ushort *gate_scales [[buffer(1)]],
    device const ushort *gate_biases [[buffer(2)]],
    device const uint *up_weights [[buffer(3)]],
    device const ushort *up_scales [[buffer(4)]],
    device const ushort *up_biases [[buffer(5)]],
    device const float *inputs [[buffer(6)]],
    device float *gate_outputs [[buffer(7)]],
    device float *up_outputs [[buffer(8)]],
    constant uint &in_dim [[buffer(9)]],
    constant uint &out_dim [[buffer(10)]],
    constant uint &count [[buffer(11)]],
    constant uint &_bits_unused [[buffer(12)]],
    uint3 tg [[threadgroup_position_in_grid]],
    uint3 tid [[thread_position_in_threadgroup]]) {
    const uint simd = tid.x >> 5;
    const uint lane = tid.x & 31u;
    const uint row = tg.x * 8u + simd;
    const uint base = tg.y * 4u;
    if (simd >= 8u || row >= out_dim || base >= count) return;

    const uint packed_cols = in_dim / 16u;
    const uint groups = in_dim / 64u;
    const bool v1 = base + 1u < count;
    const bool v2 = base + 2u < count;
    const bool v3 = base + 3u < count;

    float g0 = 0.0f, g1 = 0.0f, g2 = 0.0f, g3 = 0.0f;
    float u0 = 0.0f, u1 = 0.0f, u2 = 0.0f, u3 = 0.0f;

    for (uint col = lane; col < packed_cols; col += 32u) {
        const uint group = col / 4u;
        const float gate_scale = bf16_to_float(gate_scales[row * groups + group]);
        const float gate_bias = bf16_to_float(gate_biases[row * groups + group]);
        const float up_scale = bf16_to_float(up_scales[row * groups + group]);
        const float up_bias = bf16_to_float(up_biases[row * groups + group]);
        const uint gate_packed = gate_weights[row * packed_cols + col];
        const uint up_packed = up_weights[row * packed_cols + col];

        for (uint j = 0; j < 16u; j++) {
            const float wg =
                float((gate_packed >> (j * 2u)) & 0x3u) * gate_scale + gate_bias;
            const float wu =
                float((up_packed >> (j * 2u)) & 0x3u) * up_scale + up_bias;
            const uint xcol = col * 16u + j;

            const float x0 = inputs[(base + 0u) * in_dim + xcol];
            g0 += wg * x0; u0 += wu * x0;
            if (v1) {
                const float x1 = inputs[(base + 1u) * in_dim + xcol];
                g1 += wg * x1; u1 += wu * x1;
            }
            if (v2) {
                const float x2 = inputs[(base + 2u) * in_dim + xcol];
                g2 += wg * x2; u2 += wu * x2;
            }
            if (v3) {
                const float x3 = inputs[(base + 3u) * in_dim + xcol];
                g3 += wg * x3; u3 += wu * x3;
            }
        }
    }

    const float gs0 = simd_sum(g0), us0 = simd_sum(u0);
    const float gs1 = simd_sum(g1), us1 = simd_sum(u1);
    const float gs2 = simd_sum(g2), us2 = simd_sum(u2);
    const float gs3 = simd_sum(g3), us3 = simd_sum(u3);

    if (lane == 0) {
        gate_outputs[(base + 0u) * out_dim + row] = gs0;
        up_outputs[(base + 0u) * out_dim + row] = us0;
        if (v1) {
            gate_outputs[(base + 1u) * out_dim + row] = gs1;
            up_outputs[(base + 1u) * out_dim + row] = us1;
        }
        if (v2) {
            gate_outputs[(base + 2u) * out_dim + row] = gs2;
            up_outputs[(base + 2u) * out_dim + row] = us2;
        }
        if (v3) {
            gate_outputs[(base + 3u) * out_dim + row] = gs3;
            up_outputs[(base + 3u) * out_dim + row] = us3;
        }
    }
}

// N128 benchmark candidate: accepted M4-8row arithmetic with cooperative input
// caching. Eight SIMD groups compute eight independent output rows but consume
// the same four routed activation rows. Cache a 512-element input tile for all
// four rows (8 KiB total) once per threadgroup, then reuse it across all eight
// SIMD groups. Weight decoding, FP32 accumulation order within each SIMD, M=4,
// quantization semantics and output layout are unchanged.
kernel void grouped_tiered_gate_up_m4_8row_xcache(
    device const uint *gate_weights [[buffer(0)]],
    device const ushort *gate_scales [[buffer(1)]],
    device const ushort *gate_biases [[buffer(2)]],
    device const uint *up_weights [[buffer(3)]],
    device const ushort *up_scales [[buffer(4)]],
    device const ushort *up_biases [[buffer(5)]],
    device const float *inputs [[buffer(6)]],
    device float *gate_outputs [[buffer(7)]],
    device float *up_outputs [[buffer(8)]],
    constant uint &in_dim [[buffer(9)]],
    constant uint &out_dim [[buffer(10)]],
    constant uint &count [[buffer(11)]],
    constant uint &bits [[buffer(12)]],
    threadgroup float *input_tile [[threadgroup(0)]],
    uint3 tg [[threadgroup_position_in_grid]],
    uint3 tid [[thread_position_in_threadgroup]]) {
    const uint simd = tid.x >> 5;
    const uint lane = tid.x & 31u;
    const uint row = tg.x * 8u + simd;
    const uint base = tg.y * 4u;
    if (simd >= 8u || row >= out_dim || base >= count) return;

    const uint values_per_word = 32 / bits;
    const uint packed_cols = in_dim / values_per_word;
    const uint groups = in_dim / 64;
    const uint mask = (1u << bits) - 1u;
    const bool v1 = base + 1u < count;
    const bool v2 = base + 2u < count;
    const bool v3 = base + 3u < count;
    constexpr uint TILE_X = 512u;

    float g0 = 0.0f, g1 = 0.0f, g2 = 0.0f, g3 = 0.0f;
    float u0 = 0.0f, u1 = 0.0f, u2 = 0.0f, u3 = 0.0f;

    for (uint tile_base = 0; tile_base < in_dim; tile_base += TILE_X) {
        const uint tile_len = min(TILE_X, in_dim - tile_base);

        // Cooperative load: 256 threads fill four 512-float rows.
        for (uint i = tid.x; i < 4u * TILE_X; i += 256u) {
            const uint r = i / TILE_X;
            const uint c = i - r * TILE_X;
            const bool row_valid =
                (r == 0u) || (r == 1u && v1) || (r == 2u && v2) || (r == 3u && v3);
            input_tile[i] =
                (row_valid && c < tile_len)
                    ? inputs[(base + r) * in_dim + tile_base + c]
                    : 0.0f;
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);

        const uint packed_begin = tile_base / values_per_word;
        const uint packed_end =
            min(packed_cols, (tile_base + tile_len + values_per_word - 1u) /
                             values_per_word);

        for (uint col = packed_begin + lane; col < packed_end; col += 32u) {
            const uint group = col / (64u / values_per_word);
            const float gate_scale =
                bf16_to_float(gate_scales[row * groups + group]);
            const float gate_bias =
                bf16_to_float(gate_biases[row * groups + group]);
            const float up_scale =
                bf16_to_float(up_scales[row * groups + group]);
            const float up_bias =
                bf16_to_float(up_biases[row * groups + group]);
            const uint gate_packed = gate_weights[row * packed_cols + col];
            const uint up_packed = up_weights[row * packed_cols + col];

            for (uint j = 0; j < values_per_word; j++) {
                const uint xcol = col * values_per_word + j;
                if (xcol >= tile_base + tile_len) break;
                const uint local = xcol - tile_base;
                const float wg =
                    float((gate_packed >> (j * bits)) & mask) * gate_scale + gate_bias;
                const float wu =
                    float((up_packed >> (j * bits)) & mask) * up_scale + up_bias;

                const float x0 = input_tile[0u * TILE_X + local];
                const float x1 = input_tile[1u * TILE_X + local];
                const float x2 = input_tile[2u * TILE_X + local];
                const float x3 = input_tile[3u * TILE_X + local];
                g0 += wg * x0; u0 += wu * x0;
                g1 += wg * x1; u1 += wu * x1;
                g2 += wg * x2; u2 += wu * x2;
                g3 += wg * x3; u3 += wu * x3;
            }
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }

    const float gs0 = simd_sum(g0), us0 = simd_sum(u0);
    const float gs1 = simd_sum(g1), us1 = simd_sum(u1);
    const float gs2 = simd_sum(g2), us2 = simd_sum(u2);
    const float gs3 = simd_sum(g3), us3 = simd_sum(u3);

    if (lane == 0) {
        gate_outputs[(base + 0u) * out_dim + row] = gs0;
        up_outputs[(base + 0u) * out_dim + row] = us0;
        if (v1) {
            gate_outputs[(base + 1u) * out_dim + row] = gs1;
            up_outputs[(base + 1u) * out_dim + row] = us1;
        }
        if (v2) {
            gate_outputs[(base + 2u) * out_dim + row] = gs2;
            up_outputs[(base + 2u) * out_dim + row] = us2;
        }
        if (v3) {
            gate_outputs[(base + 3u) * out_dim + row] = gs3;
            up_outputs[(base + 3u) * out_dim + row] = us3;
        }
    }
}

// V15E benchmark candidate: fixed M=4 routed gate+up with 16-SIMD / 512-thread
// threadgroup packing. Arithmetic, quantization and per-SIMD accumulator width are
// identical to the accepted M4-8row kernel; only output-row packing changes from
// eight rows per threadgroup to sixteen. This probes the next packing boundary
// without increasing M or changing routed-down arithmetic.
kernel void grouped_tiered_gate_up_m4_16row(
    device const uint *gate_weights [[buffer(0)]],
    device const ushort *gate_scales [[buffer(1)]],
    device const ushort *gate_biases [[buffer(2)]],
    device const uint *up_weights [[buffer(3)]],
    device const ushort *up_scales [[buffer(4)]],
    device const ushort *up_biases [[buffer(5)]],
    device const float *inputs [[buffer(6)]],
    device float *gate_outputs [[buffer(7)]],
    device float *up_outputs [[buffer(8)]],
    constant uint &in_dim [[buffer(9)]],
    constant uint &out_dim [[buffer(10)]],
    constant uint &count [[buffer(11)]],
    constant uint &bits [[buffer(12)]],
    uint3 tg [[threadgroup_position_in_grid]],
    uint3 tid [[thread_position_in_threadgroup]]) {
    const uint simd = tid.x >> 5;
    const uint lane = tid.x & 31u;
    const uint row = tg.x * 16u + simd;
    const uint base = tg.y * 4u;
    if (simd >= 16u || row >= out_dim || base >= count) return;

    const uint values_per_word = 32 / bits;
    const uint packed_cols = in_dim / values_per_word;
    const uint groups = in_dim / 64;
    const bool v1 = base + 1u < count;
    const bool v2 = base + 2u < count;
    const bool v3 = base + 3u < count;

    float g0 = 0.0f, g1 = 0.0f, g2 = 0.0f, g3 = 0.0f;
    float u0 = 0.0f, u1 = 0.0f, u2 = 0.0f, u3 = 0.0f;

    for (uint col = lane; col < packed_cols; col += 32) {
        const uint group = col / (64 / values_per_word);
        const float gate_scale = bf16_to_float(gate_scales[row * groups + group]);
        const float gate_bias = bf16_to_float(gate_biases[row * groups + group]);
        const float up_scale = bf16_to_float(up_scales[row * groups + group]);
        const float up_bias = bf16_to_float(up_biases[row * groups + group]);
        const uint gate_packed = gate_weights[row * packed_cols + col];
        const uint up_packed = up_weights[row * packed_cols + col];
        const uint mask = (1u << bits) - 1u;

        for (uint j = 0; j < values_per_word; j++) {
            const float wg =
                float((gate_packed >> (j * bits)) & mask) * gate_scale + gate_bias;
            const float wu =
                float((up_packed >> (j * bits)) & mask) * up_scale + up_bias;
            const uint xcol = col * values_per_word + j;

            const float x0 = inputs[(base + 0u) * in_dim + xcol];
            g0 += wg * x0; u0 += wu * x0;
            if (v1) {
                const float x1 = inputs[(base + 1u) * in_dim + xcol];
                g1 += wg * x1; u1 += wu * x1;
            }
            if (v2) {
                const float x2 = inputs[(base + 2u) * in_dim + xcol];
                g2 += wg * x2; u2 += wu * x2;
            }
            if (v3) {
                const float x3 = inputs[(base + 3u) * in_dim + xcol];
                g3 += wg * x3; u3 += wu * x3;
            }
        }
    }

    const float gs0 = simd_sum(g0), us0 = simd_sum(u0);
    const float gs1 = simd_sum(g1), us1 = simd_sum(u1);
    const float gs2 = simd_sum(g2), us2 = simd_sum(u2);
    const float gs3 = simd_sum(g3), us3 = simd_sum(u3);

    if (lane == 0) {
        gate_outputs[(base + 0u) * out_dim + row] = gs0;
        up_outputs[(base + 0u) * out_dim + row] = us0;
        if (v1) {
            gate_outputs[(base + 1u) * out_dim + row] = gs1;
            up_outputs[(base + 1u) * out_dim + row] = us1;
        }
        if (v2) {
            gate_outputs[(base + 2u) * out_dim + row] = gs2;
            up_outputs[(base + 2u) * out_dim + row] = us2;
        }
        if (v3) {
            gate_outputs[(base + 3u) * out_dim + row] = gs3;
            up_outputs[(base + 3u) * out_dim + row] = us3;
        }
    }
}


// V15B benchmark candidate: fixed M=8 routed gate+up for denser N128 groups.
// Geometry remains 2 SIMD groups / 64 threads per threadgroup, with one output
// row per SIMD.  Relative to V13B M4, each decoded gate/up weight is reused
// across up to eight routed activations instead of four.  Per-activation input
// traversal, FP32 accumulation, SIMD reduction, quantization and output layout
// are unchanged; only the M tile width changes.
kernel void grouped_tiered_gate_up_m8_2row(
    device const uint *gate_weights [[buffer(0)]],
    device const ushort *gate_scales [[buffer(1)]],
    device const ushort *gate_biases [[buffer(2)]],
    device const uint *up_weights [[buffer(3)]],
    device const ushort *up_scales [[buffer(4)]],
    device const ushort *up_biases [[buffer(5)]],
    device const float *inputs [[buffer(6)]],
    device float *gate_outputs [[buffer(7)]],
    device float *up_outputs [[buffer(8)]],
    constant uint &in_dim [[buffer(9)]],
    constant uint &out_dim [[buffer(10)]],
    constant uint &count [[buffer(11)]],
    constant uint &bits [[buffer(12)]],
    uint3 tg [[threadgroup_position_in_grid]],
    uint3 tid [[thread_position_in_threadgroup]]) {
    const uint simd = tid.x >> 5;
    const uint lane = tid.x & 31u;
    const uint row = tg.x * 2u + simd;
    const uint base = tg.y * 8u;
    if (simd >= 2u || row >= out_dim || base >= count) return;

    const uint values_per_word = 32 / bits;
    const uint packed_cols = in_dim / values_per_word;
    const uint groups = in_dim / 64;
    const bool v1 = base + 1u < count;
    const bool v2 = base + 2u < count;
    const bool v3 = base + 3u < count;
    const bool v4 = base + 4u < count;
    const bool v5 = base + 5u < count;
    const bool v6 = base + 6u < count;
    const bool v7 = base + 7u < count;

    float g0=0.0f,g1=0.0f,g2=0.0f,g3=0.0f,g4=0.0f,g5=0.0f,g6=0.0f,g7=0.0f;
    float u0=0.0f,u1=0.0f,u2=0.0f,u3=0.0f,u4=0.0f,u5=0.0f,u6=0.0f,u7=0.0f;

    for (uint col = lane; col < packed_cols; col += 32) {
        const uint group = col / (64 / values_per_word);
        const float gate_scale = bf16_to_float(gate_scales[row * groups + group]);
        const float gate_bias = bf16_to_float(gate_biases[row * groups + group]);
        const float up_scale = bf16_to_float(up_scales[row * groups + group]);
        const float up_bias = bf16_to_float(up_biases[row * groups + group]);
        const uint gate_packed = gate_weights[row * packed_cols + col];
        const uint up_packed = up_weights[row * packed_cols + col];
        const uint mask = (1u << bits) - 1u;

        for (uint j = 0; j < values_per_word; j++) {
            const float wg = float((gate_packed >> (j * bits)) & mask) * gate_scale + gate_bias;
            const float wu = float((up_packed >> (j * bits)) & mask) * up_scale + up_bias;
            const uint xcol = col * values_per_word + j;
            const float x0 = inputs[(base + 0u) * in_dim + xcol];
            g0 += wg*x0; u0 += wu*x0;
            if (v1) { const float x=inputs[(base+1u)*in_dim+xcol]; g1+=wg*x; u1+=wu*x; }
            if (v2) { const float x=inputs[(base+2u)*in_dim+xcol]; g2+=wg*x; u2+=wu*x; }
            if (v3) { const float x=inputs[(base+3u)*in_dim+xcol]; g3+=wg*x; u3+=wu*x; }
            if (v4) { const float x=inputs[(base+4u)*in_dim+xcol]; g4+=wg*x; u4+=wu*x; }
            if (v5) { const float x=inputs[(base+5u)*in_dim+xcol]; g5+=wg*x; u5+=wu*x; }
            if (v6) { const float x=inputs[(base+6u)*in_dim+xcol]; g6+=wg*x; u6+=wu*x; }
            if (v7) { const float x=inputs[(base+7u)*in_dim+xcol]; g7+=wg*x; u7+=wu*x; }
        }
    }

    const float gs0=simd_sum(g0), us0=simd_sum(u0);
    const float gs1=simd_sum(g1), us1=simd_sum(u1);
    const float gs2=simd_sum(g2), us2=simd_sum(u2);
    const float gs3=simd_sum(g3), us3=simd_sum(u3);
    const float gs4=simd_sum(g4), us4=simd_sum(u4);
    const float gs5=simd_sum(g5), us5=simd_sum(u5);
    const float gs6=simd_sum(g6), us6=simd_sum(u6);
    const float gs7=simd_sum(g7), us7=simd_sum(u7);

    if (lane == 0) {
        gate_outputs[(base+0u)*out_dim+row]=gs0; up_outputs[(base+0u)*out_dim+row]=us0;
        if (v1) { gate_outputs[(base+1u)*out_dim+row]=gs1; up_outputs[(base+1u)*out_dim+row]=us1; }
        if (v2) { gate_outputs[(base+2u)*out_dim+row]=gs2; up_outputs[(base+2u)*out_dim+row]=us2; }
        if (v3) { gate_outputs[(base+3u)*out_dim+row]=gs3; up_outputs[(base+3u)*out_dim+row]=us3; }
        if (v4) { gate_outputs[(base+4u)*out_dim+row]=gs4; up_outputs[(base+4u)*out_dim+row]=us4; }
        if (v5) { gate_outputs[(base+5u)*out_dim+row]=gs5; up_outputs[(base+5u)*out_dim+row]=us5; }
        if (v6) { gate_outputs[(base+6u)*out_dim+row]=gs6; up_outputs[(base+6u)*out_dim+row]=us6; }
        if (v7) { gate_outputs[(base+7u)*out_dim+row]=gs7; up_outputs[(base+7u)*out_dim+row]=us7; }
    }
}

kernel void grouped_swiglu(device const float *gate [[buffer(0)]],
    device const float *up [[buffer(1)]], device float *act [[buffer(2)]],
    constant uint &count [[buffer(3)]], uint i [[thread_position_in_grid]]) {
    if (i >= count * 512) return;
    const float g = gate[i];
    act[i] = (g / (1.0f + exp(-g))) * up[i];
}

// N128 candidate: fused causal attention with online softmax.
// One 256-thread threadgroup handles one (row, query-head).  Rows share the
// already-published KV cache, but each row uses its own causal end position.
// This avoids the N x (scores, softmax, values) command sequence and does not
// materialize an N*heads*sequence score tensor.
kernel void nrow_causal_attn_online(
    device const float *Q_rows      [[buffer(0)]],
    device const float *K_cache     [[buffer(1)]],
    device const float *V_cache     [[buffer(2)]],
    device const float *gate_rows   [[buffer(3)]],
    device float *out_rows          [[buffer(4)]],
    constant uint &rows             [[buffer(5)]],
    constant uint &num_heads        [[buffer(6)]],
    constant uint &head_dim         [[buffer(7)]],
    constant uint &kv_dim           [[buffer(8)]],
    constant uint &base_len         [[buffer(9)]],
    constant uint &heads_per_kv     [[buffer(10)]],
    constant float &scale           [[buffer(11)]],
    uint tgid [[threadgroup_position_in_grid]],
    uint lid  [[thread_position_in_threadgroup]],
    uint tg_size [[threads_per_threadgroup]]
) {
    uint row = tgid / num_heads;
    uint h = tgid - row * num_heads;
    if (row >= rows || h >= num_heads) return;

    uint kv_h = h / heads_per_kv;
    uint qoff = (row * num_heads + h) * head_dim;
    float qv = (lid < head_dim) ? Q_rows[qoff + lid] : 0.0f;

    float running_m = -1.0e30f;
    float running_l = 0.0f;
    float running_v = 0.0f;
    uint seq_len = base_len + row + 1;

    threadgroup float partial[32];
    threadgroup float score_shared;
    uint lane = lid & 31u;
    uint simd_group = lid >> 5u;
    uint simd_groups = (tg_size + 31u) >> 5u;

    for (uint pos = 0; pos < seq_len; ++pos) {
        uint koff = pos * kv_dim + kv_h * head_dim;
        float prod = (lid < head_dim) ? qv * K_cache[koff + lid] : 0.0f;
        float s = simd_sum(prod);
        if (lane == 0) partial[simd_group] = s;
        threadgroup_barrier(mem_flags::mem_threadgroup);

        if (simd_group == 0) {
            float v = (lane < simd_groups) ? partial[lane] : 0.0f;
            v = simd_sum(v);
            if (lane == 0) score_shared = v * scale;
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);

        float score = score_shared;
        float new_m = max(running_m, score);
        float alpha = (running_l == 0.0f) ? 0.0f : exp(running_m - new_m);
        float beta = exp(score - new_m);
        if (lid < head_dim) {
            float vv = V_cache[koff + lid];
            running_v = running_v * alpha + vv * beta;
        }
        running_l = running_l * alpha + beta;
        running_m = new_m;
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }

    if (lid < head_dim) {
        float g = 1.0f / (1.0f + exp(-gate_rows[qoff + lid]));
        out_rows[qoff + lid] = (running_v / running_l) * g;
    }
}

