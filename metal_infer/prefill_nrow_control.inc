// Benchmark-only N-row activation control. This carries a contiguous hidden
// slab through every layer but deliberately uses the existing one-row layer
// implementation. It establishes a correctness baseline before grouped MoE
// and chunked recurrence are attached. Never included in production builds.
static double prefill_nrow_maxdiff(const float *a, const float *b, size_t n) {
    double result = 0.0;
    for (size_t i = 0; i < n; i++) {
        if (!isfinite(a[i]) || !isfinite(b[i])) return INFINITY;
        double d = fabs((double)a[i] - b[i]);
        if (d > result) result = d;
    }
    return result;
}

static int prefill_nrow_decode_step(WeightFile *wf, KVCache **kv_caches,
    void **layer_states, void **layer_mmaps, int *layer_fds, int K,
    uint16_t *final_norm_w, float *hidden, float *logits, uint32_t token,
    int pos, uint32_t *next) {
    embed_lookup(wf, token, hidden);
    if (!run_all_layers_checked(wf, hidden, kv_caches, layer_states,
                                layer_mmaps, layer_fds, pos, K)) return 0;
    complete_deferred_experts();
    apply_final_norm_inplace(hidden, final_norm_w);
    lm_head_forward(wf, hidden, logits);
    *next = (uint32_t)cpu_argmax(logits, VOCAB_SIZE);
    return 1;
}

