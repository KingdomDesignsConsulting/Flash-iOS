#include <metal_stdlib>
using namespace metal;


// Benchmark-only TensorFold-inspired Q4 affine M8 ceiling experiment.
// Flash layout: Q4 packed 8 nibbles/uint32, group_size=64, BF16 scale+bias.
// Inputs/outputs remain FP32. This intentionally changes the reduction graph
// versus production dequant_matvec_4bit_v3; correctness is measured, not assumed.
//
// Geometry for the target large affine shapes:
//   M=8 rows, S=8 K-split simdgroups, NT=4 output tiles/simdgroup.
//   One 256-thread threadgroup computes 8 rows x 32 outputs.


#define PRAGMA_UNROLL _Pragma("clang loop unroll(full)")


static inline float bf16_to_float(ushort x) {
    return as_type<float>(uint(x) << 16);
}


// 2^(-4*s), exact powers of two.
static inline float nibble_prescale(uint s) {
    return as_type<float>(uint(127u - 4u * s) << 23);
}


static inline float sum8_fp32(
    float x0, float x1, float x2, float x3,
    float x4, float x5, float x6, float x7
) {
    float v = x0;
    v = fma(x1, 1.0f, v);
    v = fma(x2, 1.0f, v);
    v = fma(x3, 1.0f, v);
    v = fma(x4, 1.0f, v);
    v = fma(x5, 1.0f, v);
    v = fma(x6, 1.0f, v);
    v = fma(x7, 1.0f, v);
    return v;
}


