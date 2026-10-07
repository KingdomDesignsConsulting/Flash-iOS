#if defined(TARGET_VERIFY_AFFINE_EXACTNESS_PROBE) && defined(TARGET_VERIFY_MULTIROW_AFFINE_MMA)
// Experiments 1 and 2 only: production M1 reproduction and scalar affine
// decomposition. No production dispatch or arithmetic is changed.
static int target_verify_exactness_probe(
    MetalCtx *ctx, MatvecBenchShape *shapes, int shape_count
) {
    id<MTLComputePipelineState> production = target_verify_load_benchmark_pipeline(
        ctx, @"target_verify_affine_exactness_probe.metal", @"affine_probe_production_m1");
    id<MTLComputePipelineState> decomposed = target_verify_load_benchmark_pipeline(
        ctx, @"target_verify_affine_exactness_probe.metal", @"affine_probe_scalar_decomposition");
    id<MTLComputePipelineState> m2 = target_verify_load_benchmark_pipeline(
        ctx, @"target_verify_affine_m2.metal", @"dense_affine_q4_m2");
    id<MTLComputePipelineState> m4 = target_verify_load_benchmark_pipeline(
        ctx, @"target_verify_affine_m4.metal", @"dense_affine_q4_m4");
    id<MTLComputePipelineState> mma = target_verify_load_benchmark_pipeline(
        ctx, @"target_verify_affine_m8_mma.metal", @"dense_affine_q4_m8_mma");
    if (!production || !decomposed || !m2 || !m4 || !mma) return 1;
    id<MTLBuffer> input = [ctx->device newBufferWithLength:8u*2048u*sizeof(float) options:MTLResourceStorageModeShared];
    id<MTLBuffer> real = [ctx->device newBufferWithLength:8u*8192u*sizeof(float) options:MTLResourceStorageModeShared];
    id<MTLBuffer> reproduced = [ctx->device newBufferWithLength:8u*8192u*sizeof(float) options:MTLResourceStorageModeShared];
    id<MTLBuffer> scalar = [ctx->device newBufferWithLength:8u*8192u*sizeof(float) options:MTLResourceStorageModeShared];
    id<MTLBuffer> mma_output = [ctx->device newBufferWithLength:8u*8192u*sizeof(float) options:MTLResourceStorageModeShared];
    id<MTLBuffer> trace = [ctx->device newBufferWithLength:8u*32u*sizeof(float) options:MTLResourceStorageModeShared];
    if (!input || !real || !reproduced || !scalar || !mma_output || !trace) return 1;
    printf("=== Verifier affine exactness probe: experiments 1 and 2 ===\n");
    int tested = 0;
    for (int si = 0; si < shape_count; si++) {
        MatvecBenchShape *shape = &shapes[si];
        if (strcmp(shape->label,"8192x2048") && strcmp(shape->label,"4096x2048")) continue;
        if (shape->tensor_count == 0) { fprintf(stderr,"ERROR: no real tensor for %s\n",shape->label); return 1; }
        const MatvecBenchTensor *tensor = &shape->tensors[0];
        float *rows = (float *)input.contents;
        for (uint32_t row=0;row<8u;row++) {
            float a=0.009f+0.0013f*(float)row,b=0.004f+0.0007f*(float)row;
            float p=0.21f+0.031f*(float)row,q=0.05f+0.006f*(float)row;
            for (uint32_t i=0;i<shape->in_dim;i++)
                rows[(size_t)row*shape->in_dim+i]=sinf((float)i*a+0.37f*(float)row)*p+cosf((float)i*b+0.19f*(float)row)*q;
        }
        if (!target_verify_m8_run_block(ctx,m2,m4,mma,shape,input,real,TARGET_VERIFY_M8_REF_M1,1,NULL,NULL) ||
            !target_verify_m8_run_block(ctx,m2,m4,mma,shape,input,mma_output,TARGET_VERIFY_M8_MMA,1,NULL,NULL)) return 1;
        id<MTLCommandBuffer> cmd=[ctx->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc=[cmd computeCommandEncoder];
        if (!cmd || !enc) return 1;
        uint32_t group_size=GROUP_SIZE;
        for (uint32_t row=0;row<8u;row++) {
            [enc setComputePipelineState:production];
            [enc setBuffer:tensor->weight_buf offset:tensor->weight_off atIndex:0];
            [enc setBuffer:tensor->weight_buf offset:tensor->scale_off atIndex:1];
            [enc setBuffer:tensor->weight_buf offset:tensor->bias_off atIndex:2];
            [enc setBuffer:input offset:(NSUInteger)row*shape->in_dim*sizeof(float) atIndex:3];
            [enc setBuffer:reproduced offset:(NSUInteger)row*shape->out_dim*sizeof(float) atIndex:4];
            [enc setBytes:&shape->out_dim length:4 atIndex:5];
            [enc setBytes:&shape->in_dim length:4 atIndex:6];
            [enc setBytes:&group_size length:4 atIndex:7];
            [enc dispatchThreadgroups:MTLSizeMake((shape->out_dim+7u)/8u,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];
            [enc setComputePipelineState:decomposed];
            [enc setBuffer:scalar offset:(NSUInteger)row*shape->out_dim*sizeof(float) atIndex:4];
            [enc setBuffer:trace offset:(NSUInteger)row*32u*sizeof(float) atIndex:8];
            [enc dispatchThreads:MTLSizeMake(shape->out_dim,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];
        }
        [enc endEncoding]; [cmd commit]; [cmd waitUntilCompleted];
        if (cmd.status != MTLCommandBufferStatusCompleted) {
            fprintf(stderr,"ERROR: exactness probe Metal command: %s\n",cmd.error.localizedDescription.UTF8String ?: "unknown");
            return 1;
        }
        size_t count=8u*(size_t)shape->out_dim, exact_ref=0, exact_scalar=0, exact_mma=0, exact_scalar_mma=0;
        size_t nan_count=0, inf_count=0;
        double max_abs=0.0,sum_sq=0.0,scalar_mma_max=0.0,row_max[8]={0};
        double mma_sum_sq=0.0,scalar_mma_sum_sq=0.0,error_cross=0.0;
        const float *rv=(const float *)real.contents,*pv=(const float *)reproduced.contents;
        const float *sv=(const float *)scalar.contents,*mv=(const float *)mma_output.contents;
        size_t first_bad=count;
        for (size_t v=0;v<count;v++) {
            uint32_t rb,pb,sb,mb;
            memcpy(&rb,&rv[v],4);memcpy(&pb,&pv[v],4);memcpy(&sb,&sv[v],4);memcpy(&mb,&mv[v],4);
            exact_ref += rb==pb; exact_scalar += rb==sb; exact_mma += rb==mb; exact_scalar_mma += sb==mb;
            if (rb!=pb && first_bad==count) first_bad=v;
            if (isnan(sv[v]) || isnan(rv[v]) || isnan(mv[v])) nan_count++;
            if (isinf(sv[v]) || isinf(rv[v]) || isinf(mv[v])) inf_count++;
            if (!isfinite(sv[v]) || !isfinite(rv[v]) || !isfinite(mv[v])) continue;
            double ds=(double)sv[v]-(double)rv[v];
            double mm=(double)mv[v]-(double)rv[v];
            double d=fabs(ds);
            double dm=fabs((double)sv[v]-(double)mv[v]);
            if (d>max_abs) max_abs=d;
            if (d>row_max[v/shape->out_dim]) row_max[v/shape->out_dim]=d;
            if (dm>scalar_mma_max) scalar_mma_max=dm;
            sum_sq+=d*d;
            mma_sum_sq+=mm*mm;
            scalar_mma_sum_sq+=dm*dm;
            error_cross+=ds*mm;
        }
        printf("%s tensor=%s values=%zu\n",shape->label,tensor->name,count);
        printf("  production reproduction: bitwise=%zu/%zu\n",exact_ref,count);
        if (exact_ref!=count) {
            uint32_t a,b;memcpy(&a,&rv[first_bad],4);memcpy(&b,&pv[first_bad],4);
            fprintf(stderr,"ERROR: reproduction differs at row=%zu neuron=%zu GPU=0x%08x probe=0x%08x\n",first_bad/shape->out_dim,first_bad%shape->out_dim,a,b);
            return 1;
        }
        printf("  scalar decomposition vs M1: max_abs=%.9g rms=%.9g bitwise=%zu/%zu differing=%zu nan=%zu inf=%zu\n",
            max_abs,sqrt(sum_sq/(double)count),exact_scalar,count,count-exact_scalar,nan_count,inf_count);
        printf("  row_max=[%.3g %.3g %.3g %.3g %.3g %.3g %.3g %.3g]\n",row_max[0],row_max[1],row_max[2],row_max[3],row_max[4],row_max[5],row_max[6],row_max[7]);
        printf("  M8 vs M1 bitwise=%zu/%zu; scalar vs M8 max_abs=%.9g bitwise=%zu/%zu\n",exact_mma,count,scalar_mma_max,exact_scalar_mma,count);
        printf("  error-pattern: M8_rms=%.9g scalar_M8_rms=%.9g signed_error_cosine=%.6g\n",
            sqrt(mma_sum_sq/(double)count),sqrt(scalar_mma_sum_sq/(double)count),
            (sum_sq>0.0 && mma_sum_sq>0.0)?error_cross/sqrt(sum_sq*mma_sum_sq):0.0);
        float *tr=(float *)trace.contents;
        uint32_t prod_bits,decomp_bits;memcpy(&prod_bits,&tr[3],4);memcpy(&decomp_bits,&tr[4],4);
        printf("  trace row=0 neuron=0 first_group_difference=%g group0_scale=%.9g bias=%.9g prod_group=%.9g(0x%08x) decomp_group=%.9g(0x%08x) P=%.9g xsum=%.9g\n",tr[0],tr[1],tr[2],tr[3],prod_bits,tr[4],decomp_bits,tr[5],tr[6]);
        for (int j=0;j<2;j++) printf("    element%d x=%.9g q=%.0f prod_contribution=%.9g\n",j,tr[8+j*3],tr[9+j*3],tr[10+j*3]);
        if (nan_count || inf_count) return 1;
        tested++;
    }
    return tested==2 ? 0 : 1;
}
#endif
