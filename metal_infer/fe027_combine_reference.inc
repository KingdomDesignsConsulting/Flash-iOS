// Bit 32: reuse the unchanged scalar GPU combine, retaining routing slot order.
// Existing post-projection scratch is dead here; no new persistent allocations.
static int fe027_combine_rows(PrefillNRowGrouped *p,const PrefillNRowCapture *cap,
    const int assignments[PREFILL_NROW_ROWS][PREFILL_NROW_K]) {
    if(!g_metal->moe_combine_residual || PREFILL_NROW_K!=8 ||
       p->linear_gate_scores.length<(size_t)PREFILL_NROW_ROWS*10*sizeof(float) ||
       p->linear_hpost_rows.length<(size_t)PREFILL_NROW_ROWS*HIDDEN_DIM*sizeof(float) ||
       p->normed_rows.length<(size_t)PREFILL_NROW_ROWS*HIDDEN_DIM*sizeof(float))return 0;
    for(int row=0;row<PREFILL_NROW_ROWS;row++) {
        float *params=(float *)p->linear_gate_scores.contents+row*10;
        memset(params,0,10*sizeof(float));
        for(int k=0;k<8;k++) {
            if(assignments[row][k]<0 || assignments[row][k]>=PREFILL_NROW_ASSIGNMENTS)return 0;
            params[k]=cap->expert_weight[row][k];
        }
        params[8]=cap->shared_score[row];
        memcpy((float *)p->linear_hpost_rows.contents+(size_t)row*HIDDEN_DIM,cap->h_mid[row],HIDDEN_DIM*sizeof(float));
    }
    id<MTLCommandBuffer> cmd=[g_metal->queue commandBuffer];
    for(int row=0;row<PREFILL_NROW_ROWS;row++) {
        id<MTLComputeCommandEncoder> enc=[cmd computeCommandEncoder];
        if(!enc)return 0;
        NSUInteger offset=(size_t)row*HIDDEN_DIM*sizeof(float);
        [enc setComputePipelineState:g_metal->moe_combine_residual];
        [enc setBuffer:p->linear_hpost_rows offset:offset atIndex:0];
        [enc setBuffer:p->shared_out_rows offset:offset atIndex:1];
        [enc setBuffer:p->normed_rows offset:offset atIndex:2];
        for(int k=0;k<8;k++)[enc setBuffer:p->output offset:(size_t)assignments[row][k]*HIDDEN_DIM*sizeof(float) atIndex:3+k];
        [enc setBuffer:p->linear_gate_scores offset:row*10*sizeof(float) atIndex:11];
        uint32_t dim=HIDDEN_DIM,count=8;
        [enc setBytes:&dim length:sizeof(dim) atIndex:12];[enc setBytes:&count length:sizeof(count) atIndex:13];
        [enc dispatchThreadgroups:MTLSizeMake((dim+255)/256,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];[enc endEncoding];
    }
    [cmd commit];[cmd waitUntilCompleted];
    return cmd.status==MTLCommandBufferStatusCompleted;
}
