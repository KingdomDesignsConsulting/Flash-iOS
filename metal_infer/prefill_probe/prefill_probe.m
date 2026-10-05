#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>

static id<MTLBuffer> buffer(id<MTLDevice> dev, size_t bytes) {
    return [dev newBufferWithLength:bytes options:MTLResourceStorageModeShared];
}

static float sample(uint32_t *seed) {
    *seed = *seed * 1664525u + 1013904223u;
    return ((float)((*seed >> 8) & 0xffff) / 65535.0f - 0.5f) * 0.04f;
}

static double wall_ms(void) {
    return [NSDate timeIntervalSinceReferenceDate] * 1000.0;
}

static double median(double *values, int count) {
    for (int i = 1; i < count; i++) {
        double x = values[i]; int j = i - 1;
        while (j >= 0 && values[j] > x) { values[j + 1] = values[j]; j--; }
        values[j + 1] = x;
    }
    return values[count / 2];
}

static double maxdiff(const float *a, const float *b, size_t n) {
    double max = 0;
    for (size_t i = 0; i < n; i++) {
        if (!isfinite(a[i]) || !isfinite(b[i])) return NAN;
        double d = fabs((double)a[i] - b[i]);
        if (d > max) max = d;
    }
    return max;
}

static id<MTLComputePipelineState> make_pipeline(id<MTLDevice> dev, id<MTLLibrary> lib,
                                         NSString *name) {
    NSError *error = nil;
    id<MTLFunction> fn = [lib newFunctionWithName:name];
    id<MTLComputePipelineState> p = [dev newComputePipelineStateWithFunction:fn error:&error];
    if (!p) fprintf(stderr, "pipeline %s: %s\n", name.UTF8String,
                    error.localizedDescription.UTF8String);
    return p;
}

static double gdn_once(id<MTLCommandQueue> queue, id<MTLComputePipelineState> p,
    NSArray<id<MTLBuffer>> *args, uint32_t start, uint32_t n, BOOL chunk) {
    id<MTLCommandBuffer> cmd = [queue commandBuffer];
    double started = wall_ms();
    for (uint32_t t = 0; t < (chunk ? 1u : n); t++) {
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:p];
        for (NSUInteger j = 0; j < args.count; j++)
            [enc setBuffer:args[j] offset:0 atIndex:j];
        uint32_t param = chunk ? n : start + t;
        [enc setBytes:&param length:sizeof(param) atIndex:7];
        [enc dispatchThreads:MTLSizeMake(4096, 1, 1)
          threadsPerThreadgroup:MTLSizeMake(128, 1, 1)];
        [enc endEncoding];
    }
    [cmd commit]; [cmd waitUntilCompleted];
    if (cmd.status != MTLCommandBufferStatusCompleted) {
        fprintf(stderr, "GDN command failed: %s\n", cmd.error.localizedDescription.UTF8String);
        return -1;
    }
    return wall_ms() - started;
}

