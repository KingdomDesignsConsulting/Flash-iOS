// Private-I/O encoders reuse the unmodified scalar pipelines. No reference
// serving buffers are rebound or overwritten by the diagnostic replay.
static void fe027_encode_prepare(id<MTLCommandBuffer> cmd,const LayerWeightCache *lc,
    id<MTLBuffer> qp,NSUInteger qo,id<MTLBuffer> kp,NSUInteger ko,id<MTLBuffer> vp,NSUInteger vo,
    id<MTLBuffer> q,NSUInteger qoff,id<MTLBuffer> gate,NSUInteger goff,
    id<MTLBuffer> kc,id<MTLBuffer> vc,int cache_pos,int pos) {
    FullAttnPrepareParams p={0};p.cache_pos=cache_pos;p.kv_dim=NUM_KV_HEADS*HEAD_DIM;
    p.head_dim=HEAD_DIM;p.rotary_dim=ROTARY_DIM;p.num_q_heads=NUM_ATTN_HEADS;p.num_kv_heads=NUM_KV_HEADS;p.eps=RMS_NORM_EPS;fill_full_attn_rope(&p,pos);
    id<MTLComputeCommandEncoder> enc=[cmd computeCommandEncoder];[enc setComputePipelineState:g_metal->full_attn_prepare_pipe];
    [enc setBuffer:qp offset:qo atIndex:0];[enc setBuffer:kp offset:ko atIndex:1];[enc setBuffer:vp offset:vo atIndex:2];
    [enc setBuffer:g_metal->wf_buf offset:(const char *)lc->q_norm_w-(const char *)g_metal->wf_buf.contents atIndex:3];
    [enc setBuffer:g_metal->wf_buf offset:(const char *)lc->k_norm_w-(const char *)g_metal->wf_buf.contents atIndex:4];
    [enc setBuffer:q offset:qoff atIndex:5];[enc setBuffer:gate offset:goff atIndex:6];[enc setBuffer:kc offset:0 atIndex:7];[enc setBuffer:vc offset:0 atIndex:8];[enc setBytes:&p length:sizeof(p) atIndex:9];
    [enc dispatchThreadgroups:MTLSizeMake(NUM_ATTN_HEADS+NUM_KV_HEADS,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];[enc endEncoding];
}
static void fe027_encode_attention(id<MTLCommandBuffer> cmd,id<MTLBuffer> q,NSUInteger qo,
    id<MTLBuffer> gate,NSUInteger go,id<MTLBuffer> k,id<MTLBuffer> v,id<MTLBuffer> scores,uint32_t stride,
    id<MTLBuffer> out,NSUInteger oo,uint32_t sl,id<MTLBuffer> ungated) {
    uint32_t hd=HEAD_DIM,kvd=NUM_KV_HEADS*HEAD_DIM,hpkv=NUM_ATTN_HEADS/NUM_KV_HEADS,qdim=NUM_ATTN_HEADS*HEAD_DIM;float scale=1.0f/sqrtf((float)HEAD_DIM);
    id<MTLComputeCommandEncoder> e=[cmd computeCommandEncoder];[e setComputePipelineState:g_metal->attn_scores_pipe];
    [e setBuffer:q offset:qo atIndex:0];[e setBuffer:k offset:0 atIndex:1];[e setBuffer:scores offset:0 atIndex:2];
    [e setBytes:&hd length:4 atIndex:3];[e setBytes:&kvd length:4 atIndex:4];[e setBytes:&sl length:4 atIndex:5];[e setBytes:&stride length:4 atIndex:6];[e setBytes:&scale length:4 atIndex:7];[e setBytes:&hpkv length:4 atIndex:8];[e setBytes:&sl length:4 atIndex:9];
    [e dispatchThreadgroups:MTLSizeMake(sl*NUM_ATTN_HEADS,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];[e endEncoding];
    e=[cmd computeCommandEncoder];[e setComputePipelineState:g_metal->attn_softmax_pipe];[e setBuffer:scores offset:0 atIndex:0];[e setBytes:&sl length:4 atIndex:1];[e setBytes:&stride length:4 atIndex:2];[e dispatchThreadgroups:MTLSizeMake(NUM_ATTN_HEADS,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];[e endEncoding];
    e=[cmd computeCommandEncoder];[e setComputePipelineState:g_metal->attn_values_pipe];[e setBuffer:scores offset:0 atIndex:0];[e setBuffer:v offset:0 atIndex:1];[e setBuffer:out offset:oo atIndex:2];[e setBytes:&hd length:4 atIndex:3];[e setBytes:&kvd length:4 atIndex:4];[e setBytes:&sl length:4 atIndex:5];[e setBytes:&stride length:4 atIndex:6];[e setBytes:&hpkv length:4 atIndex:7];[e dispatchThreadgroups:MTLSizeMake((qdim+255)/256,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];[e endEncoding];
    if(ungated){id<MTLBlitCommandEncoder>b=[cmd blitCommandEncoder];[b copyFromBuffer:out sourceOffset:oo toBuffer:ungated destinationOffset:0 size:qdim*sizeof(float)];[b endEncoding];}
    e=[cmd computeCommandEncoder];[e setComputePipelineState:g_metal->sigmoid_gate_pipe];[e setBuffer:out offset:oo atIndex:0];[e setBuffer:gate offset:go atIndex:1];[e setBytes:&qdim length:4 atIndex:2];[e dispatchThreadgroups:MTLSizeMake((qdim+255)/256,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];[e endEncoding];
}
static void fe027_cpu_attention(const float *q,const float *gate,const float *k,const float *v,int sl,float *out) {
    int qdim=NUM_ATTN_HEADS*HEAD_DIM,kvd=NUM_KV_HEADS*HEAD_DIM,hpkv=NUM_ATTN_HEADS/NUM_KV_HEADS;float scale=1.0f/sqrtf((float)HEAD_DIM);float scores[sl];memset(out,0,qdim*sizeof(float));
    for(int h=0;h<NUM_ATTN_HEADS;h++) {
        int kh=h/hpkv;const float *qh=q+h*HEAD_DIM;
        for(int p=0;p<sl;p++){float dot=0;const float *kp=k+(size_t)p*kvd+kh*HEAD_DIM;for(int d=0;d<HEAD_DIM;d++)dot+=qh[d]*kp[d];scores[p]=dot*scale;}
        cpu_softmax(scores,sl);float *oh=out+h*HEAD_DIM;
        for(int p=0;p<sl;p++){const float *vp=v+(size_t)p*kvd+kh*HEAD_DIM;for(int d=0;d<HEAD_DIM;d++)oh[d]+=scores[p]*vp[d];}
    }
    for(int i=0;i<qdim;i++)out[i]*=1.0f/(1.0f+expf(-gate[i]));
}
// Opt-in scalar-compatible attention operator; no state anchor/replay/reset.
// QKV and MoE remain batched. Only native MLX4/default GPU serving is supported.
static int fe027_reference_full_attention(PrefillNRowGrouped *p,int layer,int base_pos,KVCache *kv) {
    LayerWeightCache *lc=&layer_cache[layer];int base=kv->len,end=base+PREFILL_NROW_ROWS;
    if(base<0 || end>g_kv_seq_len || end>GPU_KV_SEQ || !kv->k_cache || !kv->v_cache ||
       lc->q_kind!=MATVEC_KIND_MLX4 || lc->k_kind!=MATVEC_KIND_MLX4 || lc->v_kind!=MATVEC_KIND_MLX4 || lc->o_kind!=MATVEC_KIND_MLX4 || !g_metal->attn_scores_pipe)return 0;
    int qdim=NUM_ATTN_HEADS*HEAD_DIM,kvd=NUM_KV_HEADS*HEAD_DIM,fi=(layer+1)/FULL_ATTN_INTERVAL-1;
    double started=now_ms();id<MTLCommandBuffer> prep=[g_metal->queue commandBuffer];
    for(int row=0;row<PREFILL_NROW_ROWS;row++) {
        int pos=base_pos+row,cp=base+row,sl=cp+1;
        float *qp=(float *)p->full_qproj_rows.contents+(size_t)row*qdim*2,*k=(float *)p->full_k_rows.contents+(size_t)row*kvd,*v=(float *)p->full_v_rows.contents+(size_t)row*kvd;
        float *q=(float *)p->full_q_rows.contents+(size_t)row*qdim,*gate=(float *)p->full_gate_rows.contents+(size_t)row*qdim;
        BOOL gpu_prepare=sl>=32 && g_cmd12_full_chain_enabled && g_gpu_resident_moe_enabled && full_attn_chain_cmd2_prereqs(lc);
        if(gpu_prepare) {
            fe027_encode_prepare(prep,lc,p->full_qproj_rows,(size_t)row*qdim*2*sizeof(float),p->full_k_rows,(size_t)row*kvd*sizeof(float),p->full_v_rows,(size_t)row*kvd*sizeof(float),p->full_q_rows,(size_t)row*qdim*sizeof(float),p->full_gate_rows,(size_t)row*qdim*sizeof(float),g_metal->buf_kv_k[fi],g_metal->buf_kv_v[fi],cp,pos);
#ifdef FLASH_SESSION_STATE_DIAGNOSTICS
            if(g_fe_fa_gpu){g_fe_fa_gpu(prep,"q_rope",layer,pos,p->full_q_rows,(size_t)row*qdim*sizeof(float),qdim);g_fe_fa_gpu(prep,"k_rope",layer,pos,g_metal->buf_kv_k[fi],(size_t)cp*kvd*sizeof(float),kvd);}
#endif
        } else {
            for(int h=0;h<NUM_ATTN_HEADS;h++){memcpy(q+h*HEAD_DIM,qp+h*2*HEAD_DIM,HEAD_DIM*sizeof(float));memcpy(gate+h*HEAD_DIM,qp+h*2*HEAD_DIM+HEAD_DIM,HEAD_DIM*sizeof(float));}
#ifdef FLASH_SESSION_STATE_DIAGNOSTICS
            if(g_fe_fa_cpu){g_fe_fa_cpu("q_raw",layer,pos,q,qdim);g_fe_fa_cpu("k_raw",layer,pos,k,kvd);}
#endif
            for(int type=0;type<2;type++){float *x=type?k:q;int heads=type?NUM_KV_HEADS:NUM_ATTN_HEADS;const uint16_t *w=type?lc->k_norm_w:lc->q_norm_w;
                for(int h=0;h<heads;h++){float *v=x+h*HEAD_DIM,ss=0;for(int d=0;d<HEAD_DIM;d++)ss+=v[d]*v[d];float inv=1.0f/sqrtf(ss/HEAD_DIM+RMS_NORM_EPS);for(int d=0;d<HEAD_DIM;d++)v[d]=v[d]*inv*bf16_to_f32(w[d]);}}
#ifdef FLASH_SESSION_STATE_DIAGNOSTICS
            if(g_fe_fa_cpu){g_fe_fa_cpu("q_norm",layer,pos,q,qdim);g_fe_fa_cpu("k_norm",layer,pos,k,kvd);}
#endif
            apply_rotary_emb(q,k,pos,NUM_ATTN_HEADS,NUM_KV_HEADS,HEAD_DIM,ROTARY_DIM);
#ifdef FLASH_SESSION_STATE_DIAGNOSTICS
            if(g_fe_fa_cpu){g_fe_fa_cpu("q_rope",layer,pos,q,qdim);g_fe_fa_cpu("k_rope",layer,pos,k,kvd);}
#endif
            memcpy(kv->k_cache+(size_t)cp*kvd,k,kvd*sizeof(float));memcpy(kv->v_cache+(size_t)cp*kvd,v,kvd*sizeof(float));
#if !defined(FLASH_EXPERIMENTAL_LAZY_SHARED_GPU_KV) && !defined(FLASH_EXPERIMENTAL_LAZY_SHARED_GPU_KV_32K)
            memcpy((float *)g_metal->buf_kv_k[fi].contents+(size_t)cp*kvd,k,kvd*sizeof(float));memcpy((float *)g_metal->buf_kv_v[fi].contents+(size_t)cp*kvd,v,kvd*sizeof(float));
#endif
        }
    }
    [prep commit];[prep waitUntilCompleted];if(prep.status!=MTLCommandBufferStatusCompleted)return 0;
#if !defined(FLASH_EXPERIMENTAL_LAZY_SHARED_GPU_KV) && !defined(FLASH_EXPERIMENTAL_LAZY_SHARED_GPU_KV_32K)
    memcpy(kv->k_cache+(size_t)base*kvd,(float *)g_metal->buf_kv_k[fi].contents+(size_t)base*kvd,(size_t)PREFILL_NROW_ROWS*kvd*sizeof(float));
    memcpy(kv->v_cache+(size_t)base*kvd,(float *)g_metal->buf_kv_v[fi].contents+(size_t)base*kvd,(size_t)PREFILL_NROW_ROWS*kvd*sizeof(float));
#endif
    kv->len=end;
    id<MTLCommandBuffer> attn=[g_metal->queue commandBuffer];uint32_t stride=(uint32_t)(g_metal->buf_attn_scores.length/(NUM_ATTN_HEADS*sizeof(float)));
    for(int row=0;row<PREFILL_NROW_ROWS;row++) {
        int sl=base+row+1;NSUInteger offset=(size_t)row*qdim*sizeof(float);
        if(sl>=32) {
            id<MTLBuffer> raw=nil;
#ifdef FLASH_SESSION_STATE_DIAGNOSTICS
            if(g_fe_fa_gpu)raw=g_metal->buf_attn_out;
#endif
            fe027_encode_attention(attn,p->full_q_rows,offset,p->full_gate_rows,offset,g_metal->buf_kv_k[fi],g_metal->buf_kv_v[fi],g_metal->buf_attn_scores,stride,p->full_attn_rows,offset,sl,raw);
#ifdef FLASH_SESSION_STATE_DIAGNOSTICS
            if(g_fe_fa_gpu && raw)g_fe_fa_gpu(attn,"attention_ungated",layer,base_pos+row,raw,0,qdim);
#endif
        } else fe027_cpu_attention((float *)p->full_q_rows.contents+(size_t)row*qdim,(float *)p->full_gate_rows.contents+(size_t)row*qdim,kv->k_cache,kv->v_cache,sl,(float *)p->full_attn_rows.contents+(size_t)row*qdim);
    }
    [attn commit];[attn waitUntilCompleted];if(attn.status!=MTLCommandBufferStatusCompleted)return 0;
#ifdef FLASH_SESSION_STATE_DIAGNOSTICS
    if(g_fe_fa_cpu){for(int row=0;row<PREFILL_NROW_ROWS;row++)g_fe_fa_cpu("attention_gated",layer,base_pos+row,(float *)p->full_attn_rows.contents+(size_t)row*qdim,qdim);
        if(end<=4096){g_fe_fa_cpu("kv_k",layer,base_pos+PREFILL_NROW_ROWS-1,kv->k_cache,(size_t)end*kvd);g_fe_fa_cpu("kv_v",layer,base_pos+PREFILL_NROW_ROWS-1,kv->v_cache,(size_t)end*kvd);}}
#endif
    p->full_attn_ms+=now_ms()-started;
    return 1;
}