static int run_prefill_nrow_control(WeightFile *wf, PromptTokens *pt,
    KVCache **kv_caches, void **layer_states, void **layer_mmaps,
    int *layer_fds, int K, uint16_t *final_norm_w, int grouped) {
    const int n = PREFILL_NROW_ROWS;
    const int anchor_pos = pt && pt->count >= 48 ? 32 : 0;
    if (!pt || pt->count < n || !g_metal) {
        fprintf(stderr, "[prefill-nrow] need enough prompt tokens for the configured N-row slab and Metal\n");
        return 1;
    }
    size_t slab_bytes = (size_t)n * HIDDEN_DIM * sizeof(float);
    float *slab = malloc(slab_bytes);
    float *scalar_hidden = malloc(HIDDEN_DIM * sizeof(float));
    float *nrow_hidden = malloc(HIDDEN_DIM * sizeof(float));
    float *scalar_logits = malloc(VOCAB_SIZE * sizeof(float));
    float *nrow_logits = malloc(VOCAB_SIZE * sizeof(float));
    PrefillNRowCapture *capture = grouped ? calloc(1, sizeof(*capture)) : NULL;
    PrefillNRowGrouped pipes = {0};
    int saved_prefetch = g_expert_prefetch_enabled;
    if (grouped) g_expert_prefetch_enabled = 0;
    ServeStateSnapshot anchor = {0}, scalar_state = {0}, nrow_state = {0};
    int ok = slab && scalar_hidden && nrow_hidden && scalar_logits && nrow_logits &&
        (!grouped || (capture && prefill_nrow_grouped_init(&pipes)));
    if (ok) {
        for (int pos = 0; pos < anchor_pos; pos++) {
            embed_lookup(wf, pt->ids[pos], scalar_hidden);
            if (!run_all_layers_checked(wf, scalar_hidden, kv_caches,
                                        layer_states, layer_mmaps, layer_fds,
                                        pos, K)) { ok = 0; break; }
            complete_deferred_experts();
        }
    }
    if (ok) ok = serve_state_snapshot_capture(&anchor, kv_caches,
                                               layer_states, anchor_pos);
    if (!ok) goto done;

    double scalar_start = now_ms();
    if (!serve_state_snapshot_restore(&anchor, kv_caches, layer_states)) { ok = 0; goto done; }
    if (g_expert_prefetch_enabled) expert_prefetch_history_reset();
    for (int row = 0; row < n; row++) {
        embed_lookup(wf, pt->ids[anchor_pos + row], scalar_hidden);
        if (!run_all_layers_checked(wf, scalar_hidden, kv_caches, layer_states,
                                    layer_mmaps, layer_fds, anchor_pos + row, K)) { ok = 0; break; }
        complete_deferred_experts();
    }
    double scalar_ms = now_ms() - scalar_start;
    if (!ok || !serve_state_snapshot_capture(&scalar_state, kv_caches,
                                              layer_states, anchor_pos + n)) { ok = 0; goto done; }

    double nrow_start = now_ms();
    if (!serve_state_snapshot_restore(&anchor, kv_caches, layer_states)) { ok = 0; goto done; }
    if (g_expert_prefetch_enabled) expert_prefetch_history_reset();
    for (int row = 0; row < n; row++)
        embed_lookup(wf, pt->ids[anchor_pos + row], slab + (size_t)row * HIDDEN_DIM);
    for (int layer = 0; layer < NUM_LAYERS && ok; layer++) {
        int full = ((layer + 1) % FULL_ATTN_INTERVAL == 0);
        double full_started = 0.0;
        if (grouped) {
            if (!full) {
                ok = prefill_nrow_linear_layer(&pipes, wf, layer, slab);
                if (!ok) break;
                g_prefill_nrow_linear_output = (float *)[pipes.attn_output contents];
            } else {
                full_started = now_ms();
                ok = prefill_nrow_full_qkv_layer(&pipes, layer, slab);
                if (!ok) break;
                g_prefill_nrow_full_qproj = (float *)[pipes.full_qproj_rows contents];
                g_prefill_nrow_full_k = (float *)[pipes.full_k_rows contents];
                g_prefill_nrow_full_v = (float *)[pipes.full_v_rows contents];
            }
            capture->count = n;
            g_prefill_nrow_capture = capture;
        }
        double linear_post_started = (grouped && !full) ? now_ms() : 0.0;
        for (int row = 0; row < n; row++) {
            if (grouped) capture->row = row;
            g_forward_error = 0;
            fused_layer_forward(wf, layer, slab + (size_t)row * HIDDEN_DIM,
                full ? kv_caches[layer] : NULL,
                full ? NULL : layer_states[layer], anchor_pos + row,
                layer_mmaps[layer] != MAP_FAILED ? layer_mmaps[layer] : NULL,
                K, layer_fds[layer]);
            if (g_forward_error) { discard_deferred_experts(); ok = 0; break; }
            if (!grouped) complete_deferred_experts();
        }
        if (ok && grouped && !full)
            pipes.linear_post_ms += now_ms() - linear_post_started;
        g_prefill_nrow_capture = NULL;
        g_prefill_nrow_linear_output = NULL;
        g_prefill_nrow_full_qproj = NULL;
        g_prefill_nrow_full_k = NULL;
        g_prefill_nrow_full_v = NULL;
        if (ok && grouped && full) pipes.full_attn_ms += now_ms() - full_started;
        if (ok && grouped)
            ok = prefill_nrow_grouped_layer(&pipes, capture, layer,
                                            layer_fds[layer],
                                            layer_mmaps[layer] != MAP_FAILED
                                                ? layer_mmaps[layer] : NULL,
                                            slab);
    }
    double nrow_ms = now_ms() - nrow_start;
    if (!ok || !serve_state_snapshot_capture(&nrow_state, kv_caches,
                                              layer_states, anchor_pos + n)) { ok = 0; goto done; }
    memcpy(nrow_hidden, slab + (size_t)(n - 1) * HIDDEN_DIM,
           HIDDEN_DIM * sizeof(float));
    double hidden_error = prefill_nrow_maxdiff(scalar_hidden, nrow_hidden, HIDDEN_DIM);
    int state_equal = target_verify_layer_state_report(&scalar_state, &nrow_state);
    apply_final_norm_inplace(scalar_hidden, final_norm_w);
    apply_final_norm_inplace(nrow_hidden, final_norm_w);
    lm_head_forward(wf, scalar_hidden, scalar_logits);
    lm_head_forward(wf, nrow_hidden, nrow_logits);
    double logits_error = prefill_nrow_maxdiff(scalar_logits, nrow_logits, VOCAB_SIZE);
    uint32_t token_a = (uint32_t)cpu_argmax(scalar_logits, VOCAB_SIZE);
    uint32_t token_b = (uint32_t)cpu_argmax(nrow_logits, VOCAB_SIZE);
    printf("[prefill-nrow-control] start=%d rows=%d scalar_ms=%.3f layer_major_ms=%.3f "
           "hidden_max=%.8g logits_max=%.8g next=%u/%u state_equal=%d "
           "slab_bytes=%zu\n", anchor_pos, n, scalar_ms, nrow_ms, hidden_error,
           logits_error, token_a, token_b, state_equal, slab_bytes);
    fflush(stdout);
    if (grouped) {
        printf("[prefill-nrow-grouped] groups=%llu repeated=%llu hot=%llu cold=%llu "
               "cache_hits=%llu cache_misses=%llu gpu_waits=%llu "
               "grouping_ms=%.3f linear_ms=%.3f linear_post_ms=%.3f "
               "full_qkv_ms=%.3f full_attn_ms=%.3f grouped_expert_ms=%.3f "
               "expert_stage_ms=%.3f expert_cache_ms=%.3f shared_ms=%.3f combine_ms=%.3f "
#ifdef FLASH_PREFILL_NROW_EXPERT_PHASE_TIMING
               "expert_gate_up_gpu_ms=%.3f expert_swiglu_gpu_ms=%.3f expert_down_gpu_ms=%.3f "
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_BIT_TIMING
               "expert_down_q4_gpu_ms=%.3f expert_down_q2_gpu_ms=%.3f "
               "down_q4_groups=%llu down_q2_groups=%llu "
               "down_q4_assignments=%llu down_q2_assignments=%llu"
#endif
               "\n",
               (unsigned long long)pipes.groups,
               (unsigned long long)pipes.repeated,
               (unsigned long long)pipes.hot,
               (unsigned long long)pipes.cold,
               (unsigned long long)pipes.cache_hits,
               (unsigned long long)pipes.cache_misses,
               (unsigned long long)pipes.gpu_waits,
               pipes.grouping_ms, pipes.linear_ms, pipes.linear_post_ms,
               pipes.full_qkv_ms, pipes.full_attn_ms, pipes.expert_ms,
               pipes.expert_stage_ms, pipes.expert_cache_ms,
               pipes.shared_ms, pipes.combine_ms
#ifdef FLASH_PREFILL_NROW_EXPERT_PHASE_TIMING
               , pipes.expert_gate_up_gpu_ms, pipes.expert_swiglu_gpu_ms,
               pipes.expert_down_gpu_ms
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_BIT_TIMING
               , pipes.expert_down_q4_gpu_ms, pipes.expert_down_q2_gpu_ms,
               (unsigned long long)pipes.down_q4_groups,
               (unsigned long long)pipes.down_q2_groups,
               (unsigned long long)pipes.down_q4_assignments,
               (unsigned long long)pipes.down_q2_assignments
#endif
               );
    }
    if (!isfinite(hidden_error) || !isfinite(logits_error) ||
        hidden_error > 1e-3 || logits_error > 1e-2 ||
        token_a != token_b || !state_equal) { ok = 0; goto done; }

    uint32_t seq_a[4], seq_b[4];
    if (!serve_state_snapshot_restore(&scalar_state, kv_caches, layer_states)) { ok = 0; goto done; }
    for (int i = 0; i < 4 && ok; i++) {
        seq_a[i] = token_a;
        ok = prefill_nrow_decode_step(wf, kv_caches, layer_states, layer_mmaps,
            layer_fds, K, final_norm_w, scalar_hidden, scalar_logits,
            token_a, anchor_pos + n + i, &token_a);
    }
    if (!ok || !serve_state_snapshot_restore(&nrow_state, kv_caches, layer_states)) {
        ok = 0; goto done;
    }
    for (int i = 0; i < 4 && ok; i++) {
        seq_b[i] = token_b;
        ok = prefill_nrow_decode_step(wf, kv_caches, layer_states, layer_mmaps,
            layer_fds, K, final_norm_w, nrow_hidden, nrow_logits,
            token_b, anchor_pos + n + i, &token_b);
    }
    if (!ok) goto done;
    for (int i = 0; i < 4; i++) if (seq_a[i] != seq_b[i]) ok = 0;
    printf("[prefill-nrow-control] decode_match=%d tokens=%u,%u,%u,%u\n",
           ok, seq_a[0], seq_a[1], seq_a[2], seq_a[3]);
done:
    g_prefill_nrow_capture = NULL;
    g_prefill_nrow_linear_output = NULL;
    g_prefill_nrow_full_qproj = NULL;
    g_prefill_nrow_full_k = NULL;
    g_prefill_nrow_full_v = NULL;
    g_expert_prefetch_enabled = saved_prefetch;
    serve_state_snapshot_free(&anchor);
    serve_state_snapshot_free(&scalar_state);
    serve_state_snapshot_free(&nrow_state);
    free(slab); free(scalar_hidden); free(nrow_hidden);
    free(scalar_logits); free(nrow_logits);
    free(capture);
    if (!ok) fprintf(stderr, "[prefill-nrow-control] FAILED\n");
    return ok ? 0 : 1;
}