static int bench_gdn(id<MTLDevice> dev, id<MTLCommandQueue> queue,
    id<MTLComputePipelineState> scalar, id<MTLComputePipelineState> chunk) {
    const uint32_t sizes[] = {1, 4, 8, 16, 32, 64};
    const size_t state_count = 32u * 128u * 128u;
    printf("GDN chunk,scalar_ms,chunk_ms,speedup,max_state_error,max_output_error\n");
    for (NSUInteger z = 0; z < sizeof(sizes)/sizeof(sizes[0]); z++) {
        const uint32_t n = sizes[z];
        id<MTLBuffer> initial = buffer(dev, state_count * sizeof(float));
        id<MTLBuffer> state_a = buffer(dev, initial.length), state_b = buffer(dev, initial.length);
        id<MTLBuffer> q = buffer(dev, (size_t)(n + 1) * 2048 * sizeof(float));
        id<MTLBuffer> k = buffer(dev, q.length);
        id<MTLBuffer> v = buffer(dev, (size_t)(n + 1) * 4096 * sizeof(float));
        id<MTLBuffer> decay = buffer(dev, (size_t)(n + 1) * 32 * sizeof(float));
        id<MTLBuffer> beta = buffer(dev, decay.length);
        id<MTLBuffer> out_a = buffer(dev, v.length), out_b = buffer(dev, v.length);
        if (!initial || !state_a || !state_b || !q || !k || !v ||
            !decay || !beta || !out_a || !out_b) return 0;
        uint32_t seed = 1234567;
        float *s = initial.contents;
        for (size_t i = 0; i < state_count; i++) s[i] = sample(&seed);
        for (size_t i = 0; i < (size_t)(n + 1) * 2048; i++) {
            ((float *)q.contents)[i] = sample(&seed);
            ((float *)k.contents)[i] = sample(&seed);
        }
        for (size_t i = 0; i < (size_t)(n + 1) * 4096; i++)
            ((float *)v.contents)[i] = sample(&seed);
        for (size_t i = 0; i < (size_t)(n + 1) * 32; i++) {
            ((float *)decay.contents)[i] = 0.96f + sample(&seed);
            ((float *)beta.contents)[i] = 0.45f + sample(&seed);
        }
        NSArray *a = @[state_a, q, k, v, decay, beta, out_a];
        NSArray *b = @[state_b, q, k, v, decay, beta, out_b];
        double times_a[5], times_b[5];
        for (int trial = -1; trial < 5; trial++) {
            memcpy(state_a.contents, initial.contents, initial.length);
            memcpy(state_b.contents, initial.contents, initial.length);
            double ta = gdn_once(queue, scalar, a, 0, n, NO);
            double tb = gdn_once(queue, chunk, b, 0, n, YES);
            if (ta < 0 || tb < 0) return 0;
            if (trial >= 0) { times_a[trial] = ta; times_b[trial] = tb; }
        }
        double ds = maxdiff(state_a.contents, state_b.contents, state_count);
        double dout = maxdiff(out_a.contents, out_b.contents, (size_t)n * 4096);
        double ma = median(times_a, 5), mb = median(times_b, 5);
        printf("GDN %u,%.3f,%.3f,%.3f,%.8g,%.8g\n", n, ma, mb, ma/mb, ds, dout);
        fflush(stdout);
        if (!isfinite(ds) || !isfinite(dout) || ds > 1e-4 || dout > 1e-4) return 0;
        if (n == 16 || n == 32) {
            if (gdn_once(queue, scalar, a, n, 1, NO) < 0 ||
                gdn_once(queue, scalar, b, n, 1, NO) < 0) return 0;
            double cs = maxdiff(state_a.contents, state_b.contents, state_count);
            double co = maxdiff((float *)out_a.contents + (size_t)n * 4096,
                (float *)out_b.contents + (size_t)n * 4096, 4096);
            printf("GDN_CONT %u,state=%.8g,output=%.8g\n", n, cs, co);
            if (!isfinite(cs) || !isfinite(co) || cs > 1e-4 || co > 1e-4) return 0;
        }
    }
    return 1;
}

static int conv_once(id<MTLCommandQueue> queue, id<MTLComputePipelineState> p,
    NSArray<id<MTLBuffer>> *args, uint32_t start, uint32_t count, BOOL chunk) {
    id<MTLCommandBuffer> cmd = [queue commandBuffer];
    for (uint32_t t = 0; t < (chunk ? 1u : count); t++) {
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:p];
        for (NSUInteger j = 0; j < args.count; j++)
            [enc setBuffer:args[j] offset:0 atIndex:j];
        uint32_t param = chunk ? count : start + t;
        [enc setBytes:&param length:4 atIndex:4];
        [enc dispatchThreads:MTLSizeMake(8192, 1, 1)
          threadsPerThreadgroup:MTLSizeMake(128, 1, 1)];
        [enc endEncoding];
    }
    [cmd commit]; [cmd waitUntilCompleted];
    if (cmd.status != MTLCommandBufferStatusCompleted) {
        fprintf(stderr, "CONV command failed: %s\n", cmd.error.localizedDescription.UTF8String);
        return 0;
    }
    return 1;
}

