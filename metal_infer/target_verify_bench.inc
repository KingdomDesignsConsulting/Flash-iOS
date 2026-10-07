// Benchmark-only serial teacher forcing. This is not a batched verifier:
// run_all_layers_checked() and the DeltaNet/conv kernels process one token
// at a time. Keep this isolated from serving and persistent state.
static int target_verify_double_cmp(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}


typedef struct {
    double ms;
    double transformer_ms, lm_head_ms;
    uint64_t unique_experts;
    uint64_t hits, misses;
    uint64_t cold_group_loads, cold_group_reuses;
    int matches;
} TargetVerifySample;


static int target_verify_run(WeightFile *wf, KVCache **kv_caches,
                             void **layer_states, void **layer_mmaps,
                             int *layer_fds, int K, float *hidden, float *logits,
                             uint16_t *final_norm_w,
                             const ServeStateSnapshot *anchor,
                             const float *anchor_hidden,
                             const uint32_t candidates[8], int count,
                             int teacher_forced, TargetVerifySample *out) {
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
    int matches = 0;
    for (int i = 0; i < count; i++) {
        apply_final_norm_inplace(hidden, final_norm_w);
        int predicted = lm_head_forward_greedy(wf, hidden, logits);
        uint32_t token = teacher_forced ? candidates[i] : (uint32_t)predicted;
        if ((uint32_t)predicted == candidates[i]) matches++;
        cache_telemetry_note_token();
        embed_lookup(wf, token, hidden);
        if (!run_all_layers_checked(wf, hidden, kv_caches, layer_states,
                                    layer_mmaps, layer_fds, anchor->pos + i, K))
            return 0;
        complete_deferred_experts();
    }
    out->ms = now_ms() - started;
    out->unique_experts = g_cache_telemetry.unique_experts_touched;
    uint64_t hits_after = g_expert_cache ? g_expert_cache->hits :
        (g_malloc_cache ? g_malloc_cache->hits : 0);
    uint64_t misses_after = g_expert_cache ? g_expert_cache->misses :
        (g_malloc_cache ? g_malloc_cache->misses : 0);
    out->hits = hits_after - hits_before;
    out->misses = misses_after - misses_before;
    out->matches = matches;
    return 1;
}


#include "target_verify_batch.inc"
#include "target_verify_grouped.inc"
#include "target_verify_exact_m2_integration.inc"


