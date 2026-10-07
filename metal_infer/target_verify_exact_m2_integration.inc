#ifdef TARGET_VERIFY_EXACT_M2_INTEGRATION
// Exact two-candidate target-verifier integration.
//
// Transformer/state production remains serial and bit-identical. The original
// two-full-snapshot transaction remains the validation oracle. The compact
// transaction retains only row 0's changed state; row 1 stays live on full
// acceptance. Both evaluate two logits rows with the exact Q4 M2 affine kernel.
// Accepted candidates are never replayed. A caller advances any fallback token.


typedef struct {
    int accepted;
    uint32_t predicted[2];
    uint32_t fallback_token;
    int has_fallback;
    int committed_pos;
} TargetVerifyExactM2PairResult;

// A draft source is supplied by the caller. No draft model or serving policy is
// selected here; returning zero disables speculation for that transaction.
typedef int (*TargetVerifyDraftProvider)(void *context, int pos,
                                          uint32_t candidates[2]);

static int target_verify_get_draft_pair(TargetVerifyDraftProvider provider,
    void *context, int enabled, int pos, uint32_t candidates[2]) {
    return enabled && provider && candidates && provider(context, pos, candidates);
}

typedef struct { uint32_t tokens[2]; int expected_pos; } TargetVerifyFixedDraft;
static int target_verify_fixed_draft(void *context, int pos, uint32_t candidates[2]) {
    TargetVerifyFixedDraft *draft = (TargetVerifyFixedDraft *)context;
    if (!draft || pos != draft->expected_pos) return 0;
    memcpy(candidates, draft->tokens, sizeof(draft->tokens));
    return 1;
}

// One retained row is sufficient: row 1 stays live on full acceptance.
// The caller's anchor snapshot remains the rollback oracle for row-0 rejection.
typedef struct {
    int valid, pos, kv_len[MAX_LAYERS];
    float *k_append[MAX_LAYERS], *v_append[MAX_LAYERS];
    float *la_conv[MAX_LAYERS], *la_ssm[MAX_LAYERS];
    void *gpu_delta[48], *gpu_conv[48];
    float *hidden;
    size_t bytes, metal_copy_bytes, metal_restore_bytes;
} TargetVerifyCompactBank;

static void target_verify_compact_free(TargetVerifyCompactBank *bank) {
    if (!bank) return;
    for (int i = 0; i < NUM_LAYERS; i++) {
        free(bank->k_append[i]); free(bank->v_append[i]);
        free(bank->la_conv[i]); free(bank->la_ssm[i]);
    }
    for (int i = 0; i < 48; i++) {
        free(bank->gpu_delta[i]); free(bank->gpu_conv[i]);
    }
    free(bank->hidden);
    memset(bank, 0, sizeof(*bank));
}

static int target_verify_compact_capture(TargetVerifyCompactBank *bank,
    const ServeStateSnapshot *anchor, KVCache **kv_caches, void **layer_states,
    const float *hidden, int pos) {
    if (!bank || !anchor || !anchor->valid || !kv_caches || !layer_states ||
        !hidden || pos != anchor->pos + 1) return 0;
    target_verify_compact_free(bank);
    const size_t kv_bytes = (size_t)NUM_KV_HEADS * HEAD_DIM * sizeof(float);
    const size_t conv_bytes = (CONV_KERNEL_SIZE - 1) * LINEAR_CONV_DIM * sizeof(float);
    const size_t ssm_bytes = LINEAR_NUM_V_HEADS * LINEAR_VALUE_DIM * LINEAR_KEY_DIM * sizeof(float);
    for (int i = 0; i < NUM_LAYERS; i++) {
        if (kv_caches[i]) {
            int old = anchor->kv_len[i], len = kv_caches[i]->len;
            if (old < 0 || len != old + 1 || len > g_kv_seq_len) goto fail;
            bank->kv_len[i] = len;
            bank->k_append[i] = malloc(kv_bytes);
            bank->v_append[i] = malloc(kv_bytes);
            if (!bank->k_append[i] || !bank->v_append[i]) goto fail;
            memcpy(bank->k_append[i], kv_caches[i]->k_cache + (size_t)old * NUM_KV_HEADS * HEAD_DIM, kv_bytes);
            memcpy(bank->v_append[i], kv_caches[i]->v_cache + (size_t)old * NUM_KV_HEADS * HEAD_DIM, kv_bytes);
            bank->bytes += 2 * kv_bytes;
            if (g_metal && old < GPU_KV_SEQ) {
                int fa_idx = (i + 1) / FULL_ATTN_INTERVAL - 1;
                if (fa_idx >= 0 && fa_idx < g_cfg.num_full_attn_layers)
                    bank->metal_restore_bytes += 2 * kv_bytes;
            }
        }
        if (layer_states[i]) {
            LinearAttnState *la = (LinearAttnState *)layer_states[i];
            bank->la_conv[i] = malloc(conv_bytes);
            bank->la_ssm[i] = malloc(ssm_bytes);
            if (!bank->la_conv[i] || !bank->la_ssm[i]) goto fail;
            memcpy(bank->la_conv[i], la->conv_state, conv_bytes);
            memcpy(bank->la_ssm[i], la->ssm_state, ssm_bytes);
            bank->bytes += conv_bytes + ssm_bytes;
        }
    }
    if (snapshot_uses_gpu_linear_state()) {
        for (int i = 0; i < g_cfg.num_linear_layers && i < 48; i++) {
            if (g_metal->buf_delta_state[i]) {
                size_t sz = 64ULL * 128 * 128 * sizeof(float);
                bank->gpu_delta[i] = malloc(sz);
                if (!bank->gpu_delta[i]) goto fail;
                memcpy(bank->gpu_delta[i], [g_metal->buf_delta_state[i] contents], sz);
                bank->bytes += sz; bank->metal_copy_bytes += sz;
            }
            if (g_metal->buf_conv_state[i]) {
                size_t sz = 3ULL * 12288 * sizeof(float);
                bank->gpu_conv[i] = malloc(sz);
                if (!bank->gpu_conv[i]) goto fail;
                memcpy(bank->gpu_conv[i], [g_metal->buf_conv_state[i] contents], sz);
                bank->bytes += sz; bank->metal_copy_bytes += sz;
            }
        }
    }
    bank->hidden = malloc((size_t)HIDDEN_DIM * sizeof(float));
    if (!bank->hidden) goto fail;
    memcpy(bank->hidden, hidden, (size_t)HIDDEN_DIM * sizeof(float));
    bank->bytes += (size_t)HIDDEN_DIM * sizeof(float) + sizeof(*bank);
    bank->metal_restore_bytes += bank->metal_copy_bytes;
    bank->pos = pos; bank->valid = 1;
    return 1;
fail:
    target_verify_compact_free(bank);
    return 0;
}

