// Benchmark-only multi-position LM-head projection. Transformer layers remain
// serial; this file must never be used by the serving decode path.
static int target_verify_snapshot_equal(const ServeStateSnapshot *a,
                                        const ServeStateSnapshot *b) {
    const size_t kv_unit = (size_t)NUM_KV_HEADS * HEAD_DIM * sizeof(float);
    const size_t conv = (CONV_KERNEL_SIZE - 1) * LINEAR_CONV_DIM * sizeof(float);
    const size_t ssm = LINEAR_NUM_V_HEADS * LINEAR_VALUE_DIM * LINEAR_KEY_DIM * sizeof(float);
    if (!a->valid || !b->valid || a->pos != b->pos) return 0;
    for (int i = 0; i < NUM_LAYERS; i++) {
        if (a->kv_len[i] != b->kv_len[i]) return 0;
        size_t kv_bytes = (size_t)a->kv_len[i] * kv_unit;
        if (kv_bytes && (memcmp(a->k_snapshot[i], b->k_snapshot[i], kv_bytes) ||
                         memcmp(a->v_snapshot[i], b->v_snapshot[i], kv_bytes))) return 0;
        if (a->la_conv_snapshot[i] &&
            memcmp(a->la_conv_snapshot[i], b->la_conv_snapshot[i], conv)) return 0;
        if (a->la_ssm_snapshot[i] &&
            memcmp(a->la_ssm_snapshot[i], b->la_ssm_snapshot[i], ssm)) return 0;
    }
    for (int i = 0; i < 48; i++) {
        if (a->gpu_delta_snapshot[i] &&
            memcmp(a->gpu_delta_snapshot[i], b->gpu_delta_snapshot[i],
                   64ULL * 128 * 128 * sizeof(float))) return 0;
        if (a->gpu_conv_snapshot[i] &&
            memcmp(a->gpu_conv_snapshot[i], b->gpu_conv_snapshot[i],
                   3ULL * 12288 * sizeof(float))) return 0;
    }
    return 1;
}

