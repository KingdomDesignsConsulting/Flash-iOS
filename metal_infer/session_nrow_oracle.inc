// Routing observations are real per-layer decisions, not intermediate model-state claims.
static NSMutableDictionary *sn_routes[2];
static int sn_route_phase,sn_probe_lo,sn_probe_hi,sn_probe_layers;
static void sn_capture_route(int layer,int pos,int count,const int *ids,const float *weights,const float *scores) {
    if(pos<sn_probe_lo || pos>=sn_probe_hi || layer>=sn_probe_layers || count!=8)return;
    NSMutableArray *selected=[NSMutableArray array],*w=[NSMutableArray array],*raw=[NSMutableArray array];
    for(int i=0;i<count;i++){[selected addObject:@(ids[i])];[w addObject:@(weights[i])];}
    for(int i=0;i<NUM_EXPERTS;i++)[raw addObject:@(scores[i])];
    sn_routes[sn_route_phase][[NSString stringWithFormat:@"%d:%d",layer,pos]]=@{@"layer":@(layer),@"position":@(pos),@"experts":selected,@"weights":w,@"router_scores":raw};
}
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
            int fi=(l+1)/FULL_ATTN_INTERVAL-1;
            size_t bytes=(size_t)pos*NUM_KV_HEADS*HEAD_DIM*sizeof(float);
            if(ref->kv_len[l]!=pos || cand->kv_len[l]!=pos || bytes>g_metal->buf_kv_k[fi].length || bytes>g_metal->buf_kv_v[fi].length) {
                [parts addObject:@{@"component":@"invalid_cache_extent",@"layer":@(l),@"floats":@0,@"different":@0,@"max_abs":@0,@"rms":@0,@"nonfinite":@0,@"invalid_extent":@YES}];continue;
            }
            size_t n=(size_t)pos*NUM_KV_HEADS*HEAD_DIM;
            [parts addObject:sn_diff("kv_k",l,ref->k_snapshot[l],cand->k_snapshot[l],n)];
            [parts addObject:sn_diff("kv_v",l,ref->v_snapshot[l],cand->v_snapshot[l],n)];
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
    if(!data || data.length>1024*1024 || !sd_enabled())return 2;
    id input=[NSJSONSerialization JSONObjectWithData:data options:0 error:NULL];
    if(![input isKindOfClass:NSDictionary.class])return 2;
    NSArray *tokens=input[@"token_ids"],*starts=input[@"batch_starts"];
    if(![tokens isKindOfClass:NSArray.class] || !tokens.count || tokens.count>SESSION_ORACLE_LIMIT || tokens.count>(NSUInteger)g_kv_seq_len || tokens.count>(NSUInteger)GPU_KV_SEQ || ![starts isKindOfClass:NSArray.class])return 2;
    uint32_t ids[SESSION_ORACLE_LIMIT];int count=(int)tokens.count;sd_state_limit=count;
    for(int i=0;i<count;i++) {if(![tokens[i] isKindOfClass:NSNumber.class] || [tokens[i] intValue]<0 || [tokens[i] intValue]>=VOCAB_SIZE)return 2;ids[i]=[tokens[i] intValue];}
    int last=-PREFILL_NROW_CAPTURE_ROWS;
    for(id start in starts) {if(![start isKindOfClass:NSNumber.class] || [start intValue]<last+PREFILL_NROW_CAPTURE_ROWS || [start intValue]+PREFILL_NROW_CAPTURE_ROWS>count)return 2;last=[start intValue];}
    NSArray *scalar_slabs=input[@"scalar_slab_starts"];
    if(scalar_slabs && ![scalar_slabs isKindOfClass:NSArray.class])return 2;
    for(id start in scalar_slabs)if(![start isKindOfClass:NSNumber.class] || [start intValue]<0 || [start intValue]+PREFILL_NROW_CAPTURE_ROWS>count || [starts containsObject:start])return 2;
    if(input[@"route_probe_start"]) {
        sn_probe_lo=[input[@"route_probe_start"] intValue];sn_probe_hi=sn_probe_lo+PREFILL_NROW_CAPTURE_ROWS;
        sn_probe_layers=12;sn_routes[0]=[NSMutableDictionary dictionary];sn_routes[1]=[NSMutableDictionary dictionary];g_session_route_hook=sn_capture_route;
    }
    ServeStateSnapshot ref={0},cand={0},probe_anchor={0};NSMutableArray *rows=[NSMutableArray array];
    float *rh=malloc(HIDDEN_DIM*sizeof(float)),*ch=malloc(HIDDEN_DIM*sizeof(float));
    float *rl=malloc(VOCAB_SIZE*sizeof(float)),*cl=malloc(VOCAB_SIZE*sizeof(float));
    float raw_ref[HIDDEN_DIM];
    int ok=rh&&ch&&rl&&cl;int batches=0,pos=0,exact=1;
    reset_delta_net_state();g_forward_error=0;
    if(ok)ok=serve_state_snapshot_capture(&ref,kv,states,0)&&serve_state_snapshot_capture(&cand,kv,states,0);
    NSString *initial_digest=sd_fingerprint(kv,states,0,"oracle_zero")[@"digest"];
    while(ok && pos<count) {
        BOOL batch=[starts containsObject:@(pos)];int n=(batch || [scalar_slabs containsObject:@(pos)])?PREFILL_NROW_CAPTURE_ROWS:1;
        // Compare completed slabs/explicit scalar blocks and scalar-tail positions.
        // No intermediate full-model state is inferred for either kind of block.
        if(g_session_route_hook && pos==sn_probe_lo) {
            if(!serve_state_snapshot_restore(&ref,kv,states) || !serve_state_snapshot_capture(&probe_anchor,kv,states,pos)){ok=0;break;}
        }
        sn_route_phase=0;
        if(!serve_state_snapshot_restore(&ref,kv,states) || !sn_forward(wf,kv,states,maps,fds,K,rh,ids+pos,pos,n,0) || !serve_state_snapshot_capture(&ref,kv,states,pos+n)) {ok=0;break;}
        NSString *reference_digest=sd_fingerprint(kv,states,pos+n,"oracle_reference")[@"digest"];
        sn_route_phase=1;
        if(!serve_state_snapshot_restore(&cand,kv,states) || !sn_forward(wf,kv,states,maps,fds,K,ch,ids+pos,pos,n,batch) || !serve_state_snapshot_capture(&cand,kv,states,pos+n)) {ok=0;break;}
        pos+=n;batches+=batch;
        NSString *candidate_digest=sd_fingerprint(kv,states,pos,"oracle_candidate")[@"digest"];
        memcpy(raw_ref,rh,HIDDEN_DIM*sizeof(float));
        NSDictionary *h=sn_diff("hidden",-1,rh,ch,HIDDEN_DIM);
        apply_final_norm_inplace(rh,norm);lm_head_forward(wf,rh,rl);
        apply_final_norm_inplace(ch,norm);lm_head_forward(wf,ch,cl);
        NSDictionary *logits=sn_diff("logits",-1,rl,cl,VOCAB_SIZE);
        NSArray *parts=sn_state(&ref,&cand,kv,pos);BOOL lengths=YES,finite=YES;double state_max=0;NSUInteger changed=0;
        for(int l=0;l<NUM_LAYERS;l++)if(kv[l])lengths&=kv[l]->len==pos && ref.kv_len[l]==pos && cand.kv_len[l]==pos;
        for(NSDictionary *part in parts) {if([part[@"invalid_extent"] boolValue])lengths=NO;finite&=[part[@"nonfinite"] unsignedLongValue]==0;double d=[part[@"max_abs"] doubleValue];state_max=fmax(state_max,d);changed+=[part[@"different"] unsignedLongValue];if([part[@"component"] hasPrefix:@"mirror_"] && d!=0)lengths=NO;}
        finite&=[h[@"nonfinite"] intValue]==0 && [logits[@"nonfinite"] intValue]==0;
        int rt=cpu_argmax(rl,VOCAB_SIZE),ct=cpu_argmax(cl,VOCAB_SIZE);
        BOOL pass=lengths && finite && state_max<1e-3 && [h[@"max_abs"] doubleValue]<=1e-3 && [logits[@"max_abs"] doubleValue]<=1e-2 && rt==ct;
        exact&=changed==0 && [h[@"different"] unsignedLongValue]==0 && [logits[@"different"] unsignedLongValue]==0;
        [rows addObject:@{@"position":@(pos),@"candidate_digest":candidate_digest,@"reference_digest":reference_digest,@"batch_rows":@(batch?n:0),@"step_rows":@(n),@"state_max_abs":@(state_max),@"state_different":@(changed),@"hidden":h,@"logits":logits,@"greedy_equal":@(rt==ct),@"kv_lengths_and_mirrors":@(lengths),@"finite":@(finite),@"pass":@(pass),@"components":parts}];
        fprintf(stderr,"[session-n128] pos=%d batch=%d state=%.9g hidden=%.9g logits=%.9g greedy=%d pass=%d\n",pos,batch,state_max,[h[@"max_abs"] doubleValue],[logits[@"max_abs"] doubleValue],rt==ct,pass);
        if(!pass){ok=0;break;}
    }
    sd_write(@"nrow-oracle.json",@{@"status":ok?@"NUMERICAL_PASS":@"FAIL",@"initial_digest":initial_digest,@"bit_exact":@(exact),@"completed_position":@(pos),@"input_tokens":@(count),@"batches":@(batches),@"threshold_source":@"prefill_nrow_control.inc and target_verify_grouped.inc at c35dc78: state<1e-3 hidden<=1e-3 logits<=1e-2, greedy identity, finite, exact KV lengths/mirrors",@"rows":rows});
    if(g_session_route_hook)sd_write(@"route-probe.json",@{@"reference":sn_routes[0],@"candidate":sn_routes[1],@"start":@(sn_probe_lo),@"end":@(sn_probe_hi),@"layers":@(sn_probe_layers)});
    g_session_route_hook=NULL;sn_routes[0]=nil;sn_routes[1]=nil;
    // Counterfactual only: isolate upstream drift from the final slab's math.
    // This does not change the failed qualification result or serving policy.
    if(!ok && probe_anchor.valid && pos==sn_probe_hi) {
        int probe_ok=serve_state_snapshot_restore(&probe_anchor,kv,states) &&
            sn_forward(wf,kv,states,maps,fds,K,ch,ids+sn_probe_lo,sn_probe_lo,PREFILL_NROW_CAPTURE_ROWS,1) &&
            serve_state_snapshot_capture(&cand,kv,states,pos);
        if(probe_ok) {
            NSArray *parts=sn_state(&ref,&cand,kv,pos);double maximum=0;for(NSDictionary *part in parts)maximum=fmax(maximum,[part[@"max_abs"] doubleValue]);
            NSDictionary *h=sn_diff("hidden",-1,raw_ref,ch,HIDDEN_DIM);apply_final_norm_inplace(ch,norm);lm_head_forward(wf,ch,cl);
            NSDictionary *logits=sn_diff("logits",-1,rl,cl,VOCAB_SIZE);
            sd_write(@"counterfactual-rebase.json",@{@"qualification":@"FAIL retained; diagnostic intervention only",@"reference_anchor":@(sn_probe_lo),@"end_position":@(pos),@"state_max_abs":@(maximum),@"hidden":h,@"logits":logits,@"greedy_equal":@(cpu_argmax(rl,VOCAB_SIZE)==cpu_argmax(cl,VOCAB_SIZE)),@"components":parts});
        }
    }
    serve_state_snapshot_free(&probe_anchor);
    serve_state_snapshot_free(&ref);serve_state_snapshot_free(&cand);free(rh);free(ch);free(rl);free(cl);
    return ok?0:3;
}
