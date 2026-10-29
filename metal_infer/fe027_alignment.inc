// Opt-in FE-027 arithmetic alignment. Uses existing scalar GPU RMS kernels,
// immutable model weights and private scratch; no routing or state resets.
static int fe027_normalize_rows(id<MTLBuffer> input,id<MTLBuffer> output,const uint16_t *weights) {
    if(!weights || !g_metal->rms_norm_sum || !g_metal->rms_norm_apply_bf16)return 0;
    static id<MTLBuffer> sums;
    if(!sums)sums=[g_metal->device newBufferWithLength:PREFILL_NROW_ROWS*sizeof(float) options:MTLResourceStorageModeShared];
    if(!sums)return 0;
    id<MTLCommandBuffer> cmd=[g_metal->queue commandBuffer];uint32_t dim=HIDDEN_DIM;float eps=RMS_NORM_EPS;
    NSUInteger weight_offset=(const char *)weights-(const char *)g_metal->wf_buf.contents;
    for(int row=0;row<PREFILL_NROW_ROWS;row++) {
        NSUInteger offset=(size_t)row*dim*sizeof(float),sum_offset=row*sizeof(float);
        id<MTLComputeCommandEncoder> enc=[cmd computeCommandEncoder];if(!enc)return 0;
        [enc setComputePipelineState:g_metal->rms_norm_sum];[enc setBuffer:input offset:offset atIndex:0];[enc setBuffer:sums offset:sum_offset atIndex:1];[enc setBytes:&dim length:4 atIndex:2];
        [enc dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];[enc endEncoding];
        enc=[cmd computeCommandEncoder];if(!enc)return 0;
        [enc setComputePipelineState:g_metal->rms_norm_apply_bf16];[enc setBuffer:input offset:offset atIndex:0];[enc setBuffer:g_metal->wf_buf offset:weight_offset atIndex:1];[enc setBuffer:sums offset:sum_offset atIndex:2];[enc setBuffer:output offset:offset atIndex:3];[enc setBytes:&dim length:4 atIndex:4];[enc setBytes:&eps length:4 atIndex:5];
        [enc dispatchThreadgroups:MTLSizeMake((dim+255)/256,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];[enc endEncoding];
    }
    [cmd commit];[cmd waitUntilCompleted];return cmd.status==MTLCommandBufferStatusCompleted;
}

// Same existing scalar GPU activation, with independent rows and no reduction.
static int fe027_shared_swiglu(id<MTLBuffer> gate,id<MTLBuffer> up,id<MTLBuffer> output) {
    if(!g_metal->swiglu)return 0;
    id<MTLCommandBuffer> cmd=[g_metal->queue commandBuffer];
    for(int row=0;row<PREFILL_NROW_ROWS;row++) {
        id<MTLComputeCommandEncoder> enc=[cmd computeCommandEncoder];if(!enc)return 0;
        uint32_t dim=SHARED_INTERMEDIATE;NSUInteger offset=(size_t)row*dim*sizeof(float);
        [enc setComputePipelineState:g_metal->swiglu];
        [enc setBuffer:gate offset:offset atIndex:0];[enc setBuffer:up offset:offset atIndex:1];[enc setBuffer:output offset:offset atIndex:2];[enc setBytes:&dim length:4 atIndex:3];
        [enc dispatchThreadgroups:MTLSizeMake((dim+255)/256,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];[enc endEncoding];
    }
    [cmd commit];[cmd waitUntilCompleted];return cmd.status==MTLCommandBufferStatusCompleted;
}
