// Benchmark-only layer-major block experiment. Each layer processes candidate
// positions in causal order, then advances the whole block to the next layer.
// Expert kernels still run per position; adjacent accesses to the same layer's
// experts can reuse the existing expert cache. Serving never calls this path.
static double target_verify_state_max_diff(const float *a, const float *b,
                                           size_t count, size_t *different) {
    double maximum = 0.0;
    for (size_t i = 0; i < count; i++) {
        double d = fabs((double)a[i] - (double)b[i]);
        if (!isfinite(d)) return INFINITY;
        if (d != 0.0) (*different)++;
        if (d > maximum) maximum = d;
    }
    return maximum;
}

static int target_verify_layer_state_report(const ServeStateSnapshot *a,
                                            const ServeStateSnapshot *b) {
    double kv_max = 0.0, cpu_conv_max = 0.0, cpu_ssm_max = 0.0;
    double gpu_conv_max = 0.0, gpu_ssm_max = 0.0;
    size_t kv_diffs = 0, cpu_conv_diffs = 0, cpu_ssm_diffs = 0;
    size_t gpu_conv_diffs = 0, gpu_ssm_diffs = 0;
    int shape_ok = a->valid && b->valid && a->pos == b->pos;
    for (int layer = 0; layer < NUM_LAYERS && shape_ok; layer++) {
        if (a->kv_len[layer] != b->kv_len[layer]) { shape_ok = 0; break; }
        size_t kv_count = (size_t)a->kv_len[layer] * NUM_KV_HEADS * HEAD_DIM;
        if (kv_count) {
            double dk = target_verify_state_max_diff(a->k_snapshot[layer],
                b->k_snapshot[layer], kv_count, &kv_diffs);
            double dv = target_verify_state_max_diff(a->v_snapshot[layer],
                b->v_snapshot[layer], kv_count, &kv_diffs);
            if (dk > kv_max) kv_max = dk;
            if (dv > kv_max) kv_max = dv;
        }
        if (a->la_conv_snapshot[layer] && b->la_conv_snapshot[layer]) {
            double d = target_verify_state_max_diff(a->la_conv_snapshot[layer],
                b->la_conv_snapshot[layer], (CONV_KERNEL_SIZE - 1) * LINEAR_CONV_DIM,
                &cpu_conv_diffs);
            if (d > cpu_conv_max) cpu_conv_max = d;
        }
        if (a->la_ssm_snapshot[layer] && b->la_ssm_snapshot[layer]) {
            double d = target_verify_state_max_diff(a->la_ssm_snapshot[layer],
                b->la_ssm_snapshot[layer], LINEAR_NUM_V_HEADS * LINEAR_VALUE_DIM *
                LINEAR_KEY_DIM, &cpu_ssm_diffs);
            if (d > cpu_ssm_max) cpu_ssm_max = d;
        }
    }
    for (int layer = 0; layer < 48 && shape_ok; layer++) {
        if (a->gpu_delta_snapshot[layer] && b->gpu_delta_snapshot[layer]) {
            double d = target_verify_state_max_diff(a->gpu_delta_snapshot[layer],
                b->gpu_delta_snapshot[layer], 64ULL * 128 * 128,
                &gpu_ssm_diffs);
            if (d > gpu_ssm_max) gpu_ssm_max = d;
        }
        if (a->gpu_conv_snapshot[layer] && b->gpu_conv_snapshot[layer]) {
            double d = target_verify_state_max_diff(a->gpu_conv_snapshot[layer],
                b->gpu_conv_snapshot[layer], 3ULL * 12288, &gpu_conv_diffs);
            if (d > gpu_conv_max) gpu_conv_max = d;
        }
    }
    printf("[target-layer-major] state shape_ok=%s kv=%.6g(%zu) "
           "cpu_conv=%.6g(%zu) cpu_ssm=%.6g(%zu) "
           "gpu_conv=%.6g(%zu) gpu_ssm=%.6g(%zu)\n",
           shape_ok ? "yes" : "no", kv_max, kv_diffs,
           cpu_conv_max, cpu_conv_diffs, cpu_ssm_max, cpu_ssm_diffs,
           gpu_conv_max, gpu_conv_diffs, gpu_ssm_max, gpu_ssm_diffs);
    return shape_ok && kv_max < 1e-3 && cpu_conv_max < 1e-3 &&
        cpu_ssm_max < 1e-3 && gpu_conv_max < 1e-3 && gpu_ssm_max < 1e-3;
}

