#include <metal_stdlib>
using namespace metal;

// Diagnostic only. The first kernel reproduces the production M1 reduction;
// the second changes only the affine algebra and uses scalar group64 sums.
static inline float probe_bf16(ushort v) {
    return as_type<float>(uint(v) << 16);
}

kernel void affine_probe_production_m1(
    device const uint *weights [[buffer(0)]],
    device const ushort *scales [[buffer(1)]],
    device const ushort *biases [[buffer(2)]],
    device const float *x [[buffer(3)]],
    device float *out [[buffer(4)]],
    constant uint &out_dim [[buffer(5)]],
    constant uint &in_dim [[buffer(6)]],
    constant uint &group_size [[buffer(7)]],
    uint tgid [[threadgroup_position_in_grid]],
    uint lid [[thread_position_in_threadgroup]],
    uint lane [[thread_index_in_simdgroup]],
    uint sg [[simdgroup_index_in_threadgroup]]
) {
    uint row = tgid * 8u + sg;
    uint packed_cols = in_dim / 8u;
    uint groups = in_dim / group_size;
    threadgroup float x_shared[4096];
    for (uint i = lid; i < in_dim; i += 256u) x_shared[i] = x[i];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if (row >= out_dim) return;
    device const uint *w_row = weights + row * packed_cols;
    device const ushort *s_row = scales + row * groups;
    device const ushort *b_row = biases + row * groups;
    float acc = 0.0f;
    for (uint col = lane; col < packed_cols; col += 32u) {
        uint g = col / (group_size / 8u);
        float scale = probe_bf16(s_row[g]);
        float bias = probe_bf16(b_row[g]);
        uint packed = w_row[col];
        uint base = col * 8u;
        float sx0 = scale * x_shared[base + 0u]; float bx0 = bias * x_shared[base + 0u];
        float sx1 = scale * x_shared[base + 1u]; float bx1 = bias * x_shared[base + 1u];
        float sx2 = scale * x_shared[base + 2u]; float bx2 = bias * x_shared[base + 2u];
        float sx3 = scale * x_shared[base + 3u]; float bx3 = bias * x_shared[base + 3u];
        float sx4 = scale * x_shared[base + 4u]; float bx4 = bias * x_shared[base + 4u];
        float sx5 = scale * x_shared[base + 5u]; float bx5 = bias * x_shared[base + 5u];
        float sx6 = scale * x_shared[base + 6u]; float bx6 = bias * x_shared[base + 6u];
        float sx7 = scale * x_shared[base + 7u]; float bx7 = bias * x_shared[base + 7u];
        acc += fma(float((packed >> 0u) & 15u), sx0, bx0);
        acc += fma(float((packed >> 4u) & 15u), sx1, bx1);
        acc += fma(float((packed >> 8u) & 15u), sx2, bx2);
        acc += fma(float((packed >> 12u) & 15u), sx3, bx3);
        acc += fma(float((packed >> 16u) & 15u), sx4, bx4);
        acc += fma(float((packed >> 20u) & 15u), sx5, bx5);
        acc += fma(float((packed >> 24u) & 15u), sx6, bx6);
        acc += fma(float((packed >> 28u) & 15u), sx7, bx7);
    }
    float sum = simd_sum(acc);
    if (lane == 0u) out[row] = sum;
}

// One thread computes one output neuron. Group and element order are ascending.
// The trace records the first differing group for row 0 / neuron 0, plus its
// first packed word and group contributions. It is not used in production.
kernel void affine_probe_scalar_decomposition(
    device const uint *weights [[buffer(0)]],
    device const ushort *scales [[buffer(1)]],
    device const ushort *biases [[buffer(2)]],
    device const float *x [[buffer(3)]],
    device float *out [[buffer(4)]],
    constant uint &out_dim [[buffer(5)]],
    constant uint &in_dim [[buffer(6)]],
    constant uint &group_size [[buffer(7)]],
    device float *trace [[buffer(8)]],
    uint row [[thread_position_in_grid]]
) {
    if (row >= out_dim) return;
    uint packed_cols = in_dim / 8u;
    uint groups = in_dim / group_size;
    uint words_per_group = group_size / 8u;
    device const uint *w_row = weights + row * packed_cols;
    device const ushort *s_row = scales + row * groups;
    device const ushort *b_row = biases + row * groups;
    float acc = 0.0f;
    if (row == 0u) trace[0] = -1.0f;
    for (uint g = 0; g < groups; g++) {
        float scale = probe_bf16(s_row[g]);
        float bias = probe_bf16(b_row[g]);
        float p = 0.0f, xsum = 0.0f, prod_group = 0.0f;
        for (uint word = 0; word < words_per_group; word++) {
            uint col = g * words_per_group + word;
            uint packed = w_row[col];
            for (uint j = 0; j < 8u; j++) {
                uint idx = col * 8u + j;
                float xv = x[idx];
                float q = float((packed >> (j * 4u)) & 15u);
                p = fma(q, xv, p);
                xsum += xv;
                float contribution = fma(q, scale * xv, bias * xv);
                prod_group += contribution;
                if (row == 0u && g == 0u && word == 0u) {
                    trace[8u + j * 3u + 0u] = xv;
                    trace[8u + j * 3u + 1u] = q;
                    trace[8u + j * 3u + 2u] = contribution;
                }
            }
        }
        float decomp_group = fma(bias, xsum, scale * p);
        if (row == 0u && g == 0u) {
            trace[1] = scale; trace[2] = bias;
            trace[3] = prod_group; trace[4] = decomp_group;
            trace[5] = p; trace[6] = xsum;
        }
        if (row == 0u && trace[0] < 0.0f &&
            as_type<uint>(prod_group) != as_type<uint>(decomp_group))
            trace[0] = float(g);
        acc = fma(scale, p, acc);
        acc = fma(bias, xsum, acc);
    }
    out[row] = acc;
}
