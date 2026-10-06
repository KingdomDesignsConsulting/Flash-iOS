#if (defined(FLASH_PREFILL_NROW_GATEUP_M4_2ROW) + defined(FLASH_PREFILL_NROW_GATEUP_M4_4ROW) + defined(FLASH_PREFILL_NROW_GATEUP_M4_8ROW) + defined(FLASH_PREFILL_NROW_GATEUP_M4_8ROW_XCACHE) + defined(FLASH_PREFILL_NROW_GATEUP_M4_8ROW_BITSPLIT) + defined(FLASH_PREFILL_NROW_GATEUP_M4_16ROW) + defined(FLASH_PREFILL_NROW_GATEUP_M8_2ROW)) > 1
#error choose exactly one routed gate+up candidate
#endif
#if defined(FLASH_PREFILL_NROW_DOWN_BIT_TIMING) && !defined(FLASH_PREFILL_NROW_EXPERT_PHASE_TIMING)
#error FLASH_PREFILL_NROW_DOWN_BIT_TIMING requires FLASH_PREFILL_NROW_EXPERT_PHASE_TIMING
#endif
#if (defined(FLASH_PREFILL_NROW_DOWN_ACC16) || defined(FLASH_PREFILL_NROW_DOWN_ACC32) || defined(FLASH_PREFILL_NROW_DOWN_M4) || defined(FLASH_PREFILL_NROW_DOWN_M4_2ROW) || defined(FLASH_PREFILL_NROW_DOWN_M4_2ROW_BITSPLIT) || defined(FLASH_PREFILL_NROW_DOWN_M4_4ROW)) && (defined(FLASH_PREFILL_NROW_DOWN_2ROW) || defined(FLASH_PREFILL_NROW_DOWN_COOP_2ROW))
#error routed-down diagnostics cannot be combined with V8/V9 down geometry
#endif
#if (defined(FLASH_PREFILL_NROW_DOWN_ACC16) && (defined(FLASH_PREFILL_NROW_DOWN_ACC32) || defined(FLASH_PREFILL_NROW_DOWN_M4) || defined(FLASH_PREFILL_NROW_DOWN_M4_2ROW) || defined(FLASH_PREFILL_NROW_DOWN_M4_2ROW_BITSPLIT) || defined(FLASH_PREFILL_NROW_DOWN_M4_4ROW))) || \
    (defined(FLASH_PREFILL_NROW_DOWN_ACC32) && (defined(FLASH_PREFILL_NROW_DOWN_M4) || defined(FLASH_PREFILL_NROW_DOWN_M4_2ROW) || defined(FLASH_PREFILL_NROW_DOWN_M4_2ROW_BITSPLIT) || defined(FLASH_PREFILL_NROW_DOWN_M4_4ROW))) || \
    (defined(FLASH_PREFILL_NROW_DOWN_M4) && (defined(FLASH_PREFILL_NROW_DOWN_M4_2ROW) || defined(FLASH_PREFILL_NROW_DOWN_M4_2ROW_BITSPLIT) || defined(FLASH_PREFILL_NROW_DOWN_M4_4ROW))) || \
    (defined(FLASH_PREFILL_NROW_DOWN_M4_2ROW) && (defined(FLASH_PREFILL_NROW_DOWN_M4_2ROW_BITSPLIT) || defined(FLASH_PREFILL_NROW_DOWN_M4_4ROW))) || \
    (defined(FLASH_PREFILL_NROW_DOWN_M4_2ROW_BITSPLIT) && defined(FLASH_PREFILL_NROW_DOWN_M4_4ROW))
#error choose exactly one routed-down diagnostic kernel
#endif

// Grouped tiered MoE for N-row prompt prefill (benchmark and production).
//
// The original integrated correctness prototype synchronized once per unique
// expert group.  That made the grouped arithmetic correct but serialized CMD3
// badly.  This version packs all 16x8 routed assignments into disjoint scratch
// rows, stages any expert bytes that cannot be referenced safely in-place, and
// submits all unique groups for a layer in one command buffer.  The only CPU
// completion wait in the routed-expert phase is therefore the layer-level wait
// needed before the benchmark's CPU-side weighted combine.
enum {
    PREFILL_NROW_ROWS = PREFILL_NROW_CAPTURE_ROWS,
    PREFILL_NROW_K = 8,
    PREFILL_NROW_ASSIGNMENTS = PREFILL_NROW_ROWS * PREFILL_NROW_K,
};
typedef struct {
    id<MTLComputePipelineState> projection;
#ifdef FLASH_PREFILL_NROW_DOWN_ACC16
    id<MTLComputePipelineState> projection_acc16;
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_ACC32
    id<MTLComputePipelineState> projection_acc32;
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_M4
    id<MTLComputePipelineState> projection_m4;
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_M4_2ROW
    id<MTLComputePipelineState> projection_m4_2row;
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_M4_2ROW_BITSPLIT
    id<MTLComputePipelineState> projection_m4_2row_q4;
    id<MTLComputePipelineState> projection_m4_2row_q2;
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_M4_4ROW
    id<MTLComputePipelineState> projection_m4_4row;
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_2ROW
    id<MTLComputePipelineState> down_2row_projection;
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_COOP_2ROW
    id<MTLComputePipelineState> down_coop_2row_projection;
#endif
    id<MTLComputePipelineState> gate_up_projection;
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_2ROW
    id<MTLComputePipelineState> gate_up_projection_m4_2row;
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_4ROW
    id<MTLComputePipelineState> gate_up_projection_m4_4row;
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_8ROW
    id<MTLComputePipelineState> gate_up_projection_m4_8row;
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_8ROW_BITSPLIT
    id<MTLComputePipelineState> gate_up_projection_m4_8row_q4;
    id<MTLComputePipelineState> gate_up_projection_m4_8row_q2;
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_8ROW_XCACHE
    id<MTLComputePipelineState> gate_up_projection_m4_8row_xcache;
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_16ROW
    id<MTLComputePipelineState> gate_up_projection_m4_16row;
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M8_2ROW
    id<MTLComputePipelineState> gate_up_projection_m8_2row;
#endif
    id<MTLComputePipelineState> swiglu;
    id<MTLComputePipelineState> full_attn_batch;
    id<MTLComputePipelineState> conv_chunk, split_qkv, gdn_chunk;
    // Routed-expert scratch is sized by routed assignments, not by experts.
    // The sum of all group counts is exactly 16*8, so disjoint ranges allow
    // every unique expert to be encoded before a single command-buffer commit.
    id<MTLBuffer> input, gate, up, act, output;
    // Shared expert N-row scratch.  The capture path already provides 16
    // shared gate/up rows.  We form 16 SwiGLU activations on CPU (matching the
    // existing benchmark semantics), then encode all 16 shared down projections
    // into one Metal command buffer instead of synchronously dispatching one
    // matvec per row.
    id<MTLBuffer> shared_act_rows, shared_out_rows;
    id<MTLBuffer> shared_gate_rows, shared_up_rows;
    // N-row normalized inputs for the linear-attention QKV/Z/beta/alpha
    // projections.  Keeping all 16 rows in one shared Metal buffer lets those
    // projections feed the existing chunked conv/GDN command buffer without
    // 16 synchronous fast_batch_matvec round trips.
    id<MTLBuffer> normed_rows;
    // Full-attention V4 projection slabs. Q keeps the model's packed
    // [q, gate] head layout; K/V use the native KV-head geometry.
    id<MTLBuffer> full_qproj_rows, full_k_rows, full_v_rows;
    id<MTLBuffer> full_q_rows, full_gate_rows, full_attn_rows;
    // N128 linear post-attention batching: out_proj, normalized h_post, router
    // scores and shared-gate score. Shared gate/up reuse existing row buffers.
    id<MTLBuffer> linear_oproj_rows, linear_hpost_rows;
    id<MTLBuffer> linear_gate_scores, linear_shared_scores;
    // N-row staging for cold experts and hot-cache misses.  Each staged
    // group gets a private max-expert-size slice so its weight bytes remain valid
    // until the layer command buffer completes.
    id<MTLBuffer> expert_stage;
    size_t expert_stage_stride;
    size_t expert_stage_slots;
    id<MTLBuffer> conv_input, conv_output, q, k, v;
    id<MTLBuffer> z, alpha, beta, decay, beta_gate, gdn_output, attn_output;
    uint64_t groups, repeated, hot, cold, cache_hits, cache_misses, gpu_waits;
    double grouping_ms, expert_ms, shared_ms, linear_ms;
    double full_qkv_ms, full_attn_ms;
    double expert_stage_ms, expert_cache_ms, combine_ms, linear_post_ms;
#ifdef FLASH_PREFILL_NROW_EXPERT_PHASE_TIMING
    double expert_gate_up_gpu_ms, expert_swiglu_gpu_ms, expert_down_gpu_ms;
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_BIT_TIMING
    double expert_down_q4_gpu_ms, expert_down_q2_gpu_ms;
    uint64_t down_q4_groups, down_q2_groups;
    uint64_t down_q4_assignments, down_q2_assignments;
#endif
} PrefillNRowGrouped;

static __attribute__((unused)) void prefill_nrow_grouped_release(PrefillNRowGrouped *p) {
    if (!p) return;
    p->projection = nil;
#ifdef FLASH_PREFILL_NROW_DOWN_ACC16
    p->projection_acc16 = nil;
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_ACC32
    p->projection_acc32 = nil;
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_M4
    p->projection_m4 = nil;
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_M4_2ROW
    p->projection_m4_2row = nil;
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_M4_2ROW_BITSPLIT
    p->projection_m4_2row_q4 = nil;
    p->projection_m4_2row_q2 = nil;
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_M4_4ROW
    p->projection_m4_4row = nil;
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_2ROW
    p->down_2row_projection = nil;
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_COOP_2ROW
    p->down_coop_2row_projection = nil;
#endif
    p->gate_up_projection = nil;
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_2ROW
    p->gate_up_projection_m4_2row = nil;
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_4ROW
    p->gate_up_projection_m4_4row = nil;
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_8ROW
    p->gate_up_projection_m4_8row = nil;
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_8ROW_BITSPLIT
    p->gate_up_projection_m4_8row_q4 = nil;
    p->gate_up_projection_m4_8row_q2 = nil;
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_8ROW_XCACHE
    p->gate_up_projection_m4_8row_xcache = nil;
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_16ROW
    p->gate_up_projection_m4_16row = nil;
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M8_2ROW
    p->gate_up_projection_m8_2row = nil;
#endif
    p->swiglu = nil;
    p->full_attn_batch = nil;
    p->conv_chunk = nil;
    p->split_qkv = nil;
    p->gdn_chunk = nil;
    p->input = nil;
    p->gate = nil;
    p->up = nil;
    p->act = nil;
    p->output = nil;
    p->shared_act_rows = nil;
    p->shared_out_rows = nil;
    p->shared_gate_rows = nil;
    p->shared_up_rows = nil;
    p->normed_rows = nil;
    p->full_qproj_rows = nil;
    p->full_k_rows = nil;
    p->full_v_rows = nil;
    p->full_q_rows = nil;
    p->full_gate_rows = nil;
    p->full_attn_rows = nil;
    p->linear_oproj_rows = nil;
    p->linear_hpost_rows = nil;
    p->linear_gate_scores = nil;
    p->linear_shared_scores = nil;
    p->expert_stage = nil;
    p->conv_input = nil;
    p->conv_output = nil;
    p->q = nil;
    p->k = nil;
    p->v = nil;
    p->z = nil;
    p->alpha = nil;
    p->beta = nil;
    p->decay = nil;
    p->beta_gate = nil;
    p->gdn_output = nil;
    p->attn_output = nil;
    p->expert_stage_stride = 0;
    p->expert_stage_slots = 0;
}