static int target_verify_compact_restore(const TargetVerifyCompactBank *bank,
    const ServeStateSnapshot *anchor, KVCache **kv_caches, void **layer_states,
    float *hidden) {
    if (!bank || !bank->valid || !anchor || !anchor->valid ||
        bank->pos != anchor->pos + 1 || !hidden || !bank->hidden) return 0;
    const size_t kv_dim = (size_t)NUM_KV_HEADS * HEAD_DIM;
    const size_t kv_bytes = kv_dim * sizeof(float);
    const size_t conv_bytes = (CONV_KERNEL_SIZE - 1) * LINEAR_CONV_DIM * sizeof(float);
    const size_t ssm_bytes = LINEAR_NUM_V_HEADS * LINEAR_VALUE_DIM * LINEAR_KEY_DIM * sizeof(float);
    // Validate all sections before mutating any state.
    for (int i = 0; i < NUM_LAYERS; i++) {
        if (kv_caches[i] && (bank->kv_len[i] != anchor->kv_len[i] + 1 ||
            !bank->k_append[i] || !bank->v_append[i])) return 0;
        if (layer_states[i] && (!bank->la_conv[i] || !bank->la_ssm[i])) return 0;
    }
    if (snapshot_uses_gpu_linear_state()) {
        for (int i = 0; i < g_cfg.num_linear_layers && i < 48; i++) {
            if (g_metal->buf_delta_state[i] && !bank->gpu_delta[i]) return 0;
            if (g_metal->buf_conv_state[i] && !bank->gpu_conv[i]) return 0;
        }
    }
    for (int i = 0; i < NUM_LAYERS; i++) {
        if (kv_caches[i]) {
            size_t offset = (size_t)anchor->kv_len[i] * kv_dim;
            memcpy(kv_caches[i]->k_cache + offset, bank->k_append[i], kv_bytes);
            memcpy(kv_caches[i]->v_cache + offset, bank->v_append[i], kv_bytes);
            kv_caches[i]->len = bank->kv_len[i];
            if (g_metal && anchor->kv_len[i] < GPU_KV_SEQ) {
                int fa_idx = (i + 1) / FULL_ATTN_INTERVAL - 1;
                if (fa_idx >= 0 && fa_idx < g_cfg.num_full_attn_layers) {
                    memcpy((float *)[g_metal->buf_kv_k[fa_idx] contents] + offset, bank->k_append[i], kv_bytes);
                    memcpy((float *)[g_metal->buf_kv_v[fa_idx] contents] + offset, bank->v_append[i], kv_bytes);
                }
            }
        }
        if (layer_states[i]) {
            LinearAttnState *la = (LinearAttnState *)layer_states[i];
            memcpy(la->conv_state, bank->la_conv[i], conv_bytes);
            memcpy(la->ssm_state, bank->la_ssm[i], ssm_bytes);
        }
    }
    if (snapshot_uses_gpu_linear_state()) {
        for (int i = 0; i < g_cfg.num_linear_layers && i < 48; i++) {
            if (bank->gpu_delta[i]) memcpy([g_metal->buf_delta_state[i] contents], bank->gpu_delta[i], 64ULL * 128 * 128 * sizeof(float));
            if (bank->gpu_conv[i]) memcpy([g_metal->buf_conv_state[i] contents], bank->gpu_conv[i], 3ULL * 12288 * sizeof(float));
        }
    }
    memcpy(hidden, bank->hidden, (size_t)HIDDEN_DIM * sizeof(float));
    return 1;
}


static id<MTLComputePipelineState> target_verify_exact_m2_pipeline(MetalCtx *ctx) {
    if (!ctx || !ctx->device) return nil;
    NSString *filename = @"target_verify_affine_m2.metal";
    NSString *executable_dir = infer_executable_directory();
    NSMutableArray<NSString *> *paths = [NSMutableArray array];
    if (executable_dir.length > 0) {
        [paths addObject:[executable_dir
            stringByAppendingPathComponent:[@"prefill_probe"
                stringByAppendingPathComponent:filename]]];
        NSString *repo_root = executable_dir;
        for (int i = 0; i < 3 && repo_root.length > 1; i++)
            repo_root = [repo_root stringByDeletingLastPathComponent];
        [paths addObject:[repo_root
            stringByAppendingPathComponent:[@"metal_infer/prefill_probe"
                stringByAppendingPathComponent:filename]]];
    }
    [paths addObject:[@"prefill_probe" stringByAppendingPathComponent:filename]];
    [paths addObject:[@"metal_infer/prefill_probe" stringByAppendingPathComponent:filename]];


    NSString *source = nil;
    NSString *source_path = nil;
    for (NSString *candidate in paths) {
        source = [NSString stringWithContentsOfFile:candidate
            encoding:NSUTF8StringEncoding error:NULL];
        if (source) { source_path = candidate; break; }
    }
    if (!source) {
        fprintf(stderr, "[target-exact-m2] ERROR: cannot find %s\n",
                filename.UTF8String);
        return nil;
    }


    NSError *error = nil;
    id<MTLLibrary> library = [ctx->device newLibraryWithSource:source
        options:nil error:&error];
    if (!library) {
        fprintf(stderr, "[target-exact-m2] ERROR: Metal compile failed (%s): %s\n",
                source_path.UTF8String,
                error.localizedDescription.UTF8String ?: "unknown error");
        return nil;
    }
    id<MTLFunction> fn = [library newFunctionWithName:@"dense_affine_q4_m2"];
    if (!fn) {
        fprintf(stderr, "[target-exact-m2] ERROR: dense_affine_q4_m2 missing\n");
        return nil;
    }
    id<MTLComputePipelineState> pipeline =
        [ctx->device newComputePipelineStateWithFunction:fn error:&error];
    if (!pipeline) {
        fprintf(stderr, "[target-exact-m2] ERROR: pipeline creation failed: %s\n",
                error.localizedDescription.UTF8String ?: "unknown error");
        return nil;
    }
    printf("[target-exact-m2] shader source=%s\n", source_path.UTF8String);
    return pipeline;
}


