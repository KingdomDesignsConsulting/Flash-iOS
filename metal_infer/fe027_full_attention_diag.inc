// Diagnostic-only bounded actual-tensor capture. GPU copies are encoded after
// producers in their original command buffers; no early wait or state repair.
static NSMutableDictionary *fa_records[2];
static int fa_base,fa_layer;
static BOOL fa_selected(int layer,int pos) {
    if(!fa_records[0] || layer!=fa_layer)return NO;
    int row=pos-fa_base;
    return row==0 || row==1 || row==7 || row==30 || row==31 || row==32 || row==63 || row==127;
}
static NSString *fa_key(const char *stage,int layer,int pos) {return [NSString stringWithFormat:@"%d:%d:%s",layer,pos,stage];}
static void fa_cpu(const char *stage,int layer,int pos,const float *data,size_t count) {
    if(!fa_selected(layer,pos) || !data)return;
    if(!strncmp(stage,"kv_",3) && pos-fa_base!=127)return;
    NSString *key=fa_key(stage,layer,pos);
    if(!fa_records[sn_route_phase][key])fa_records[sn_route_phase][key]=@{@"data":[NSData dataWithBytes:data length:count*sizeof(float)],@"path":@"actual CPU-visible tensor",@"stage":@(stage),@"layer":@(layer),@"position":@(pos),@"floats":@(count)};
}
static void fa_gpu(id<MTLCommandBuffer> cmd,const char *stage,int layer,int pos,id<MTLBuffer> src,NSUInteger offset,size_t count) {
    if(!fa_selected(layer,pos) || !src)return;
    NSString *key=fa_key(stage,layer,pos);if(fa_records[sn_route_phase][key])return;
    NSCAssert(offset+count*sizeof(float)<=src.length,@"FA capture extent");
    id<MTLBuffer> dst=[g_metal->device newBufferWithLength:count*sizeof(float) options:MTLResourceStorageModeShared];
    NSCAssert(dst!=nil,@"FA diagnostic allocation");
    id<MTLBlitCommandEncoder> enc=[cmd blitCommandEncoder];
    [enc copyFromBuffer:src sourceOffset:offset toBuffer:dst destinationOffset:0 size:count*sizeof(float)];[enc endEncoding];
    fa_records[sn_route_phase][key]=@{@"buffer":dst,@"path":@"actual GPU tensor, ordered private blit",@"stage":@(stage),@"layer":@(layer),@"position":@(pos),@"floats":@(count)};
}
static NSDictionary *fa_diff(const float *a,const float *b,size_t n) {
    NSMutableDictionary *d=[sn_diff("tensor",fa_layer,a,b,n) mutableCopy];size_t bits=0;long first=-1;
    for(size_t i=0;i<n;i++)if(memcmp(a+i,b+i,sizeof(float))){bits++;if(first<0)first=(long)i;}
    d[@"bit_different"]=@(bits);d[@"first_different"]=@(first);d[@"exact"]=@(bits==0);return d;
}
static NSData *fa_data(NSDictionary *record) {
    if(record[@"data"])return record[@"data"];
    id<MTLBuffer> buffer=record[@"buffer"];
    return buffer?[NSData dataWithBytes:buffer.contents length:buffer.length]:nil;
}
static void fa_replay(void);
static void fa_begin(void) {
    fa_base=getenv("FLASH_FE027_FULL_BASE")?atoi(getenv("FLASH_FE027_FULL_BASE")):0;fa_layer=3;
    fa_records[0]=[NSMutableDictionary dictionary];fa_records[1]=[NSMutableDictionary dictionary];g_fe_fa_cpu=fa_cpu;g_fe_fa_gpu=fa_gpu;
}
static void fa_end(void) {
    if(!fa_records[0])return;
    NSMutableArray *rows=[NSMutableArray array];NSString *dir=@(getenv("FLASH_SESSION_TOKEN_TRACE_DIR"));
    for(int phase=0;phase<2;phase++)for(NSString *key in fa_records[phase].allKeys) {
        NSMutableDictionary *record=[fa_records[phase][key] mutableCopy];NSData *data=fa_data(record);
        NSString *name=[NSString stringWithFormat:@"fa-%d-%@.f32",phase,[key stringByReplacingOccurrencesOfString:@":" withString:@"-"]];
        [data writeToFile:[dir stringByAppendingPathComponent:name] atomically:YES];record[@"file"]=name;record[@"data"]=data;[record removeObjectForKey:@"buffer"];fa_records[phase][key]=record;
    }
    // GPU preparation fuses split/normalization/RoPE. The split alone is an
    // exact index map of the captured packed projection, not a math replay.
    for(int phase=0;phase<2;phase++)for(int row=0;row<128;row++) {
        int pos=fa_base+row;NSString *key=fa_key("q_raw",fa_layer,pos);
        NSDictionary *packed=fa_records[phase][fa_key("qproj",fa_layer,pos)];
        if(!fa_records[phase][key] && packed) {
            NSMutableData *q=[NSMutableData dataWithLength:NUM_ATTN_HEADS*HEAD_DIM*sizeof(float)];
            for(int h=0;h<NUM_ATTN_HEADS;h++)memcpy((float *)q.mutableBytes+h*HEAD_DIM,(const float *)[packed[@"data"] bytes]+h*2*HEAD_DIM,HEAD_DIM*sizeof(float));
            NSString *name=[NSString stringWithFormat:@"fa-%d-%d-%d-q_raw.f32",phase,fa_layer,pos];[q writeToFile:[dir stringByAppendingPathComponent:name] atomically:YES];
            fa_records[phase][key]=@{@"data":q,@"file":name,@"path":@"actual packed projection, exact split index map",@"stage":@"q_raw",@"layer":@(fa_layer),@"position":@(pos),@"floats":@(NUM_ATTN_HEADS*HEAD_DIM)};
        }
    }
    NSMutableSet *keys=[NSMutableSet setWithArray:fa_records[0].allKeys];[keys addObjectsFromArray:fa_records[1].allKeys];
    for(NSString *key in [[keys allObjects] sortedArrayUsingSelector:@selector(compare:)]) {
        NSDictionary *a=fa_records[0][key],*b=fa_records[1][key],*one=a?:b;
        NSMutableDictionary *row=[@{@"stage":one[@"stage"],@"layer":one[@"layer"],@"position":one[@"position"],@"row":@([one[@"position"] intValue]-fa_base),@"floats":one[@"floats"],@"reference_observed":@(a!=nil),@"candidate_observed":@(b!=nil)} mutableCopy];
        NSString *stage=one[@"stage"];
        row[@"dimensions"]=[stage hasPrefix:@"kv_"]?@[@([one[@"floats"] intValue]/(NUM_KV_HEADS*HEAD_DIM)),@(NUM_KV_HEADS),@(HEAD_DIM)]:[stage isEqual:@"qproj"]?@[@(NUM_ATTN_HEADS),@2,@(HEAD_DIM)]:
            ([stage hasPrefix:@"q_"] || [stage hasPrefix:@"attention_"])?@[@(NUM_ATTN_HEADS),@(HEAD_DIM)]:
            ([stage hasPrefix:@"k"] || [stage isEqual:@"vproj"])?@[@(NUM_KV_HEADS),@(HEAD_DIM)]:@[@(HIDDEN_DIM)];
        if(a)row[@"reference_file"]=a[@"file"];if(b)row[@"candidate_file"]=b[@"file"];
        if(a && b){NSCAssert([a[@"floats"] isEqual:b[@"floats"]],@"FA shape mismatch");[row addEntriesFromDictionary:fa_diff([a[@"data"] bytes],[b[@"data"] bytes],[a[@"floats"] unsignedLongValue])];row[@"reference_path"]=a[@"path"];row[@"candidate_path"]=b[@"path"];}
        [rows addObject:row];
    }
    fa_replay();
    sd_write(@"full-attention-tensors.json",@{@"layer":@(fa_layer),@"base":@(fa_base),@"rows":rows,@"scope":@"Actual selected per-layer tensors; fused normalization/ungated stages may be unobservable. No intermediate full-model state inferred."});
    fa_records[0]=nil;fa_records[1]=nil;g_fe_fa_cpu=NULL;g_fe_fa_gpu=NULL;
}
#ifdef FLASH_FE027_NUMERICS
static NSData *fa_operand(const char *stage,int pos) {return fa_records[0][fa_key(stage,fa_layer,pos)][@"data"];}
static id<MTLBuffer> fa_buffer(NSData *data) {return [g_metal->device newBufferWithBytes:data.bytes length:data.length options:MTLResourceStorageModeShared];}
static id<MTLBuffer> fa_space(size_t floats) {return [g_metal->device newBufferWithLength:floats*sizeof(float) options:MTLResourceStorageModeShared];}
static void fa_wait(id<MTLCommandBuffer> cmd) {[cmd commit];[cmd waitUntilCompleted];NSCAssert(cmd.status==MTLCommandBufferStatusCompleted,@"FA private replay GPU failure");}
static void fa_replay(void) {
    if(fa_base!=0)return; // First-slab replay only; never invent missing history.
    LayerWeightCache *lc=&layer_cache[fa_layer];
    if(lc->q_kind!=MATVEC_KIND_MLX4 || lc->k_kind!=MATVEC_KIND_MLX4 || lc->v_kind!=MATVEC_KIND_MLX4)return;
    const int qdim=NUM_ATTN_HEADS*HEAD_DIM,kvd=NUM_KV_HEADS*HEAD_DIM;
    NSData *kd=fa_operand("kv_k",127),*vd=fa_operand("kv_v",127);if(!kd || !vd)return;
    id<MTLBuffer> kc=fa_buffer(kd),vc=fa_buffer(vd),scores=fa_space(NUM_ATTN_HEADS*128);
    id<MTLBuffer> input=fa_space(128*HIDDEN_DIM),bq=fa_space(128*qdim*2),bk=fa_space(128*kvd),bv=fa_space(128*kvd);
    memset(input.contents,0,input.length);
    for(int pos=0;pos<128;pos++){NSData *x=fa_operand("input_norm",pos);if(x)memcpy((float *)input.contents+(size_t)pos*HIDDEN_DIM,x.bytes,x.length);}
    id<MTLCommandBuffer> cmd=[g_metal->queue commandBuffer];id<MTLComputeCommandEncoder> e=[cmd computeCommandEncoder];
    int encoded=prefill_nrow_encode_dense_rows(e,lc->q_w,lc->q_s,lc->q_b,lc->q_kind,lc->q_source,input,HIDDEN_DIM*sizeof(float),bq,qdim*2*sizeof(float),qdim*2,HIDDEN_DIM,GROUP_SIZE) &&
        prefill_nrow_encode_dense_rows(e,lc->k_w,lc->k_s,lc->k_b,lc->k_kind,lc->k_source,input,HIDDEN_DIM*sizeof(float),bk,kvd*sizeof(float),kvd,HIDDEN_DIM,GROUP_SIZE) &&
        prefill_nrow_encode_dense_rows(e,lc->v_w,lc->v_s,lc->v_b,lc->v_kind,lc->v_source,input,HIDDEN_DIM*sizeof(float),bv,kvd*sizeof(float),kvd,HIDDEN_DIM,GROUP_SIZE);
    [e endEncoding];NSCAssert(encoded,@"FA projection replay encode");fa_wait(cmd);
    NSMutableArray *rows=[NSMutableArray array];
    for(int pos=0;pos<128;pos++) {
        NSData *norm=fa_operand("input_norm",pos),*qp=fa_operand("qproj",pos),*kp=fa_operand("kproj",pos),*vp=fa_operand("vproj",pos),*qr=fa_operand("q_rope",pos);if(!norm || !qp || !kp || !vp || !qr)continue;
        MetalCtx private_ctx={0};private_ctx.wf_buf=g_metal->wf_buf;private_ctx.matvec_fast=g_metal->matvec_fast;private_ctx.matvec_v3=g_metal->matvec_v3;private_ctx.buf_input=fa_buffer(norm);
        private_ctx.batch_out[0]=fa_space(qdim*2);private_ctx.batch_out[1]=fa_space(kvd);private_ctx.batch_out[2]=fa_space(kvd);
        BatchMatvecSpec specs[3]={
            {lc->q_w,lc->q_s,lc->q_b,NULL,(uint32_t)qdim*2,(uint32_t)HIDDEN_DIM,GROUP_SIZE,0,lc->q_kind,lc->q_source},
            {lc->k_w,lc->k_s,lc->k_b,NULL,(uint32_t)kvd,(uint32_t)HIDDEN_DIM,GROUP_SIZE,1,lc->k_kind,lc->k_source},
            {lc->v_w,lc->v_s,lc->v_b,NULL,(uint32_t)kvd,(uint32_t)HIDDEN_DIM,GROUP_SIZE,2,lc->v_kind,lc->v_source}};
        cmd=[g_metal->queue commandBuffer];gpu_encode_batch_matvec(&private_ctx,cmd,specs,3);fa_wait(cmd);
        NSMutableDictionary *row=[@{@"position":@(pos),@"layer":@(fa_layer),@"row":@(pos),@"same_operands":@YES} mutableCopy];
        row[@"scalar_q_projection_replay_vs_live"]=fa_diff(qp.bytes,private_ctx.batch_out[0].contents,qdim*2);
        row[@"scalar_k_projection_replay_vs_live"]=fa_diff(kp.bytes,private_ctx.batch_out[1].contents,kvd);
        row[@"scalar_v_projection_replay_vs_live"]=fa_diff(vp.bytes,private_ctx.batch_out[2].contents,kvd);
        row[@"q_projection_scalar_vs_nrow"]=fa_diff(private_ctx.batch_out[0].contents,(float *)bq.contents+(size_t)pos*qdim*2,qdim*2);
        row[@"k_projection_scalar_vs_nrow"]=fa_diff(private_ctx.batch_out[1].contents,(float *)bk.contents+(size_t)pos*kvd,kvd);
        row[@"v_projection_scalar_vs_nrow"]=fa_diff(private_ctx.batch_out[2].contents,(float *)bv.contents+(size_t)pos*kvd,kvd);
        id<MTLBuffer> qpb=fa_buffer(qp),kpb=fa_buffer(kp),vpb=fa_buffer(vp),gq=fa_space(qdim),gg=fa_space(qdim),gk=fa_space(kvd),gv=fa_space(kvd);
        cmd=[g_metal->queue commandBuffer];fe027_encode_prepare(cmd,lc,qpb,0,kpb,0,vpb,0,gq,0,gg,0,gk,gv,0,pos);fa_wait(cmd);
        float cq[qdim],ck[kvd],gate[qdim];const float *packed=qp.bytes;
        for(int h=0;h<NUM_ATTN_HEADS;h++){memcpy(cq+h*HEAD_DIM,packed+h*2*HEAD_DIM,HEAD_DIM*sizeof(float));memcpy(gate+h*HEAD_DIM,packed+h*2*HEAD_DIM+HEAD_DIM,HEAD_DIM*sizeof(float));}
        memcpy(ck,kp.bytes,kp.length);
        for(int type=0;type<2;type++){float *x=type?ck:cq;int heads=type?NUM_KV_HEADS:NUM_ATTN_HEADS;const uint16_t *w=type?lc->k_norm_w:lc->q_norm_w;
            for(int h=0;h<heads;h++){float *v=x+h*HEAD_DIM,ss=0;for(int d=0;d<HEAD_DIM;d++)ss+=v[d]*v[d];float inv=1.0f/sqrtf(ss/HEAD_DIM+RMS_NORM_EPS);for(int d=0;d<HEAD_DIM;d++)v[d]=v[d]*inv*bf16_to_f32(w[d]);}}
        NSData *live_norm=fa_operand("q_norm",pos);if(live_norm)row[@"cpu_q_normalization_replay_vs_live"]=fa_diff(live_norm.bytes,cq,qdim);
        live_norm=fa_operand("k_norm",pos);if(live_norm)row[@"cpu_k_normalization_replay_vs_live"]=fa_diff(live_norm.bytes,ck,kvd);
        int tail=HEAD_DIM-ROTARY_DIM;float cpu_tail[NUM_ATTN_HEADS*tail],gpu_tail[NUM_ATTN_HEADS*tail];
        for(int h=0;h<NUM_ATTN_HEADS;h++){memcpy(cpu_tail+h*tail,cq+h*HEAD_DIM+ROTARY_DIM,tail*sizeof(float));memcpy(gpu_tail+h*tail,(float *)gq.contents+h*HEAD_DIM+ROTARY_DIM,tail*sizeof(float));}
        row[@"q_normalization_cpu_vs_gpu_nonrotary"]=fa_diff(cpu_tail,gpu_tail,NUM_ATTN_HEADS*tail);
        apply_rotary_emb(cq,ck,pos,NUM_ATTN_HEADS,NUM_KV_HEADS,HEAD_DIM,ROTARY_DIM);
        row[@"q_preparation_cpu_vs_gpu"]=fa_diff(cq,gq.contents,qdim);row[@"k_preparation_cpu_vs_gpu"]=fa_diff(ck,gk.contents,kvd);
        row[@"reference_preparation_replay_vs_live"]=fa_diff(qr.bytes,pos>=31?gq.contents:cq,qdim);
        id<MTLBuffer> qb=fa_buffer(qr),gb=[g_metal->device newBufferWithBytes:gate length:qdim*sizeof(float) options:MTLResourceStorageModeShared],out=fa_space(qdim),ungated=fa_space(qdim),online=fa_space(qdim);
        cmd=[g_metal->queue commandBuffer];fe027_encode_attention(cmd,qb,0,gb,0,kc,vc,scores,128,out,0,pos+1,ungated);fa_wait(cmd);
        float cpu_attention[qdim];fe027_cpu_attention(qr.bytes,gate,kd.bytes,vd.bytes,pos+1,cpu_attention);
        NSData *live=fa_operand("attention_gated",pos);
        row[@"reference_attention_replay_vs_live"]=fa_diff(live.bytes,pos>=31?out.contents:cpu_attention,qdim);
        cmd=[g_metal->queue commandBuffer];e=[cmd computeCommandEncoder];[e setComputePipelineState:g_prefill_nrow_runtime_pipes.full_attn_batch];
        [e setBuffer:qb offset:0 atIndex:0];[e setBuffer:kc offset:0 atIndex:1];[e setBuffer:vc offset:0 atIndex:2];[e setBuffer:gb offset:0 atIndex:3];[e setBuffer:online offset:0 atIndex:4];
        uint32_t one=1,nh=NUM_ATTN_HEADS,hd=HEAD_DIM,kd_u=kvd,base=pos,hpkv=NUM_ATTN_HEADS/NUM_KV_HEADS;float scale=1.0f/sqrtf((float)HEAD_DIM);
        [e setBytes:&one length:4 atIndex:5];[e setBytes:&nh length:4 atIndex:6];[e setBytes:&hd length:4 atIndex:7];[e setBytes:&kd_u length:4 atIndex:8];[e setBytes:&base length:4 atIndex:9];[e setBytes:&hpkv length:4 atIndex:10];[e setBytes:&scale length:4 atIndex:11];[e dispatchThreadgroups:MTLSizeMake(NUM_ATTN_HEADS,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];[e endEncoding];fa_wait(cmd);
        row[@"attention_reference_vs_online_identical_inputs"]=fa_diff(pos>=31?out.contents:cpu_attention,online.contents,qdim);
        // Isolate gating with the exact same already-computed ungated values.
        NSData *raw=fa_operand("attention_ungated",pos);if(raw){id<MTLBuffer> gate_out=fa_buffer(raw);cmd=[g_metal->queue commandBuffer];e=[cmd computeCommandEncoder];[e setComputePipelineState:g_metal->sigmoid_gate_pipe];[e setBuffer:gate_out offset:0 atIndex:0];[e setBuffer:gb offset:0 atIndex:1];uint32_t n=qdim;[e setBytes:&n length:4 atIndex:2];[e dispatchThreadgroups:MTLSizeMake((n+255)/256,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];[e endEncoding];fa_wait(cmd);float c[qdim];memcpy(c,raw.bytes,raw.length);for(int i=0;i<qdim;i++)c[i]*=1.0f/(1.0f+expf(-gate[i]));row[@"gate_cpu_vs_gpu_identical_inputs"]=fa_diff(c,gate_out.contents,qdim);row[@"reference_gate_replay_vs_live"]=fa_diff(live.bytes,pos>=31?gate_out.contents:c,qdim);}
        if(lc->o_kind==MATVEC_KIND_MLX4 && g_oproj_v3_enabled){id<MTLBuffer> ob=fa_buffer(live),oo=fa_space(HIDDEN_DIM);cmd=[g_metal->queue commandBuffer];gpu_encode_dequant_matvec_with_io_bufs(g_metal,cmd,lc->o_w,lc->o_s,lc->o_b,ob,oo,HIDDEN_DIM,qdim,GROUP_SIZE);fa_wait(cmd);row[@"oprojection_replay_vs_live"]=fa_diff([fa_operand("oprojection",pos) bytes],oo.contents,HIDDEN_DIM);}
        float sum[HIDDEN_DIM];const float *a=fa_operand("layer_input",pos).bytes,*b=fa_operand("oprojection",pos).bytes;for(int i=0;i<HIDDEN_DIM;i++)sum[i]=a[i]+b[i];row[@"residual_cpu_add_vs_live"]=fa_diff([fa_operand("residual",pos) bytes],sum,HIDDEN_DIM);
        [rows addObject:row];
    }
    sd_write(@"full-attention-identical-inputs.json",@{@"layer":@(fa_layer),@"heads":@(NUM_ATTN_HEADS),@"head_dim":@(HEAD_DIM),@"rotary_dim":@(ROTARY_DIM),@"rows":rows,@"scope":@"Private-I/O replay using actual captured scalar operands; live-path validation metrics must pass before causal attribution."});
}
#else
static void fa_replay(void) {}
#endif
