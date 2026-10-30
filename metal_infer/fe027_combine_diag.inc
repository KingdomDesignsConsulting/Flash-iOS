// Two bounded observation banks. Captures actual producer order, never repairs
// state or waits early. All diagnostic GPU replay I/O is private.
static NSMutableDictionary *cb_records[2];
static BOOL cb_selected(int layer,int pos) {
    return cb_records[0] && (layer==0 || layer==2 || layer==3 || layer==23) &&
        (pos==0 || pos==1 || pos==7 || pos==31 || pos==63 || pos==127);
}
static NSString *cb_key(int layer,int pos) {return [NSString stringWithFormat:@"%d:%d",layer,pos];}
static NSArray *cb_ids(const int *ids) {NSMutableArray *a=[NSMutableArray array];for(int k=0;k<8;k++)[a addObject:@(ids[k])];return a;}
static void cb_gpu(id<MTLCommandBuffer> cmd,int layer,int pos,const int *ids,int count) {
    if(!cb_selected(layer,pos) || count!=8)return;
    const size_t bytes=HIDDEN_DIM*sizeof(float);
    id<MTLBuffer> dst=[g_metal->device newBufferWithLength:11*bytes+10*sizeof(float) options:MTLResourceStorageModeShared];
    NSCAssert(dst!=nil,@"combine capture allocation");
    id<MTLBlitCommandEncoder> e=[cmd blitCommandEncoder];
    [e copyFromBuffer:g_metal->buf_h_mid sourceOffset:0 toBuffer:dst destinationOffset:0 size:bytes];
    [e copyFromBuffer:g_metal->buf_shared_out sourceOffset:0 toBuffer:dst destinationOffset:bytes size:bytes];
    for(int k=0;k<8;k++)[e copyFromBuffer:g_metal->buf_multi_expert_out[k] sourceOffset:0 toBuffer:dst destinationOffset:(2+k)*bytes size:bytes];
    [e copyFromBuffer:g_metal->buf_moe_hidden sourceOffset:0 toBuffer:dst destinationOffset:10*bytes size:bytes];
    [e copyFromBuffer:g_metal->buf_combine_params sourceOffset:0 toBuffer:dst destinationOffset:11*bytes size:10*sizeof(float)];[e endEncoding];
    cb_records[sn_route_phase][cb_key(layer,pos)]=@{@"buffer":dst,@"ids":cb_ids(ids),@"layer":@(layer),@"position":@(pos),@"path":@"actual scalar GPU combine; ordered CMD3 blit"};
}
static void cb_cpu(int layer,int pos,const float *mid,const float *shared,const float *const *experts,const float *weights,const int *ids,float score,const float *output) {
    if(!cb_selected(layer,pos))return;
    NSMutableData *data=[NSMutableData dataWithLength:(11*HIDDEN_DIM+10)*sizeof(float)];float *x=data.mutableBytes;size_t bytes=HIDDEN_DIM*sizeof(float);
    memcpy(x,mid,bytes);memcpy(x+HIDDEN_DIM,shared,bytes);
    for(int k=0;k<8;k++)memcpy(x+(2+k)*HIDDEN_DIM,experts[k],bytes);
    memcpy(x+10*HIDDEN_DIM,output,bytes);memcpy(x+11*HIDDEN_DIM,weights,8*sizeof(float));x[11*HIDDEN_DIM+8]=score;
    cb_records[sn_route_phase][cb_key(layer,pos)]=@{@"data":data,@"ids":cb_ids(ids),@"layer":@(layer),@"position":@(pos),@"path":@"actual completed grouped combine CPU-visible operands/output"};
}
static void cb_begin(void) {cb_records[0]=[NSMutableDictionary dictionary];cb_records[1]=[NSMutableDictionary dictionary];g_fe_combine_gpu=cb_gpu;g_fe_combine_cpu=cb_cpu;}
static NSDictionary *cb_diff(const float *a,const float *b,size_t n) {
    NSMutableDictionary *d=[sn_diff("combine",-1,a,b,n) mutableCopy];long first=-1;size_t bits=0;
    for(size_t i=0;i<n;i++)if(memcmp(a+i,b+i,4)){bits++;if(first<0)first=(long)i;}
    d[@"exact"]=@(bits==0);d[@"bit_different"]=@(bits);d[@"first_different"]=@(first);return d;
}
static void cb_cpu_trace(const float *x,float *trace) {
    const int d=HIDDEN_DIM;const float *p=x+11*d;float sum[HIDDEN_DIM];memset(sum,0,sizeof(sum));
    for(int k=0;k<8;k++) {
        const float *expert=x+(2+k)*d;
        for(int i=0;i<d;i++)trace[k*d+i]=p[k]*expert[i];
        cpu_vec_madd(sum,expert,p[k],d);memcpy(trace+(8+k)*d,sum,d*sizeof(float));
    }
    float gate=cpu_sigmoid(p[8]);
    for(int i=0;i<d;i++) {
        trace[16*d+i]=gate;trace[17*d+i]=gate*x[d+i];trace[18*d+i]=x[i]+sum[i];
        trace[19*d+i]=x[i]+sum[i]+gate*x[d+i];
    }
}
static void cb_end(void) {
    if(!cb_records[0])return;
    // Disable callbacks before replay; the original observations are immutable.
    g_fe_combine_gpu=NULL;g_fe_combine_cpu=NULL;
    NSString *dir=@(getenv("FLASH_SESSION_TOKEN_TRACE_DIR"));
    NSString *source=[NSString stringWithContentsOfFile:[infer_executable_directory() stringByAppendingPathComponent:@"fe027_combine_trace.metal"] encoding:NSUTF8StringEncoding error:NULL];
    NSCAssert(source!=nil,@"combine trace source");
    MTLCompileOptions *opts=[MTLCompileOptions new];opts.mathMode=MTLMathModeFast;opts.languageVersion=MTLLanguageVersion3_1;
    NSError *error=nil;id<MTLLibrary> library=[g_metal->device newLibraryWithSource:source options:opts error:&error];
    id<MTLComputePipelineState> pipe=library?[g_metal->device newComputePipelineStateWithFunction:[library newFunctionWithName:@"fe027_combine_trace"] error:&error]:nil;
    NSCAssert(pipe!=nil,@"combine trace compile: %@",error);
    NSMutableArray *rows=[NSMutableArray array];
    for(int phase=0;phase<2;phase++)for(NSString *key in [[cb_records[phase] allKeys] sortedArrayUsingSelector:@selector(compare:)]) {
        NSDictionary *record=cb_records[phase][key];id<MTLBuffer> captured=record[@"buffer"];
        NSData *data=record[@"data"]?:[NSData dataWithBytes:captured.contents length:captured.length];
        int layer=[record[@"layer"] intValue],pos=[record[@"position"] intValue];
        const float *x=data.bytes;size_t bytes=HIDDEN_DIM*sizeof(float);uint32_t dim=HIDDEN_DIM,k=8;
        id<MTLBuffer> input=[g_metal->device newBufferWithBytes:x length:data.length options:MTLResourceStorageModeShared];
        id<MTLBuffer> output=[g_metal->device newBufferWithLength:bytes options:MTLResourceStorageModeShared];
        id<MTLBuffer> trace=[g_metal->device newBufferWithLength:20*bytes options:MTLResourceStorageModeShared];
        id<MTLCommandBuffer> cmd=[g_metal->queue commandBuffer];id<MTLComputeCommandEncoder> e=[cmd computeCommandEncoder];
        [e setComputePipelineState:g_metal->moe_combine_residual];
        [e setBuffer:input offset:0 atIndex:0];[e setBuffer:input offset:bytes atIndex:1];[e setBuffer:output offset:0 atIndex:2];
        for(int j=0;j<8;j++)[e setBuffer:input offset:(2+j)*bytes atIndex:3+j];
        [e setBuffer:input offset:11*bytes atIndex:11];[e setBytes:&dim length:4 atIndex:12];[e setBytes:&k length:4 atIndex:13];
        [e dispatchThreadgroups:MTLSizeMake((dim+255)/256,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];[e endEncoding];
        e=[cmd computeCommandEncoder];[e setComputePipelineState:pipe];[e setBuffer:input offset:0 atIndex:0];[e setBuffer:trace offset:0 atIndex:1];[e setBytes:&dim length:4 atIndex:2];
        [e dispatchThreadgroups:MTLSizeMake((dim+255)/256,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];[e endEncoding];[cmd commit];[cmd waitUntilCompleted];
        NSCAssert(cmd.status==MTLCommandBufferStatusCompleted,@"combine private replay failure");
        float cpu[20*HIDDEN_DIM];cb_cpu_trace(x,cpu);const float *gpu=trace.contents;
        NSMutableArray *stages=[NSMutableArray array];
        for(int j=0;j<20;j++) {
            NSString *name=j<8?@"weighted_product":j<16?@"expert_accumulation":j==16?@"sigmoid":j==17?@"shared_contribution":j==18?@"residual_plus_experts":@"final";
            [stages addObject:@{@"stage":name,@"slot":@(j<8?j:j<16?j-8:-1),@"difference":cb_diff(cpu+j*dim,gpu+j*dim,j==16?1:dim)}];
        }
        NSDictionary *gpu_live=cb_diff(output.contents,x+10*dim,dim),*cpu_live=cb_diff(cpu+19*dim,x+10*dim,dim);
        BOOL gpu_expected=phase==0;
#ifdef FLASH_FE027_NUMERICS
        gpu_expected|=(fe027_numerics_mask()&32)!=0;
#endif
        NSMutableDictionary *row=[@{@"phase":@(phase),@"layer":@(layer),@"position":@(pos),@"path":record[@"path"],@"ids":record[@"ids"],@"gpu_replay_vs_live":gpu_live,@"cpu_replay_vs_live":cpu_live,@"expected_live_replay_exact":gpu_expected?gpu_live[@"exact"]:cpu_live[@"exact"],@"trace_vs_original_gpu":cb_diff(gpu+19*dim,output.contents,dim),@"stages":stages} mutableCopy];
        NSDictionary *other=cb_records[1-phase][key];
        if(other) {
            id<MTLBuffer> ob=other[@"buffer"];NSData *od=other[@"data"]?:[NSData dataWithBytes:ob.contents length:ob.length];const float *y=od.bytes;
            NSMutableArray *operands=[NSMutableArray array];
            for(int j=0;j<10;j++)[operands addObject:cb_diff(x+j*dim,y+j*dim,dim)];
            row[@"operand_differences"]=operands;row[@"weights"]=cb_diff(x+11*dim,y+11*dim,8);row[@"shared_score"]=cb_diff(x+11*dim+8,y+11*dim+8,1);row[@"same_expert_ids"]=@([record[@"ids"] isEqual:other[@"ids"]]);row[@"actual_output_difference"]=cb_diff(x+10*dim,y+10*dim,dim);
        }
        NSString *name=[NSString stringWithFormat:@"combine-%d-%d-%d.f32",phase,layer,pos];[data writeToFile:[dir stringByAppendingPathComponent:name] atomically:YES];
        [rows addObject:row];
    }
    sd_write(@"combine-operators.json",@{@"rows":rows,@"dimensions":@(HIDDEN_DIM),@"scope":@"Actual bounded operands and live outputs; private CPU/original-GPU replays authenticated to live path. GPU trace must match original kernel before interpretation. Rounded product stages are diagnostic, not separately materialized original FMA intermediates."});
    cb_records[0]=nil;cb_records[1]=nil;
}
