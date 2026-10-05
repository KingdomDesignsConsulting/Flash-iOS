#include <metal_stdlib>
using namespace metal;

// Benchmark-only multi-position 4-bit LM head. One simdgroup owns one vocab
// row and reuses its dequantized weights across up to eight candidate positions.
kernel void target_verify_lmhead_batch(
    device const uint32_t *weights [[buffer(0)]],
    device const uint16_t *scales [[buffer(1)]],
    device const uint16_t *biases [[buffer(2)]],
    device const float *inputs [[buffer(3)]],
    device float *outputs [[buffer(4)]],
    constant uint &out_dim [[buffer(5)]],
    constant uint &in_dim [[buffer(6)]],
    constant uint &token_count [[buffer(7)]],
    uint group [[threadgroup_position_in_grid]],
    uint lane [[thread_index_in_simdgroup]],
    uint simd_group [[simdgroup_index_in_threadgroup]]) {
    uint row = group * 8 + simd_group;
    if (row >= out_dim) return;
    uint packed_cols = in_dim / 8;
    uint groups = in_dim / 64;
    device const uint32_t *w_row = weights + row * packed_cols;
    device const uint16_t *s_row = scales + row * groups;
    device const uint16_t *b_row = biases + row * groups;
    float accum[8] = {0.0f, 0.0f, 0.0f, 0.0f,
                      0.0f, 0.0f, 0.0f, 0.0f};
    for (uint col = lane; col < packed_cols; col += 32) {
        uint packed = w_row[col];
        uint scale_bits = uint(s_row[col / 8]) << 16;
        uint bias_bits = uint(b_row[col / 8]) << 16;
        float scale = as_type<float>(scale_bits);
        float bias = as_type<float>(bias_bits);
        for (uint nibble = 0; nibble < 8; nibble++) {
            float weight = float((packed >> (nibble * 4)) & 15u) * scale + bias;
            uint column = col * 8 + nibble;
            for (uint token = 0; token < token_count; token++)
                accum[token] += weight * inputs[token * in_dim + column];
        }
    }
    for (uint token = 0; token < token_count; token++) {
        float sum = simd_sum(accum[token]);
        if (lane == 0) outputs[token * out_dim + row] = sum;
    }
}
