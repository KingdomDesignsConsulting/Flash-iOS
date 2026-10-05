// Benchmark-only grouped tiered MoE for the N-row activation slab. The first
// integrated correctness prototype uses one synchronization per unique expert;
// this cost is measured and must not be hidden in performance conclusions.
typedef struct {
    id<MTLComputePipelineState> projection;
    id<MTLComputePipelineState> swiglu;
    id<MTLComputePipelineState> conv_chunk, split_qkv, gdn_chunk;
    id<MTLBuffer> input, gate, up, act, output;
    id<MTLBuffer> conv_input, conv_output, q, k, v;
    id<MTLBuffer> z, alpha, beta, decay, beta_gate, gdn_output, attn_output;
    uint64_t groups, repeated, hot, cold, cache_hits, cache_misses, gpu_waits;
    double grouping_ms, expert_ms, shared_ms, linear_ms;
} PrefillNRowGrouped;

static int prefill_nrow_grouped_init(PrefillNRowGrouped *p) {
    NSString *path = @"prefill_probe/chunk_kernels.metal";
    NSString *source = [NSString stringWithContentsOfFile:path
        encoding:NSUTF8StringEncoding error:NULL];
    if (!source) source = [NSString stringWithContentsOfFile:
        @"metal_infer/prefill_probe/chunk_kernels.metal"
        encoding:NSUTF8StringEncoding error:NULL];
    if (!source) { fprintf(stderr, "[prefill-nrow] missing grouped Metal kernels\n"); return 0; }
    NSError *error = nil;
    id<MTLLibrary> library = [g_metal->device newLibraryWithSource:source
        options:nil error:&error];
    if (!library) {
        fprintf(stderr, "[prefill-nrow] shader: %s\n", error.localizedDescription.UTF8String);
        return 0;
    }
    id<MTLFunction> fn = [library newFunctionWithName:@"grouped_tiered_projection"];
    p->projection = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    fn = [library newFunctionWithName:@"grouped_swiglu"];
    p->swiglu = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    fn = [library newFunctionWithName:@"conv_chunk"];
    p->conv_chunk = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    fn = [library newFunctionWithName:@"split_qkv"];
    p->split_qkv = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    fn = [library newFunctionWithName:@"gdn_chunk"];
    p->gdn_chunk = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    const size_t hidden_bytes = 16u * HIDDEN_DIM * sizeof(float);
    const size_t mid_bytes = 16u * MOE_INTERMEDIATE * sizeof(float);
    p->input = [g_metal->device newBufferWithLength:hidden_bytes options:MTLResourceStorageModeShared];
    p->gate = [g_metal->device newBufferWithLength:mid_bytes options:MTLResourceStorageModeShared];
    p->up = [g_metal->device newBufferWithLength:mid_bytes options:MTLResourceStorageModeShared];
    p->act = [g_metal->device newBufferWithLength:mid_bytes options:MTLResourceStorageModeShared];
    p->output = [g_metal->device newBufferWithLength:hidden_bytes options:MTLResourceStorageModeShared];
    const size_t qkv_bytes = 16u * LINEAR_CONV_DIM * sizeof(float);
    const size_t key_bytes = 16u * LINEAR_TOTAL_KEY * sizeof(float);
    const size_t value_bytes = 16u * LINEAR_TOTAL_VALUE * sizeof(float);
    const size_t head_bytes = 16u * LINEAR_NUM_V_HEADS * sizeof(float);
    MTLResourceOptions shared = MTLResourceStorageModeShared;
    p->conv_input = [g_metal->device newBufferWithLength:qkv_bytes options:shared];
    p->conv_output = [g_metal->device newBufferWithLength:qkv_bytes options:shared];
    p->q = [g_metal->device newBufferWithLength:key_bytes options:shared];
    p->k = [g_metal->device newBufferWithLength:key_bytes options:shared];
    p->v = [g_metal->device newBufferWithLength:value_bytes options:shared];
    p->z = [g_metal->device newBufferWithLength:value_bytes options:shared];
    p->alpha = [g_metal->device newBufferWithLength:head_bytes options:shared];
    p->beta = [g_metal->device newBufferWithLength:head_bytes options:shared];
    p->decay = [g_metal->device newBufferWithLength:head_bytes options:shared];
    p->beta_gate = [g_metal->device newBufferWithLength:head_bytes options:shared];
    p->gdn_output = [g_metal->device newBufferWithLength:value_bytes options:shared];
    p->attn_output = [g_metal->device newBufferWithLength:value_bytes options:shared];
    return p->projection && p->swiglu && p->conv_chunk && p->split_qkv &&
        p->gdn_chunk && p->input && p->gate && p->up && p->act && p->output &&
        p->conv_input && p->conv_output && p->q && p->k && p->v && p->z &&
        p->alpha && p->beta && p->decay && p->beta_gate && p->gdn_output &&
        p->attn_output;
}