static int target_verify_layer_major_trial(WeightFile *wf, KVCache **kv_caches,
    void **layer_states, void **layer_mmaps, int *layer_fds, int K,
    const ServeStateSnapshot *anchor, const float *anchor_hidden,
    const uint32_t candidates[8], int count, uint16_t *final_norm_w,
    id<MTLComputePipelineState> pipeline, id<MTLBuffer> input,
    id<MTLBuffer> output, float *block_hidden, float *rows,
    TargetVerifySample *sample, ServeStateSnapshot *final_state) {
    if (!serve_state_snapshot_restore(anchor, kv_caches, layer_states)) return 0;
    if (g_expert_prefetch_enabled) expert_prefetch_history_reset();
    g_pred_valid = 0;
#ifdef TARGET_VERIFY_COLD_CACHE
    g_target_cold_active = 1;
    g_target_cold_layer = -1;
    g_target_cold_count = 0;
    g_target_cold_loads = g_target_cold_reuses = 0;
#endif
    uint64_t hits_before = g_expert_cache ? g_expert_cache->hits :
        (g_malloc_cache ? g_malloc_cache->hits : 0);
    uint64_t misses_before = g_expert_cache ? g_expert_cache->misses :
        (g_malloc_cache ? g_malloc_cache->misses : 0);
    cache_telemetry_reset();
    double started = now_ms();
    for (int i = 0; i < count; i++)
        embed_lookup(wf, candidates[i], block_hidden + (size_t)i * HIDDEN_DIM);
    for (int layer = 0; layer < NUM_LAYERS; layer++) {
        int is_full = ((layer + 1) % FULL_ATTN_INTERVAL == 0);
        for (int i = 0; i < count; i++) {
            cache_telemetry_note_token();
            g_forward_error = 0;
            fused_layer_forward(wf, layer, block_hidden + (size_t)i * HIDDEN_DIM,
                is_full ? kv_caches[layer] : NULL,
                is_full ? NULL : layer_states[layer], anchor->pos + i,
                layer_mmaps[layer] != MAP_FAILED ? layer_mmaps[layer] : NULL,
                K, layer_fds[layer]);
            if (g_forward_error) { discard_deferred_experts(); return 0; }
            complete_deferred_experts();
        }
    }
    sample->transformer_ms = now_ms() - started;
    memcpy(rows, anchor_hidden, HIDDEN_DIM * sizeof(float));
    for (int i = 1; i < count; i++)
        memcpy(rows + (size_t)i * HIDDEN_DIM,
               block_hidden + (size_t)(i - 1) * HIDDEN_DIM,
               HIDDEN_DIM * sizeof(float));
    for (int i = 0; i < count; i++)
        apply_final_norm_inplace(rows + (size_t)i * HIDDEN_DIM, final_norm_w);
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
#ifdef TARGET_VERIFY_COLD_CACHE
    sample->cold_group_loads = g_target_cold_loads;
    sample->cold_group_reuses = g_target_cold_reuses;
    g_target_cold_active = 0;
#endif
    if (final_state && !serve_state_snapshot_capture(final_state, kv_caches,
                                                      layer_states, anchor->pos + count)) return 0;
    return 1;
}