kernel void dense_affine_q4_m8_scale_inside(
    device const uint *W [[buffer(0)]],
    device const ushort *SC [[buffer(1)]],
    device const ushort *BI [[buffer(2)]],
    device const float *X [[buffer(3)]],
    device float *OUT [[buffer(4)]],
    constant uint &N [[buffer(5)]],
    constant uint &K [[buffer(6)]],
    constant uint &group_size [[buffer(7)]],
    constant uint &input_stride [[buffer(8)]],
    constant uint &output_stride [[buffer(9)]],
    uint tgx [[threadgroup_position_in_grid]],
    uint lane [[thread_index_in_simdgroup]],
    uint sg [[simdgroup_index_in_threadgroup]]
) {
    if (group_size != 64u || K != 2048u || (N & 31u) != 0u) return;


    constexpr int S = 8;
    constexpr int NT = 4;
    constexpr int G = 32; // K / 64 for K=2048.


    const int c = int(sg);
    const int qid = int(lane) / 4;
    const int fm = (qid & 4) + ((int(lane) / 2) % 4);
    const int fn = (qid & 2) * 2 + (int(lane) % 2) * 2;
    const int nb = int(tgx) * 32;


    // S chunks x NT output tiles x 64 result elements.
    threadgroup float red[S * NT * 64];


    // Each lane owns two weight words from each of four output tiles.
    int wrow[NT];
    PRAGMA_UNROLL
    for (int t = 0; t < NT; t++)
        wrow[t] = min(nb + 8 * t + fm, int(N) - 1);


    // Each lane owns two verifier rows.
    const int xr0 = fn;
    const int xr1 = fn + 1;


    float acc[NT][2];
    PRAGMA_UNROLL
    for (int t = 0; t < NT; t++) {
        acc[t][0] = 0.0f;
        acc[t][1] = 0.0f;
    }


    device const uint2 *W2 = reinterpret_cast<device const uint2 *>(W);


    for (int g = c; g < G; g += S) {
        uint2 wv[NT];
        PRAGMA_UNROLL
        for (int t = 0; t < NT; t++) {
            // K/16 uint2 entries per output row; four uint2 per group64.
            wv[t] = W2[size_t(wrow[t]) * (K / 16u) + 4u * uint(g) + uint(fn / 2)];
        }


        // Two FP32 rows, eight contiguous inputs for this lane's fm block.
        const uint xb = uint(g) * 64u + uint(fm) * 8u;
        const device float *x0 = X + size_t(xr0) * input_stride + xb;
        const device float *x1 = X + size_t(xr1) * input_stride + xb;


        const float x00=x0[0], x01=x0[1], x02=x0[2], x03=x0[3];
        const float x04=x0[4], x05=x0[5], x06=x0[6], x07=x0[7];
        const float x10=x1[0], x11=x1[1], x12=x1[2], x13=x1[3];
        const float x14=x1[4], x15=x1[5], x16=x1[6], x17=x1[7];


        float xs0 = sum8_fp32(x00,x01,x02,x03,x04,x05,x06,x07);
        float xs1 = sum8_fp32(x10,x11,x12,x13,x14,x15,x16,x17);
        xs0 = fma(simd_shuffle_xor(xs0, ushort(2)), 1.0f, xs0);
        xs1 = fma(simd_shuffle_xor(xs1, ushort(2)), 1.0f, xs1);
        xs0 = fma(simd_shuffle_xor(xs0, ushort(4)), 1.0f, xs0);
        xs1 = fma(simd_shuffle_xor(xs1, ushort(4)), 1.0f, xs1);
        xs0 = fma(simd_shuffle_xor(xs0, ushort(16)), 1.0f, xs0);
        xs1 = fma(simd_shuffle_xor(xs1, ushort(16)), 1.0f, xs1);


        simdgroup_matrix<float, 8, 8> P[NT];
        PRAGMA_UNROLL
        for (int t = 0; t < NT; t++)
            P[t] = simdgroup_matrix<float, 8, 8>(0.0f);


        PRAGMA_UNROLL
        for (uint s = 0; s < 8u; s++) {
            const float ps = nibble_prescale(s);
            const uint mask = 0xFu << (4u * s);


            simdgroup_matrix<float, 8, 8> bm;
            // thread_elements()[0/1] are the two matrix elements owned by this lane.
            const float r0[8] = {x00,x01,x02,x03,x04,x05,x06,x07};
            const float r1[8] = {x10,x11,x12,x13,x14,x15,x16,x17};
            bm.thread_elements()[0] = r0[s] * ps;
            bm.thread_elements()[1] = r1[s] * ps;


            PRAGMA_UNROLL
            for (int t = 0; t < NT; t++) {
                simdgroup_matrix<float, 8, 8> am;
                const float sc = bf16_to_float(SC[size_t(wrow[t]) * G + uint(g)]);
                am.thread_elements()[0] = float(wv[t].x & mask) * sc;
                am.thread_elements()[1] = float(wv[t].y & mask) * sc;
                simdgroup_multiply_accumulate(P[t], am, bm, P[t]);
            }
        }


        PRAGMA_UNROLL
        for (int t = 0; t < NT; t++) {
            const float bi = bf16_to_float(BI[size_t(wrow[t]) * G + uint(g)]);
            acc[t][0] = fma(bi, xs0, acc[t][0] + P[t].thread_elements()[0]);
            acc[t][1] = fma(bi, xs1, acc[t][1] + P[t].thread_elements()[1]);
        }
    }


    // Fixed S=8 reduction across K chunks.
    PRAGMA_UNROLL
    for (int t = 0; t < NT; t++) {
        red[(c * NT + t) * 64 + int(lane) * 2 + 0] = acc[t][0];
        red[(c * NT + t) * 64 + int(lane) * 2 + 1] = acc[t][1];
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);


    // All 256 threads cooperatively reduce the four 8x8 output tiles.
    const int tid = c * 32 + int(lane);
    for (int idx = tid; idx < NT * 64; idx += S * 32) {
        float v[S];
        PRAGMA_UNROLL
        for (int k = 0; k < S; k++)
            v[k] = red[k * (NT * 64) + idx];
        PRAGMA_UNROLL
        for (int w = 1; w < S; w *= 2)
            for (int k = 0; k + w < S; k += 2 * w)
                v[k] = fma(v[k + w], 1.0f, v[k]);


        const int t = idx / 64;
        const int l = (idx % 64) / 2;
        const int e = idx % 2;
        const int lq = l / 4;
        const int row = (lq & 2) * 2 + (l % 2) * 2 + e;
        const int n = nb + 8 * t + (lq & 4) + ((l / 2) % 4);
        if (row < 8 && n < int(N))
            OUT[size_t(row) * output_stride + size_t(n)] = v[0];
    }
}