static int run_target_verify_benchmark(WeightFile *wf, KVCache **kv_caches,
                                       void **layer_states, void **layer_mmaps,
                                       int *layer_fds, int K, float *hidden,
                                       float *logits, uint16_t *final_norm_w,
                                       int batched) {
    const char *prefix = "<|im_start|>system\nTarget verifier timing benchmark."
        "\n<|im_end|>\n<|im_start|>user\nContinue a short sentence."
        "\n<|im_end|>\n<|im_start|>assistant\n";
    PromptTokens *pt = encode_prompt_text_to_tokens(prefix);
    if (!pt || !validate_prompt_tokens(pt, 1, "target verifier benchmark")) return 1;
    if (!context_preflight("target verifier benchmark", 0, pt->count, 8)) return 1;
    g_cache_telemetry_enabled = 1;
    reset_delta_net_state();
    int pos = 0;
    for (int i = 0; i < pt->count; i++) {
        embed_lookup(wf, pt->ids[i], hidden);
        cache_telemetry_note_token();
        if (!run_all_layers_checked(wf, hidden, kv_caches, layer_states,
                                    layer_mmaps, layer_fds, pos, K)) return 1;
        complete_deferred_experts();
        pos++;
    }
    ServeStateSnapshot anchor = {0};
    if (!serve_state_snapshot_capture(&anchor, kv_caches, layer_states, pos)) return 1;
    float *anchor_hidden = malloc(HIDDEN_DIM * sizeof(float));
    if (!anchor_hidden) { serve_state_snapshot_free(&anchor); return 1; }
    memcpy(anchor_hidden, hidden, HIDDEN_DIM * sizeof(float));
    uint32_t candidates[8] = {0};
    TargetVerifySample sample = {0};
    int ok = 1;
    // Generate a deterministic full-acceptance candidate sequence outside timing.
    if (!serve_state_snapshot_restore(&anchor, kv_caches, layer_states)) ok = 0;
    if (ok) memcpy(hidden, anchor_hidden, HIDDEN_DIM * sizeof(float));
    for (int i = 0; ok && i < 8; i++) {
        apply_final_norm_inplace(hidden, final_norm_w);
        candidates[i] = (uint32_t)lm_head_forward_greedy(wf, hidden, logits);
        embed_lookup(wf, candidates[i], hidden);
        ok = run_all_layers_checked(wf, hidden, kv_caches, layer_states,
                                    layer_mmaps, layer_fds, pos + i, K);
        if (ok) complete_deferred_experts();
    }
    if (ok && batched) {
        int result;
#ifdef TARGET_VERIFY_EXACT_M2_INTEGRATION
        if (batched == 1)
            result = target_verify_exact_m2_integration_experiment(wf, kv_caches,
                layer_states, layer_mmaps, layer_fds, K, hidden, logits,
                final_norm_w, &anchor, anchor_hidden, candidates);
        else
#endif
        if (batched == 2)
            result = target_verify_layer_major_experiment(wf, kv_caches, layer_states,
                layer_mmaps, layer_fds, K, hidden, logits, final_norm_w,
                &anchor, anchor_hidden, candidates);
        else
            result = target_verify_batched_experiment(wf, kv_caches, layer_states,
                layer_mmaps, layer_fds, K, hidden, logits, final_norm_w,
                &anchor, anchor_hidden, candidates);
        free(anchor_hidden);
        serve_state_snapshot_free(&anchor);
        free(pt->ids);
        free(pt);
        return result;
    }
    printf("[target-verify-bench] method=serial_teacher_forcing true_batch=no "
           "prefix_tokens=%d repetitions=5 warmups=1 reset_ms_excluded=yes\n", pos);
    printf("[target-verify-bench] GPU_moe=%d oproj_v3=%d tiny_fast=%d "
           "cmd12=%d cmd12_full=%d K=%d\n",
           g_gpu_resident_moe_enabled, g_oproj_v3_enabled,
           g_tiny_matvec_fast_enabled, g_cmd12_chain_enabled,
           g_cmd12_full_chain_enabled, K);
    double baseline_one_ms = 0.0;
    const int sizes[4] = {1, 2, 4, 8};
    for (int block = 0; ok && block < 4; block++) {
        double times[2][5] = {{0}};
        uint64_t unique_sum = 0, hit_sum = 0, miss_sum = 0;
        int matches = 0;
        for (int rep = -1; rep < 5 && ok; rep++) {
            for (int phase = 0; phase < 2 && ok; phase++) {
                int teacher_forced = (phase + (rep < 0 ? 0 : rep)) & 1;
                ok = target_verify_run(wf, kv_caches, layer_states, layer_mmaps,
                    layer_fds, K, hidden, logits, final_norm_w, &anchor,
                    anchor_hidden, candidates, sizes[block], teacher_forced, &sample);
                if (ok && rep >= 0) {
                    times[teacher_forced][rep] = sample.ms;
                    if (teacher_forced) {
                        unique_sum += sample.unique_experts;
                        hit_sum += sample.hits;
                        miss_sum += sample.misses;
                        matches += sample.matches;
                    }
                }
            }
        }
        if (!ok) break;
        qsort(times[0], 5, sizeof(double), target_verify_double_cmp);
        qsort(times[1], 5, sizeof(double), target_verify_double_cmp);
        if (block == 0) baseline_one_ms = times[0][2];
        double sequential = sizes[block] * baseline_one_ms;
        printf("[target-verify-bench] block=%d verify_median_ms=%.3f "
               "verify_min_ms=%.3f verify_max_ms=%.3f greedy_median_ms=%.3f "
               "verified_tok_s=%.2f sequential_equiv_ms=%.3f advantage=%.3f "
               "unique_experts_avg=%.1f hits_avg=%.1f misses_avg=%.1f "
               "candidate_matches=%d/%d\n",
               sizes[block], times[1][2], times[1][0], times[1][4], times[0][2],
               times[1][2] > 0 ? sizes[block] * 1000.0 / times[1][2] : 0.0,
               sequential, times[1][2] > 0 ? sequential / times[1][2] : 0.0,
               unique_sum / 5.0, hit_sum / 5.0, miss_sum / 5.0,
               matches, 5 * sizes[block]);
        fflush(stdout);
    }
    free(anchor_hidden);
    serve_state_snapshot_free(&anchor);
    free(pt->ids);
    free(pt);
    return ok ? 0 : 1;
}