static int bench_conv(id<MTLDevice> dev, id<MTLCommandQueue> queue,
    id<MTLComputePipelineState> scalar, id<MTLComputePipelineState> chunk) {
    const uint32_t sizes[] = {16, 32};
    const size_t tail_count = 3u * 8192u;
    for (NSUInteger z = 0; z < 2; z++) {
        uint32_t n = sizes[z], seed = 0x98765u;
        id<MTLBuffer> initial = buffer(dev, tail_count * sizeof(float));
        id<MTLBuffer> sa = buffer(dev, initial.length), sb = buffer(dev, initial.length);
        id<MTLBuffer> input = buffer(dev, (size_t)(n + 1) * 8192 * sizeof(float));
        id<MTLBuffer> weights = buffer(dev, (size_t)8192 * 4 * sizeof(uint16_t));
        id<MTLBuffer> oa = buffer(dev, input.length), ob = buffer(dev, input.length);
        if (!initial || !sa || !sb || !input || !weights || !oa || !ob) return 0;
        for (size_t i = 0; i < tail_count; i++)
            ((float *)initial.contents)[i] = sample(&seed);
        for (size_t i = 0; i < (size_t)(n + 1) * 8192; i++)
            ((float *)input.contents)[i] = sample(&seed);
        for (size_t i = 0; i < (size_t)8192 * 4; i++) {
            float w = sample(&seed);
            uint32_t bits;
            memcpy(&bits, &w, sizeof(bits));
            ((uint16_t *)weights.contents)[i] = (uint16_t)(bits >> 16);
        }
        memcpy(sa.contents, initial.contents, initial.length);
        memcpy(sb.contents, initial.contents, initial.length);
        NSArray *a = @[sa, input, weights, oa], *b = @[sb, input, weights, ob];
        if (!conv_once(queue, scalar, a, 0, n, NO) ||
            !conv_once(queue, chunk, b, 0, n, YES)) return 0;
        double pre_o = maxdiff(oa.contents, ob.contents, (size_t)n * 8192);
        double pre_s = maxdiff(sa.contents, sb.contents, tail_count);
        if (!conv_once(queue, scalar, a, n, 1, NO) ||
            !conv_once(queue, scalar, b, n, 1, NO)) return 0;
        double next_o = maxdiff((float *)oa.contents + (size_t)n * 8192,
            (float *)ob.contents + (size_t)n * 8192, 8192);
        double next_s = maxdiff(sa.contents, sb.contents, tail_count);
        printf("CONV_CONT %u,prefix_output=%.8g,prefix_tail=%.8g,next_output=%.8g,next_tail=%.8g\n",
            n, pre_o, pre_s, next_o, next_s);
        fflush(stdout);
        if (!isfinite(pre_o) || !isfinite(pre_s) || !isfinite(next_o) || !isfinite(next_s) ||
            pre_o > 1e-4 || pre_s > 1e-4 || next_o > 1e-4 || next_s > 1e-4) return 0;
    }
    return 1;
}

typedef struct { size_t w, s, b; } ProjectionOffsets;
typedef struct {
    ProjectionOffsets gate, up, down;
    size_t bytes;
} ExpertLayout;

static ExpertLayout layout_for_bits(uint32_t bits) {
    const size_t mid = 512, hid = 2048, gs = 64;
    const size_t stride = 32 / bits;
    const size_t gw = mid * (hid / stride) * 4;
    const size_t gs_bytes = mid * (hid / gs) * 2;
    const size_t dw = hid * (mid / stride) * 4;
    const size_t ds_bytes = hid * (mid / gs) * 2;
    size_t p = 0; ExpertLayout l = {0};
    l.gate = (ProjectionOffsets){p, p + gw, p + gw + gs_bytes};
    p += gw + 2 * gs_bytes;
    l.up = (ProjectionOffsets){p, p + gw, p + gw + gs_bytes};
    p += gw + 2 * gs_bytes;
    l.down = (ProjectionOffsets){p, p + dw, p + dw + ds_bytes};
    l.bytes = p + dw + 2 * ds_bytes;
    return l;
}