static int target_verify_batch_lm(WeightFile *wf, id<MTLComputePipelineState> pipeline,
                                  id<MTLBuffer> input, id<MTLBuffer> output,
                                  const float *rows, int count) {
    TensorInfo *w = get_tensor_info(wf, "lm_head.weight");
    TensorInfo *s = get_tensor_info(wf, "lm_head.scales");
    TensorInfo *b = get_tensor_info(wf, "lm_head.biases");
    if (!w || !s || !b || !g_metal || !g_metal->wf_buf || count < 1 || count > 8)
        return 0;
    memcpy([input contents], rows, (size_t)count * HIDDEN_DIM * sizeof(float));
    id<MTLCommandBuffer> command = [g_metal->queue commandBuffer];
    id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
    [encoder setComputePipelineState:pipeline];
    [encoder setBuffer:g_metal->wf_buf offset:w->offset atIndex:0];
    [encoder setBuffer:g_metal->wf_buf offset:s->offset atIndex:1];
    [encoder setBuffer:g_metal->wf_buf offset:b->offset atIndex:2];
    [encoder setBuffer:input offset:0 atIndex:3];
    [encoder setBuffer:output offset:0 atIndex:4];
    uint32_t out_dim = VOCAB_SIZE, in_dim = HIDDEN_DIM, n = (uint32_t)count;
    [encoder setBytes:&out_dim length:sizeof(out_dim) atIndex:5];
    [encoder setBytes:&in_dim length:sizeof(in_dim) atIndex:6];
    [encoder setBytes:&n length:sizeof(n) atIndex:7];
    [encoder dispatchThreadgroups:MTLSizeMake((out_dim + 7) / 8, 1, 1)
           threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
    [encoder endEncoding];
    [command commit];
    [command waitUntilCompleted];
    return command.status == MTLCommandBufferStatusCompleted;
}

static int target_verify_batch_trial(WeightFile *wf, KVCache **kv_caches,
                                     void **layer_states, void **layer_mmaps,
                                     int *layer_fds, int K, float *hidden,
                                     uint16_t *final_norm_w,
                                     const ServeStateSnapshot *anchor,
                                     const float *anchor_hidden,
                                     const uint32_t candidates[8], int count,
                                     id<MTLComputePipelineState> pipeline,
                                     id<MTLBuffer> input, id<MTLBuffer> output,
                                     float *rows, TargetVerifySample *sample,
                                     ServeStateSnapshot *final_state) {
    if (!serve_state_snapshot_restore(anchor, kv_caches, layer_states)) return 0;
    memcpy(hidden, anchor_hidden, HIDDEN_DIM * sizeof(float));
    if (g_expert_prefetch_enabled) expert_prefetch_history_reset();
    g_pred_valid = 0;
    uint64_t hits_before = g_expert_cache ? g_expert_cache->hits :
        (g_malloc_cache ? g_malloc_cache->hits : 0);
    uint64_t misses_before = g_expert_cache ? g_expert_cache->misses :
        (g_malloc_cache ? g_malloc_cache->misses : 0);
    cache_telemetry_reset();
    double started = now_ms();
    for (int i = 0; i < count; i++) {
        memcpy(rows + (size_t)i * HIDDEN_DIM, hidden, HIDDEN_DIM * sizeof(float));
        apply_final_norm_inplace(rows + (size_t)i * HIDDEN_DIM, final_norm_w);
        cache_telemetry_note_token();
        embed_lookup(wf, candidates[i], hidden);
        if (!run_all_layers_checked(wf, hidden, kv_caches, layer_states,
                                    layer_mmaps, layer_fds, anchor->pos + i, K)) return 0;
        complete_deferred_experts();
    }
    sample->transformer_ms = now_ms() - started;
    double head_started = now_ms();
    if (!target_verify_batch_lm(wf, pipeline, input, output, rows, count)) return 0;
    sample->lm_head_ms = now_ms() - head_started;
    sample->ms = now_ms() - started;
    sample->unique_experts = g_cache_telemetry.unique_experts_touched;
    uint64_t hits_after = g_expert_cache ? g_expert_cache->hits :
        (g_malloc_cache ? g_malloc_cache->hits : 0);
    uint64_t misses_after = g_expert_cache ? g_expert_cache->misses :
        (g_malloc_cache ? g_malloc_cache->misses : 0);
    sample->hits = hits_after - hits_before;
    sample->misses = misses_after - misses_before;
    if (final_state && !serve_state_snapshot_capture(final_state, kv_caches,
                                                     layer_states, anchor->pos + count)) return 0;
    return 1;
}

static int target_verify_batched_experiment(WeightFile *wf, KVCache **kv_caches,
                                             void **layer_states, void **layer_mmaps,
                                             int *layer_fds, int K, float *hidden,
                                             float *logits, uint16_t *final_norm_w,
                                             const ServeStateSnapshot *anchor,
                                             const float *anchor_hidden,
                                             const uint32_t candidates[8]) {
    NSString *source = [NSString stringWithContentsOfFile:@"target_verify_lmhead.metal"
        encoding:NSUTF8StringEncoding error:NULL];
    if (!source || !g_metal) {
        fprintf(stderr, "[target-batch] missing benchmark Metal source/device\n");
        return 1;
    }
    MTLCompileOptions *options = [[MTLCompileOptions alloc] init];
    options.languageVersion = MTLLanguageVersion3_1;
    options.mathMode = MTLMathModeFast;
    NSError *error = nil;
    id<MTLLibrary> library = [g_metal->device newLibraryWithSource:source options:options error:&error];
    id<MTLFunction> function = [library newFunctionWithName:@"target_verify_lmhead_batch"];
    id<MTLComputePipelineState> pipeline = function
        ? [g_metal->device newComputePipelineStateWithFunction:function error:&error] : nil;
    if (!pipeline) {
        fprintf(stderr, "[target-batch] Metal compile failed: %s\n",
                error.localizedDescription.UTF8String ?: "unknown");
        return 1;
    }
    id<MTLBuffer> input = [g_metal->device newBufferWithLength:8ULL * HIDDEN_DIM * sizeof(float)
        options:MTLResourceStorageModeShared];
    id<MTLBuffer> output = [g_metal->device newBufferWithLength:8ULL * VOCAB_SIZE * sizeof(float)
        options:MTLResourceStorageModeShared];
    float *rows = malloc(8ULL * HIDDEN_DIM * sizeof(float));
    float *reference = malloc(8ULL * VOCAB_SIZE * sizeof(float));
    if (!input || !output || !rows || !reference) return 1;
    const int sizes[4] = {1, 2, 4, 8};
    printf("[target-batch] partial_batch=lm_head_only recurrent_attention_moe=serial "
           "prefix_tokens=%d repetitions=5 warmups=1 reset_ms_excluded=yes\n", anchor->pos);
    int ok = 1;
    double baseline_one_ms = 0.0;
    for (int block = 0; block < 4 && ok; block++) {
        int count = sizes[block];
        ServeStateSnapshot serial_state = {0}, batch_state = {0};
        if (!serve_state_snapshot_restore(anchor, kv_caches, layer_states)) { ok = 0; break; }
        memcpy(hidden, anchor_hidden, HIDDEN_DIM * sizeof(float));
        for (int i = 0; i < count && ok; i++) {
            apply_final_norm_inplace(hidden, final_norm_w);
            lm_head_forward(wf, hidden, reference + (size_t)i * VOCAB_SIZE);
            embed_lookup(wf, candidates[i], hidden);
            ok = run_all_layers_checked(wf, hidden, kv_caches, layer_states,
                                        layer_mmaps, layer_fds, anchor->pos + i, K);
            if (ok) complete_deferred_experts();
        }
        if (ok) ok = serve_state_snapshot_capture(&serial_state, kv_caches,
                                                  layer_states, anchor->pos + count);
        TargetVerifySample sample = {0};
        if (ok) ok = target_verify_batch_trial(wf, kv_caches, layer_states,
            layer_mmaps, layer_fds, K, hidden, final_norm_w, anchor,
            anchor_hidden, candidates, count, pipeline, input, output,
            rows, &sample, &batch_state);
        double max_abs = 0.0, sum_sq = 0.0;
        int argmax_matches = 0;
        const float *batch_logits = [output contents];
        if (ok) {
            for (int i = 0; i < count; i++) {
                const float *serial_row = reference + (size_t)i * VOCAB_SIZE;
                const float *batch_row = batch_logits + (size_t)i * VOCAB_SIZE;
                if (cpu_argmax(serial_row, VOCAB_SIZE) ==
                    cpu_argmax(batch_row, VOCAB_SIZE)) argmax_matches++;
                for (int j = 0; j < VOCAB_SIZE; j++) {
                    double diff = fabs((double)serial_row[j] - batch_row[j]);
                    if (diff > max_abs) max_abs = diff;
                    sum_sq += diff * diff;
                }
            }
        }
        double rms = sqrt(sum_sq / ((double)count * VOCAB_SIZE));
        int state_equal = ok && target_verify_snapshot_equal(&serial_state, &batch_state);
        printf("[target-batch] correctness block=%d argmax=%d/%d max_abs=%.6g "
               "rms=%.6g final_state_exact=%s\n", count, argmax_matches, count,
               max_abs, rms, state_equal ? "yes" : "no");
        ok = ok && argmax_matches == count && max_abs < 0.1 && rms < 0.01 && state_equal;
        serve_state_snapshot_free(&serial_state);
        serve_state_snapshot_free(&batch_state);
        if (!ok) break;
        double samples[5] = {0}, serial_samples[5] = {0};
        double transformer_samples[5] = {0}, head_samples[5] = {0};
        uint64_t unique = 0, hits = 0, misses = 0;
        for (int rep = -1; rep < 5 && ok; rep++) {
            TargetVerifySample serial_sample = {0};
            for (int phase = 0; phase < 2 && ok; phase++) {
                int batch_first = (rep >= 0 && (rep & 1));
                int run_batch = (phase == 0) == batch_first;
                if (run_batch)
                    ok = target_verify_batch_trial(wf, kv_caches, layer_states,
                        layer_mmaps, layer_fds, K, hidden, final_norm_w, anchor,
                        anchor_hidden, candidates, count, pipeline, input, output,
                        rows, &sample, NULL);
                else
                    ok = target_verify_run(wf, kv_caches, layer_states,
                        layer_mmaps, layer_fds, K, hidden, logits,
                        final_norm_w, anchor, anchor_hidden, candidates,
                        count, 0, &serial_sample);
            }
            if (ok && rep >= 0) {
                samples[rep] = sample.ms;
                serial_samples[rep] = serial_sample.ms;
                transformer_samples[rep] = sample.transformer_ms;
                head_samples[rep] = sample.lm_head_ms;
                unique += sample.unique_experts;
                hits += sample.hits;
                misses += sample.misses;
            }
        }
        if (!ok) break;
        qsort(samples, 5, sizeof(double), target_verify_double_cmp);
        qsort(serial_samples, 5, sizeof(double), target_verify_double_cmp);
        qsort(transformer_samples, 5, sizeof(double), target_verify_double_cmp);
        qsort(head_samples, 5, sizeof(double), target_verify_double_cmp);
        if (block == 0) baseline_one_ms = serial_samples[2];
        double sequential = baseline_one_ms * count;
        printf("[target-batch] block=%d serial_median_ms=%.3f batch_median_ms=%.3f "
               "batch_min_ms=%.3f batch_max_ms=%.3f transformer_median_ms=%.3f "
               "lm_head_median_ms=%.3f verified_tok_s=%.2f "
               "sequential_equiv_ms=%.3f advantage=%.3f unique_experts_avg=%.1f "
               "hits_avg=%.1f misses_avg=%.1f\n", count, serial_samples[2],
               samples[2], samples[0], samples[4], transformer_samples[2],
               head_samples[2], count * 1000.0 / samples[2], sequential,
               sequential / samples[2], unique / 5.0, hits / 5.0, misses / 5.0);
        fflush(stdout);
    }
    free(reference);
    free(rows);
    return ok ? 0 : 1;
}