static int prefill_nrow_linear_layer(PrefillNRowGrouped *p, WeightFile *wf,
    int layer, const float *slab) {
    (void)wf;
    LayerWeightCache *lc = &layer_cache[layer];
    int li = layer - (layer + 1) / FULL_ATTN_INTERVAL;
    if (li < 0 || li >= g_cfg.num_linear_layers || !lc->conv1d_w ||
        !lc->A_log || !lc->dt_bias || !lc->gated_norm_w) return 0;
    double started = now_ms();
    float normed[2048];
    for (int row = 0; row < 16; row++) {
        cpu_rms_norm(slab + (size_t)row * HIDDEN_DIM,
            lc->input_norm_w, normed, HIDDEN_DIM, RMS_NORM_EPS);
        BatchMatvecSpec specs[4] = {
            { lc->qkv_w, lc->qkv_s, lc->qkv_b,
              (float *)[p->conv_input contents] + (size_t)row * LINEAR_CONV_DIM,
              (uint32_t)LINEAR_CONV_DIM, HIDDEN_DIM, GROUP_SIZE, 0,
              lc->qkv_kind, lc->qkv_source },
            { lc->z_w, lc->z_s, lc->z_b,
              (float *)[p->z contents] + (size_t)row * LINEAR_TOTAL_VALUE,
              (uint32_t)LINEAR_TOTAL_VALUE, HIDDEN_DIM, GROUP_SIZE, 1,
              lc->z_kind, lc->z_source },
            { lc->b_w, lc->b_s, lc->b_b,
              (float *)[p->beta contents] + (size_t)row * LINEAR_NUM_V_HEADS,
              (uint32_t)LINEAR_NUM_V_HEADS, HIDDEN_DIM, GROUP_SIZE, 2,
              MATVEC_KIND_MLX4, MATVEC_SOURCE_WF },
            { lc->a_w, lc->a_s, lc->a_b,
              (float *)[p->alpha contents] + (size_t)row * LINEAR_NUM_V_HEADS,
              (uint32_t)LINEAR_NUM_V_HEADS, HIDDEN_DIM, GROUP_SIZE, 3,
              MATVEC_KIND_MLX4, MATVEC_SOURCE_WF },
        };
        fast_batch_matvec(normed, HIDDEN_DIM, specs, 4);
    }
    id<MTLCommandBuffer> cmd = [g_metal->queue commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
    [enc setComputePipelineState:p->conv_chunk];
    [enc setBuffer:g_metal->buf_conv_state[li] offset:0 atIndex:0];
    [enc setBuffer:p->conv_input offset:0 atIndex:1];
    NSUInteger conv_w_off = (NSUInteger)((const char *)lc->conv1d_w -
        (const char *)[g_metal->wf_buf contents]);
    [enc setBuffer:g_metal->wf_buf offset:conv_w_off atIndex:2];
    [enc setBuffer:p->conv_output offset:0 atIndex:3];
    uint32_t n = 16;
    [enc setBytes:&n length:4 atIndex:4];
    [enc dispatchThreads:MTLSizeMake(LINEAR_CONV_DIM, 1, 1)
        threadsPerThreadgroup:MTLSizeMake(128, 1, 1)];
    [enc endEncoding];

    uint32_t key_dim = LINEAR_KEY_DIM;
    float inv_scale = 1.0f / sqrtf((float)key_dim);
    NSUInteger a_off = (NSUInteger)((const char *)lc->A_log -
        (const char *)[g_metal->wf_buf contents]);
    NSUInteger dt_off = (NSUInteger)((const char *)lc->dt_bias -
        (const char *)[g_metal->wf_buf contents]);
    for (int row = 0; row < 16; row++) {
        enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:g_metal->rms_norm_qk];
        NSUInteger base = (size_t)row * LINEAR_CONV_DIM * sizeof(float);
        [enc setBuffer:p->conv_output offset:base atIndex:0];
        [enc setBuffer:p->conv_output offset:base +
            LINEAR_TOTAL_KEY * sizeof(float) atIndex:1];
        [enc setBytes:&key_dim length:4 atIndex:2];
        [enc setBytes:&inv_scale length:4 atIndex:3];
        [enc dispatchThreadgroups:MTLSizeMake(LINEAR_NUM_K_HEADS, 1, 1)
            threadsPerThreadgroup:MTLSizeMake(LINEAR_KEY_DIM, 1, 1)];
        [enc endEncoding];

        enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:g_metal->compute_decay_beta];
        NSUInteger hbase = (size_t)row * LINEAR_NUM_V_HEADS * sizeof(float);
        [enc setBuffer:p->alpha offset:hbase atIndex:0];
        [enc setBuffer:p->beta offset:hbase atIndex:1];
        [enc setBuffer:g_metal->wf_buf offset:a_off atIndex:2];
        [enc setBuffer:g_metal->wf_buf offset:dt_off atIndex:3];
        [enc setBuffer:p->decay offset:hbase atIndex:4];
        [enc setBuffer:p->beta_gate offset:hbase atIndex:5];
        [enc dispatchThreadgroups:MTLSizeMake(1, 1, 1)
            threadsPerThreadgroup:MTLSizeMake(LINEAR_NUM_V_HEADS, 1, 1)];
        [enc endEncoding];
    }
    enc = [cmd computeCommandEncoder];
    [enc setComputePipelineState:p->split_qkv];
    [enc setBuffer:p->conv_output offset:0 atIndex:0];
    [enc setBuffer:p->q offset:0 atIndex:1];
    [enc setBuffer:p->k offset:0 atIndex:2];
    [enc setBuffer:p->v offset:0 atIndex:3];
    [enc setBytes:&n length:4 atIndex:4];
    [enc dispatchThreads:MTLSizeMake((size_t)n * LINEAR_CONV_DIM, 1, 1)
        threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
    [enc endEncoding];

    enc = [cmd computeCommandEncoder];
    [enc setComputePipelineState:p->gdn_chunk];
    [enc setBuffer:g_metal->buf_delta_state[li] offset:0 atIndex:0];
    [enc setBuffer:p->q offset:0 atIndex:1];
    [enc setBuffer:p->k offset:0 atIndex:2];
    [enc setBuffer:p->v offset:0 atIndex:3];
    [enc setBuffer:p->decay offset:0 atIndex:4];
    [enc setBuffer:p->beta_gate offset:0 atIndex:5];
    [enc setBuffer:p->gdn_output offset:0 atIndex:6];
    [enc setBytes:&n length:4 atIndex:7];
    [enc dispatchThreads:MTLSizeMake(LINEAR_TOTAL_VALUE, 1, 1)
        threadsPerThreadgroup:MTLSizeMake(128, 1, 1)];
    [enc endEncoding];

    NSUInteger gnorm_off = (NSUInteger)((const char *)lc->gated_norm_w -
        (const char *)[g_metal->wf_buf contents]);
    uint32_t value_dim = LINEAR_VALUE_DIM;
    float eps = RMS_NORM_EPS;
    for (int row = 0; row < 16; row++) {
        enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:g_metal->gated_rms_norm];
        NSUInteger vbase = (size_t)row * LINEAR_TOTAL_VALUE * sizeof(float);
        [enc setBuffer:p->gdn_output offset:vbase atIndex:0];
        [enc setBuffer:p->z offset:vbase atIndex:1];
        [enc setBuffer:g_metal->wf_buf offset:gnorm_off atIndex:2];
        [enc setBuffer:p->attn_output offset:vbase atIndex:3];
        [enc setBytes:&value_dim length:4 atIndex:4];
        [enc setBytes:&eps length:4 atIndex:5];
        [enc dispatchThreadgroups:MTLSizeMake(LINEAR_NUM_V_HEADS, 1, 1)
            threadsPerThreadgroup:MTLSizeMake(LINEAR_VALUE_DIM, 1, 1)];
        [enc endEncoding];
    }
    [cmd commit]; [cmd waitUntilCompleted];
    p->gpu_waits++;
    p->linear_ms += now_ms() - started;
    if (cmd.status != MTLCommandBufferStatusCompleted) {
        fprintf(stderr, "[prefill-nrow] chunked linear GPU failed: %s\n",
                cmd.error.localizedDescription.UTF8String);
        return 0;
    }
    return 1;
}