static void encode_projection(id<MTLCommandBuffer> cmd, id<MTLComputePipelineState> p,
    id<MTLBuffer> expert, ProjectionOffsets offsets, id<MTLBuffer> input,
    size_t input_offset, id<MTLBuffer> output, size_t output_offset,
    uint32_t in_dim, uint32_t out_dim, uint32_t count, uint32_t bits) {
    id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
    [enc setComputePipelineState:p];
    [enc setBuffer:expert offset:offsets.w atIndex:0];
    [enc setBuffer:expert offset:offsets.s atIndex:1];
    [enc setBuffer:expert offset:offsets.b atIndex:2];
    [enc setBuffer:input offset:input_offset atIndex:3];
    [enc setBuffer:output offset:output_offset atIndex:4];
    [enc setBytes:&in_dim length:4 atIndex:5];
    [enc setBytes:&out_dim length:4 atIndex:6];
    [enc setBytes:&count length:4 atIndex:7];
    [enc setBytes:&bits length:4 atIndex:8];
    [enc dispatchThreadgroups:MTLSizeMake(out_dim, 1, 1)
      threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
    [enc endEncoding];
}

static void encode_swiglu(id<MTLCommandBuffer> cmd, id<MTLComputePipelineState> p,
    id<MTLBuffer> gate, id<MTLBuffer> up, id<MTLBuffer> act,
    size_t offset, uint32_t count) {
    id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
    [enc setComputePipelineState:p];
    [enc setBuffer:gate offset:offset atIndex:0];
    [enc setBuffer:up offset:offset atIndex:1];
    [enc setBuffer:act offset:offset atIndex:2];
    [enc setBytes:&count length:4 atIndex:3];
    [enc dispatchThreads:MTLSizeMake((size_t)count * 512, 1, 1)
      threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
    [enc endEncoding];
}

static double expert_once(id<MTLCommandQueue> queue, id<MTLComputePipelineState> proj,
    id<MTLComputePipelineState> swiglu, id<MTLBuffer> expert, ExpertLayout layout,
    id<MTLBuffer> input, id<MTLBuffer> gate, id<MTLBuffer> up,
    id<MTLBuffer> act, id<MTLBuffer> out, uint32_t n, uint32_t bits, BOOL grouped) {
    id<MTLCommandBuffer> cmd = [queue commandBuffer];
    double started = wall_ms();
    for (uint32_t m = 0; m < (grouped ? 1u : n); m++) {
        const uint32_t rows = grouped ? n : 1;
        const size_t in_off = (size_t)m * 2048 * sizeof(float);
        const size_t mid_off = (size_t)m * 512 * sizeof(float);
        encode_projection(cmd, proj, expert, layout.gate, input, in_off,
            gate, mid_off, 2048, 512, rows, bits);
        encode_projection(cmd, proj, expert, layout.up, input, in_off,
            up, mid_off, 2048, 512, rows, bits);
        encode_swiglu(cmd, swiglu, gate, up, act, mid_off, rows);
        encode_projection(cmd, proj, expert, layout.down, act, mid_off,
            out, in_off, 512, 2048, rows, bits);
    }
    [cmd commit]; [cmd waitUntilCompleted];
    if (cmd.status != MTLCommandBufferStatusCompleted) {
        fprintf(stderr, "expert command failed: %s\n", cmd.error.localizedDescription.UTF8String);
        return -1;
    }
    return wall_ms() - started;
}

static int bench_expert(id<MTLDevice> dev, id<MTLCommandQueue> queue,
    id<MTLComputePipelineState> proj, id<MTLComputePipelineState> swiglu,
    NSString *model_dir, uint32_t bits, int expert_id, uint64_t file_offset) {
    ExpertLayout layout = layout_for_bits(bits);
    NSString *path = [[model_dir stringByAppendingPathComponent:@"packed_experts_tiered"]
        stringByAppendingPathComponent:@"layer_00.bin"];
    int fd = open(path.fileSystemRepresentation, O_RDONLY);
    if (fd < 0) return 0;
    id<MTLBuffer> expert = buffer(dev, layout.bytes);
    ssize_t got = pread(fd, expert.contents, layout.bytes, (off_t)file_offset);
    close(fd);
    if (got != (ssize_t)layout.bytes) return 0;
    printf("EXPERT bits=%u id=%d bytes=%zu\n", bits, expert_id, layout.bytes);
    const uint32_t sizes[] = {1, 4, 8, 16, 32};
    for (NSUInteger z = 0; z < sizeof(sizes)/sizeof(sizes[0]); z++) {
        uint32_t n = sizes[z], seed = 52341;
        id<MTLBuffer> input = buffer(dev, (size_t)n * 2048 * sizeof(float));
        for (size_t i = 0; i < (size_t)n * 2048; i++)
            ((float *)input.contents)[i] = sample(&seed);
        id<MTLBuffer> ga = buffer(dev, (size_t)n * 512 * sizeof(float));
        id<MTLBuffer> ua = buffer(dev, ga.length), aa = buffer(dev, ga.length);
        id<MTLBuffer> oa = buffer(dev, input.length);
        id<MTLBuffer> gb = buffer(dev, ga.length), ub = buffer(dev, ga.length);
        id<MTLBuffer> ab = buffer(dev, ga.length), ob = buffer(dev, input.length);
        if (!input || !ga || !ua || !aa || !oa || !gb || !ub || !ab || !ob) return 0;
        double ta[5], tb[5];
        for (int trial = -1; trial < 5; trial++) {
            double a = expert_once(queue, proj, swiglu, expert, layout,
                input, ga, ua, aa, oa, n, bits, NO);
            double b = expert_once(queue, proj, swiglu, expert, layout,
                input, gb, ub, ab, ob, n, bits, YES);
            if (a < 0 || b < 0) return 0;
            if (trial >= 0) { ta[trial] = a; tb[trial] = b; }
        }
        double error = maxdiff(oa.contents, ob.contents, (size_t)n * 2048);
        double a = median(ta, 5), b = median(tb, 5);
        printf("MOE %u %u,%.3f,%.3f,%.3f,%.8g\n", bits, n, a, b, a/b, error);
        fflush(stdout);
        if (!isfinite(error) || error > 1e-2) return 0;
    }
    return 1;
}

int main(int argc, const char **argv) {
    @autoreleasepool {
        if (argc != 3) {
            fprintf(stderr, "usage: prefill_probe MODEL_DIR KERNEL_FILE\n");
            return 2;
        }
        NSString *model_dir = @(argv[1]);
        NSString *config_path = [model_dir stringByAppendingPathComponent:@"config.json"];
        NSData *config_data = [NSData dataWithContentsOfFile:config_path];
        if (!config_data) {
            fprintf(stderr, "cannot read model config: %s\n", config_path.UTF8String);
            return 2;
        }
        NSDictionary *config = [NSJSONSerialization JSONObjectWithData:config_data
            options:0 error:NULL];
        NSDictionary *geometry = config[@"text_config"] ?: config;
        if (![geometry[@"linear_num_value_heads"] isEqual:@32] ||
            ![geometry[@"linear_num_key_heads"] isEqual:@16] ||
            ![geometry[@"linear_key_head_dim"] isEqual:@128] ||
            ![geometry[@"linear_value_head_dim"] isEqual:@128] ||
            ![geometry[@"linear_conv_kernel_dim"] isEqual:@4]) {
            fprintf(stderr, "probe requires model geometry V=32 K=16 key/value=128 conv=4\n");
            return 2;
        }
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { fprintf(stderr, "no Metal device\n"); return 1; }
        NSString *source = [NSString stringWithContentsOfFile:@(argv[2])
            encoding:NSUTF8StringEncoding error:NULL];
        NSError *error = nil;
        id<MTLLibrary> lib = [dev newLibraryWithSource:source options:nil error:&error];
        if (!lib) { fprintf(stderr, "shader: %s\n", error.localizedDescription.UTF8String); return 1; }
        id<MTLCommandQueue> queue = [dev newCommandQueue];
        id<MTLComputePipelineState> scalar = make_pipeline(dev, lib, @"gdn_scalar");
        id<MTLComputePipelineState> chunk = make_pipeline(dev, lib, @"gdn_chunk");
        id<MTLComputePipelineState> conv_scalar_pipe = make_pipeline(dev, lib, @"conv_scalar");
        id<MTLComputePipelineState> conv_chunk_pipe = make_pipeline(dev, lib, @"conv_chunk");
        id<MTLComputePipelineState> proj = make_pipeline(dev, lib, @"grouped_tiered_projection");
        id<MTLComputePipelineState> swiglu = make_pipeline(dev, lib, @"grouped_swiglu");
        if (!scalar || !chunk || !conv_scalar_pipe || !conv_chunk_pipe || !proj || !swiglu) return 1;
        NSString *manifest_path = [model_dir stringByAppendingPathComponent:
            @"packed_experts_tiered/tiered_manifest.json"];
        NSData *manifest_data = [NSData dataWithContentsOfFile:manifest_path];
        if (!manifest_data) {
            fprintf(stderr, "cannot read tiered manifest: %s\n", manifest_path.UTF8String);
            return 2;
        }
        id manifest = [NSJSONSerialization JSONObjectWithData:manifest_data
            options:0 error:&error];
        NSArray *experts = manifest[@"layers"][@"0"][@"experts"];
        int ids[2] = {-1, -1}; uint64_t offsets[2] = {0, 0};
        for (int i = 0; i < (int)experts.count; i++) {
            int bits = [experts[i][@"bits"] intValue];
            int slot = bits == 4 ? 0 : (bits == 2 ? 1 : -1);
            if (slot >= 0 && ids[slot] < 0) {
                ids[slot] = i; offsets[slot] = [experts[i][@"offset"] unsignedLongLongValue];
            }
        }
        if (ids[0] < 0 || ids[1] < 0) return 1;
        printf("BENCH_START device=%s\n", dev.name.UTF8String);
        if (!bench_gdn(dev, queue, scalar, chunk)) return 1;
        if (!bench_conv(dev, queue, conv_scalar_pipe, conv_chunk_pipe)) return 1;
        if (!bench_expert(dev, queue, proj, swiglu, model_dir, 4, ids[0], offsets[0])) return 1;
        if (!bench_expert(dev, queue, proj, swiglu, model_dir, 2, ids[1], offsets[1])) return 1;
        printf("BENCH_PASS\n");
        return 0;
    }
}