// A full-prompt, uncached comparison. Both arms start from the same empty
// state. This intentionally keeps the first integrated grouped scheduler's
// per-expert waits; its measurements must include that cost.
static int run_prefill_nrow_fullbench(WeightFile *wf, PromptTokens *pt,
    KVCache **kv_caches, void **layer_states, void **layer_mmaps,
    int *layer_fds, int K, uint16_t *final_norm_w) {
    const int n = PREFILL_NROW_ROWS;
#ifdef FLASH_PREFILL_NROW_1K_1024
    const int count = 1024;
#else
    const int count = 1008;
#endif
    if (!pt || pt->count < count || !g_metal || (count % n) != 0) {
        fprintf(stderr, "[prefill-nrow-1k] need %d prompt tokens divisible by N=%d and Metal\n", count, n);
        return 1;
    }
    float *slab = malloc((size_t)n * HIDDEN_DIM * sizeof(float));
    float *scalar_hidden = malloc(HIDDEN_DIM * sizeof(float));
    float *nrow_hidden = malloc(HIDDEN_DIM * sizeof(float));
    float *scalar_logits = malloc(VOCAB_SIZE * sizeof(float));
    float *nrow_logits = malloc(VOCAB_SIZE * sizeof(float));
    PrefillNRowCapture *capture = calloc(1, sizeof(*capture));
    PrefillNRowGrouped pipes = {0};
    ServeStateSnapshot empty = {0}, scalar_state = {0}, nrow_state = {0};
    int saved_prefetch = g_expert_prefetch_enabled;
    g_expert_prefetch_enabled = 0;
    int ok = slab && scalar_hidden && nrow_hidden && scalar_logits &&
        nrow_logits && capture && prefill_nrow_grouped_init(&pipes) &&
        serve_state_snapshot_capture(&empty, kv_caches, layer_states, 0);
    if (!ok) goto done;
    double scalar_started = now_ms();
    for (int pos = 0; pos < count && ok; pos++) {
        embed_lookup(wf, pt->ids[pos], scalar_hidden);
        ok = run_all_layers_checked(wf, scalar_hidden, kv_caches,
            layer_states, layer_mmaps, layer_fds, pos, K);
        if (ok) complete_deferred_experts();
    }
    double scalar_ms = now_ms() - scalar_started;
    if (!ok || !serve_state_snapshot_capture(&scalar_state, kv_caches,
        layer_states, count)) { ok = 0; goto done; }
    if (!serve_state_snapshot_restore(&empty, kv_caches, layer_states)) {
        ok = 0; goto done;
    }
    double nrow_started = now_ms();
    for (int base = 0; base < count && ok; base += n) {
        for (int row = 0; row < n; row++)
            embed_lookup(wf, pt->ids[base + row],
                slab + (size_t)row * HIDDEN_DIM);
        for (int layer = 0; layer < NUM_LAYERS && ok; layer++) {
            int full = ((layer + 1) % FULL_ATTN_INTERVAL == 0);
            double full_started = 0.0;
            if (!full) {
                ok = prefill_nrow_linear_layer(&pipes, wf, layer, slab);
                if (!ok) break;
                g_prefill_nrow_linear_output = (float *)[pipes.attn_output contents];
            } else {
                full_started = now_ms();
                ok = prefill_nrow_full_qkv_layer(&pipes, layer, slab);
                if (!ok) break;
                g_prefill_nrow_full_qproj = (float *)[pipes.full_qproj_rows contents];
                g_prefill_nrow_full_k = (float *)[pipes.full_k_rows contents];
                g_prefill_nrow_full_v = (float *)[pipes.full_v_rows contents];
            }
            capture->count = n;
            g_prefill_nrow_capture = capture;
            double linear_post_started = !full ? now_ms() : 0.0;
            for (int row = 0; row < n; row++) {
                capture->row = row;
                g_forward_error = 0;
                fused_layer_forward(wf, layer,
                    slab + (size_t)row * HIDDEN_DIM,
                    full ? kv_caches[layer] : NULL,
                    full ? NULL : layer_states[layer], base + row,
                    layer_mmaps[layer] != MAP_FAILED ? layer_mmaps[layer] : NULL,
                    K, layer_fds[layer]);
                if (g_forward_error) {
                    discard_deferred_experts(); ok = 0; break;
                }
            }
            if (ok && !full)
                pipes.linear_post_ms += now_ms() - linear_post_started;
            g_prefill_nrow_capture = NULL;
            g_prefill_nrow_linear_output = NULL;
            g_prefill_nrow_full_qproj = NULL;
            g_prefill_nrow_full_k = NULL;
            g_prefill_nrow_full_v = NULL;
            if (ok && full) pipes.full_attn_ms += now_ms() - full_started;
            if (ok) ok = prefill_nrow_grouped_layer(&pipes, capture,
                layer, layer_fds[layer],
                layer_mmaps[layer] != MAP_FAILED ? layer_mmaps[layer] : NULL,
                slab);
        }
    }
    double nrow_ms = now_ms() - nrow_started;
    if (!ok || !serve_state_snapshot_capture(&nrow_state, kv_caches,
        layer_states, count)) { ok = 0; goto done; }
    memcpy(nrow_hidden, slab + (size_t)(n - 1) * HIDDEN_DIM,
        HIDDEN_DIM * sizeof(float));
    double hidden_diff = prefill_nrow_maxdiff(scalar_hidden, nrow_hidden,
        HIDDEN_DIM);
    int state_equal = target_verify_layer_state_report(&scalar_state,
        &nrow_state);
    apply_final_norm_inplace(scalar_hidden, final_norm_w);
    apply_final_norm_inplace(nrow_hidden, final_norm_w);
    lm_head_forward(wf, scalar_hidden, scalar_logits);
    lm_head_forward(wf, nrow_hidden, nrow_logits);
    double logits_diff = prefill_nrow_maxdiff(scalar_logits, nrow_logits,
        VOCAB_SIZE);
    uint32_t next_a = (uint32_t)cpu_argmax(scalar_logits, VOCAB_SIZE);
    uint32_t next_b = (uint32_t)cpu_argmax(nrow_logits, VOCAB_SIZE);
    printf("[prefill-nrow-1k] tokens=%d scalar_ms=%.3f nrow_ms=%.3f "
           "scalar_tps=%.3f nrow_tps=%.3f ratio=%.4f hidden_max=%.8g "
           "logits_max=%.8g next=%u/%u state_equal=%d\n",
           count, scalar_ms, nrow_ms, count * 1000.0 / scalar_ms,
           count * 1000.0 / nrow_ms, scalar_ms / nrow_ms, hidden_diff,
           logits_diff, next_a, next_b, state_equal);
    printf("[prefill-nrow-1k] groups=%llu repeated=%llu hot=%llu cold=%llu "
           "cache_hits=%llu cache_misses=%llu gpu_waits=%llu "
           "grouping_ms=%.3f linear_ms=%.3f linear_post_ms=%.3f "
           "full_qkv_ms=%.3f full_attn_ms=%.3f expert_ms=%.3f "
           "expert_stage_ms=%.3f expert_cache_ms=%.3f shared_ms=%.3f combine_ms=%.3f "
#ifdef FLASH_PREFILL_NROW_EXPERT_PHASE_TIMING
           "expert_gate_up_gpu_ms=%.3f expert_swiglu_gpu_ms=%.3f expert_down_gpu_ms=%.3f "
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_BIT_TIMING
           "expert_down_q4_gpu_ms=%.3f expert_down_q2_gpu_ms=%.3f "
           "down_q4_groups=%llu down_q2_groups=%llu "
           "down_q4_assignments=%llu down_q2_assignments=%llu"
#endif
           "\n",
           (unsigned long long)pipes.groups,
           (unsigned long long)pipes.repeated,
           (unsigned long long)pipes.hot,
           (unsigned long long)pipes.cold,
           (unsigned long long)pipes.cache_hits,
           (unsigned long long)pipes.cache_misses,
           (unsigned long long)pipes.gpu_waits,
           pipes.grouping_ms, pipes.linear_ms, pipes.linear_post_ms,
           pipes.full_qkv_ms, pipes.full_attn_ms, pipes.expert_ms,
           pipes.expert_stage_ms, pipes.expert_cache_ms,
           pipes.shared_ms, pipes.combine_ms
#ifdef FLASH_PREFILL_NROW_EXPERT_PHASE_TIMING
           , pipes.expert_gate_up_gpu_ms, pipes.expert_swiglu_gpu_ms,
           pipes.expert_down_gpu_ms
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_BIT_TIMING
           , pipes.expert_down_q4_gpu_ms, pipes.expert_down_q2_gpu_ms,
           (unsigned long long)pipes.down_q4_groups,
           (unsigned long long)pipes.down_q2_groups,
           (unsigned long long)pipes.down_q4_assignments,
           (unsigned long long)pipes.down_q2_assignments
#endif
           );
    fflush(stdout);
    if (!state_equal || next_a != next_b || hidden_diff > 1e-3 ||
        logits_diff > 1e-2) ok = 0;
done:
    g_prefill_nrow_capture = NULL;
    g_prefill_nrow_linear_output = NULL;
    g_prefill_nrow_full_qproj = NULL;
    g_prefill_nrow_full_k = NULL;
    g_prefill_nrow_full_v = NULL;
    g_expert_prefetch_enabled = saved_prefetch;
    serve_state_snapshot_free(&empty);
    serve_state_snapshot_free(&scalar_state);
    serve_state_snapshot_free(&nrow_state);
    free(slab); free(scalar_hidden); free(nrow_hidden);
    free(scalar_logits); free(nrow_logits); free(capture);
    if (!ok) fprintf(stderr, "[prefill-nrow-1k] FAILED\n");
    return ok ? 0 : 1;
}