static void prefill_nrow_encode_projection(id<MTLCommandBuffer> cmd,
    PrefillNRowGrouped *p, id<MTLBuffer> data, NSUInteger w, NSUInteger s,
    NSUInteger b, id<MTLBuffer> input, id<MTLBuffer> output,
    uint32_t in_dim, uint32_t out_dim, uint32_t count, uint32_t bits) {
    id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
    [enc setComputePipelineState:p->projection];
    [enc setBuffer:data offset:w atIndex:0];
    [enc setBuffer:data offset:s atIndex:1];
    [enc setBuffer:data offset:b atIndex:2];
    [enc setBuffer:input offset:0 atIndex:3];
    [enc setBuffer:output offset:0 atIndex:4];
    [enc setBytes:&in_dim length:4 atIndex:5];
    [enc setBytes:&out_dim length:4 atIndex:6];
    [enc setBytes:&count length:4 atIndex:7];
    [enc setBytes:&bits length:4 atIndex:8];
    [enc dispatchThreadgroups:MTLSizeMake(out_dim, 1, 1)
        threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
    [enc endEncoding];
}

static int prefill_nrow_grouped_layer(PrefillNRowGrouped *p,
    PrefillNRowCapture *cap, int layer, int packed_fd, float *slab) {
    if (!g_use_tiered || !g_tiered_manifest || cap->count != 16 || packed_fd < 0)
        return 0;
    const size_t slot_count = 16u * 8u * HIDDEN_DIM;
    float *slot_results = calloc(slot_count, sizeof(float));
    if (!slot_results) return 0;
    double group_started = now_ms();
    int unique_ids[128], unique_count = 0;
    for (int row = 0; row < 16; row++) for (int k = 0; k < 8; k++) {
        int e = cap->expert_id[row][k];
        int found = 0;
        for (int j = 0; j < unique_count; j++) if (unique_ids[j] == e) { found = 1; break; }
        if (!found) unique_ids[unique_count++] = e;
    }
    p->grouping_ms += now_ms() - group_started;
    p->groups += unique_count;
    p->repeated += 128 - unique_count;
    int ok = 1;
    for (int group = 0; group < unique_count && ok; group++) {
        int e = unique_ids[group];
        int rows[16], slots[16], count = 0;
        for (int row = 0; row < 16; row++) for (int k = 0; k < 8; k++) {
            if (cap->expert_id[row][k] == e) {
                if (count >= 16) { ok = 0; break; }
                rows[count] = row; slots[count] = k; count++;
            }
        }
        if (!ok || count < 1) break;
        TieredExpertInfo *ti = &TIERED(layer, e);
        uint32_t bits = ti->bits;
        if (bits != 2 && bits != 4) { ok = 0; break; }
        ExpertLayout layout = expert_layout_for_kind(
            bits == 2 ? EXPERT_QUANT_2BIT : EXPERT_QUANT_4BIT);
        if (layout.expert_size != ti->size) { ok = 0; break; }
        id<MTLBuffer> data = nil;
        int needs_read = 1;
        if (bits == 4 && g_malloc_cache) {
            p->hot++;
            data = malloc_cache_lookup(g_malloc_cache, layer, e);
            if (data) { needs_read = 0; p->cache_hits++; }
            else {
                int cache_idx = -1;
                data = malloc_cache_insert(g_malloc_cache, layer, e, &cache_idx);
                p->cache_misses++;
            }
        } else {
            p->cold++;
            data = g_metal->buf_multi_expert_data[0];
        }
        if (!data || [data length] < ti->size) { ok = 0; break; }
        if (needs_read && pread(packed_fd, [data contents], ti->size,
                                (off_t)ti->offset) != (ssize_t)ti->size) {
            fprintf(stderr, "[prefill-nrow] expert read failed layer=%d expert=%d\n", layer, e);
            ok = 0; break;
        }
        for (int j = 0; j < count; j++)
            memcpy((float *)[p->input contents] + (size_t)j * HIDDEN_DIM,
                cap->h_post[rows[j]], HIDDEN_DIM * sizeof(float));
        double expert_started = now_ms();
        id<MTLCommandBuffer> cmd = [g_metal->queue commandBuffer];
        prefill_nrow_encode_projection(cmd, p, data,
            layout.gate_w_off, layout.gate_s_off, layout.gate_b_off,
            p->input, p->gate, HIDDEN_DIM, MOE_INTERMEDIATE, count, bits);
        prefill_nrow_encode_projection(cmd, p, data,
            layout.up_w_off, layout.up_s_off, layout.up_b_off,
            p->input, p->up, HIDDEN_DIM, MOE_INTERMEDIATE, count, bits);
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:p->swiglu];
        [enc setBuffer:p->gate offset:0 atIndex:0];
        [enc setBuffer:p->up offset:0 atIndex:1];
        [enc setBuffer:p->act offset:0 atIndex:2];
        uint32_t n = (uint32_t)count;
        [enc setBytes:&n length:4 atIndex:3];
        [enc dispatchThreads:MTLSizeMake((size_t)n * MOE_INTERMEDIATE, 1, 1)
            threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
        [enc endEncoding];
        prefill_nrow_encode_projection(cmd, p, data,
            layout.down_w_off, layout.down_s_off, layout.down_b_off,
            p->act, p->output, MOE_INTERMEDIATE, HIDDEN_DIM, count, bits);
        [cmd commit]; [cmd waitUntilCompleted];
        p->gpu_waits++;
        p->expert_ms += now_ms() - expert_started;
        if (cmd.status != MTLCommandBufferStatusCompleted) {
            fprintf(stderr, "[prefill-nrow] grouped expert GPU failed: %s\n",
                    cmd.error.localizedDescription.UTF8String);
            ok = 0; break;
        }
        for (int j = 0; j < count; j++)
            memcpy(slot_results + ((size_t)rows[j] * 8 + slots[j]) * HIDDEN_DIM,
                   (float *)[p->output contents] + (size_t)j * HIDDEN_DIM,
                   HIDDEN_DIM * sizeof(float));
    }
    if (ok) {
        LayerWeightCache *lc = &layer_cache[layer];
        if (!lc->sd_w) ok = 0;
        double shared_started = now_ms();
        for (int row = 0; row < 16 && ok; row++) {
            float shared_act[512], shared_out[2048], moe_out[2048];
            cpu_swiglu(cap->shared_gate[row], cap->shared_up[row],
                       shared_act, SHARED_INTERMEDIATE);
            fast_kind_matvec(lc->sd_w, lc->sd_s, lc->sd_b,
                lc->sd_kind, lc->sd_source, shared_act, shared_out,
                HIDDEN_DIM, SHARED_INTERMEDIATE, GROUP_SIZE);
            memset(moe_out, 0, sizeof(moe_out));
            for (int k = 0; k < 8; k++)
                cpu_vec_madd(moe_out,
                    slot_results + ((size_t)row * 8 + k) * HIDDEN_DIM,
                    cap->expert_weight[row][k], HIDDEN_DIM);
            float shared_weight = cpu_sigmoid(cap->shared_score[row]);
            float *dest = slab + (size_t)row * HIDDEN_DIM;
            for (int i = 0; i < HIDDEN_DIM; i++)
                dest[i] = cap->h_mid[row][i] + moe_out[i] +
                          shared_weight * shared_out[i];
        }
        p->shared_ms += now_ms() - shared_started;
    }
    free(slot_results);
    return ok;
}