static int target_verify_exact_m2_lm_pair(WeightFile *wf,
    id<MTLComputePipelineState> pipeline, id<MTLBuffer> input,
    id<MTLBuffer> output, const float *row0, const float *row1,
    float *out_logits) {
    if (!wf || !pipeline || !input || !output || !row0 || !row1 ||
        !out_logits || !g_metal || !g_metal->wf_buf || wf->gguf_lm_head_data)
        return 0;


    TensorInfo *w = get_tensor_info(wf, "lm_head.weight");
    TensorInfo *s = get_tensor_info(wf, "lm_head.scales");
    TensorInfo *b = get_tensor_info(wf, "lm_head.biases");
    if (!w || !s || !b) return 0;


    float *dst = (float *)[input contents];
    memcpy(dst, row0, HIDDEN_DIM * sizeof(float));
    memcpy(dst + HIDDEN_DIM, row1, HIDDEN_DIM * sizeof(float));


    id<MTLCommandBuffer> cmd = [g_metal->queue commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
    if (!cmd || !enc) return 0;


    uint32_t out_dim = VOCAB_SIZE;
    uint32_t in_dim = HIDDEN_DIM;
    uint32_t group_size = GROUP_SIZE;
    uint32_t input_stride = HIDDEN_DIM;
    uint32_t output_stride = VOCAB_SIZE;
    uint32_t num_tgs = (out_dim + 7u) / 8u;


    [enc setComputePipelineState:pipeline];
    [enc setBuffer:g_metal->wf_buf offset:w->offset atIndex:0];
    [enc setBuffer:g_metal->wf_buf offset:s->offset atIndex:1];
    [enc setBuffer:g_metal->wf_buf offset:b->offset atIndex:2];
    [enc setBuffer:input offset:0 atIndex:3];
    [enc setBuffer:output offset:0 atIndex:4];
    [enc setBytes:&out_dim length:sizeof(out_dim) atIndex:5];
    [enc setBytes:&in_dim length:sizeof(in_dim) atIndex:6];
    [enc setBytes:&group_size length:sizeof(group_size) atIndex:7];
    [enc setBytes:&input_stride length:sizeof(input_stride) atIndex:8];
    [enc setBytes:&output_stride length:sizeof(output_stride) atIndex:9];
    [enc dispatchThreadgroups:MTLSizeMake(num_tgs, 1, 1)
        threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
    [enc endEncoding];
    [cmd commit];
    [cmd waitUntilCompleted];
    if (cmd.status != MTLCommandBufferStatusCompleted) {
        NSString *detail = cmd.error.localizedDescription;
        fprintf(stderr, "[target-exact-m2] ERROR: M2 LM command failed: %s\n",
                detail.length ? detail.UTF8String : "unknown error");
        return 0;
    }


    memcpy(out_logits, [output contents],
           2ULL * VOCAB_SIZE * sizeof(float));
    return 1;
}


static int target_verify_exact_m2_pair(WeightFile *wf, KVCache **kv_caches,
    void **layer_states, void **layer_mmaps, int *layer_fds, int K,
    float *hidden, const ServeStateSnapshot *anchor, const float *anchor_hidden,
    const uint32_t candidates[2], uint16_t *final_norm_w,
    id<MTLComputePipelineState> pipeline, id<MTLBuffer> input,
    id<MTLBuffer> output, float *pair_logits,
    TargetVerifyExactM2PairResult *result) {
    if (!wf || !kv_caches || !layer_states || !layer_mmaps || !layer_fds ||
        !hidden || !anchor || !anchor_hidden || !candidates || !final_norm_w ||
        !pipeline || !input || !output || !pair_logits || !result)
        return 0;


    memset(result, 0, sizeof(*result));
    result->fallback_token = UINT32_MAX;


    ServeStateSnapshot banks[2] = {{0}, {0}};
    double bank_capture_ms = 0.0, bank_restore_ms = 0.0;
    float *rows = malloc(2ULL * HIDDEN_DIM * sizeof(float));
    float *hidden_after0 = malloc(HIDDEN_DIM * sizeof(float));
    float *hidden_after1 = malloc(HIDDEN_DIM * sizeof(float));
    if (!rows || !hidden_after0 || !hidden_after1) {
        free(rows); free(hidden_after0); free(hidden_after1);
        return 0;
    }


    int ok = serve_state_snapshot_restore(anchor, kv_caches, layer_states);
    if (ok) memcpy(hidden, anchor_hidden, HIDDEN_DIM * sizeof(float));
    if (ok && g_expert_prefetch_enabled) expert_prefetch_history_reset();
    g_pred_valid = 0;


    // Row 0 predicts candidate 0 from the current anchor hidden.
    if (ok) memcpy(rows, hidden, HIDDEN_DIM * sizeof(float));


    // Advance candidate 0 through the exact production transformer/state path.
    if (ok) {
        cache_telemetry_note_token();
        embed_lookup(wf, candidates[0], hidden);
        ok = run_all_layers_checked(wf, hidden, kv_caches, layer_states,
                                    layer_mmaps, layer_fds, anchor->pos, K);
        if (ok) complete_deferred_experts();
    }
    if (ok) {
        memcpy(hidden_after0, hidden, HIDDEN_DIM * sizeof(float));
        memcpy(rows + HIDDEN_DIM, hidden, HIDDEN_DIM * sizeof(float));
        double t = now_ms();
        ok = serve_state_snapshot_capture(&banks[0], kv_caches, layer_states,
                                          anchor->pos + 1);
        bank_capture_ms += now_ms() - t;
    }


    // Advance candidate 1 before deciding acceptance. The full-snapshot
    // oracle later selects the matching post-row bank.
    if (ok) {
        cache_telemetry_note_token();
        embed_lookup(wf, candidates[1], hidden);
        ok = run_all_layers_checked(wf, hidden, kv_caches, layer_states,
                                    layer_mmaps, layer_fds, anchor->pos + 1, K);
        if (ok) complete_deferred_experts();
    }
    if (ok) {
        memcpy(hidden_after1, hidden, HIDDEN_DIM * sizeof(float));
        double t = now_ms();
        ok = serve_state_snapshot_capture(&banks[1], kv_caches, layer_states,
                                          anchor->pos + 2);
        bank_capture_ms += now_ms() - t;
    }


    if (ok) {
        // Normalize copies only; the committed hidden values stay unnormalized.
        apply_final_norm_inplace(rows, final_norm_w);
        apply_final_norm_inplace(rows + HIDDEN_DIM, final_norm_w);
        ok = target_verify_exact_m2_lm_pair(wf, pipeline, input, output,
            rows, rows + HIDDEN_DIM, pair_logits);
    }


    if (ok) {
        result->predicted[0] = (uint32_t)cpu_argmax(pair_logits, VOCAB_SIZE);
        result->predicted[1] = (uint32_t)cpu_argmax(
            pair_logits + VOCAB_SIZE, VOCAB_SIZE);
        if (result->predicted[0] != candidates[0]) {
            result->accepted = 0;
            result->has_fallback = 1;
            result->fallback_token = result->predicted[0];
        } else if (result->predicted[1] != candidates[1]) {
            result->accepted = 1;
            result->has_fallback = 1;
            result->fallback_token = result->predicted[1];
        } else {
            result->accepted = 2;
            result->has_fallback = 0;
        }


        const ServeStateSnapshot *commit = result->accepted == 0
            ? anchor : &banks[result->accepted - 1];
        const float *commit_hidden = result->accepted == 0
            ? anchor_hidden : (result->accepted == 1 ? hidden_after0 : hidden_after1);
        double t = now_ms();
        ok = serve_state_snapshot_restore(commit, kv_caches, layer_states);
        bank_restore_ms = now_ms() - t;
        if (ok) {
            memcpy(hidden, commit_hidden, HIDDEN_DIM * sizeof(float));
            result->committed_pos = anchor->pos + result->accepted;
            // Rejected teacher-forced rows may have advanced auxiliary routing
            // predictors/prefetch history even though model state is rolled back.
            // They are performance hints, not model state, so invalidate them.
            g_pred_valid = 0;
            if (g_expert_prefetch_enabled) expert_prefetch_history_reset();
        }
    }


    if (!ok) {
        // Best-effort transactional rollback on verifier failure.
        if (serve_state_snapshot_restore(anchor, kv_caches, layer_states))
            memcpy(hidden, anchor_hidden, HIDDEN_DIM * sizeof(float));
        g_pred_valid = 0;
        if (g_expert_prefetch_enabled) expert_prefetch_history_reset();
    }


    printf("[target-exact-m2] full_bank_bytes=%zu capture_ms=%.3f restore_ms=%.3f accepted=%d\n", serve_state_snapshot_bytes(&banks[0]) + serve_state_snapshot_bytes(&banks[1]), bank_capture_ms, bank_restore_ms, result->accepted);
    serve_state_snapshot_free(&banks[0]);
    serve_state_snapshot_free(&banks[1]);
    free(rows);
    free(hidden_after0);
    free(hidden_after1);
    return ok;
}


static int target_verify_exact_m2_pair_compact(WeightFile *wf, KVCache **kv_caches,
    void **layer_states, void **layer_mmaps, int *layer_fds, int K,
    float *hidden, const ServeStateSnapshot *anchor, const float *anchor_hidden,
    const uint32_t candidates[2], uint16_t *final_norm_w,
    id<MTLComputePipelineState> pipeline, id<MTLBuffer> input,
    id<MTLBuffer> output, float *pair_logits,
    TargetVerifyExactM2PairResult *result) {
    if (!wf || !kv_caches || !layer_states || !layer_mmaps || !layer_fds ||
        !hidden || !anchor || !anchor_hidden || !candidates || !final_norm_w ||
        !pipeline || !input || !output || !pair_logits || !result)
        return 0;


    memset(result, 0, sizeof(*result));
    result->fallback_token = UINT32_MAX;


    TargetVerifyCompactBank bank = {0};
    double capture_ms = 0.0, commit_ms = 0.0, rollback_ms = 0.0;
    float *rows = malloc(2ULL * HIDDEN_DIM * sizeof(float));
    if (!rows) return 0;


    int ok = serve_state_snapshot_restore(anchor, kv_caches, layer_states);
    if (ok) memcpy(hidden, anchor_hidden, HIDDEN_DIM * sizeof(float));
    if (ok && g_expert_prefetch_enabled) expert_prefetch_history_reset();
    g_pred_valid = 0;


    // Row 0 predicts candidate 0 from the current anchor hidden.
    if (ok) memcpy(rows, hidden, HIDDEN_DIM * sizeof(float));


    // Advance candidate 0 through the exact production transformer/state path.
    if (ok) {
        cache_telemetry_note_token();
        embed_lookup(wf, candidates[0], hidden);
        ok = run_all_layers_checked(wf, hidden, kv_caches, layer_states,
                                    layer_mmaps, layer_fds, anchor->pos, K);
        if (ok) complete_deferred_experts();
    }
    if (ok) {
        memcpy(rows + HIDDEN_DIM, hidden, HIDDEN_DIM * sizeof(float));
        double t = now_ms();
        ok = target_verify_compact_capture(&bank, anchor, kv_caches, layer_states, hidden, anchor->pos + 1);
        capture_ms = now_ms() - t;
    }


    // Advance candidate 1 before deciding acceptance. A partial rejection
    // restores the compact state-after-row0 bank directly.
    if (ok) {
        cache_telemetry_note_token();
        embed_lookup(wf, candidates[1], hidden);
        ok = run_all_layers_checked(wf, hidden, kv_caches, layer_states,
                                    layer_mmaps, layer_fds, anchor->pos + 1, K);
        if (ok) complete_deferred_experts();
    }


    if (ok) {
        // Normalize copies only; the committed hidden values stay unnormalized.
        apply_final_norm_inplace(rows, final_norm_w);
        apply_final_norm_inplace(rows + HIDDEN_DIM, final_norm_w);
        ok = target_verify_exact_m2_lm_pair(wf, pipeline, input, output,
            rows, rows + HIDDEN_DIM, pair_logits);
    }


    if (ok) {
        result->predicted[0] = (uint32_t)cpu_argmax(pair_logits, VOCAB_SIZE);
        result->predicted[1] = (uint32_t)cpu_argmax(
            pair_logits + VOCAB_SIZE, VOCAB_SIZE);
        if (result->predicted[0] != candidates[0]) {
            result->accepted = 0;
            result->has_fallback = 1;
            result->fallback_token = result->predicted[0];
        } else if (result->predicted[1] != candidates[1]) {
            result->accepted = 1;
            result->has_fallback = 1;
            result->fallback_token = result->predicted[1];
        } else {
            result->accepted = 2;
            result->has_fallback = 0;
        }


        double t = now_ms();
        if (result->accepted == 0) {
            ok = serve_state_snapshot_restore(anchor, kv_caches, layer_states);
            rollback_ms = now_ms() - t;
        } else if (result->accepted == 1) {
            ok = target_verify_compact_restore(&bank, anchor, kv_caches, layer_states, hidden);
            commit_ms = now_ms() - t;
        } else {
            commit_ms = now_ms() - t;
        }
        if (ok) {
            if (result->accepted == 0)
                memcpy(hidden, anchor_hidden, HIDDEN_DIM * sizeof(float));
            result->committed_pos = anchor->pos + result->accepted;
            // Rejected teacher-forced rows may have advanced auxiliary routing
            // predictors/prefetch history even though model state is rolled back.
            // They are performance hints, not model state, so invalidate them.
            g_pred_valid = 0;
            if (g_expert_prefetch_enabled) expert_prefetch_history_reset();
        }
    }


    if (!ok) {
        // Best-effort transactional rollback on verifier failure.
        if (serve_state_snapshot_restore(anchor, kv_caches, layer_states))
            memcpy(hidden, anchor_hidden, HIDDEN_DIM * sizeof(float));
        g_pred_valid = 0;
        if (g_expert_prefetch_enabled) expert_prefetch_history_reset();
    }


    printf("[target-exact-m2] compact_bank_bytes=%zu compact_bank_mib=%.3f metal_capture_bytes=%zu metal_restore_bytes=%zu added_gpu_sync=0 capture_ms=%.3f commit_ms=%.3f rollback_ms=%.3f accepted=%d\n", bank.bytes, bank.bytes / 1048576.0, bank.metal_copy_bytes, bank.metal_restore_bytes, capture_ms, commit_ms, rollback_ms, result->accepted);
    target_verify_compact_free(&bank);
    free(rows);
    return ok;
}


static int target_verify_exact_m2_gpu_kv_coherent(KVCache **kv_caches) {
    if (!g_metal) return 1;
    const size_t kv_dim = (size_t)NUM_KV_HEADS * HEAD_DIM;
    for (int i = 0; i < NUM_LAYERS; i++) {
        if (!kv_caches[i]) continue;
        int fa_idx = (i + 1) / FULL_ATTN_INTERVAL - 1;
        if (fa_idx < 0 || fa_idx >= g_cfg.num_full_attn_layers) continue;
        size_t count = (size_t)kv_caches[i]->len;
        if (count > GPU_KV_SEQ) count = GPU_KV_SEQ;
        size_t bytes = count * kv_dim * sizeof(float);
        if (bytes && (memcmp(kv_caches[i]->k_cache,
                             [g_metal->buf_kv_k[fa_idx] contents], bytes) ||
                      memcmp(kv_caches[i]->v_cache,
                             [g_metal->buf_kv_v[fa_idx] contents], bytes)))
            return 0;
    }
    return 1;
}

static int target_verify_exact_m2_pair_checked(WeightFile *wf, KVCache **kv_caches,
    void **layer_states, void **layer_mmaps, int *layer_fds, int K,
    float *hidden, const ServeStateSnapshot *anchor, const float *anchor_hidden,
    const uint32_t candidates[2], uint16_t *final_norm_w,
    id<MTLComputePipelineState> pipeline, id<MTLBuffer> input,
    id<MTLBuffer> output, float *pair_logits,
    TargetVerifyExactM2PairResult *result) {
    ServeStateSnapshot reference = {0}, compact = {0};
    float *reference_hidden = malloc(HIDDEN_DIM * sizeof(float));
    float *reference_logits = malloc(2ULL * VOCAB_SIZE * sizeof(float));
    TargetVerifyExactM2PairResult expected = {0};
    int reference_gpu_kv_coherent = 0;
    int ok = reference_hidden && reference_logits;
    if (ok) ok = target_verify_exact_m2_pair(wf, kv_caches, layer_states,
        layer_mmaps, layer_fds, K, hidden, anchor, anchor_hidden, candidates,
        final_norm_w, pipeline, input, output, pair_logits, &expected);
    if (ok) {
        reference_gpu_kv_coherent = target_verify_exact_m2_gpu_kv_coherent(kv_caches);
        memcpy(reference_hidden, hidden, HIDDEN_DIM * sizeof(float));
        memcpy(reference_logits, pair_logits, 2ULL * VOCAB_SIZE * sizeof(float));
        ok = serve_state_snapshot_capture(&reference, kv_caches, layer_states,
                                          expected.committed_pos);
    }
    if (ok) ok = target_verify_exact_m2_pair_compact(wf, kv_caches, layer_states,
        layer_mmaps, layer_fds, K, hidden, anchor, anchor_hidden, candidates,
        final_norm_w, pipeline, input, output, pair_logits, result);
    if (ok) ok = serve_state_snapshot_capture(&compact, kv_caches, layer_states,
                                               result->committed_pos);
    int exact = ok && expected.accepted == result->accepted &&
        expected.predicted[0] == result->predicted[0] &&
        expected.predicted[1] == result->predicted[1] &&
        expected.fallback_token == result->fallback_token &&
        expected.has_fallback == result->has_fallback &&
        expected.committed_pos == result->committed_pos &&
        !memcmp(reference_hidden, hidden, HIDDEN_DIM * sizeof(float)) &&
        !memcmp(reference_logits, pair_logits, 2ULL * VOCAB_SIZE * sizeof(float)) &&
        reference_gpu_kv_coherent &&
        target_verify_snapshot_equal(&reference, &compact) &&
        target_verify_exact_m2_gpu_kv_coherent(kv_caches);
    printf("[target-exact-m2] compact_oracle accepted=%d exact=%s full_gpu_kv_coherent=%s compact_gpu_kv_coherent=%s\n",
           result->accepted, exact ? "yes" : "no",
           reference_gpu_kv_coherent ? "yes" : "no",
           target_verify_exact_m2_gpu_kv_coherent(kv_caches) ? "yes" : "no");
    serve_state_snapshot_free(&reference);
    serve_state_snapshot_free(&compact);
    free(reference_hidden);
    free(reference_logits);
    return exact;
}

static uint64_t target_verify_exact_m2_bitwise_count(const float *a,
    const float *b, size_t n, double *max_abs) {
    uint64_t exact = 0;
    double max_diff = 0.0;
    for (size_t i = 0; i < n; i++) {
        uint32_t ua = 0, ub = 0;
        memcpy(&ua, &a[i], sizeof(ua));
        memcpy(&ub, &b[i], sizeof(ub));
        if (ua == ub) exact++;
        double d = fabs((double)a[i] - (double)b[i]);
        if (d > max_diff) max_diff = d;
    }
    if (max_abs) *max_abs = max_diff;
    return exact;
}


static int target_verify_exact_m2_advance_one(WeightFile *wf,
    KVCache **kv_caches, void **layer_states, void **layer_mmaps,
    int *layer_fds, int K, float *hidden, uint32_t token, int pos) {
    cache_telemetry_note_token();
    embed_lookup(wf, token, hidden);
    if (!run_all_layers_checked(wf, hidden, kv_caches, layer_states,
                                layer_mmaps, layer_fds, pos, K))
        return 0;
    complete_deferred_experts();
    return 1;
}


static int target_verify_exact_m2_snapshot_current(ServeStateSnapshot *snap,
    KVCache **kv_caches, void **layer_states, int pos) {
    return serve_state_snapshot_capture(snap, kv_caches, layer_states, pos);
}


static int target_verify_exact_m2_integration_experiment(WeightFile *wf,
    KVCache **kv_caches, void **layer_states, void **layer_mmaps,
    int *layer_fds, int K, float *hidden, float *logits,
    uint16_t *final_norm_w, const ServeStateSnapshot *anchor,
    const float *anchor_hidden, const uint32_t candidates[8]) {
    if (!g_metal || !g_metal->wf_buf || wf->gguf_lm_head_data) {
        fprintf(stderr,
            "[target-exact-m2] ERROR: integration requires resident Q4 LM head\n");
        return 1;
    }


    id<MTLComputePipelineState> pipeline = target_verify_exact_m2_pipeline(g_metal);
    if (!pipeline) return 1;
    id<MTLBuffer> input = [g_metal->device
        newBufferWithLength:2ULL * HIDDEN_DIM * sizeof(float)
        options:MTLResourceStorageModeShared];
    id<MTLBuffer> output = [g_metal->device
        newBufferWithLength:2ULL * VOCAB_SIZE * sizeof(float)
        options:MTLResourceStorageModeShared];
    float *pair_logits = malloc(2ULL * VOCAB_SIZE * sizeof(float));
    float *reference_logits = malloc(2ULL * VOCAB_SIZE * sizeof(float));
    float *serial_hidden0 = malloc(HIDDEN_DIM * sizeof(float));
    float *serial_hidden1 = malloc(HIDDEN_DIM * sizeof(float));
    float *norm_row = malloc(HIDDEN_DIM * sizeof(float));
    if (!input || !output || !pair_logits || !reference_logits ||
        !serial_hidden0 || !serial_hidden1 || !norm_row) {
        free(pair_logits); free(reference_logits); free(serial_hidden0);
        free(serial_hidden1); free(norm_row);
        return 1;
    }


    int ok = 1;
    ServeStateSnapshot serial0 = {0}, serial1 = {0}, observed = {0};


    // Build the immutable serial reference for the two known-good candidates.
    ok = serve_state_snapshot_restore(anchor, kv_caches, layer_states);
    if (ok) memcpy(hidden, anchor_hidden, HIDDEN_DIM * sizeof(float));
    if (ok) {
        memcpy(norm_row, hidden, HIDDEN_DIM * sizeof(float));
        apply_final_norm_inplace(norm_row, final_norm_w);
        lm_head_forward(wf, norm_row, reference_logits);
        ok = target_verify_exact_m2_advance_one(wf, kv_caches, layer_states,
            layer_mmaps, layer_fds, K, hidden, candidates[0], anchor->pos);
    }
    if (ok) {
        memcpy(serial_hidden0, hidden, HIDDEN_DIM * sizeof(float));
        ok = target_verify_exact_m2_snapshot_current(&serial0, kv_caches,
            layer_states, anchor->pos + 1);
    }
    if (ok) {
        memcpy(norm_row, hidden, HIDDEN_DIM * sizeof(float));
        apply_final_norm_inplace(norm_row, final_norm_w);
        lm_head_forward(wf, norm_row, reference_logits + VOCAB_SIZE);
        ok = target_verify_exact_m2_advance_one(wf, kv_caches, layer_states,
            layer_mmaps, layer_fds, K, hidden, candidates[1], anchor->pos + 1);
    }
    if (ok) {
        memcpy(serial_hidden1, hidden, HIDDEN_DIM * sizeof(float));
    ok = target_verify_exact_m2_snapshot_current(&serial1, kv_caches,
            layer_states, anchor->pos + 2);
    }


    uint32_t serial_pred0 = ok ? (uint32_t)cpu_argmax(reference_logits, VOCAB_SIZE) : 0;
    uint32_t serial_pred1 = ok ? (uint32_t)cpu_argmax(reference_logits + VOCAB_SIZE,
                                                       VOCAB_SIZE) : 0;
    if (ok && (serial_pred0 != candidates[0] || serial_pred1 != candidates[1])) {
        fprintf(stderr,
            "[target-exact-m2] ERROR: generated full-accept candidates drifted "
            "serial=(%u,%u) candidates=(%u,%u)\n",
            serial_pred0, serial_pred1, candidates[0], candidates[1]);
        ok = 0;
    }


    TargetVerifyExactM2PairResult result = {0};
    uint32_t full[2] = {candidates[0], candidates[1]};
    TargetVerifyFixedDraft draft = {{candidates[0], candidates[1]}, anchor->pos};
    uint32_t disabled_probe[2] = {UINT32_MAX, UINT32_MAX};
    int provider_disabled = !target_verify_get_draft_pair(target_verify_fixed_draft,
        &draft, 0, anchor->pos, disabled_probe) &&
        disabled_probe[0] == UINT32_MAX && disabled_probe[1] == UINT32_MAX;
    int provider_enabled = target_verify_get_draft_pair(target_verify_fixed_draft,
        &draft, 1, anchor->pos, full) &&
        full[0] == candidates[0] && full[1] == candidates[1];
    printf("[target-exact-m2] draft_provider enabled=%s disabled=%s\n",
           provider_enabled ? "pass" : "fail",
           provider_disabled ? "pass" : "fail");
    ok = ok && provider_enabled && provider_disabled;
    if (ok) ok = target_verify_exact_m2_pair_checked(wf, kv_caches, layer_states,
        layer_mmaps, layer_fds, K, hidden, anchor, anchor_hidden, full,
        final_norm_w, pipeline, input, output, pair_logits, &result);


    double lm_max_abs = 0.0;
    uint64_t lm_exact = ok ? target_verify_exact_m2_bitwise_count(
        reference_logits, pair_logits, 2ULL * VOCAB_SIZE, &lm_max_abs) : 0;
    size_t lm_values = 2ULL * VOCAB_SIZE;
    int full_state_exact = 0, full_hidden_exact = 0;
    if (ok) {
        ok = target_verify_exact_m2_snapshot_current(&observed, kv_caches,
            layer_states, result.committed_pos);
        full_state_exact = ok && target_verify_snapshot_equal(&serial1, &observed);
        full_hidden_exact = memcmp(hidden, serial_hidden1,
            HIDDEN_DIM * sizeof(float)) == 0;
        serve_state_snapshot_free(&observed);
    }
    printf("[target-exact-m2] full_accept accepted=%d/2 lm_bitwise=%llu/%llu "
           "lm_max_abs=%.9g state_exact=%s hidden_exact=%s\n",
           result.accepted, (unsigned long long)lm_exact,
           (unsigned long long)lm_values, lm_max_abs,
           full_state_exact ? "yes" : "no", full_hidden_exact ? "yes" : "no");
    ok = ok && result.accepted == 2 && lm_exact == lm_values &&
         full_state_exact && full_hidden_exact;


    // Continue one target step from the compact full-accept commit and from
    // the serial oracle to catch state that diverges only on the next token.
    ServeStateSnapshot continuation_compact = {0}, continuation_serial = {0};
    int continuation_exact = 0;
    if (ok) {
        memcpy(norm_row, hidden, HIDDEN_DIM * sizeof(float));
        apply_final_norm_inplace(norm_row, final_norm_w);
        uint32_t next = (uint32_t)lm_head_forward_greedy(wf, norm_row, logits);
        ok = target_verify_exact_m2_advance_one(wf, kv_caches, layer_states,
            layer_mmaps, layer_fds, K, hidden, next, anchor->pos + 2);
        if (ok) memcpy(norm_row, hidden, HIDDEN_DIM * sizeof(float));
        if (ok) ok = target_verify_exact_m2_snapshot_current(&continuation_compact,
            kv_caches, layer_states, anchor->pos + 3);
        if (ok) ok = serve_state_snapshot_restore(&serial1, kv_caches, layer_states);
        if (ok) memcpy(hidden, serial_hidden1, HIDDEN_DIM * sizeof(float));
        if (ok) ok = target_verify_exact_m2_advance_one(wf, kv_caches,
            layer_states, layer_mmaps, layer_fds, K, hidden, next, anchor->pos + 2);
        if (ok) ok = target_verify_exact_m2_snapshot_current(&continuation_serial,
            kv_caches, layer_states, anchor->pos + 3);
        continuation_exact = ok &&
            target_verify_snapshot_equal(&continuation_compact, &continuation_serial) &&
            !memcmp(norm_row, hidden, HIDDEN_DIM * sizeof(float)) &&
            target_verify_exact_m2_gpu_kv_coherent(kv_caches);
        ok = ok && continuation_exact;
    }
    printf("[target-exact-m2] continuation_after_full_accept exact=%s\n",
           continuation_exact ? "yes" : "no");
    serve_state_snapshot_free(&continuation_compact);
    serve_state_snapshot_free(&continuation_serial);


    // Reject row 0: commit anchor, then advance the target fallback once.
    uint32_t reject0[2] = {(serial_pred0 + 1u) % VOCAB_SIZE, candidates[1]};
    if (reject0[0] == serial_pred0) reject0[0] = (serial_pred0 + 2u) % VOCAB_SIZE;
    if (ok) ok = target_verify_exact_m2_pair_checked(wf, kv_caches, layer_states,
        layer_mmaps, layer_fds, K, hidden, anchor, anchor_hidden, reject0,
        final_norm_w, pipeline, input, output, pair_logits, &result);
    int reject0_anchor_state = 0, reject0_anchor_hidden = 0;
    if (ok) {
        ok = target_verify_exact_m2_snapshot_current(&observed, kv_caches,
            layer_states, result.committed_pos);
        reject0_anchor_state = ok && target_verify_snapshot_equal(anchor, &observed);
        reject0_anchor_hidden = memcmp(hidden, anchor_hidden,
            HIDDEN_DIM * sizeof(float)) == 0;
        serve_state_snapshot_free(&observed);
    }
    int reject0_fallback_state = 0, reject0_fallback_hidden = 0;
    if (ok && result.has_fallback)
        ok = target_verify_exact_m2_advance_one(wf, kv_caches, layer_states,
            layer_mmaps, layer_fds, K, hidden, result.fallback_token, anchor->pos);
    if (ok) {
        ok = target_verify_exact_m2_snapshot_current(&observed, kv_caches,
            layer_states, anchor->pos + 1);
        reject0_fallback_state = ok && target_verify_snapshot_equal(&serial0, &observed);
        reject0_fallback_hidden = memcmp(hidden, serial_hidden0,
            HIDDEN_DIM * sizeof(float)) == 0;
        serve_state_snapshot_free(&observed);
    }
    printf("[target-exact-m2] reject0 accepted=%d fallback=%u expected=%u "
           "commit_state_exact=%s commit_hidden_exact=%s "
           "fallback_state_exact=%s fallback_hidden_exact=%s replayed_accepted=0\n",
           result.accepted, result.fallback_token, serial_pred0,
           reject0_anchor_state ? "yes" : "no",
           reject0_anchor_hidden ? "yes" : "no",
           reject0_fallback_state ? "yes" : "no",
           reject0_fallback_hidden ? "yes" : "no");
    ok = ok && result.accepted == 0 && result.has_fallback &&
         result.fallback_token == serial_pred0 && reject0_anchor_state &&
         reject0_anchor_hidden && reject0_fallback_state && reject0_fallback_hidden;


    // Reject row 1: commit state-after-row0 with no replay, then advance fallback.
    uint32_t reject1[2] = {serial_pred0, (serial_pred1 + 1u) % VOCAB_SIZE};
    if (reject1[1] == serial_pred1) reject1[1] = (serial_pred1 + 2u) % VOCAB_SIZE;
    if (ok) ok = target_verify_exact_m2_pair_checked(wf, kv_caches, layer_states,
        layer_mmaps, layer_fds, K, hidden, anchor, anchor_hidden, reject1,
        final_norm_w, pipeline, input, output, pair_logits, &result);
    int reject1_commit_state = 0, reject1_commit_hidden = 0;
    if (ok) {
        ok = target_verify_exact_m2_snapshot_current(&observed, kv_caches,
            layer_states, result.committed_pos);
        reject1_commit_state = ok && target_verify_snapshot_equal(&serial0, &observed);
        reject1_commit_hidden = memcmp(hidden, serial_hidden0,
            HIDDEN_DIM * sizeof(float)) == 0;
        serve_state_snapshot_free(&observed);
    }
    int reject1_fallback_state = 0, reject1_fallback_hidden = 0;
    if (ok && result.has_fallback)
        ok = target_verify_exact_m2_advance_one(wf, kv_caches, layer_states,
            layer_mmaps, layer_fds, K, hidden, result.fallback_token, anchor->pos + 1);
    if (ok) {
        ok = target_verify_exact_m2_snapshot_current(&observed, kv_caches,
            layer_states, anchor->pos + 2);
        reject1_fallback_state = ok && target_verify_snapshot_equal(&serial1, &observed);
        reject1_fallback_hidden = memcmp(hidden, serial_hidden1,
            HIDDEN_DIM * sizeof(float)) == 0;
        serve_state_snapshot_free(&observed);
    }
    printf("[target-exact-m2] reject1 accepted=%d fallback=%u expected=%u "
           "commit_state_exact=%s commit_hidden_exact=%s "
           "fallback_state_exact=%s fallback_hidden_exact=%s replayed_accepted=0\n",
           result.accepted, result.fallback_token, serial_pred1,
           reject1_commit_state ? "yes" : "no",
           reject1_commit_hidden ? "yes" : "no",
           reject1_fallback_state ? "yes" : "no",
           reject1_fallback_hidden ? "yes" : "no");
    ok = ok && result.accepted == 1 && result.has_fallback &&
         result.fallback_token == serial_pred1 && reject1_commit_state &&
         reject1_commit_hidden && reject1_fallback_state && reject1_fallback_hidden;


    double bank_mib = (serve_state_snapshot_bytes(&serial0) +
                       serve_state_snapshot_bytes(&serial1)) / 1048576.0;
    printf("[target-exact-m2] state_bank_reference_mib=%.2f "
           "transformer_rows=serial_exact lm_head_rows=M2_exact "
           "serving_enabled=no draft_source=not_wired\n", bank_mib);
    printf("[target-exact-m2] RESULT: %s\n", ok ? "PASS" : "FAIL");


    serve_state_snapshot_free(&serial0);
    serve_state_snapshot_free(&serial1);
    serve_state_snapshot_free(&observed);
    free(pair_logits);
    free(reference_logits);
    free(serial_hidden0);
    free(serial_hidden1);
    free(norm_row);
    (void)logits;
    return ok ? 0 : 1;
}
#endif
