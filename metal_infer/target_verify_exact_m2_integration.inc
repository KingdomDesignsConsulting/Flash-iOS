#ifdef TARGET_VERIFY_EXACT_M2_INTEGRATION
// Exact two-candidate target-verifier integration.
//
// Transformer/state production remains serial and bit-identical: candidate 0 is
// advanced through the ordinary production forward, state-after-0 is captured,
// then candidate 1 is advanced and state-after-1 is captured.  The two logits
// rows are evaluated together with the exact Q4 M2 affine kernel.  Longest-prefix
// commit selects anchor/state-after-0/state-after-1 directly; accepted candidates
// are never replayed.  A caller must still advance the target fallback token after
// a rejection, which is required speculative-decode work rather than replay.


typedef struct {
    int accepted;
    uint32_t predicted[2];
    uint32_t fallback_token;
    int has_fallback;
    int committed_pos;
} TargetVerifyExactM2PairResult;


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
        ok = serve_state_snapshot_capture(&banks[0], kv_caches, layer_states,
                                          anchor->pos + 1);
    }


    // Advance candidate 1 before deciding acceptance.  This is teacher-forced
    // target verification; a later partial reject restores banks[0] directly.
    if (ok) {
        cache_telemetry_note_token();
        embed_lookup(wf, candidates[1], hidden);
        ok = run_all_layers_checked(wf, hidden, kv_caches, layer_states,
                                    layer_mmaps, layer_fds, anchor->pos + 1, K);
        if (ok) complete_deferred_experts();
    }
    if (ok) {
        memcpy(hidden_after1, hidden, HIDDEN_DIM * sizeof(float));
        ok = serve_state_snapshot_capture(&banks[1], kv_caches, layer_states,
                                          anchor->pos + 2);
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
        ok = serve_state_snapshot_restore(commit, kv_caches, layer_states);
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


    serve_state_snapshot_free(&banks[0]);
    serve_state_snapshot_free(&banks[1]);
    free(rows);
    free(hidden_after0);
    free(hidden_after1);
    return ok;
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
    if (ok) ok = target_verify_exact_m2_pair(wf, kv_caches, layer_states,
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


    // Reject row 0: commit anchor, then advance the target fallback once.
    uint32_t reject0[2] = {(serial_pred0 + 1u) % VOCAB_SIZE, candidates[1]};
    if (reject0[0] == serial_pred0) reject0[0] = (serial_pred0 + 2u) % VOCAB_SIZE;
    if (ok) ok = target_verify_exact_m2_pair(wf, kv_caches, layer_states,
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
    if (ok) ok = target_verify_exact_m2_pair(wf, kv_caches, layer_states,
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