static int target_verify_layer_major_experiment(WeightFile *wf,
    KVCache **kv_caches, void **layer_states, void **layer_mmaps,
    int *layer_fds, int K, float *hidden, float *logits,
    uint16_t *final_norm_w, const ServeStateSnapshot *anchor,
    const float *anchor_hidden, const uint32_t candidates[8]) {
    NSString *source = [NSString stringWithContentsOfFile:@"target_verify_lmhead.metal"
        encoding:NSUTF8StringEncoding error:NULL];
    if (!source || !g_metal) return 1;
    MTLCompileOptions *options = [[MTLCompileOptions alloc] init];
    options.languageVersion = MTLLanguageVersion3_1;
    options.mathMode = MTLMathModeFast;
    NSError *error = nil;
    id<MTLLibrary> library = [g_metal->device newLibraryWithSource:source
        options:options error:&error];
    id<MTLFunction> function = [library newFunctionWithName:@"target_verify_lmhead_batch"];
    id<MTLComputePipelineState> pipeline = function
        ? [g_metal->device newComputePipelineStateWithFunction:function error:&error] : nil;
    if (!pipeline) {
        fprintf(stderr, "[target-layer-major] Metal compile failed: %s\n",
                error.localizedDescription.UTF8String ?: "unknown");
        return 1;
    }
    id<MTLBuffer> input = [g_metal->device newBufferWithLength:8ULL * HIDDEN_DIM * sizeof(float)
        options:MTLResourceStorageModeShared];
    id<MTLBuffer> output = [g_metal->device newBufferWithLength:8ULL * VOCAB_SIZE * sizeof(float)
        options:MTLResourceStorageModeShared];
    float *block_hidden = malloc(8ULL * HIDDEN_DIM * sizeof(float));
    float *rows = malloc(8ULL * HIDDEN_DIM * sizeof(float));
    float *reference = malloc(8ULL * VOCAB_SIZE * sizeof(float));
    if (!input || !output || !block_hidden || !rows || !reference) {
        free(block_hidden); free(rows); free(reference);
        return 1;
    }
    printf("[target-layer-major] transformer=layer_major positions=causal "
           "moe_execution=per_position cache_locality=layer_grouped "
#ifdef TARGET_VERIFY_COLD_CACHE
           "cold_weight_staging=per_layer "
#else
           "cold_weight_staging=off "
#endif
           "lm_head=batched repetitions=5 warmups=1 reset_ms_excluded=yes\n");
    int ok = 1;
    const int sizes[2] = {4, 8};
    for (int block = 0; block < 2 && ok; block++) {
        int count = sizes[block];
        ServeStateSnapshot serial_state = {0}, layer_state = {0};
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
#ifdef TARGET_VERIFY_ROUTE_STATS
        memset(&g_target_verify_route_stats, 0, sizeof(g_target_verify_route_stats));
        g_target_verify_route_stats_active = 1;
#endif
        if (ok) ok = target_verify_layer_major_trial(wf, kv_caches, layer_states,
            layer_mmaps, layer_fds, K, anchor, anchor_hidden, candidates, count,
            final_norm_w, pipeline, input, output, block_hidden, rows,
            &sample, &layer_state);
#ifdef TARGET_VERIFY_ROUTE_STATS
        g_target_verify_route_stats_active = 0;
        printf("[target-layer-major] cold_routes=%llu cold_unique=%llu "
               "cold_routed_MiB=%.1f ideal_grouped_MiB=%.1f "
               "potential_reuse=%.2fx\n",
               (unsigned long long)g_target_verify_route_stats.cold_occurrences,
               (unsigned long long)g_target_verify_route_stats.cold_unique,
               g_target_verify_route_stats.cold_routed_bytes / 1048576.0,
               g_target_verify_route_stats.cold_unique_bytes / 1048576.0,
               g_target_verify_route_stats.cold_unique_bytes
                   ? (double)g_target_verify_route_stats.cold_routed_bytes /
                     (double)g_target_verify_route_stats.cold_unique_bytes : 0.0);
#endif
        double max_abs = 0.0;
        int argmax_matches = 0;
        if (ok) {
            const float *batch_logits = [output contents];
            for (int i = 0; i < count; i++) {
                const float *a = reference + (size_t)i * VOCAB_SIZE;
                const float *b = batch_logits + (size_t)i * VOCAB_SIZE;
                if (cpu_argmax(a, VOCAB_SIZE) == cpu_argmax(b, VOCAB_SIZE))
                    argmax_matches++;
                for (int j = 0; j < VOCAB_SIZE; j++) {
                    double diff = fabs((double)a[j] - b[j]);
                    if (diff > max_abs) max_abs = diff;
                }
            }
        }
        int state_exact = ok && target_verify_snapshot_equal(&serial_state, &layer_state);
        int state_close = ok && target_verify_layer_state_report(&serial_state, &layer_state);
        printf("[target-layer-major] correctness block=%d argmax=%d/%d "
               "max_abs=%.6g final_state_exact=%s final_state_close=%s\n", count,
               argmax_matches, count, max_abs, state_exact ? "yes" : "no",
               state_close ? "yes" : "no");
        serve_state_snapshot_free(&serial_state);
        serve_state_snapshot_free(&layer_state);
        ok = ok && argmax_matches == count && max_abs < 0.01 && state_close;
        if (!ok) break;
        double serial_times[5] = {0}, layer_times[5] = {0};
        double transformer_times[5] = {0}, head_times[5] = {0};
        uint64_t unique = 0, hits = 0, misses = 0;
        uint64_t cold_group_loads = 0, cold_group_reuses = 0;
        for (int rep = -1; rep < 5 && ok; rep++) {
            TargetVerifySample serial_sample = {0};
            for (int phase = 0; phase < 2 && ok; phase++) {
                int layer_first = (rep >= 0 && (rep & 1));
                if ((phase == 0) == layer_first)
                    ok = target_verify_layer_major_trial(wf, kv_caches,
                        layer_states, layer_mmaps, layer_fds, K, anchor,
                        anchor_hidden, candidates, count, final_norm_w,
                        pipeline, input, output, block_hidden, rows,
                        &sample, NULL);
                else
                    ok = target_verify_run(wf, kv_caches, layer_states,
                        layer_mmaps, layer_fds, K, hidden, logits, final_norm_w,
                        anchor, anchor_hidden, candidates, count, 1,
                        &serial_sample);
            }
            if (ok && rep >= 0) {
                serial_times[rep] = serial_sample.ms;
                layer_times[rep] = sample.ms;
                transformer_times[rep] = sample.transformer_ms;
                head_times[rep] = sample.lm_head_ms;
                unique += sample.unique_experts;
                hits += sample.hits;
                misses += sample.misses;
                cold_group_loads += sample.cold_group_loads;
                cold_group_reuses += sample.cold_group_reuses;
            }
        }
        if (!ok) break;
        qsort(serial_times, 5, sizeof(double), target_verify_double_cmp);
        qsort(layer_times, 5, sizeof(double), target_verify_double_cmp);
        qsort(transformer_times, 5, sizeof(double), target_verify_double_cmp);
        qsort(head_times, 5, sizeof(double), target_verify_double_cmp);
        double advantage = serial_times[2] / layer_times[2];
        printf("[target-layer-major] block=%d serial_median_ms=%.3f "
               "layer_median_ms=%.3f advantage=%.3f transformer_ms=%.3f "
               "lm_head_ms=%.3f verified_tok_s=%.2f unique_experts_avg=%.1f "
               "hits_avg=%.1f misses_avg=%.1f "
               "cold_group_loads_avg=%.1f cold_group_reuses_avg=%.1f\n",
               count, serial_times[2],
               layer_times[2], advantage, transformer_times[2], head_times[2],
               count * 1000.0 / layer_times[2], unique / 5.0,
               hits / 5.0, misses / 5.0,
               cold_group_loads / 5.0, cold_group_reuses / 5.0);
        fflush(stdout);
        if (count == 4 && advantage < 1.15) {
            printf("[target-layer-major] stop_before_8=yes reason=N4_below_15pct_gain\n");
            break;
        }
    }
    free(block_hidden); free(rows); free(reference);
    return ok ? 0 : 1;
}
