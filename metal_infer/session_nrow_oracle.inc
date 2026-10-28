// Diagnostic-only matched-token scalar/N128 oracle. Two bounded reference banks;
// no production snapshot pool, no intermediate batch-state claims.
static NSDictionary *sn_diff(const char *kind,int layer,const float *a,const float *b,size_t n) {
    double maximum=0.0,sum=0.0;size_t different=0,nonfinite=0;
    for(size_t i=0;i<n;i++) {
        if(!isfinite(a[i]) || !isfinite(b[i])) {nonfinite++;continue;}
        double d=fabs((double)a[i]-b[i]);maximum=fmax(maximum,d);sum+=d*d;different+=(d!=0.0);
    }
    return @{@"component":@(kind),@"layer":@(layer),@"floats":@(n),@"different":@(different),
        @"max_abs":@(maximum),@"rms":@(n?sqrt(sum/n):0),@"nonfinite":@(nonfinite)};
}
static NSArray *sn_state(const ServeStateSnapshot *ref,const ServeStateSnapshot *cand,KVCache **kv,int pos) {
    NSMutableArray *parts=[NSMutableArray array];int li=0;
    for(int l=0;l<NUM_LAYERS;l++) {
        if(kv[l]) {
            size_t n=(size_t)pos*NUM_KV_HEADS*HEAD_DIM;
            [parts addObject:sn_diff("kv_k",l,ref->k_snapshot[l],cand->k_snapshot[l],n)];
            [parts addObject:sn_diff("kv_v",l,ref->v_snapshot[l],cand->v_snapshot[l],n)];
            int fi=(l+1)/FULL_ATTN_INTERVAL-1;
            [parts addObject:sn_diff("mirror_k",l,cand->k_snapshot[l],g_metal->buf_kv_k[fi].contents,n)];
            [parts addObject:sn_diff("mirror_v",l,cand->v_snapshot[l],g_metal->buf_kv_v[fi].contents,n)];
        } else {
            [parts addObject:sn_diff("gpu_gdn",l,ref->gpu_delta_snapshot[li],cand->gpu_delta_snapshot[li],LINEAR_NUM_V_HEADS*LINEAR_VALUE_DIM*LINEAR_KEY_DIM)];
            [parts addObject:sn_diff("gpu_conv",l,ref->gpu_conv_snapshot[li],cand->gpu_conv_snapshot[li],(CONV_KERNEL_SIZE-1)*LINEAR_CONV_DIM)];
            [parts addObject:sn_diff("cpu_gdn_shadow",l,ref->la_ssm_snapshot[l],cand->la_ssm_snapshot[l],LINEAR_NUM_V_HEADS*LINEAR_VALUE_DIM*LINEAR_KEY_DIM)];
            [parts addObject:sn_diff("cpu_conv_shadow",l,ref->la_conv_snapshot[l],cand->la_conv_snapshot[l],(CONV_KERNEL_SIZE-1)*LINEAR_CONV_DIM)];li++;
        }
    }
    return parts;
}
static int sn_forward(WeightFile *wf,KVCache **kv,void **states,void **maps,int *fds,int K,float *hidden,const uint32_t *ids,int pos,int count,int batch) {
    if(batch) {
        if(count!=PREFILL_NROW_CAPTURE_ROWS || !prefill_nrow_runtime_cache_range_eligible(kv))return 0;
        return prefill_nrow_runtime_chunk(wf,kv,states,maps,fds,K,pos,ids,NULL,hidden,NULL,NULL) && complete_deferred_experts();
    }
    for(int i=0;i<count;i++) {
        embed_lookup(wf,ids[i],hidden);
        if(!run_all_layers_checked(wf,hidden,kv,states,maps,fds,pos+i,K) || !complete_deferred_experts())return 0;
    }
    return 1;
}
static int sn_oracle(WeightFile *wf,KVCache **kv,void **states,void **maps,int *fds,int K,uint16_t *norm) {
    NSData *data=[NSData dataWithContentsOfFile:@(getenv("FLASH_SESSION_NROW_ORACLE_INPUT"))];
    if(!data || data.length>65536 || !sd_enabled())return 2;
    id input=[NSJSONSerialization JSONObjectWithData:data options:0 error:NULL];
    if(![input isKindOfClass:NSDictionary.class])return 2;
    NSArray *tokens=input[@"token_ids"],*starts=input[@"batch_starts"];
    if(![tokens isKindOfClass:NSArray.class] || !tokens.count || tokens.count>SESSION_DIAG_LIMIT || ![starts isKindOfClass:NSArray.class])return 2;
    uint32_t ids[SESSION_DIAG_LIMIT];int count=(int)tokens.count;
    for(int i=0;i<count;i++) {if(![tokens[i] isKindOfClass:NSNumber.class] || [tokens[i] intValue]<0 || [tokens[i] intValue]>=VOCAB_SIZE)return 2;ids[i]=[tokens[i] intValue];}
    int last=-PREFILL_NROW_CAPTURE_ROWS;
    for(id start in starts) {if(![start isKindOfClass:NSNumber.class] || [start intValue]<last+PREFILL_NROW_CAPTURE_ROWS || [start intValue]+PREFILL_NROW_CAPTURE_ROWS>count)return 2;last=[start intValue];}
    ServeStateSnapshot ref={0},cand={0};NSMutableArray *rows=[NSMutableArray array];
    float *rh=malloc(HIDDEN_DIM*sizeof(float)),*ch=malloc(HIDDEN_DIM*sizeof(float));
    float *rl=malloc(VOCAB_SIZE*sizeof(float)),*cl=malloc(VOCAB_SIZE*sizeof(float));
    int ok=rh&&ch&&rl&&cl;int batches=0,pos=0,exact=1;
    reset_delta_net_state();g_forward_error=0;
    if(ok)ok=serve_state_snapshot_capture(&ref,kv,states,0)&&serve_state_snapshot_capture(&cand,kv,states,0);
    NSString *initial_digest=sd_fingerprint(kv,states,0,"oracle_zero")[@"digest"];
    while(ok && pos<count) {
        BOOL batch=[starts containsObject:@(pos)];int n=batch?PREFILL_NROW_CAPTURE_ROWS:1;
        // Skip comparing uninteresting scalar prefix positions, but still run
        // both copies; their identical endpoint is checked at each following row.
        if(!serve_state_snapshot_restore(&ref,kv,states) || !sn_forward(wf,kv,states,maps,fds,K,rh,ids+pos,pos,n,0) || !serve_state_snapshot_capture(&ref,kv,states,pos+n)) {ok=0;break;}
        NSString *reference_digest=sd_fingerprint(kv,states,pos+n,"oracle_reference")[@"digest"];
        if(!serve_state_snapshot_restore(&cand,kv,states) || !sn_forward(wf,kv,states,maps,fds,K,ch,ids+pos,pos,n,batch) || !serve_state_snapshot_capture(&cand,kv,states,pos+n)) {ok=0;break;}
        pos+=n;batches+=batch;
        NSString *candidate_digest=sd_fingerprint(kv,states,pos,"oracle_candidate")[@"digest"];
        NSDictionary *h=sn_diff("hidden",-1,rh,ch,HIDDEN_DIM);
        apply_final_norm_inplace(rh,norm);lm_head_forward(wf,rh,rl);
        apply_final_norm_inplace(ch,norm);lm_head_forward(wf,ch,cl);
        NSDictionary *logits=sn_diff("logits",-1,rl,cl,VOCAB_SIZE);
        NSArray *parts=sn_state(&ref,&cand,kv,pos);BOOL lengths=YES,finite=YES;double state_max=0;NSUInteger changed=0;
        for(int l=0;l<NUM_LAYERS;l++)if(kv[l])lengths&=kv[l]->len==pos && ref.kv_len[l]==pos && cand.kv_len[l]==pos;
        for(NSDictionary *part in parts) {finite&=[part[@"nonfinite"] unsignedLongValue]==0;double d=[part[@"max_abs"] doubleValue];state_max=fmax(state_max,d);changed+=[part[@"different"] unsignedLongValue];if([part[@"component"] hasPrefix:@"mirror_"] && d!=0)lengths=NO;}
        finite&=[h[@"nonfinite"] intValue]==0 && [logits[@"nonfinite"] intValue]==0;
        int rt=cpu_argmax(rl,VOCAB_SIZE),ct=cpu_argmax(cl,VOCAB_SIZE);
        BOOL pass=lengths && finite && state_max<1e-3 && [h[@"max_abs"] doubleValue]<=1e-3 && [logits[@"max_abs"] doubleValue]<=1e-2 && rt==ct;
        exact&=changed==0 && [h[@"different"] unsignedLongValue]==0 && [logits[@"different"] unsignedLongValue]==0;
        [rows addObject:@{@"position":@(pos),@"candidate_digest":candidate_digest,@"reference_digest":reference_digest,@"batch_rows":@(batch?n:0),@"state_max_abs":@(state_max),@"state_different":@(changed),@"hidden":h,@"logits":logits,@"greedy_equal":@(rt==ct),@"kv_lengths_and_mirrors":@(lengths),@"finite":@(finite),@"pass":@(pass),@"components":parts}];
        fprintf(stderr,"[session-n128] pos=%d batch=%d state=%.9g hidden=%.9g logits=%.9g greedy=%d pass=%d\n",pos,batch,state_max,[h[@"max_abs"] doubleValue],[logits[@"max_abs"] doubleValue],rt==ct,pass);
        if(!pass){ok=0;break;}
    }
    sd_write(@"nrow-oracle.json",@{@"status":ok?@"NUMERICAL_PASS":@"FAIL",@"initial_digest":initial_digest,@"bit_exact":@(exact),@"completed_position":@(pos),@"input_tokens":@(count),@"batches":@(batches),@"threshold_source":@"prefill_nrow_control.inc and target_verify_grouped.inc at c35dc78: state<1e-3 hidden<=1e-3 logits<=1e-2, greedy identity, finite, exact KV lengths/mirrors",@"rows":rows});
    serve_state_snapshot_free(&ref);serve_state_snapshot_free(&cand);free(rh);free(ch);free(rl);free(cl);
    return ok?0:3;
}
