#if defined(TARGET_VERIFY_AFFINE_MMA_TREE_PROBE) && defined(TARGET_VERIFY_MULTIROW_AFFINE_MMA)
static uint32_t affine_tree_bits(float x) { uint32_t u; memcpy(&u,&x,4); return u; }

static int target_verify_affine_mma_tree_probe(MetalCtx *ctx,MatvecBenchShape *shapes,int shape_count) {
    id<MTLComputePipelineState> partial_pipe=target_verify_load_benchmark_pipeline(
        ctx,@"target_verify_affine_m8_partials.metal",@"dense_affine_q4_m8_partials");
    id<MTLComputePipelineState> m2=target_verify_load_benchmark_pipeline(ctx,@"target_verify_affine_m2.metal",@"dense_affine_q4_m2");
    id<MTLComputePipelineState> m4=target_verify_load_benchmark_pipeline(ctx,@"target_verify_affine_m4.metal",@"dense_affine_q4_m4");
    id<MTLComputePipelineState> mma=target_verify_load_benchmark_pipeline(ctx,@"target_verify_affine_m8_mma.metal",@"dense_affine_q4_m8_mma");
    id<MTLComputePipelineState> scale_inside=target_verify_load_benchmark_pipeline(ctx,@"target_verify_affine_m8_scale_inside.metal",@"dense_affine_q4_m8_scale_inside");
    if(!partial_pipe||!m2||!m4||!mma||!scale_inside) return 1;
    id<MTLBuffer> input=[ctx->device newBufferWithLength:8u*2048u*sizeof(float) options:MTLResourceStorageModeShared];
    id<MTLBuffer> output=[ctx->device newBufferWithLength:8u*8192u*sizeof(float) options:MTLResourceStorageModeShared];
    id<MTLBuffer> baseline=[ctx->device newBufferWithLength:8u*8192u*sizeof(float) options:MTLResourceStorageModeShared];
    id<MTLBuffer> production=[ctx->device newBufferWithLength:8u*8192u*sizeof(float) options:MTLResourceStorageModeShared];
    id<MTLBuffer> scaled_output=[ctx->device newBufferWithLength:8u*8192u*sizeof(float) options:MTLResourceStorageModeShared];
    id<MTLBuffer> partial=[ctx->device newBufferWithLength:32u*8u*8u*16u*sizeof(float) options:MTLResourceStorageModeShared];
    id<MTLBuffer> group_partial=[ctx->device newBufferWithLength:32u*8u*8192u*sizeof(float) options:MTLResourceStorageModeShared];
    if(!input||!output||!baseline||!production||!scaled_output||!partial||!group_partial) return 1;
    int tested=0;
    for(int si=0;si<shape_count;si++) {
        MatvecBenchShape *shape=&shapes[si];
        if(strcmp(shape->label,"8192x2048") && strcmp(shape->label,"4096x2048")) continue;
        if(shape->tensor_count==0) return 1;
        const MatvecBenchTensor *tensor=&shape->tensors[0];
        float *rows=(float *)input.contents;
        for(uint32_t row=0;row<8u;row++) {
            float a=0.009f+0.0013f*(float)row,b=0.004f+0.0007f*(float)row;
            float p=0.21f+0.031f*(float)row,q=0.05f+0.006f*(float)row;
            for(uint32_t i=0;i<shape->in_dim;i++) rows[(size_t)row*shape->in_dim+i]=sinf((float)i*a+0.37f*(float)row)*p+cosf((float)i*b+0.19f*(float)row)*q;
        }
        if(!target_verify_m8_run_block(ctx,m2,m4,mma,shape,input,baseline,TARGET_VERIFY_M8_MMA,1,NULL,NULL))return 1;
        if(!target_verify_m8_run_block(ctx,m2,m4,mma,shape,input,production,TARGET_VERIFY_M8_REF_M1,1,NULL,NULL))return 1;
        if(!target_verify_m8_run_block(ctx,m2,m4,scale_inside,shape,input,scaled_output,TARGET_VERIFY_M8_MMA,1,NULL,NULL))return 1;
        id<MTLCommandBuffer> cmd=[ctx->queue commandBuffer];id<MTLComputeCommandEncoder> enc=[cmd computeCommandEncoder];
        if(!cmd||!enc)return 1;
        uint32_t group_size=GROUP_SIZE,input_stride=shape->in_dim,output_stride=shape->out_dim;
        [enc setComputePipelineState:partial_pipe];
        [enc setBuffer:tensor->weight_buf offset:tensor->weight_off atIndex:0];
        [enc setBuffer:tensor->weight_buf offset:tensor->scale_off atIndex:1];
        [enc setBuffer:tensor->weight_buf offset:tensor->bias_off atIndex:2];
        [enc setBuffer:input offset:0 atIndex:3];[enc setBuffer:output offset:0 atIndex:4];
        [enc setBytes:&shape->out_dim length:4 atIndex:5];[enc setBytes:&shape->in_dim length:4 atIndex:6];
        [enc setBytes:&group_size length:4 atIndex:7];[enc setBytes:&input_stride length:4 atIndex:8];[enc setBytes:&output_stride length:4 atIndex:9];
        [enc setBuffer:partial offset:0 atIndex:10];
        [enc setBuffer:group_partial offset:0 atIndex:11];
        [enc dispatchThreadgroups:MTLSizeMake((shape->out_dim+31u)/32u,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];
        [enc endEncoding];[cmd commit];[cmd waitUntilCompleted];
        if(cmd.status!=MTLCommandBufferStatusCompleted){fprintf(stderr,"ERROR: partial MMA command: %s\n",cmd.error.localizedDescription.UTF8String?:"unknown");return 1;}
        size_t output_count=8u*(size_t)shape->out_dim;
        size_t output_exact=target_verify_m8_exact_count((const float*)output.contents,(const float*)baseline.contents,output_count);
        if(output_exact!=output_count){fprintf(stderr,"ERROR: instrumented MMA output changed: %zu/%zu\n",output_exact,output_count);return 1;}
        const float *prod_values=(const float*)production.contents,*scaled_values=(const float*)scaled_output.contents;
        size_t scaled_exact=target_verify_m8_exact_count(prod_values,scaled_values,output_count);
        double scaled_max=0.0,scaled_sum_sq=0.0;
        for(size_t v=0;v<output_count;v++){
            double d=fabs((double)prod_values[v]-(double)scaled_values[v]);
            if(d>scaled_max)scaled_max=d;scaled_sum_sq+=d*d;
        }
        printf("%s scale_inside_MMA_vs_M1 bitwise=%zu/%zu max_abs=%.9g rms=%.9g\n",shape->label,scaled_exact,output_count,scaled_max,sqrt(scaled_sum_sq/(double)output_count));
        const uint32_t *weights=(const uint32_t*)((const char*)tensor->weight_buf.contents+tensor->weight_off);
        const uint16_t *scales=(const uint16_t*)((const char*)tensor->weight_buf.contents+tensor->scale_off);
        const uint16_t *biases=(const uint16_t*)((const char*)tensor->weight_buf.contents+tensor->bias_off);
        const float *gpu=(const float*)partial.contents;
        char dump_path[256];snprintf(dump_path,sizeof(dump_path),"../benchmark-logs/affine-mma-partials-%s.bin",shape->label);
        FILE *dump=fopen(dump_path,"wb");if(!dump){perror(dump_path);return 1;}
        uint32_t header[4]={0x33414d4du,shape->out_dim,shape->in_dim,16u};
        size_t wrote=0;
        wrote+=fwrite(header,sizeof(uint32_t),4,dump)==4;
        wrote+=fwrite(rows,sizeof(float),8u*shape->in_dim,dump)==8u*shape->in_dim;
        wrote+=fwrite(weights,sizeof(uint32_t),16u*(shape->in_dim/8u),dump)==16u*(shape->in_dim/8u);
        wrote+=fwrite(scales,sizeof(uint16_t),16u*(shape->in_dim/64u),dump)==16u*(shape->in_dim/64u);
        wrote+=fwrite(biases,sizeof(uint16_t),16u*(shape->in_dim/64u),dump)==16u*(shape->in_dim/64u);
        wrote+=fwrite(gpu,sizeof(float),32u*8u*8u*16u,dump)==32u*8u*8u*16u;
        for(int row=0;row<8;row++)wrote+=fwrite((const float*)production.contents+(size_t)row*shape->out_dim,sizeof(float),16,dump)==16;
        for(int row=0;row<8;row++)wrote+=fwrite((const float*)baseline.contents+(size_t)row*shape->out_dim,sizeof(float),16,dump)==16;
        int close_result=fclose(dump);if(wrote!=6u+16u || close_result){fprintf(stderr,"ERROR: partial dump incomplete: %s\n",dump_path);return 1;}
        printf("  partial_dump=%s\n",dump_path);
        char full_path[256];snprintf(full_path,sizeof(full_path),"../benchmark-logs/affine-mma-full-%s.bin",shape->label);
        FILE *full=fopen(full_path,"wb");if(!full){perror(full_path);return 1;}
        uint32_t full_header[4]={0x34414d4du,shape->out_dim,shape->in_dim,16u};
        size_t full_wrote=0;
        full_wrote+=fwrite(full_header,4,4,full)==4;
        full_wrote+=fwrite(rows,4,8u*shape->in_dim,full)==8u*shape->in_dim;
        full_wrote+=fwrite(scales,2,(size_t)shape->out_dim*32u,full)==(size_t)shape->out_dim*32u;
        full_wrote+=fwrite(biases,2,(size_t)shape->out_dim*32u,full)==(size_t)shape->out_dim*32u;
        full_wrote+=fwrite(group_partial.contents,4,(size_t)32u*8u*shape->out_dim,full)==(size_t)32u*8u*shape->out_dim;
        full_wrote+=fwrite(production.contents,4,(size_t)8u*shape->out_dim,full)==(size_t)8u*shape->out_dim;
        full_wrote+=fwrite(baseline.contents,4,(size_t)8u*shape->out_dim,full)==(size_t)8u*shape->out_dim;
        int full_close=fclose(full);if(full_wrote!=7u||full_close){fprintf(stderr,"ERROR: full partial dump incomplete: %s\n",full_path);return 1;}
        printf("  full_dump=%s\n",full_path);
        size_t matches[4]={0},matches_s0[4]={0},total=0,total_s0=0;
        double max_error[4]={0};
        for(int g=0;g<32;g++)for(int s=0;s<8;s++)for(int row=0;row<8;row++)for(int n=0;n<16;n++) {
            float old=s?gpu[((((g*8+s-1)*8+row)*16)+n)]:0.0f;
            float actual=gpu[((((g*8+s)*8+row)*16)+n)];
            float qa[8],xb[8],products[8];
            float ps=ldexpf(1.0f,-4*s);
            for(int k=0;k<8;k++){
                uint32_t packed=weights[n*256+g*8+k];
                qa[k]=(float)(packed & (15u<<(4*s)));
                xb[k]=rows[row*2048+g*64+k*8+s]*ps;
                products[k]=qa[k]*xb[k];
            }
            float v[4]={old,old,old,old};
            for(int k=0;k<8;k++) v[0]=fmaf(qa[k],xb[k],v[0]);
            for(int k=7;k>=0;k--) v[1]=fmaf(qa[k],xb[k],v[1]);
            for(int k=0;k<8;k++) v[2]+=products[k];
            float tree[8];memcpy(tree,products,sizeof(tree));
            for(int width=1;width<8;width*=2)for(int k=0;k<8;k+=2*width)tree[k]=fmaf(tree[k+width],1.0f,tree[k]);
            v[3]=fmaf(tree[0],1.0f,old);
            for(int mode=0;mode<4;mode++){
                matches[mode]+=affine_tree_bits(v[mode])==affine_tree_bits(actual);
                if(s==0)matches_s0[mode]+=affine_tree_bits(v[mode])==affine_tree_bits(actual);
                double error=fabs((double)v[mode]-(double)actual);if(error>max_error[mode])max_error[mode]=error;
            }
            total++;if(s==0)total_s0++;
        }
        printf("%s instrumented_M8_output_bitwise=%zu/%zu partials=%zu\n",shape->label,output_exact,output_count,total);
        const char *names[4]={"ascending_fma","descending_fma","ascending_mul_add","pairwise_products"};
        for(int mode=0;mode<4;mode++)printf("  tree %-20s bitwise=%zu/%zu step0=%zu/%zu max_abs=%.9g\n",names[mode],matches[mode],total,matches_s0[mode],total_s0,max_error[mode]);
        tested++;
    }
    return tested==2?0:1;
}
#endif