static int prefill_nrow_grouped_init(PrefillNRowGrouped *p) {
    NSString *executable_dir = infer_executable_directory();
    NSArray<NSString *> *paths = executable_dir
        ? @[[executable_dir stringByAppendingPathComponent:@"prefill_probe/chunk_kernels.metal"],
            @"prefill_probe/chunk_kernels.metal",
            @"metal_infer/prefill_probe/chunk_kernels.metal"]
        : @[@"prefill_probe/chunk_kernels.metal",
            @"metal_infer/prefill_probe/chunk_kernels.metal"];
    NSString *source = nil;
    NSString *source_path = nil;
    for (NSString *path in paths) {
        source = [NSString stringWithContentsOfFile:path
            encoding:NSUTF8StringEncoding error:NULL];
        if (source) { source_path = path; break; }
    }
    if (!source) { fprintf(stderr, "[prefill-nrow] missing grouped Metal kernels\n"); return 0; }
    fprintf(stderr, "[prefill-nrow] shader source=%s\n", source_path.UTF8String);
    NSError *error = nil;
    id<MTLLibrary> library = [g_metal->device newLibraryWithSource:source
        options:nil error:&error];
    if (!library) {
        fprintf(stderr, "[prefill-nrow] shader: %s\n", error.localizedDescription.UTF8String);
        return 0;
    }
    id<MTLFunction> fn = [library newFunctionWithName:@"grouped_tiered_projection"];
    p->projection = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
#ifdef FLASH_PREFILL_NROW_DOWN_ACC16
    fn = [library newFunctionWithName:@"grouped_tiered_projection_acc16"];
    p->projection_acc16 = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_ACC32
    fn = [library newFunctionWithName:@"grouped_tiered_projection_acc32"];
    p->projection_acc32 = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_M4
    fn = [library newFunctionWithName:@"grouped_tiered_projection_m4"];
    p->projection_m4 = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_M4_2ROW
    fn = [library newFunctionWithName:@"grouped_tiered_projection_m4_2row"];
    p->projection_m4_2row = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_M4_2ROW_BITSPLIT
    fn = [library newFunctionWithName:@"grouped_tiered_projection_m4_2row_q4"];
    p->projection_m4_2row_q4 = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    fn = [library newFunctionWithName:@"grouped_tiered_projection_m4_2row_q2"];
    p->projection_m4_2row_q2 = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_M4_4ROW
    fn = [library newFunctionWithName:@"grouped_tiered_projection_m4_4row"];
    p->projection_m4_4row = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_2ROW
    fn = [library newFunctionWithName:@"grouped_tiered_projection_2row"];
    p->down_2row_projection = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_COOP_2ROW
    fn = [library newFunctionWithName:@"grouped_tiered_projection_2row_coop"];
    p->down_coop_2row_projection = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    fprintf(stderr, "[prefill-nrow] routed down candidate=coop-2row activation-cache\n");
#endif
fprintf(stderr, "[prefill-nrow] slab_rows=%d assignments=%d\n",
        PREFILL_NROW_ROWS, PREFILL_NROW_ASSIGNMENTS);
#ifdef FLASH_PREFILL_NROW_DOWN_BIT_TIMING
#ifdef FLASH_PREFILL_NROW_DOWN_M4_2ROW_BITSPLIT
    fprintf(stderr, "[prefill-nrow] routed down diagnostics=Q4/Q2 gpu-time candidate=M4-2row-bitsplit\n");
#elif defined(FLASH_PREFILL_NROW_DOWN_M4_2ROW)
    fprintf(stderr, "[prefill-nrow] routed down diagnostics=Q4/Q2 gpu-time candidate=M4-2row\n");
#elif defined(FLASH_PREFILL_NROW_DOWN_M4_4ROW)
    fprintf(stderr, "[prefill-nrow] routed down diagnostics=Q4/Q2 gpu-time candidate=M4-4row\n");
#elif defined(FLASH_PREFILL_NROW_DOWN_M4)
    fprintf(stderr, "[prefill-nrow] routed down diagnostics=Q4/Q2 gpu-time candidate=M4-fixed\n");
#elif defined(FLASH_PREFILL_NROW_DOWN_ACC16)
    fprintf(stderr, "[prefill-nrow] routed down diagnostics=Q4/Q2 gpu-time acc=16\n");
#elif defined(FLASH_PREFILL_NROW_DOWN_ACC32)
    fprintf(stderr, "[prefill-nrow] routed down diagnostics=Q4/Q2 gpu-time acc=32\n");
#else
    fprintf(stderr, "[prefill-nrow] routed down diagnostics=Q4/Q2 gpu-time acc=64\n");
#endif
#endif
#ifndef FLASH_PREFILL_NROW_DOWN_BIT_TIMING
#ifdef FLASH_PREFILL_NROW_DOWN_M4_2ROW_BITSPLIT
    fprintf(stderr, "[prefill-nrow] routed down candidate=M4-2row-bitsplit\n");
#elif defined(FLASH_PREFILL_NROW_DOWN_M4_2ROW)
    fprintf(stderr, "[prefill-nrow] routed down candidate=M4-2row\n");
#elif defined(FLASH_PREFILL_NROW_DOWN_M4_4ROW)
    fprintf(stderr, "[prefill-nrow] routed down candidate=M4-4row\n");
#elif defined(FLASH_PREFILL_NROW_DOWN_M4)
    fprintf(stderr, "[prefill-nrow] routed down candidate=M4-fixed\n");
#endif
#endif
    fn = [library newFunctionWithName:@"grouped_tiered_gate_up"];
    p->gate_up_projection = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_2ROW
    fn = [library newFunctionWithName:@"grouped_tiered_gate_up_m4_2row"];
    p->gate_up_projection_m4_2row =
        [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    fprintf(stderr, "[prefill-nrow] routed gate+up candidate=M4-2row\n");
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_4ROW
    fn = [library newFunctionWithName:@"grouped_tiered_gate_up_m4_4row"];
    p->gate_up_projection_m4_4row =
        [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    fprintf(stderr, "[prefill-nrow] routed gate+up candidate=M4-4row\n");
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_8ROW
    fn = [library newFunctionWithName:@"grouped_tiered_gate_up_m4_8row"];
    p->gate_up_projection_m4_8row =
        [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    fprintf(stderr, "[prefill-nrow] routed gate+up candidate=M4-8row\n");
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_8ROW_BITSPLIT
    fn = [library newFunctionWithName:@"grouped_tiered_gate_up_m4_8row_q4"];
    p->gate_up_projection_m4_8row_q4 =
        [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    fn = [library newFunctionWithName:@"grouped_tiered_gate_up_m4_8row_q2"];
    p->gate_up_projection_m4_8row_q2 =
        [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    fprintf(stderr, "[prefill-nrow] routed gate+up candidate=M4-8row-bitsplit\n");
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_8ROW_XCACHE
    fn = [library newFunctionWithName:@"grouped_tiered_gate_up_m4_8row_xcache"];
    p->gate_up_projection_m4_8row_xcache =
        [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    fprintf(stderr, "[prefill-nrow] routed gate+up candidate=M4-8row-xcache\n");
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_16ROW
    fn = [library newFunctionWithName:@"grouped_tiered_gate_up_m4_16row"];
    p->gate_up_projection_m4_16row =
        [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    fprintf(stderr, "[prefill-nrow] routed gate+up candidate=M4-16row\n");
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M8_2ROW
    fn = [library newFunctionWithName:@"grouped_tiered_gate_up_m8_2row"];
    p->gate_up_projection_m8_2row =
        [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    fprintf(stderr, "[prefill-nrow] routed gate+up candidate=M8-2row\n");
#endif
    fn = [library newFunctionWithName:@"grouped_swiglu"];
    p->swiglu = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    fn = [library newFunctionWithName:@"nrow_causal_attn_online"];
    p->full_attn_batch = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    if (!p->full_attn_batch) fprintf(stderr, "[prefill-nrow] batched causal attention pipeline unavailable\n");
    fn = [library newFunctionWithName:@"conv_chunk"];
    p->conv_chunk = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    fn = [library newFunctionWithName:@"split_qkv"];
    p->split_qkv = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    fn = [library newFunctionWithName:@"gdn_chunk"];
    p->gdn_chunk = [g_metal->device newComputePipelineStateWithFunction:fn error:&error];
    const size_t hidden_bytes = (size_t)PREFILL_NROW_ASSIGNMENTS *
        HIDDEN_DIM * sizeof(float);
    const size_t mid_bytes = (size_t)PREFILL_NROW_ASSIGNMENTS *
        MOE_INTERMEDIATE * sizeof(float);
    p->input = [g_metal->device newBufferWithLength:hidden_bytes options:MTLResourceStorageModeShared];
    p->gate = [g_metal->device newBufferWithLength:mid_bytes options:MTLResourceStorageModeShared];
    p->up = [g_metal->device newBufferWithLength:mid_bytes options:MTLResourceStorageModeShared];
    p->act = [g_metal->device newBufferWithLength:mid_bytes options:MTLResourceStorageModeShared];
    p->output = [g_metal->device newBufferWithLength:hidden_bytes options:MTLResourceStorageModeShared];
    p->shared_act_rows = [g_metal->device newBufferWithLength:
        (size_t)PREFILL_NROW_ROWS * SHARED_INTERMEDIATE * sizeof(float)
        options:MTLResourceStorageModeShared];
    p->shared_out_rows = [g_metal->device newBufferWithLength:
        (size_t)PREFILL_NROW_ROWS * HIDDEN_DIM * sizeof(float)
        options:MTLResourceStorageModeShared];
    p->shared_gate_rows = [g_metal->device newBufferWithLength:
        (size_t)PREFILL_NROW_ROWS * SHARED_INTERMEDIATE * sizeof(float)
        options:MTLResourceStorageModeShared];
    p->shared_up_rows = [g_metal->device newBufferWithLength:
        (size_t)PREFILL_NROW_ROWS * SHARED_INTERMEDIATE * sizeof(float)
        options:MTLResourceStorageModeShared];
    p->normed_rows = [g_metal->device newBufferWithLength:
        (size_t)PREFILL_NROW_ROWS * HIDDEN_DIM * sizeof(float)
        options:MTLResourceStorageModeShared];
    const size_t full_qproj_dim = (size_t)NUM_ATTN_HEADS * HEAD_DIM * 2u;
    const size_t full_kv_dim = (size_t)NUM_KV_HEADS * HEAD_DIM;
    p->full_qproj_rows = [g_metal->device newBufferWithLength:
        (size_t)PREFILL_NROW_ROWS * full_qproj_dim * sizeof(float)
        options:MTLResourceStorageModeShared];
    p->full_k_rows = [g_metal->device newBufferWithLength:
        (size_t)PREFILL_NROW_ROWS * full_kv_dim * sizeof(float)
        options:MTLResourceStorageModeShared];
    p->full_v_rows = [g_metal->device newBufferWithLength:
        (size_t)PREFILL_NROW_ROWS * full_kv_dim * sizeof(float)
        options:MTLResourceStorageModeShared];
    const size_t full_q_dim = (size_t)NUM_ATTN_HEADS * HEAD_DIM;
    p->full_q_rows = [g_metal->device newBufferWithLength:
        (size_t)PREFILL_NROW_ROWS * full_q_dim * sizeof(float)
        options:MTLResourceStorageModeShared];
    p->full_gate_rows = [g_metal->device newBufferWithLength:
        (size_t)PREFILL_NROW_ROWS * full_q_dim * sizeof(float)
        options:MTLResourceStorageModeShared];
    p->full_attn_rows = [g_metal->device newBufferWithLength:
        (size_t)PREFILL_NROW_ROWS * full_q_dim * sizeof(float)
        options:MTLResourceStorageModeShared];
    p->linear_oproj_rows = [g_metal->device newBufferWithLength:
        (size_t)PREFILL_NROW_ROWS * HIDDEN_DIM * sizeof(float)
        options:MTLResourceStorageModeShared];
    p->linear_hpost_rows = [g_metal->device newBufferWithLength:
        (size_t)PREFILL_NROW_ROWS * HIDDEN_DIM * sizeof(float)
        options:MTLResourceStorageModeShared];
    p->linear_gate_scores = [g_metal->device newBufferWithLength:
        (size_t)PREFILL_NROW_ROWS * NUM_EXPERTS * sizeof(float)
        options:MTLResourceStorageModeShared];
    p->linear_shared_scores = [g_metal->device newBufferWithLength:
        (size_t)PREFILL_NROW_ROWS * sizeof(float)
        options:MTLResourceStorageModeShared];
    size_t max_expert = max_expert_size_for_current_config();
    p->expert_stage_stride = (max_expert + 255u) & ~(size_t)255u;
    // Staging is per unique expert, not per routed assignment.  Size it from
    // the loaded model geometry rather than the generic compile-time capacity.
    // For Qwen3.5-35B-A3B at N128 this is min(1024 assignments, 256 experts) = 256.
    p->expert_stage_slots = (size_t)g_cfg.num_experts;
    if (p->expert_stage_slots > (size_t)PREFILL_NROW_ASSIGNMENTS)
        p->expert_stage_slots = (size_t)PREFILL_NROW_ASSIGNMENTS;
    if (p->expert_stage_slots == 0 ||
        p->expert_stage_slots > (size_t)MAX_EXPERTS ||
        p->expert_stage_stride == 0 ||
        p->expert_stage_stride > SIZE_MAX / p->expert_stage_slots) {
        fprintf(stderr, "[prefill-nrow] invalid expert staging geometry\n");
        return 0;
    }
    p->expert_stage = [g_metal->device newBufferWithLength:
        p->expert_stage_stride * p->expert_stage_slots
        options:MTLResourceStorageModeShared];
    const size_t qkv_bytes = (size_t)PREFILL_NROW_ROWS * LINEAR_CONV_DIM * sizeof(float);
    const size_t key_bytes = (size_t)PREFILL_NROW_ROWS * LINEAR_TOTAL_KEY * sizeof(float);
    const size_t value_bytes = (size_t)PREFILL_NROW_ROWS * LINEAR_TOTAL_VALUE * sizeof(float);
    const size_t head_bytes = (size_t)PREFILL_NROW_ROWS * LINEAR_NUM_V_HEADS * sizeof(float);
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
    return p->projection &&
#ifdef FLASH_PREFILL_NROW_DOWN_ACC16
        p->projection_acc16 &&
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_ACC32
        p->projection_acc32 &&
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_M4
        p->projection_m4 &&
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_M4_2ROW
        p->projection_m4_2row &&
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_M4_2ROW_BITSPLIT
        p->projection_m4_2row_q4 &&
        p->projection_m4_2row_q2 &&
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_M4_4ROW
        p->projection_m4_4row &&
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_2ROW
        p->down_2row_projection &&
#endif
#ifdef FLASH_PREFILL_NROW_DOWN_COOP_2ROW
        p->down_coop_2row_projection &&
#endif
        p->gate_up_projection &&
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_2ROW
        p->gate_up_projection_m4_2row &&
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_4ROW
        p->gate_up_projection_m4_4row &&
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_8ROW
        p->gate_up_projection_m4_8row &&
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_8ROW_BITSPLIT
        p->gate_up_projection_m4_8row_q4 &&
        p->gate_up_projection_m4_8row_q2 &&
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_8ROW_XCACHE
        p->gate_up_projection_m4_8row_xcache &&
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M4_16ROW
        p->gate_up_projection_m4_16row &&
#endif
#ifdef FLASH_PREFILL_NROW_GATEUP_M8_2ROW
        p->gate_up_projection_m8_2row &&
#endif
        p->swiglu && p->full_attn_batch &&
        p->conv_chunk && p->split_qkv &&
        p->gdn_chunk && p->input && p->gate && p->up && p->act && p->output &&
        p->shared_act_rows && p->shared_out_rows &&
        p->shared_gate_rows && p->shared_up_rows && p->normed_rows &&
        p->full_qproj_rows && p->full_k_rows && p->full_v_rows &&
        p->full_q_rows && p->full_gate_rows && p->full_attn_rows &&
        p->linear_oproj_rows && p->linear_hpost_rows &&
        p->linear_gate_scores && p->linear_shared_scores &&
        p->expert_stage && p->conv_input && p->conv_output && p->q && p->k && p->v && p->z &&
        p->alpha && p->beta && p->decay && p->beta_gate && p->gdn_output &&
        p->attn_output;
}


// Encode one projection family for all N rows into an existing compute encoder.
// This preserves the same production matvec kernels/weight formats while
// replacing N synchronous fast_batch_matvec submissions with GPU-ordered work
// in the linear layer's existing command buffer.
static int prefill_nrow_encode_dense_rows(
    id<MTLComputeCommandEncoder> enc,
    const void *W, const void *scales, const void *biases,
    uint8_t kind, uint8_t source,
    id<MTLBuffer> input, NSUInteger input_stride,
    id<MTLBuffer> output, NSUInteger output_stride,
    uint32_t out_dim, uint32_t in_dim, uint32_t group_size
) {
    if (!enc || !W || !input || !output || !g_metal) return 0;

    if (kind == MATVEC_KIND_GGUF_Q8_0) {
        const char *w_base = NULL;
        id<MTLBuffer> w_buf = matvec_source_buffer(g_metal, source, &w_base);
        if (!w_buf || !w_base || !g_metal->matvec_q8_0) return 0;
        NSUInteger w_off = (NSUInteger)((const char *)W - w_base);
        if ((const char *)W < w_base ||
            (size_t)w_off >= [w_buf length]) return 0;

        [enc setComputePipelineState:g_metal->matvec_q8_0];
        [enc setBuffer:w_buf offset:w_off atIndex:0];
        [enc setBytes:&out_dim length:4 atIndex:3];
        [enc setBytes:&in_dim length:4 atIndex:4];
        uint32_t num_tgs = (out_dim + 7) / 8;
        for (int row = 0; row < PREFILL_NROW_ROWS; row++) {
            [enc setBuffer:input offset:(NSUInteger)row * input_stride atIndex:1];
            [enc setBuffer:output offset:(NSUInteger)row * output_stride atIndex:2];
            [enc dispatchThreadgroups:MTLSizeMake(num_tgs, 1, 1)
                threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
        }
        return 1;
    }

    if (kind != MATVEC_KIND_MLX4 || source != MATVEC_SOURCE_WF ||
        !scales || !biases || !g_metal->wf_buf) return 0;

    const char *wf_base = (const char *)[g_metal->wf_buf contents];
    NSUInteger w_off = (NSUInteger)((const char *)W - wf_base);
    NSUInteger s_off = (NSUInteger)((const char *)scales - wf_base);
    NSUInteger b_off = (NSUInteger)((const char *)biases - wf_base);
    if ((const char *)W < wf_base || (const char *)scales < wf_base ||
        (const char *)biases < wf_base ||
        (size_t)w_off >= [g_metal->wf_buf length] ||
        (size_t)s_off >= [g_metal->wf_buf length] ||
        (size_t)b_off >= [g_metal->wf_buf length]) return 0;

    BatchMatvecSpec shape = {
        W, scales, biases, NULL, out_dim, in_dim, group_size, 0, kind, source
    };
    int use_v3 = tiny_matvec_select_v3(&shape);
    [enc setComputePipelineState:use_v3 ? g_metal->matvec_v3 : g_metal->matvec_fast];
    [enc setBuffer:g_metal->wf_buf offset:w_off atIndex:0];
    [enc setBuffer:g_metal->wf_buf offset:s_off atIndex:1];
    [enc setBuffer:g_metal->wf_buf offset:b_off atIndex:2];
    [enc setBytes:&out_dim length:4 atIndex:5];
    [enc setBytes:&in_dim length:4 atIndex:6];
    [enc setBytes:&group_size length:4 atIndex:7];

    for (int row = 0; row < PREFILL_NROW_ROWS; row++) {
        [enc setBuffer:input offset:(NSUInteger)row * input_stride atIndex:3];
        [enc setBuffer:output offset:(NSUInteger)row * output_stride atIndex:4];
        if (use_v3) {
            uint32_t num_tgs = (out_dim + 7) / 8;
            [enc dispatchThreadgroups:MTLSizeMake(num_tgs, 1, 1)
                threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
        } else {
            [enc dispatchThreadgroups:MTLSizeMake(out_dim, 1, 1)
                threadsPerThreadgroup:MTLSizeMake(64, 1, 1)];
        }
    }
    return 1;
}


// V4: project full-attention Q/K/V for all 16 rows in one command buffer.
// Downstream Q/K norm, RoPE, KV-cache publication, causal attention and o_proj
// deliberately remain on the existing row-wise path for this gate.
static int prefill_nrow_full_qkv_layer(PrefillNRowGrouped *p,
    int layer, const float *slab) {
    if (!p || !slab || !g_metal) return 0;
    LayerWeightCache *lc = &layer_cache[layer];
    if (!lc->input_norm_w || !lc->q_w || !lc->q_s || !lc->q_b ||
        !lc->k_w || !lc->k_s || !lc->k_b ||
        !lc->v_w || !lc->v_s || !lc->v_b) return 0;

    double started = now_ms();
    float *normed_rows = (float *)[p->normed_rows contents];
    for (int row = 0; row < PREFILL_NROW_ROWS; row++) {
        cpu_rms_norm(slab + (size_t)row * HIDDEN_DIM,
            lc->input_norm_w,
            normed_rows + (size_t)row * HIDDEN_DIM,
            HIDDEN_DIM, RMS_NORM_EPS);
    }

    const uint32_t q_proj_dim = (uint32_t)(NUM_ATTN_HEADS * HEAD_DIM * 2);
    const uint32_t kv_dim = (uint32_t)(NUM_KV_HEADS * HEAD_DIM);
    const NSUInteger norm_stride = (NSUInteger)HIDDEN_DIM * sizeof(float);
    id<MTLCommandBuffer> cmd = [g_metal->queue commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
    if (!enc) return 0;

    int encoded =
        prefill_nrow_encode_dense_rows(enc,
            lc->q_w, lc->q_s, lc->q_b, lc->q_kind, lc->q_source,
            p->normed_rows, norm_stride,
            p->full_qproj_rows, (NSUInteger)q_proj_dim * sizeof(float),
            q_proj_dim, HIDDEN_DIM, GROUP_SIZE) &&
        prefill_nrow_encode_dense_rows(enc,
            lc->k_w, lc->k_s, lc->k_b, lc->k_kind, lc->k_source,
            p->normed_rows, norm_stride,
            p->full_k_rows, (NSUInteger)kv_dim * sizeof(float),
            kv_dim, HIDDEN_DIM, GROUP_SIZE) &&
        prefill_nrow_encode_dense_rows(enc,
            lc->v_w, lc->v_s, lc->v_b, lc->v_kind, lc->v_source,
            p->normed_rows, norm_stride,
            p->full_v_rows, (NSUInteger)kv_dim * sizeof(float),
            kv_dim, HIDDEN_DIM, GROUP_SIZE);
    [enc endEncoding];
    if (!encoded) return 0;

    [cmd commit];
    [cmd waitUntilCompleted];
    p->full_qkv_ms += now_ms() - started;
    if (cmd.status != MTLCommandBufferStatusCompleted) {
        fprintf(stderr, "[prefill-nrow] full QKV batch failed: %s\n",
                cmd.error.localizedDescription.UTF8String);
        return 0;
    }
    return 1;
}


static __attribute__((unused)) int prefill_nrow_full_attention_batch(PrefillNRowGrouped *p,
    int layer, int base_pos, KVCache *kv) {
    if (!p || !kv || !g_metal || !p->full_attn_batch) return 0;
    LayerWeightCache *lc = &layer_cache[layer];
    if (!lc->q_norm_w || !lc->k_norm_w) return 0;

    const int q_dim = NUM_ATTN_HEADS * HEAD_DIM;
    const int q_proj_dim = q_dim * 2;
    const int kv_dim = NUM_KV_HEADS * HEAD_DIM;
    const int base_cache_pos = kv->len;
    if (!kv->k_cache || !kv->v_cache ||
        base_cache_pos < 0 ||
        base_cache_pos + PREFILL_NROW_ROWS > g_kv_seq_len ||
        base_cache_pos + PREFILL_NROW_ROWS > GPU_KV_SEQ) {
        fprintf(stderr,
            "[prefill-nrow] batched full attention cache range invalid base=%d rows=%d\n",
            base_cache_pos, PREFILL_NROW_ROWS);
        return 0;
    }

    float *qproj_rows = (float *)[p->full_qproj_rows contents];
    float *k_rows = (float *)[p->full_k_rows contents];
    float *v_rows = (float *)[p->full_v_rows contents];
    float *q_rows = (float *)[p->full_q_rows contents];
    float *gate_rows = (float *)[p->full_gate_rows contents];

    const double prep_started = now_ms();
    for (int row = 0; row < PREFILL_NROW_ROWS; row++) {
        float *qproj = qproj_rows + (size_t)row * q_proj_dim;
        float *q = q_rows + (size_t)row * q_dim;
        float *gate = gate_rows + (size_t)row * q_dim;
        float *k = k_rows + (size_t)row * kv_dim;
        float *v = v_rows + (size_t)row * kv_dim;

        for (int h = 0; h < NUM_ATTN_HEADS; h++) {
            float *src = qproj + h * (2 * HEAD_DIM);
            memcpy(q + h * HEAD_DIM, src, HEAD_DIM * sizeof(float));
            memcpy(gate + h * HEAD_DIM, src + HEAD_DIM, HEAD_DIM * sizeof(float));
        }

        for (int h = 0; h < NUM_ATTN_HEADS; h++) {
            float *qh = q + h * HEAD_DIM;
            float ss = 0.0f;
            for (int d = 0; d < HEAD_DIM; d++) ss += qh[d] * qh[d];
            float inv = 1.0f / sqrtf(ss / HEAD_DIM + RMS_NORM_EPS);
            for (int d = 0; d < HEAD_DIM; d++)
                qh[d] = qh[d] * inv * bf16_to_f32(lc->q_norm_w[d]);
        }
        for (int h = 0; h < NUM_KV_HEADS; h++) {
            float *kh = k + h * HEAD_DIM;
            float ss = 0.0f;
            for (int d = 0; d < HEAD_DIM; d++) ss += kh[d] * kh[d];
            float inv = 1.0f / sqrtf(ss / HEAD_DIM + RMS_NORM_EPS);
            for (int d = 0; d < HEAD_DIM; d++)
                kh[d] = kh[d] * inv * bf16_to_f32(lc->k_norm_w[d]);
        }

        apply_rotary_emb(q, k, base_pos + row,
            NUM_ATTN_HEADS, NUM_KV_HEADS, HEAD_DIM, ROTARY_DIM);

        const int cache_pos = base_cache_pos + row;
        memcpy(kv->k_cache + (size_t)cache_pos * kv_dim,
            k, (size_t)kv_dim * sizeof(float));
        memcpy(kv->v_cache + (size_t)cache_pos * kv_dim,
            v, (size_t)kv_dim * sizeof(float));
    }

    const int fa_idx = (layer + 1) / FULL_ATTN_INTERVAL - 1;
    if (fa_idx < 0 || fa_idx >= g_cfg.num_full_attn_layers ||
        !g_metal->buf_kv_k[fa_idx] || !g_metal->buf_kv_v[fa_idx])
        return 0;

    memcpy((float *)[g_metal->buf_kv_k[fa_idx] contents] +
            (size_t)base_cache_pos * kv_dim,
        k_rows,
        (size_t)PREFILL_NROW_ROWS * kv_dim * sizeof(float));
    memcpy((float *)[g_metal->buf_kv_v[fa_idx] contents] +
            (size_t)base_cache_pos * kv_dim,
        v_rows,
        (size_t)PREFILL_NROW_ROWS * kv_dim * sizeof(float));
    kv->len = base_cache_pos + PREFILL_NROW_ROWS;

    const double gpu_started = now_ms();
    id<MTLCommandBuffer> cmd = [g_metal->queue commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
    if (!enc) return 0;

    uint32_t rows = PREFILL_NROW_ROWS;
    uint32_t num_heads = NUM_ATTN_HEADS;
    uint32_t head_dim = HEAD_DIM;
    uint32_t kv_dim_u = (uint32_t)kv_dim;
    uint32_t base_len = (uint32_t)base_cache_pos;
    uint32_t heads_per_kv = NUM_ATTN_HEADS / NUM_KV_HEADS;
    float scale = 1.0f / sqrtf((float)HEAD_DIM);

    [enc setComputePipelineState:p->full_attn_batch];
    [enc setBuffer:p->full_q_rows offset:0 atIndex:0];
    [enc setBuffer:g_metal->buf_kv_k[fa_idx] offset:0 atIndex:1];
    [enc setBuffer:g_metal->buf_kv_v[fa_idx] offset:0 atIndex:2];
    [enc setBuffer:p->full_gate_rows offset:0 atIndex:3];
    [enc setBuffer:p->full_attn_rows offset:0 atIndex:4];
    [enc setBytes:&rows length:4 atIndex:5];
    [enc setBytes:&num_heads length:4 atIndex:6];
    [enc setBytes:&head_dim length:4 atIndex:7];
    [enc setBytes:&kv_dim_u length:4 atIndex:8];
    [enc setBytes:&base_len length:4 atIndex:9];
    [enc setBytes:&heads_per_kv length:4 atIndex:10];
    [enc setBytes:&scale length:4 atIndex:11];
    [enc dispatchThreadgroups:MTLSizeMake((NSUInteger)rows * num_heads, 1, 1)
        threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
    [enc endEncoding];
    [cmd commit];
    [cmd waitUntilCompleted];
    if (cmd.status != MTLCommandBufferStatusCompleted) {
        fprintf(stderr, "[prefill-nrow] batched causal attention failed: %s\n",
            cmd.error.localizedDescription.UTF8String);
        return 0;
    }

    fprintf(stderr,
        "[prefill-nrow-attn128] layer=%d base=%d prep=%.3fms gpu=%.3fms\n",
        layer, base_cache_pos,
        gpu_started - prep_started, now_ms() - gpu_started);
    return 1;
}

static int prefill_nrow_linear_layer(PrefillNRowGrouped *p, WeightFile *wf,
    int layer, const float *slab) {
    (void)wf;
    LayerWeightCache *lc = &layer_cache[layer];
    int li = layer - (layer + 1) / FULL_ATTN_INTERVAL;
    if (li < 0 || li >= g_cfg.num_linear_layers || !lc->conv1d_w ||
        !lc->A_log || !lc->dt_bias || !lc->gated_norm_w) return 0;
    if (!lc->qkv_w || !lc->z_w || !lc->b_w || !lc->a_w ||
        !lc->input_norm_w) return 0;

    double started = now_ms();
    float *normed_rows = (float *)[p->normed_rows contents];
    for (int row = 0; row < PREFILL_NROW_ROWS; row++) {
        cpu_rms_norm(slab + (size_t)row * HIDDEN_DIM,
            lc->input_norm_w,
            normed_rows + (size_t)row * HIDDEN_DIM,
            HIDDEN_DIM, RMS_NORM_EPS);
    }

    id<MTLCommandBuffer> cmd = [g_metal->queue commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
    if (!enc) return 0;

    const NSUInteger norm_stride = (NSUInteger)HIDDEN_DIM * sizeof(float);
    if (!prefill_nrow_encode_dense_rows(enc,
            lc->qkv_w, lc->qkv_s, lc->qkv_b,
            lc->qkv_kind, lc->qkv_source,
            p->normed_rows, norm_stride,
            p->conv_input, (NSUInteger)LINEAR_CONV_DIM * sizeof(float),
            (uint32_t)LINEAR_CONV_DIM, HIDDEN_DIM, GROUP_SIZE) ||
        !prefill_nrow_encode_dense_rows(enc,
            lc->z_w, lc->z_s, lc->z_b,
            lc->z_kind, lc->z_source,
            p->normed_rows, norm_stride,
            p->z, (NSUInteger)LINEAR_TOTAL_VALUE * sizeof(float),
            (uint32_t)LINEAR_TOTAL_VALUE, HIDDEN_DIM, GROUP_SIZE) ||
        !prefill_nrow_encode_dense_rows(enc,
            lc->b_w, lc->b_s, lc->b_b,
            MATVEC_KIND_MLX4, MATVEC_SOURCE_WF,
            p->normed_rows, norm_stride,
            p->beta, (NSUInteger)LINEAR_NUM_V_HEADS * sizeof(float),
            (uint32_t)LINEAR_NUM_V_HEADS, HIDDEN_DIM, GROUP_SIZE) ||
        !prefill_nrow_encode_dense_rows(enc,
            lc->a_w, lc->a_s, lc->a_b,
            MATVEC_KIND_MLX4, MATVEC_SOURCE_WF,
            p->normed_rows, norm_stride,
            p->alpha, (NSUInteger)LINEAR_NUM_V_HEADS * sizeof(float),
            (uint32_t)LINEAR_NUM_V_HEADS, HIDDEN_DIM, GROUP_SIZE)) {
        [enc endEncoding];
        return 0;
    }
    [enc endEncoding];

    // Projection outputs are consumed by the remaining encoders in this same
    // command buffer.  Metal command-buffer ordering supplies the dependency;
    // no CPU-visible completion is needed between QKV/Z/beta/alpha and conv/GDN.
    enc = [cmd computeCommandEncoder];
    [enc setComputePipelineState:p->conv_chunk];
    [enc setBuffer:g_metal->buf_conv_state[li] offset:0 atIndex:0];
    [enc setBuffer:p->conv_input offset:0 atIndex:1];
    NSUInteger conv_w_off = (NSUInteger)((const char *)lc->conv1d_w -
        (const char *)[g_metal->wf_buf contents]);
    [enc setBuffer:g_metal->wf_buf offset:conv_w_off atIndex:2];
    [enc setBuffer:p->conv_output offset:0 atIndex:3];
    uint32_t n = PREFILL_NROW_ROWS;
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
    for (int row = 0; row < PREFILL_NROW_ROWS; row++) {
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
    for (int row = 0; row < PREFILL_NROW_ROWS; row++) {
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

#if !defined(FLASH_PREFILL_NROW_DOWN_M4) && \
    !defined(FLASH_PREFILL_NROW_DOWN_M4_2ROW) && \
    !defined(FLASH_PREFILL_NROW_DOWN_M4_4ROW) && \
    !defined(FLASH_PREFILL_NROW_DOWN_2ROW) && \
    !defined(FLASH_PREFILL_NROW_DOWN_COOP_2ROW)
static void prefill_nrow_encode_projection(id<MTLCommandBuffer> cmd,
    PrefillNRowGrouped *p, id<MTLBuffer> data, NSUInteger data_base,
    NSUInteger w, NSUInteger s, NSUInteger b,
    id<MTLBuffer> input, NSUInteger input_offset,
    id<MTLBuffer> output, NSUInteger output_offset,
    uint32_t in_dim, uint32_t out_dim, uint32_t count, uint32_t bits) {
    id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
#ifdef FLASH_PREFILL_NROW_DOWN_ACC16
    [enc setComputePipelineState:p->projection_acc16];
#elif defined(FLASH_PREFILL_NROW_DOWN_ACC32)
    [enc setComputePipelineState:p->projection_acc32];
#else
    [enc setComputePipelineState:p->projection];
#endif
    [enc setBuffer:data offset:data_base + w atIndex:0];
    [enc setBuffer:data offset:data_base + s atIndex:1];
    [enc setBuffer:data offset:data_base + b atIndex:2];
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
#endif

#ifdef FLASH_PREFILL_NROW_DOWN_M4
// V12A fixed-M=4 routed-down encoder.  One SIMD workgroup
// handles one output row and one tile of up to four activations.
static void prefill_nrow_encode_down_m4(id<MTLCommandBuffer> cmd,
    PrefillNRowGrouped *p, id<MTLBuffer> data, NSUInteger data_base,
    NSUInteger w, NSUInteger s, NSUInteger b,
    id<MTLBuffer> input, NSUInteger input_offset,
    id<MTLBuffer> output, NSUInteger output_offset,
    uint32_t in_dim, uint32_t out_dim, uint32_t count, uint32_t bits) {
    id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
    [enc setComputePipelineState:p->projection_m4];
    [enc setBuffer:data offset:data_base + w atIndex:0];
    [enc setBuffer:data offset:data_base + s atIndex:1];
    [enc setBuffer:data offset:data_base + b atIndex:2];
    [enc setBuffer:input offset:input_offset atIndex:3];
    [enc setBuffer:output offset:output_offset atIndex:4];
    [enc setBytes:&in_dim length:4 atIndex:5];
    [enc setBytes:&out_dim length:4 atIndex:6];
    [enc setBytes:&count length:4 atIndex:7];
    [enc setBytes:&bits length:4 atIndex:8];
    [enc dispatchThreadgroups:MTLSizeMake(out_dim, (count + 3u) / 4u, 1)
        threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
    [enc endEncoding];
}
#endif

#ifdef FLASH_PREFILL_NROW_DOWN_M4_2ROW
// V12C accepted production occupancy midpoint: two output rows per 64-thread TG.
static void prefill_nrow_encode_down_m4_2row(id<MTLCommandBuffer> cmd,
    PrefillNRowGrouped *p, id<MTLBuffer> data, NSUInteger data_base,
    NSUInteger w, NSUInteger s, NSUInteger b,
    id<MTLBuffer> input, NSUInteger input_offset,
    id<MTLBuffer> output, NSUInteger output_offset,
    uint32_t in_dim, uint32_t out_dim, uint32_t count, uint32_t bits) {
    id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
    [enc setComputePipelineState:p->projection_m4_2row];
    [enc setBuffer:data offset:data_base + w atIndex:0];
    [enc setBuffer:data offset:data_base + s atIndex:1];
    [enc setBuffer:data offset:data_base + b atIndex:2];
    [enc setBuffer:input offset:input_offset atIndex:3];
    [enc setBuffer:output offset:output_offset atIndex:4];
    [enc setBytes:&in_dim length:4 atIndex:5];
    [enc setBytes:&out_dim length:4 atIndex:6];
    [enc setBytes:&count length:4 atIndex:7];
    [enc setBytes:&bits length:4 atIndex:8];
    [enc dispatchThreadgroups:MTLSizeMake((out_dim + 1u) / 2u, (count + 3u) / 4u, 1)
        threadsPerThreadgroup:MTLSizeMake(64, 1, 1)];
    [enc endEncoding];
}
#endif

#ifdef FLASH_PREFILL_NROW_DOWN_M4_2ROW_BITSPLIT
// Fixed-bit specialization of the accepted M4-2row routed-down geometry.
// Q4 and Q2 use separate pipelines so unpack width, masks, and shifts are
// compiler constants while row packing, activation order, and reductions stay
// identical to the accepted dynamic-bit kernel.
static void prefill_nrow_encode_down_m4_2row_bitsplit(id<MTLCommandBuffer> cmd,
    PrefillNRowGrouped *p, id<MTLBuffer> data, NSUInteger data_base,
    NSUInteger w, NSUInteger s, NSUInteger b,
    id<MTLBuffer> input, NSUInteger input_offset,
    id<MTLBuffer> output, NSUInteger output_offset,
    uint32_t in_dim, uint32_t out_dim, uint32_t count, uint32_t bits) {
    id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
    [enc setComputePipelineState:(bits == 4u)
        ? p->projection_m4_2row_q4 : p->projection_m4_2row_q2];
    [enc setBuffer:data offset:data_base + w atIndex:0];
    [enc setBuffer:data offset:data_base + s atIndex:1];
    [enc setBuffer:data offset:data_base + b atIndex:2];
    [enc setBuffer:input offset:input_offset atIndex:3];
    [enc setBuffer:output offset:output_offset atIndex:4];
    [enc setBytes:&in_dim length:4 atIndex:5];
    [enc setBytes:&out_dim length:4 atIndex:6];
    [enc setBytes:&count length:4 atIndex:7];
    [enc setBytes:&bits length:4 atIndex:8];
    [enc dispatchThreadgroups:MTLSizeMake((out_dim + 1u) / 2u,
                                          (count + 3u) / 4u, 1)
        threadsPerThreadgroup:MTLSizeMake(64, 1, 1)];
    [enc endEncoding];
}
#endif

#ifdef FLASH_PREFILL_NROW_DOWN_M4_4ROW
// V12B benchmark-only occupancy variant: four output rows per 128-thread TG.
static void prefill_nrow_encode_down_m4_4row(id<MTLCommandBuffer> cmd,
    PrefillNRowGrouped *p, id<MTLBuffer> data, NSUInteger data_base,
    NSUInteger w, NSUInteger s, NSUInteger b,
    id<MTLBuffer> input, NSUInteger input_offset,
    id<MTLBuffer> output, NSUInteger output_offset,
    uint32_t in_dim, uint32_t out_dim, uint32_t count, uint32_t bits) {
    id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
    [enc setComputePipelineState:p->projection_m4_4row];
    [enc setBuffer:data offset:data_base + w atIndex:0];
    [enc setBuffer:data offset:data_base + s atIndex:1];
    [enc setBuffer:data offset:data_base + b atIndex:2];
    [enc setBuffer:input offset:input_offset atIndex:3];
    [enc setBuffer:output offset:output_offset atIndex:4];
    [enc setBytes:&in_dim length:4 atIndex:5];
    [enc setBytes:&out_dim length:4 atIndex:6];
    [enc setBytes:&count length:4 atIndex:7];
    [enc setBytes:&bits length:4 atIndex:8];
    [enc dispatchThreadgroups:MTLSizeMake((out_dim + 3u) / 4u, (count + 3u) / 4u, 1)
        threadsPerThreadgroup:MTLSizeMake(128, 1, 1)];
    [enc endEncoding];
}
#endif

#ifdef FLASH_PREFILL_NROW_DOWN_2ROW
// V8 benchmark-only routed down encoder.  Arithmetic/output layout is
// identical to prefill_nrow_encode_projection; only dispatch geometry changes.
static void prefill_nrow_encode_down_2row(id<MTLCommandBuffer> cmd,
    PrefillNRowGrouped *p, id<MTLBuffer> data, NSUInteger data_base,
    NSUInteger w, NSUInteger s, NSUInteger b,
    id<MTLBuffer> input, NSUInteger input_offset,
    id<MTLBuffer> output, NSUInteger output_offset,
    uint32_t in_dim, uint32_t out_dim, uint32_t count, uint32_t bits) {
    id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
    [enc setComputePipelineState:p->down_2row_projection];
    [enc setBuffer:data offset:data_base + w atIndex:0];
    [enc setBuffer:data offset:data_base + s atIndex:1];
    [enc setBuffer:data offset:data_base + b atIndex:2];
    [enc setBuffer:input offset:input_offset atIndex:3];
    [enc setBuffer:output offset:output_offset atIndex:4];
    [enc setBytes:&in_dim length:4 atIndex:5];
    [enc setBytes:&out_dim length:4 atIndex:6];
    [enc setBytes:&count length:4 atIndex:7];
    [enc setBytes:&bits length:4 atIndex:8];
    [enc dispatchThreadgroups:MTLSizeMake((out_dim + 1u) / 2u, 1, 1)
        threadsPerThreadgroup:MTLSizeMake(64, 1, 1)];
    [enc endEncoding];
}
#endif

#ifdef FLASH_PREFILL_NROW_DOWN_COOP_2ROW
// V9 benchmark-only routed down encoder.  V8's two-row geometry is retained,
// but one dynamic threadgroup cache holds the count x 512 activation slab so
// both SIMD groups reuse the same global activation reads.
static void prefill_nrow_encode_down_coop_2row(id<MTLCommandBuffer> cmd,
    PrefillNRowGrouped *p, id<MTLBuffer> data, NSUInteger data_base,
    NSUInteger w, NSUInteger s, NSUInteger b,
    id<MTLBuffer> input, NSUInteger input_offset,
    id<MTLBuffer> output, NSUInteger output_offset,
    uint32_t in_dim, uint32_t out_dim, uint32_t count, uint32_t bits) {
    id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
    [enc setComputePipelineState:p->down_coop_2row_projection];
    [enc setBuffer:data offset:data_base + w atIndex:0];
    [enc setBuffer:data offset:data_base + s atIndex:1];
    [enc setBuffer:data offset:data_base + b atIndex:2];
    [enc setBuffer:input offset:input_offset atIndex:3];
    [enc setBuffer:output offset:output_offset atIndex:4];
    [enc setBytes:&in_dim length:4 atIndex:5];
    [enc setBytes:&out_dim length:4 atIndex:6];
    [enc setBytes:&count length:4 atIndex:7];
    [enc setBytes:&bits length:4 atIndex:8];
    const NSUInteger tg_bytes = (NSUInteger)count * (NSUInteger)in_dim * sizeof(float);
    [enc setThreadgroupMemoryLength:tg_bytes atIndex:0];
    [enc dispatchThreadgroups:MTLSizeMake((out_dim + 1u) / 2u, 1, 1)
        threadsPerThreadgroup:MTLSizeMake(64, 1, 1)];
    [enc endEncoding];
}
#endif


// V6: encode gate and up together for one routed expert group. The expert's
// quantization bit width applies to all three routed projections, so both
// projection families share in_dim/out_dim/count/bits while retaining their
// own packed weight/scale/bias ranges.
static void prefill_nrow_encode_gate_up(id<MTLCommandBuffer> cmd,
    PrefillNRowGrouped *p, id<MTLBuffer> data, NSUInteger data_base,
    NSUInteger gate_w, NSUInteger gate_s, NSUInteger gate_b,
    NSUInteger up_w, NSUInteger up_s, NSUInteger up_b,
    id<MTLBuffer> input, NSUInteger input_offset,
    id<MTLBuffer> gate_output, NSUInteger gate_output_offset,
    id<MTLBuffer> up_output, NSUInteger up_output_offset,
    uint32_t in_dim, uint32_t out_dim, uint32_t count, uint32_t bits) {
    id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
#ifdef FLASH_PREFILL_NROW_GATEUP_M8_2ROW
    [enc setComputePipelineState:p->gate_up_projection_m8_2row];
#elif defined(FLASH_PREFILL_NROW_GATEUP_M4_16ROW)
    [enc setComputePipelineState:p->gate_up_projection_m4_16row];
#elif defined(FLASH_PREFILL_NROW_GATEUP_M4_8ROW_XCACHE)
    [enc setComputePipelineState:p->gate_up_projection_m4_8row_xcache];
#elif defined(FLASH_PREFILL_NROW_GATEUP_M4_8ROW_BITSPLIT)
    [enc setComputePipelineState:(bits == 4u
        ? p->gate_up_projection_m4_8row_q4
        : p->gate_up_projection_m4_8row_q2)];
#elif defined(FLASH_PREFILL_NROW_GATEUP_M4_8ROW)
    [enc setComputePipelineState:p->gate_up_projection_m4_8row];
#elif defined(FLASH_PREFILL_NROW_GATEUP_M4_4ROW)
    [enc setComputePipelineState:p->gate_up_projection_m4_4row];
#elif defined(FLASH_PREFILL_NROW_GATEUP_M4_2ROW)
    [enc setComputePipelineState:p->gate_up_projection_m4_2row];
#else
    [enc setComputePipelineState:p->gate_up_projection];
#endif
    [enc setBuffer:data offset:data_base + gate_w atIndex:0];
    [enc setBuffer:data offset:data_base + gate_s atIndex:1];
    [enc setBuffer:data offset:data_base + gate_b atIndex:2];
    [enc setBuffer:data offset:data_base + up_w atIndex:3];
    [enc setBuffer:data offset:data_base + up_s atIndex:4];
    [enc setBuffer:data offset:data_base + up_b atIndex:5];
    [enc setBuffer:input offset:input_offset atIndex:6];
    [enc setBuffer:gate_output offset:gate_output_offset atIndex:7];
    [enc setBuffer:up_output offset:up_output_offset atIndex:8];
    [enc setBytes:&in_dim length:4 atIndex:9];
    [enc setBytes:&out_dim length:4 atIndex:10];
    [enc setBytes:&count length:4 atIndex:11];
    [enc setBytes:&bits length:4 atIndex:12];
#ifdef FLASH_PREFILL_NROW_GATEUP_M8_2ROW
    [enc dispatchThreadgroups:
        MTLSizeMake((out_dim + 1u) / 2u, (count + 7u) / 8u, 1)
        threadsPerThreadgroup:MTLSizeMake(64, 1, 1)];
#elif defined(FLASH_PREFILL_NROW_GATEUP_M4_16ROW)
    [enc dispatchThreadgroups:
        MTLSizeMake((out_dim + 15u) / 16u, (count + 3u) / 4u, 1)
        threadsPerThreadgroup:MTLSizeMake(512, 1, 1)];
#elif defined(FLASH_PREFILL_NROW_GATEUP_M4_8ROW_XCACHE)
    [enc setThreadgroupMemoryLength:(NSUInteger)(4u * 512u * sizeof(float)) atIndex:0];
    [enc dispatchThreadgroups:
        MTLSizeMake((out_dim + 7u) / 8u, (count + 3u) / 4u, 1)
        threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
#elif defined(FLASH_PREFILL_NROW_GATEUP_M4_8ROW_BITSPLIT)
    [enc dispatchThreadgroups:
        MTLSizeMake((out_dim + 7u) / 8u, (count + 3u) / 4u, 1)
        threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
#elif defined(FLASH_PREFILL_NROW_GATEUP_M4_8ROW)
    [enc dispatchThreadgroups:
        MTLSizeMake((out_dim + 7u) / 8u, (count + 3u) / 4u, 1)
        threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
#elif defined(FLASH_PREFILL_NROW_GATEUP_M4_4ROW)
    [enc dispatchThreadgroups:
        MTLSizeMake((out_dim + 3u) / 4u, (count + 3u) / 4u, 1)
        threadsPerThreadgroup:MTLSizeMake(128, 1, 1)];
#elif defined(FLASH_PREFILL_NROW_GATEUP_M4_2ROW)
    [enc dispatchThreadgroups:
        MTLSizeMake((out_dim + 1u) / 2u, (count + 3u) / 4u, 1)
        threadsPerThreadgroup:MTLSizeMake(64, 1, 1)];
#else
    [enc dispatchThreadgroups:MTLSizeMake(out_dim, 1, 1)
        threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
#endif
    [enc endEncoding];
}


// Encode the shared-expert down projection for the full N-row slab into one
// command buffer. It supports both the native MLX4 shared weights and the
// optional GGUF Q8_0 shared overlay used by LayerWeightCache.
static int prefill_nrow_encode_shared_down(
    PrefillNRowGrouped *p,
    id<MTLCommandBuffer> cmd,
    LayerWeightCache *lc
) {
    if (!p || !cmd || !lc || !g_metal || !lc->sd_w) return 0;

    const uint32_t out_dim = HIDDEN_DIM;
    const uint32_t in_dim = SHARED_INTERMEDIATE;
    const uint32_t group_size = GROUP_SIZE;
    id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
    if (!enc) return 0;

    if (lc->sd_kind == MATVEC_KIND_GGUF_Q8_0) {
        const char *w_base = NULL;
        id<MTLBuffer> w_buf =
            matvec_source_buffer(g_metal, lc->sd_source, &w_base);
        if (!w_buf || !w_base || !g_metal->matvec_q8_0) {
            [enc endEncoding];
            return 0;
        }
        NSUInteger w_off =
            (NSUInteger)((const char *)lc->sd_w - w_base);
        [enc setComputePipelineState:g_metal->matvec_q8_0];
        [enc setBuffer:w_buf offset:w_off atIndex:0];
        [enc setBytes:&out_dim length:4 atIndex:3];
        [enc setBytes:&in_dim length:4 atIndex:4];

        uint32_t num_tgs = (out_dim + 7) / 8;
        for (int row = 0; row < PREFILL_NROW_ROWS; row++) {
            NSUInteger in_off = (NSUInteger)((size_t)row *
                SHARED_INTERMEDIATE * sizeof(float));
            NSUInteger out_off = (NSUInteger)((size_t)row *
                HIDDEN_DIM * sizeof(float));
            [enc setBuffer:p->shared_act_rows offset:in_off atIndex:1];
            [enc setBuffer:p->shared_out_rows offset:out_off atIndex:2];
            [enc dispatchThreadgroups:MTLSizeMake(num_tgs, 1, 1)
                threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
        }
    } else {
        // The native non-Q8 shared overlay is the production MLX4 triplet in
        // wf_buf.  Fail closed for an unexpected kind/source rather than
        // silently changing arithmetic.
        if (lc->sd_kind != MATVEC_KIND_MLX4 ||
            lc->sd_source != MATVEC_SOURCE_WF ||
            !lc->sd_s || !lc->sd_b || !g_metal->wf_buf) {
            [enc endEncoding];
            return 0;
        }
        const char *wf_base = (const char *)[g_metal->wf_buf contents];
        NSUInteger w_off =
            (NSUInteger)((const char *)lc->sd_w - wf_base);
        NSUInteger s_off =
            (NSUInteger)((const char *)lc->sd_s - wf_base);
        NSUInteger b_off =
            (NSUInteger)((const char *)lc->sd_b - wf_base);

        // SHARED_INTERMEDIATE=512, so the same V3 kernel selected by the
        // synchronous production helper is valid here.
        [enc setComputePipelineState:g_metal->matvec_v3];
        [enc setBuffer:g_metal->wf_buf offset:w_off atIndex:0];
        [enc setBuffer:g_metal->wf_buf offset:s_off atIndex:1];
        [enc setBuffer:g_metal->wf_buf offset:b_off atIndex:2];
        [enc setBytes:&out_dim length:4 atIndex:5];
        [enc setBytes:&in_dim length:4 atIndex:6];
        [enc setBytes:&group_size length:4 atIndex:7];

        uint32_t num_tgs = (out_dim + 7) / 8;
        for (int row = 0; row < PREFILL_NROW_ROWS; row++) {
            NSUInteger in_off = (NSUInteger)((size_t)row *
                SHARED_INTERMEDIATE * sizeof(float));
            NSUInteger out_off = (NSUInteger)((size_t)row *
                HIDDEN_DIM * sizeof(float));
            [enc setBuffer:p->shared_act_rows offset:in_off atIndex:3];
            [enc setBuffer:p->shared_out_rows offset:out_off atIndex:4];
            [enc dispatchThreadgroups:MTLSizeMake(num_tgs, 1, 1)
                threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
        }
    }
    [enc endEncoding];
    return 1;
}

// Batch the linear layer's post-GDN work for the complete N128 slab.
// Recurrence state has already been advanced by prefill_nrow_linear_layer().
// This replaces 128 one-row CMD2/router submissions with two slab-level command
// buffers while preserving the existing CPU top-K and grouped-expert semantics.
static __attribute__((unused)) int prefill_nrow_linear_post_capture(PrefillNRowGrouped *p,
    PrefillNRowCapture *cap, int layer, const float *slab) {
    if (!p || !cap || !slab || !g_metal) return 0;
    LayerWeightCache *lc = &layer_cache[layer];
    if (!lc->out_proj_w || !lc->post_attn_norm_w ||
        !lc->gate_w || !lc->gate_s || !lc->gate_b ||
        !lc->sg_w || !lc->sg_s || !lc->sg_b ||
        !lc->su_w || !lc->su_s || !lc->su_b ||
        !lc->seg_w || !lc->seg_s || !lc->seg_b) return 0;

    const NSUInteger lin_stride = (NSUInteger)LINEAR_TOTAL_VALUE * sizeof(float);
    const NSUInteger hidden_stride = (NSUInteger)HIDDEN_DIM * sizeof(float);
    id<MTLCommandBuffer> oproj_cmd = [g_metal->queue commandBuffer];
    id<MTLComputeCommandEncoder> enc = [oproj_cmd computeCommandEncoder];
    if (!enc) return 0;
    int encoded = prefill_nrow_encode_dense_rows(enc,
        lc->out_proj_w, lc->out_proj_s, lc->out_proj_b,
        lc->out_proj_kind, lc->out_proj_source,
        p->attn_output, lin_stride,
        p->linear_oproj_rows, hidden_stride,
        HIDDEN_DIM, LINEAR_TOTAL_VALUE, GROUP_SIZE);
    [enc endEncoding];
    if (!encoded) return 0;
    [oproj_cmd commit];
    [oproj_cmd waitUntilCompleted];
    if (oproj_cmd.status != MTLCommandBufferStatusCompleted) {
        fprintf(stderr, "[prefill-nrow] linear post out_proj batch failed: %s\n",
            oproj_cmd.error.localizedDescription.UTF8String);
        return 0;
    }

    const float *oproj = (const float *)[p->linear_oproj_rows contents];
    float *hpost_rows = (float *)[p->linear_hpost_rows contents];
    for (int row = 0; row < PREFILL_NROW_ROWS; row++) {
        const float *src = slab + (size_t)row * HIDDEN_DIM;
        const float *proj = oproj + (size_t)row * HIDDEN_DIM;
        float *mid = cap->h_mid[row];
        float *post = hpost_rows + (size_t)row * HIDDEN_DIM;
        for (int i = 0; i < HIDDEN_DIM; i++) mid[i] = src[i] + proj[i];
        cpu_rms_norm(mid, lc->post_attn_norm_w, post, HIDDEN_DIM, RMS_NORM_EPS);
        memcpy(cap->h_post[row], post, HIDDEN_DIM * sizeof(float));
    }

    id<MTLCommandBuffer> route_cmd = [g_metal->queue commandBuffer];
    enc = [route_cmd computeCommandEncoder];
    if (!enc) return 0;
    encoded =
        prefill_nrow_encode_dense_rows(enc,
            lc->gate_w, lc->gate_s, lc->gate_b,
            MATVEC_KIND_MLX4, MATVEC_SOURCE_WF,
            p->linear_hpost_rows, hidden_stride,
            p->linear_gate_scores, (NSUInteger)NUM_EXPERTS * sizeof(float),
            NUM_EXPERTS, HIDDEN_DIM, GROUP_SIZE) &&
        prefill_nrow_encode_dense_rows(enc,
            lc->sg_w, lc->sg_s, lc->sg_b, lc->sg_kind, lc->sg_source,
            p->linear_hpost_rows, hidden_stride,
            p->shared_gate_rows, (NSUInteger)SHARED_INTERMEDIATE * sizeof(float),
            SHARED_INTERMEDIATE, HIDDEN_DIM, GROUP_SIZE) &&
        prefill_nrow_encode_dense_rows(enc,
            lc->su_w, lc->su_s, lc->su_b, lc->su_kind, lc->su_source,
            p->linear_hpost_rows, hidden_stride,
            p->shared_up_rows, (NSUInteger)SHARED_INTERMEDIATE * sizeof(float),
            SHARED_INTERMEDIATE, HIDDEN_DIM, GROUP_SIZE) &&
        prefill_nrow_encode_dense_rows(enc,
            lc->seg_w, lc->seg_s, lc->seg_b,
            MATVEC_KIND_MLX4, MATVEC_SOURCE_WF,
            p->linear_hpost_rows, hidden_stride,
            p->linear_shared_scores, sizeof(float),
            1, HIDDEN_DIM, GROUP_SIZE);
    [enc endEncoding];
    if (!encoded) return 0;
    [route_cmd commit];
    [route_cmd waitUntilCompleted];
    if (route_cmd.status != MTLCommandBufferStatusCompleted) {
        fprintf(stderr, "[prefill-nrow] linear post router batch failed: %s\n",
            route_cmd.error.localizedDescription.UTF8String);
        return 0;
    }

    const float *gate_scores = (const float *)[p->linear_gate_scores contents];
    const float *sg = (const float *)[p->shared_gate_rows contents];
    const float *su = (const float *)[p->shared_up_rows contents];
    const float *ss = (const float *)[p->linear_shared_scores contents];
    for (int row = 0; row < PREFILL_NROW_ROWS; row++) {
        cpu_topk_softmax_raw(
            gate_scores + (size_t)row * NUM_EXPERTS, NUM_EXPERTS,
            PREFILL_NROW_K, cap->expert_id[row], cap->expert_weight[row]);
        memcpy(cap->shared_gate[row],
            sg + (size_t)row * SHARED_INTERMEDIATE,
            SHARED_INTERMEDIATE * sizeof(float));
        memcpy(cap->shared_up[row],
            su + (size_t)row * SHARED_INTERMEDIATE,
            SHARED_INTERMEDIATE * sizeof(float));
        cap->shared_score[row] = ss[row];
    }
    return 1;
}

static int prefill_nrow_grouped_layer(PrefillNRowGrouped *p,
    PrefillNRowCapture *cap, int layer, int packed_fd,
    const void *mmap_base, float *slab) {
    if (!g_use_tiered || !g_tiered_manifest ||
        cap->count != PREFILL_NROW_ROWS || packed_fd < 0)
        return 0;

    double group_started = now_ms();
    int unique_ids[PREFILL_NROW_ASSIGNMENTS], unique_count = 0;
    for (int row = 0; row < PREFILL_NROW_ROWS; row++) {
        for (int k = 0; k < PREFILL_NROW_K; k++) {
            int e = cap->expert_id[row][k];
            int found = 0;
            for (int j = 0; j < unique_count; j++) {
                if (unique_ids[j] == e) { found = 1; break; }
            }
            if (!found) unique_ids[unique_count++] = e;
        }
    }
    p->grouping_ms += now_ms() - group_started;
    p->groups += unique_count;
    p->repeated += PREFILL_NROW_ASSIGNMENTS - unique_count;

    // Pack routed assignments by expert.  Every route slot owns exactly one
    // packed row, so all expert groups can use disjoint offsets in the same
    // input/gate/up/act/output buffers.
    int group_start[PREFILL_NROW_ASSIGNMENTS];
    int group_count[PREFILL_NROW_ASSIGNMENTS];
    int assignment_index[PREFILL_NROW_ROWS][PREFILL_NROW_K];
    memset(assignment_index, 0xff, sizeof(assignment_index));
    int packed_rows = 0;
    for (int group = 0; group < unique_count; group++) {
        int e = unique_ids[group];
        group_start[group] = packed_rows;
        for (int row = 0; row < PREFILL_NROW_ROWS; row++) {
            for (int k = 0; k < PREFILL_NROW_K; k++) {
                if (cap->expert_id[row][k] != e) continue;
                if (packed_rows >= PREFILL_NROW_ASSIGNMENTS) return 0;
                assignment_index[row][k] = packed_rows;
                memcpy((float *)[p->input contents] +
                           (size_t)packed_rows * HIDDEN_DIM,
                       cap->h_post[row], HIDDEN_DIM * sizeof(float));
                packed_rows++;
            }
        }
        group_count[group] = packed_rows - group_start[group];
        // Top-K routing should not contain the same expert twice for one row,
        // so a group cannot exceed the 16 rows supported by the kernel's local
        // accumulator.  Fail closed if a malformed route violates that.
        if (group_count[group] < 1 || group_count[group] > PREFILL_NROW_ROWS)
            return 0;
    }
    if (packed_rows != PREFILL_NROW_ASSIGNMENTS) return 0;

    id<MTLBuffer> group_data[PREFILL_NROW_ASSIGNMENTS];
    NSUInteger group_base[PREFILL_NROW_ASSIGNMENTS];
    uint32_t group_bits[PREFILL_NROW_ASSIGNMENTS];
    ExpertLayout group_layout[PREFILL_NROW_ASSIGNMENTS];
    int group_hot_miss[PREFILL_NROW_ASSIGNMENTS];
    memset(group_hot_miss, 0, sizeof(group_hot_miss));

    // IMPORTANT: do not insert hot misses into the malloc cache until the GPU
    // has finished this layer.  An insertion can evict a cache-hit buffer that
    // an already-encoded group still references.  Hot misses and all cold
    // experts therefore use private slices of expert_stage for this command.
    double stage_started = now_ms();
    InferPreadTask stage_tasks[PREFILL_NROW_ASSIGNMENTS];
    int stage_expert[PREFILL_NROW_ASSIGNMENTS];
    memset(stage_tasks, 0, sizeof(stage_tasks));
    int stage_slot = 0;
    for (int group = 0; group < unique_count; group++) {
        int e = unique_ids[group];
        TieredExpertInfo *ti = &TIERED(layer, e);
        uint32_t bits = ti->bits;
        if (bits != 2 && bits != 4) return 0;
        ExpertLayout layout = expert_layout_for_kind(
            bits == 2 ? EXPERT_QUANT_2BIT : EXPERT_QUANT_4BIT);
        if (layout.expert_size != ti->size || ti->size > p->expert_stage_stride)
            return 0;

        group_bits[group] = bits;
        group_layout[group] = layout;
        group_base[group] = 0;
        group_data[group] = nil;

        if (bits == 4) p->hot++; else p->cold++;

        if (bits == 4 && g_malloc_cache) {
            id<MTLBuffer> cached = malloc_cache_lookup(g_malloc_cache, layer, e);
            if (cached) {
                group_data[group] = cached;
                p->cache_hits++;
                continue;
            }
            p->cache_misses++;
            group_hot_miss[group] = 1;
        }

        if ((size_t)stage_slot >= p->expert_stage_slots) return 0;
        NSUInteger base = (NSUInteger)((size_t)stage_slot * p->expert_stage_stride);
        if ((size_t)base + ti->size > [p->expert_stage length]) return 0;
        int fd = expert_pick_fd(layer, e, packed_fd);

        stage_tasks[stage_slot].fd = fd;
        stage_tasks[stage_slot].dst =
            (char *)[p->expert_stage contents] + base;
        stage_tasks[stage_slot].offset = (off_t)ti->offset;
        stage_tasks[stage_slot].size = ti->size;
        stage_tasks[stage_slot].result = 0;
        stage_tasks[stage_slot].error_no = 0;
        if (mmap_base && fd == packed_fd) {
            stage_tasks[stage_slot].mmap_base = mmap_base;
            stage_tasks[stage_slot].mmap_size = g_layer_mmap_sizes[layer];
        }
        stage_expert[stage_slot] = e;

        group_data[group] = p->expert_stage;
        group_base[group] = base;
        stage_slot++;
    }

    if (stage_slot > 0) {
        if (g_io_pool_initialized) {
            int generation = io_pool_start(stage_tasks, stage_slot);
            io_pool_wait_generation(generation);
        } else {
            for (int i = 0; i < stage_slot; i++) {
                InferPreadTask *t = &stage_tasks[i];
                if (t->mmap_base) {
                    if (t->offset < 0 ||
                        (uint64_t)t->offset > (uint64_t)t->mmap_size ||
                        t->size > t->mmap_size - (size_t)t->offset) {
                        t->result = -1;
                        t->error_no = EINVAL;
                    } else {
                        memcpy(t->dst,
                            (const char *)t->mmap_base + t->offset, t->size);
                        t->result = (ssize_t)t->size;
                    }
                } else {
                    errno = 0;
                    t->result = pread(t->fd, t->dst, t->size, t->offset);
                    t->error_no = (t->result < 0) ? errno : 0;
                }
            }
        }

        for (int i = 0; i < stage_slot; i++) {
            if (stage_tasks[i].result != (ssize_t)stage_tasks[i].size) {
                fprintf(stderr,
                    "[prefill-nrow] expert read failed layer=%d expert=%d "
                    "got=%zd expected=%zu errno=%d\n",
                    layer, stage_expert[i], stage_tasks[i].result,
                    stage_tasks[i].size, stage_tasks[i].error_no);
                return 0;
            }
        }
    }
    p->expert_stage_ms += now_ms() - stage_started;

    // Routed expert GPU work.  Normal V6 keeps the accepted single-command-buffer
    // interleaving.  The optional phase-timing build instead submits three
    // command buffers on the same queue (gate+up, SwiGLU, down) and waits only
    // on the final one.  Queue order preserves dependencies while each command
    // buffer's GPUStartTime/GPUEndTime exposes actual stage GPU time.
    double expert_started = now_ms();
#ifdef FLASH_PREFILL_NROW_EXPERT_PHASE_TIMING
    id<MTLCommandBuffer> gate_cmd = [g_metal->queue commandBuffer];
    id<MTLCommandBuffer> swiglu_cmd = [g_metal->queue commandBuffer];
#ifdef FLASH_PREFILL_NROW_DOWN_BIT_TIMING
    id<MTLCommandBuffer> down_q4_cmd = [g_metal->queue commandBuffer];
    id<MTLCommandBuffer> down_q2_cmd = [g_metal->queue commandBuffer];
    if (!gate_cmd || !swiglu_cmd || !down_q4_cmd || !down_q2_cmd) return 0;
#else
    id<MTLCommandBuffer> down_cmd = [g_metal->queue commandBuffer];
    if (!gate_cmd || !swiglu_cmd || !down_cmd) return 0;
#endif

    for (int group = 0; group < unique_count; group++) {
        int start = group_start[group];
        uint32_t count = (uint32_t)group_count[group];
        uint32_t bits = group_bits[group];
        ExpertLayout layout = group_layout[group];
        id<MTLBuffer> data = group_data[group];
        NSUInteger data_base = group_base[group];
        NSUInteger hidden_off = (NSUInteger)((size_t)start * HIDDEN_DIM * sizeof(float));
        NSUInteger mid_off = (NSUInteger)((size_t)start * MOE_INTERMEDIATE * sizeof(float));

        prefill_nrow_encode_gate_up(gate_cmd, p, data, data_base,
            layout.gate_w_off, layout.gate_s_off, layout.gate_b_off,
            layout.up_w_off, layout.up_s_off, layout.up_b_off,
            p->input, hidden_off, p->gate, mid_off, p->up, mid_off,
            HIDDEN_DIM, MOE_INTERMEDIATE, count, bits);

        id<MTLComputeCommandEncoder> enc = [swiglu_cmd computeCommandEncoder];
        [enc setComputePipelineState:p->swiglu];
        [enc setBuffer:p->gate offset:mid_off atIndex:0];
        [enc setBuffer:p->up offset:mid_off atIndex:1];
        [enc setBuffer:p->act offset:mid_off atIndex:2];
        [enc setBytes:&count length:4 atIndex:3];
        [enc dispatchThreads:MTLSizeMake((size_t)count * MOE_INTERMEDIATE, 1, 1)
            threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
        [enc endEncoding];

#ifdef FLASH_PREFILL_NROW_DOWN_BIT_TIMING
        id<MTLCommandBuffer> selected_down_cmd =
            (bits == 4) ? down_q4_cmd : down_q2_cmd;
        if (bits == 4) {
            p->down_q4_groups++;
            p->down_q4_assignments += count;
        } else {
            p->down_q2_groups++;
            p->down_q2_assignments += count;
        }
#else
        id<MTLCommandBuffer> selected_down_cmd = down_cmd;
#endif
#if defined(FLASH_PREFILL_NROW_DOWN_M4_2ROW_BITSPLIT)
        prefill_nrow_encode_down_m4_2row_bitsplit(selected_down_cmd, p, data, data_base,
            layout.down_w_off, layout.down_s_off, layout.down_b_off,
            p->act, mid_off, p->output, hidden_off,
            MOE_INTERMEDIATE, HIDDEN_DIM, count, bits);
#elif defined(FLASH_PREFILL_NROW_DOWN_M4_2ROW)
        prefill_nrow_encode_down_m4_2row(selected_down_cmd, p, data, data_base,
            layout.down_w_off, layout.down_s_off, layout.down_b_off,
            p->act, mid_off, p->output, hidden_off,
            MOE_INTERMEDIATE, HIDDEN_DIM, count, bits);
#elif defined(FLASH_PREFILL_NROW_DOWN_M4_4ROW)
        prefill_nrow_encode_down_m4_4row(selected_down_cmd, p, data, data_base,
            layout.down_w_off, layout.down_s_off, layout.down_b_off,
            p->act, mid_off, p->output, hidden_off,
            MOE_INTERMEDIATE, HIDDEN_DIM, count, bits);
#elif defined(FLASH_PREFILL_NROW_DOWN_M4)
        prefill_nrow_encode_down_m4(selected_down_cmd, p, data, data_base,
            layout.down_w_off, layout.down_s_off, layout.down_b_off,
            p->act, mid_off, p->output, hidden_off,
            MOE_INTERMEDIATE, HIDDEN_DIM, count, bits);
#elif defined(FLASH_PREFILL_NROW_DOWN_COOP_2ROW)
        prefill_nrow_encode_down_coop_2row(selected_down_cmd, p, data, data_base,
            layout.down_w_off, layout.down_s_off, layout.down_b_off,
            p->act, mid_off, p->output, hidden_off,
            MOE_INTERMEDIATE, HIDDEN_DIM, count, bits);
#elif defined(FLASH_PREFILL_NROW_DOWN_2ROW)
        prefill_nrow_encode_down_2row(selected_down_cmd, p, data, data_base,
            layout.down_w_off, layout.down_s_off, layout.down_b_off,
            p->act, mid_off, p->output, hidden_off,
            MOE_INTERMEDIATE, HIDDEN_DIM, count, bits);
#else
        prefill_nrow_encode_projection(selected_down_cmd, p, data, data_base,
            layout.down_w_off, layout.down_s_off, layout.down_b_off,
            p->act, mid_off, p->output, hidden_off,
            MOE_INTERMEDIATE, HIDDEN_DIM, count, bits);
#endif
    }

    [gate_cmd commit];
    [swiglu_cmd commit];
#ifdef FLASH_PREFILL_NROW_DOWN_BIT_TIMING
    // Partition only the routed down phase by quantization width.  Alternate
    // submission order by layer to reduce systematic first/second-buffer bias.
    id<MTLCommandBuffer> final_down_cmd = nil;
    if ((layer & 1) == 0) {
        [down_q4_cmd commit];
        [down_q2_cmd commit];
        final_down_cmd = down_q2_cmd;
    } else {
        [down_q2_cmd commit];
        [down_q4_cmd commit];
        final_down_cmd = down_q4_cmd;
    }
    [final_down_cmd waitUntilCompleted];
#else
    [down_cmd commit];
    [down_cmd waitUntilCompleted];
#endif
    p->gpu_waits++;
    p->expert_ms += now_ms() - expert_started;
#ifdef FLASH_PREFILL_NROW_DOWN_BIT_TIMING
    if (gate_cmd.status != MTLCommandBufferStatusCompleted ||
        swiglu_cmd.status != MTLCommandBufferStatusCompleted ||
        down_q4_cmd.status != MTLCommandBufferStatusCompleted ||
        down_q2_cmd.status != MTLCommandBufferStatusCompleted) {
        NSError *error = gate_cmd.error ?: (swiglu_cmd.error ?:
            (down_q4_cmd.error ?: down_q2_cmd.error));
        fprintf(stderr, "[prefill-nrow] grouped expert diagnostic GPU failed: %s\n",
                error.localizedDescription.UTF8String);
        return 0;
    }
#else
    if (gate_cmd.status != MTLCommandBufferStatusCompleted ||
        swiglu_cmd.status != MTLCommandBufferStatusCompleted ||
        down_cmd.status != MTLCommandBufferStatusCompleted) {
        NSError *error = gate_cmd.error ?: (swiglu_cmd.error ?: down_cmd.error);
        fprintf(stderr, "[prefill-nrow] grouped expert phase GPU failed: %s\n",
                error.localizedDescription.UTF8String);
        return 0;
    }
#endif
    if (gate_cmd.GPUEndTime >= gate_cmd.GPUStartTime)
        p->expert_gate_up_gpu_ms +=
            (gate_cmd.GPUEndTime - gate_cmd.GPUStartTime) * 1000.0;
    if (swiglu_cmd.GPUEndTime >= swiglu_cmd.GPUStartTime)
        p->expert_swiglu_gpu_ms +=
            (swiglu_cmd.GPUEndTime - swiglu_cmd.GPUStartTime) * 1000.0;
#ifdef FLASH_PREFILL_NROW_DOWN_BIT_TIMING
    double q4_ms = 0.0, q2_ms = 0.0;
    if (down_q4_cmd.GPUEndTime >= down_q4_cmd.GPUStartTime)
        q4_ms = (down_q4_cmd.GPUEndTime - down_q4_cmd.GPUStartTime) * 1000.0;
    if (down_q2_cmd.GPUEndTime >= down_q2_cmd.GPUStartTime)
        q2_ms = (down_q2_cmd.GPUEndTime - down_q2_cmd.GPUStartTime) * 1000.0;
    p->expert_down_q4_gpu_ms += q4_ms;
    p->expert_down_q2_gpu_ms += q2_ms;
    p->expert_down_gpu_ms += q4_ms + q2_ms;
#else
    if (down_cmd.GPUEndTime >= down_cmd.GPUStartTime)
        p->expert_down_gpu_ms +=
            (down_cmd.GPUEndTime - down_cmd.GPUStartTime) * 1000.0;
#endif
#else
    id<MTLCommandBuffer> cmd = [g_metal->queue commandBuffer];
    for (int group = 0; group < unique_count; group++) {
        int start = group_start[group];
        uint32_t count = (uint32_t)group_count[group];
        uint32_t bits = group_bits[group];
        ExpertLayout layout = group_layout[group];
        id<MTLBuffer> data = group_data[group];
        NSUInteger data_base = group_base[group];
        NSUInteger hidden_off = (NSUInteger)((size_t)start * HIDDEN_DIM * sizeof(float));
        NSUInteger mid_off = (NSUInteger)((size_t)start * MOE_INTERMEDIATE * sizeof(float));

        prefill_nrow_encode_gate_up(cmd, p, data, data_base,
            layout.gate_w_off, layout.gate_s_off, layout.gate_b_off,
            layout.up_w_off, layout.up_s_off, layout.up_b_off,
            p->input, hidden_off, p->gate, mid_off, p->up, mid_off,
            HIDDEN_DIM, MOE_INTERMEDIATE, count, bits);

        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:p->swiglu];
        [enc setBuffer:p->gate offset:mid_off atIndex:0];
        [enc setBuffer:p->up offset:mid_off atIndex:1];
        [enc setBuffer:p->act offset:mid_off atIndex:2];
        [enc setBytes:&count length:4 atIndex:3];
        [enc dispatchThreads:MTLSizeMake((size_t)count * MOE_INTERMEDIATE, 1, 1)
            threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
        [enc endEncoding];

#if defined(FLASH_PREFILL_NROW_DOWN_M4_2ROW_BITSPLIT)
        prefill_nrow_encode_down_m4_2row_bitsplit(cmd, p, data, data_base,
            layout.down_w_off, layout.down_s_off, layout.down_b_off,
            p->act, mid_off, p->output, hidden_off,
            MOE_INTERMEDIATE, HIDDEN_DIM, count, bits);
#elif defined(FLASH_PREFILL_NROW_DOWN_M4_2ROW)
        prefill_nrow_encode_down_m4_2row(cmd, p, data, data_base,
            layout.down_w_off, layout.down_s_off, layout.down_b_off,
            p->act, mid_off, p->output, hidden_off,
            MOE_INTERMEDIATE, HIDDEN_DIM, count, bits);
#elif defined(FLASH_PREFILL_NROW_DOWN_M4_4ROW)
        prefill_nrow_encode_down_m4_4row(cmd, p, data, data_base,
            layout.down_w_off, layout.down_s_off, layout.down_b_off,
            p->act, mid_off, p->output, hidden_off,
            MOE_INTERMEDIATE, HIDDEN_DIM, count, bits);
#elif defined(FLASH_PREFILL_NROW_DOWN_M4)
        prefill_nrow_encode_down_m4(cmd, p, data, data_base,
            layout.down_w_off, layout.down_s_off, layout.down_b_off,
            p->act, mid_off, p->output, hidden_off,
            MOE_INTERMEDIATE, HIDDEN_DIM, count, bits);
#elif defined(FLASH_PREFILL_NROW_DOWN_COOP_2ROW)
        prefill_nrow_encode_down_coop_2row(cmd, p, data, data_base,
            layout.down_w_off, layout.down_s_off, layout.down_b_off,
            p->act, mid_off, p->output, hidden_off,
            MOE_INTERMEDIATE, HIDDEN_DIM, count, bits);
#elif defined(FLASH_PREFILL_NROW_DOWN_2ROW)
        prefill_nrow_encode_down_2row(cmd, p, data, data_base,
            layout.down_w_off, layout.down_s_off, layout.down_b_off,
            p->act, mid_off, p->output, hidden_off,
            MOE_INTERMEDIATE, HIDDEN_DIM, count, bits);
#else
        prefill_nrow_encode_projection(cmd, p, data, data_base,
            layout.down_w_off, layout.down_s_off, layout.down_b_off,
            p->act, mid_off, p->output, hidden_off,
            MOE_INTERMEDIATE, HIDDEN_DIM, count, bits);
#endif
    }
    [cmd commit];
    [cmd waitUntilCompleted];
    p->gpu_waits++;
    p->expert_ms += now_ms() - expert_started;
    if (cmd.status != MTLCommandBufferStatusCompleted) {
        fprintf(stderr, "[prefill-nrow] grouped expert GPU failed: %s\n",
                cmd.error.localizedDescription.UTF8String);
        return 0;
    }
#endif

    // Now that no command references cache-hit buffers, safely warm the hot
    // cache with bytes staged for 4-bit misses.  This preserves useful cache
    // behavior across subsequent chunks without risking in-flight eviction.
    double cache_started = now_ms();
    if (g_malloc_cache) {
        for (int group = 0; group < unique_count; group++) {
            if (!group_hot_miss[group]) continue;
            int e = unique_ids[group];
            TieredExpertInfo *ti = &TIERED(layer, e);
            int cache_idx = -1;
            id<MTLBuffer> cached =
                malloc_cache_insert(g_malloc_cache, layer, e, &cache_idx);
            if (cached && [cached length] >= ti->size) {
                memcpy([cached contents],
                       (char *)[p->expert_stage contents] + group_base[group],
                       ti->size);
            }
        }
    }
    p->expert_cache_ms += now_ms() - cache_started;

    LayerWeightCache *lc = &layer_cache[layer];
    if (!lc->sd_w) return 0;
    double shared_started = now_ms();

    // Preserve the already-validated CPU SwiGLU arithmetic, but prepare all
    // rows up front so the down projection can be submitted as one GPU batch.
    float *shared_act_rows = (float *)[p->shared_act_rows contents];
    for (int row = 0; row < PREFILL_NROW_ROWS; row++) {
        cpu_swiglu(cap->shared_gate[row], cap->shared_up[row],
                   shared_act_rows + (size_t)row * SHARED_INTERMEDIATE,
                   SHARED_INTERMEDIATE);
    }

    id<MTLCommandBuffer> shared_cmd = [g_metal->queue commandBuffer];
    if (!prefill_nrow_encode_shared_down(p, shared_cmd, lc)) return 0;
    [shared_cmd commit];
    [shared_cmd waitUntilCompleted];
    if (shared_cmd.status != MTLCommandBufferStatusCompleted) {
        fprintf(stderr, "[prefill-nrow] shared expert GPU failed: %s\n",
                shared_cmd.error.localizedDescription.UTF8String);
        return 0;
    }

    const float *shared_out_rows =
        (const float *)[p->shared_out_rows contents];
    double combine_started = now_ms();
    for (int row = 0; row < PREFILL_NROW_ROWS; row++) {
        float moe_out[2048];
        memset(moe_out, 0, sizeof(moe_out));
        for (int k = 0; k < PREFILL_NROW_K; k++) {
            int packed = assignment_index[row][k];
            if (packed < 0 || packed >= PREFILL_NROW_ASSIGNMENTS) return 0;
            cpu_vec_madd(moe_out,
                (float *)[p->output contents] + (size_t)packed * HIDDEN_DIM,
                cap->expert_weight[row][k], HIDDEN_DIM);
        }
        float shared_weight = cpu_sigmoid(cap->shared_score[row]);
        const float *shared_out =
            shared_out_rows + (size_t)row * HIDDEN_DIM;
        float *dest = slab + (size_t)row * HIDDEN_DIM;
        for (int i = 0; i < HIDDEN_DIM; i++)
            dest[i] = cap->h_mid[row][i] + moe_out[i] +
                      shared_weight * shared_out[i];
    }
    p->combine_ms += now_ms() - combine_started;
    p->shared_ms += now_ms() - shared_started;
    return 1;
}

#ifdef FLASH_PREFILL_NROW_PRODUCTION
// Persistent production N-row workspace. The server is single-request-at-a-time,
// so one process-wide workspace can be safely reused across requests and CLI
// prefill without per-request Metal-buffer allocation.
static PrefillNRowGrouped g_prefill_nrow_runtime_pipes;
static PrefillNRowCapture *g_prefill_nrow_runtime_capture = NULL;
static float *g_prefill_nrow_runtime_slab = NULL;
static int g_prefill_nrow_runtime_state = 0; // 0=untried, 1=ready, -1=failed

static int prefill_nrow_runtime_prepare(int K) {
    if (g_prefill_nrow_runtime_state != 0)
        return g_prefill_nrow_runtime_state > 0;
    if (!g_metal || !g_use_tiered || !g_tiered_manifest ||
        K != PREFILL_NROW_K || !snapshot_uses_gpu_linear_state()) {
        g_prefill_nrow_runtime_state = -1;
        return 0;
    }
    for (int li = 0; li < g_cfg.num_linear_layers; li++) {
        if (!g_metal->buf_conv_state[li] || !g_metal->buf_delta_state[li]) {
            fprintf(stderr,
                "[prefill-nrow] GPU linear recurrence state unavailable at linear layer %d\n",
                li);
            g_prefill_nrow_runtime_state = -1;
            return 0;
        }
    }

    PrefillNRowCapture *capture = calloc(1, sizeof(*capture));
    float *slab = malloc((size_t)PREFILL_NROW_ROWS * HIDDEN_DIM * sizeof(float));
    if (!capture || !slab || !prefill_nrow_grouped_init(&g_prefill_nrow_runtime_pipes)) {
        fprintf(stderr, "[prefill-nrow] production workspace initialization failed\n");
        free(capture);
        free(slab);
        prefill_nrow_grouped_release(&g_prefill_nrow_runtime_pipes);
        g_prefill_nrow_runtime_state = -1;
        return 0;
    }
    g_prefill_nrow_runtime_capture = capture;
    g_prefill_nrow_runtime_slab = slab;
    g_prefill_nrow_runtime_state = 1;
    fprintf(stderr,
        "[prefill-nrow] production runtime ready N=%d assignments=%d stage_slots=%zu\n",
        PREFILL_NROW_ROWS, PREFILL_NROW_ASSIGNMENTS,
        g_prefill_nrow_runtime_pipes.expert_stage_slots);
    return 1;
}

static int prefill_nrow_runtime_chunk(
    WeightFile *wf, KVCache **kv_caches, void **layer_states,
    void **layer_mmaps, int *layer_fds, int K, int base_pos,
    const uint32_t *token_ids, const float *embedded_rows,
    float *last_hidden, PrefillNRowPollFn poll_fn, void *poll_ctx) {
    if (!prefill_nrow_runtime_prepare(K) || !wf || !kv_caches ||
        !layer_states || !layer_mmaps || !layer_fds)
        return 0;

    float *slab = g_prefill_nrow_runtime_slab;
    PrefillNRowCapture *capture = g_prefill_nrow_runtime_capture;
    const double prof_qk0 = g_prefill_nrow_prof_qk_rope_ms;
    const double prof_kv0 = g_prefill_nrow_prof_kv_publish_ms;
    const double prof_attn0 = g_prefill_nrow_prof_attn_prep_ms;
    const double prof_cmd20 = g_prefill_nrow_prof_cmd2_ms;
    const uint64_t prof_rows0 = g_prefill_nrow_prof_full_rows;
    const uint64_t prof_gpu0 = g_prefill_nrow_prof_gpu_attn_rows;
    const uint64_t prof_cpu0 = g_prefill_nrow_prof_cpu_attn_rows;
    double direct_full_qkv_ms = 0.0;
    double direct_full_rowwise_ms = 0.0;
    double direct_full_grouped_ms = 0.0;
    double direct_linear_batch_ms = 0.0;
    double direct_linear_post_batch_ms = 0.0;
    double direct_linear_rowwise_ms = 0.0;
    double direct_linear_grouped_ms = 0.0;
    double direct_linear_grouping_ms = 0.0;
    double direct_linear_stage_ms = 0.0;
    double direct_linear_expert_ms = 0.0;
    double direct_linear_cache_ms = 0.0;
    double direct_linear_shared_ms = 0.0;
    double direct_linear_combine_ms = 0.0;
    uint64_t direct_full_layers = 0;
    uint64_t direct_linear_layers = 0;
    if (embedded_rows) {
        memcpy(slab, embedded_rows,
            (size_t)PREFILL_NROW_ROWS * HIDDEN_DIM * sizeof(float));
    } else {
        if (!token_ids) return 0;
        for (int row = 0; row < PREFILL_NROW_ROWS; row++)
            embed_lookup(wf, token_ids[row],
                slab + (size_t)row * HIDDEN_DIM);
    }

    int ok = 1;
    for (int layer = 0; layer < NUM_LAYERS && ok; layer++) {
        if (poll_fn && !poll_fn(poll_ctx)) {
            ok = 0;
            break;
        }
        int full = ((layer + 1) % FULL_ATTN_INTERVAL == 0);
        if (!full) {
            double direct_linear_batch_started = now_ms();
            ok = prefill_nrow_linear_layer(
                &g_prefill_nrow_runtime_pipes, wf, layer, slab);
            direct_linear_batch_ms += now_ms() - direct_linear_batch_started;
            direct_linear_layers++;
            if (!ok) break;
            g_prefill_nrow_linear_output =
                (float *)[g_prefill_nrow_runtime_pipes.attn_output contents];
            capture->count = PREFILL_NROW_ROWS;
            double direct_linear_post_started = now_ms();
            ok = prefill_nrow_linear_post_capture(
                &g_prefill_nrow_runtime_pipes, capture, layer, slab);
            direct_linear_post_batch_ms += now_ms() - direct_linear_post_started;
            if (!ok) break;
        } else {
            double direct_full_qkv_started = now_ms();
            ok = prefill_nrow_full_qkv_layer(
                &g_prefill_nrow_runtime_pipes, layer, slab);
            direct_full_qkv_ms += now_ms() - direct_full_qkv_started;
            direct_full_layers++;
            if (!ok) break;
            g_prefill_nrow_full_qproj =
                (float *)[g_prefill_nrow_runtime_pipes.full_qproj_rows contents];
            g_prefill_nrow_full_k =
                (float *)[g_prefill_nrow_runtime_pipes.full_k_rows contents];
            g_prefill_nrow_full_v =
                (float *)[g_prefill_nrow_runtime_pipes.full_v_rows contents];
            ok = prefill_nrow_full_attention_batch(
                &g_prefill_nrow_runtime_pipes, layer, base_pos,
                kv_caches[layer]);
            if (!ok) break;
            g_prefill_nrow_full_attn_out =
                (float *)[g_prefill_nrow_runtime_pipes.full_attn_rows contents];
        }

        capture->count = PREFILL_NROW_ROWS;
        if (full) {
            g_prefill_nrow_capture = capture;
            double direct_full_rowwise_started = now_ms();
            for (int row = 0; row < PREFILL_NROW_ROWS; row++) {
                capture->row = row;
                g_forward_error = 0;
                fused_layer_forward(wf, layer,
                    slab + (size_t)row * HIDDEN_DIM,
                    kv_caches[layer], NULL, base_pos + row,
                    layer_mmaps[layer] != MAP_FAILED ? layer_mmaps[layer] : NULL,
                    K, layer_fds[layer]);
                if (g_forward_error) {
                    discard_deferred_experts();
                    ok = 0;
                    break;
                }
            }
            direct_full_rowwise_ms += now_ms() - direct_full_rowwise_started;
            g_prefill_nrow_capture = NULL;
        }
        g_prefill_nrow_linear_output = NULL;
        g_prefill_nrow_full_qproj = NULL;
        g_prefill_nrow_full_k = NULL;
        g_prefill_nrow_full_v = NULL;
        g_prefill_nrow_full_attn_out = NULL;
        if (ok) {
            double direct_grouped_started = now_ms();
            const double grouped_grouping0 = g_prefill_nrow_runtime_pipes.grouping_ms;
            const double grouped_stage0 = g_prefill_nrow_runtime_pipes.expert_stage_ms;
            const double grouped_expert0 = g_prefill_nrow_runtime_pipes.expert_ms;
            const double grouped_cache0 = g_prefill_nrow_runtime_pipes.expert_cache_ms;
            const double grouped_shared0 = g_prefill_nrow_runtime_pipes.shared_ms;
            const double grouped_combine0 = g_prefill_nrow_runtime_pipes.combine_ms;
            ok = prefill_nrow_grouped_layer(
                &g_prefill_nrow_runtime_pipes, capture,
                layer, layer_fds[layer],
                layer_mmaps[layer] != MAP_FAILED ? layer_mmaps[layer] : NULL,
                slab);
            if (full) {
                direct_full_grouped_ms += now_ms() - direct_grouped_started;
            } else {
                direct_linear_grouped_ms += now_ms() - direct_grouped_started;
                direct_linear_grouping_ms +=
                    g_prefill_nrow_runtime_pipes.grouping_ms - grouped_grouping0;
                direct_linear_stage_ms +=
                    g_prefill_nrow_runtime_pipes.expert_stage_ms - grouped_stage0;
                direct_linear_expert_ms +=
                    g_prefill_nrow_runtime_pipes.expert_ms - grouped_expert0;
                direct_linear_cache_ms +=
                    g_prefill_nrow_runtime_pipes.expert_cache_ms - grouped_cache0;
                direct_linear_shared_ms +=
                    g_prefill_nrow_runtime_pipes.shared_ms - grouped_shared0;
                direct_linear_combine_ms +=
                    g_prefill_nrow_runtime_pipes.combine_ms - grouped_combine0;
            }
        }
    }

    g_prefill_nrow_capture = NULL;
    g_prefill_nrow_linear_output = NULL;
    g_prefill_nrow_full_qproj = NULL;
    g_prefill_nrow_full_k = NULL;
    g_prefill_nrow_full_v = NULL;
    g_prefill_nrow_full_attn_out = NULL;
    if (!ok) return 0;

    if (last_hidden)
        memcpy(last_hidden,
            slab + (size_t)(PREFILL_NROW_ROWS - 1) * HIDDEN_DIM,
            HIDDEN_DIM * sizeof(float));

    fprintf(stderr, "\n");
    fprintf(stderr,
        "[prefill-nrow-profile-direct] full_layers=%llu full_qkv=%.3fms "
        "full_rowwise=%.3fms full_grouped=%.3fms "
        "linear_layers=%llu linear_batch=%.3fms linear_post_batch=%.3fms "
        "linear_rowwise=%.3fms linear_grouped=%.3fms "
        "linear_grouping=%.3fms linear_stage=%.3fms linear_expert=%.3fms "
        "linear_cache=%.3fms linear_shared=%.3fms linear_combine=%.3fms\n",
        (unsigned long long)direct_full_layers,
        direct_full_qkv_ms, direct_full_rowwise_ms, direct_full_grouped_ms,
        (unsigned long long)direct_linear_layers,
        direct_linear_batch_ms, direct_linear_post_batch_ms,
        direct_linear_rowwise_ms, direct_linear_grouped_ms,
        direct_linear_grouping_ms, direct_linear_stage_ms,
        direct_linear_expert_ms, direct_linear_cache_ms,
        direct_linear_shared_ms, direct_linear_combine_ms);

    const uint64_t prof_rows = g_prefill_nrow_prof_full_rows - prof_rows0;
    if (prof_rows) {
        fprintf(stderr,
            "[prefill-nrow-profile] full_rows=%llu qk_rope=%.3fms kv_publish=%.3fms "
            "attn_prep=%.3fms cmd2=%.3fms gpu_attn_rows=%llu cpu_attn_rows=%llu\n",
            (unsigned long long)prof_rows,
            g_prefill_nrow_prof_qk_rope_ms - prof_qk0,
            g_prefill_nrow_prof_kv_publish_ms - prof_kv0,
            g_prefill_nrow_prof_attn_prep_ms - prof_attn0,
            g_prefill_nrow_prof_cmd2_ms - prof_cmd20,
            (unsigned long long)(g_prefill_nrow_prof_gpu_attn_rows - prof_gpu0),
            (unsigned long long)(g_prefill_nrow_prof_cpu_attn_rows - prof_cpu0));
    }
    return 1;
}
#endif

