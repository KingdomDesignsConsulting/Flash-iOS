// Bounded diagnostic build only. Never changes the chat template or sampler.
#include <CommonCrypto/CommonDigest.h>
#ifndef SESSION_DIAG_LIMIT
#define SESSION_DIAG_LIMIT 512
#endif
#ifndef SESSION_PREFILL_OBSERVE_STRIDE
#define SESSION_PREFILL_OBSERVE_STRIDE 1
#endif
#if SESSION_DIAG_LIMIT < 512 || SESSION_DIAG_LIMIT > 32768 || SESSION_PREFILL_OBSERVE_STRIDE < 1 || SESSION_PREFILL_OBSERVE_STRIDE > 128
#error diagnostic history/observation bounds exceeded
#endif
#define SESSION_ORACLE_LIMIT 32768
static int sd_state_limit=SESSION_DIAG_LIMIT;
static NSDictionary *sd_replay_expected_points;
static BOOL sd_should_observe(int position,const char *phase) {
    if(sd_replay_expected_points)
        return sd_replay_expected_points[[NSString stringWithFormat:@"%d",position]]!=nil;
    // Retain every input token. Only scalar prefill observations may be sparse;
    // final prefill, decode/EOS and request boundaries remain explicit.
    return SESSION_PREFILL_OBSERVE_STRIDE==1 || strcmp(phase,"prefill") ||
        position%SESSION_PREFILL_OBSERVE_STRIDE==0;
}
#if SESSION_PREFILL_OBSERVE_STRIDE > 1
static BOOL sd_sparse_points_valid(id points,NSUInteger count) {
    if(![points isKindOfClass:NSDictionary.class] || ![points count] || !count)return NO;
    id final=points[[NSString stringWithFormat:@"%lu",(unsigned long)count]];
    return [final isKindOfClass:NSString.class] && [final length]==64;
}
#endif
static NSMutableArray *sd_history,*sd_steps;
static NSArray *sd_base_tokens;
static NSString *sd_identity;
static BOOL sd_history_complete;
static int sd_initial_pos,sd_polled_layers;
static id<MTLBuffer> sd_combine_capture;
static NSDictionary *sd_combine_capture_metadata;
static BOOL sd_dump_identity_selected(void) {
    const char *identity=getenv("FLASH_SESSION_STATE_DUMP_IDENTITY");
    return !identity || (sd_identity && [sd_identity isEqualToString:@(identity)]);
}
// Diagnostic producer-ordered copy: no early fence or inference-state writes.
static void sd_capture_combine(id<MTLCommandBuffer> cmd,int layer,int pos,const int *ids,int count) {
    const char *enabled=getenv("FLASH_SESSION_COMBINE_CAPTURE");
    const char *at=getenv("FLASH_SESSION_STATE_DUMP_POSITION");
    const char *selected=getenv("FLASH_SESSION_COMBINE_LAYER");
    if(!enabled || strcmp(enabled,"1") || !at || pos!=atoi(at)-1 ||
       layer!=(selected?atoi(selected):0) || count!=8 || !sd_dump_identity_selected())return;
    size_t bytes=HIDDEN_DIM*sizeof(float);
    id<MTLBuffer> dst=[g_metal->device newBufferWithLength:11*bytes+10*sizeof(float) options:MTLResourceStorageModeShared];
    id<MTLBlitCommandEncoder> encoder=dst?[cmd blitCommandEncoder]:nil;
    if(!encoder){fprintf(stderr,"[session-state] combine capture unavailable\n");return;}
    [encoder copyFromBuffer:g_metal->buf_h_mid sourceOffset:0 toBuffer:dst destinationOffset:0 size:bytes];
    [encoder copyFromBuffer:g_metal->buf_shared_out sourceOffset:0 toBuffer:dst destinationOffset:bytes size:bytes];
    for(int k=0;k<8;k++)[encoder copyFromBuffer:g_metal->buf_multi_expert_out[k] sourceOffset:0 toBuffer:dst destinationOffset:(2+k)*bytes size:bytes];
    [encoder copyFromBuffer:g_metal->buf_moe_hidden sourceOffset:0 toBuffer:dst destinationOffset:10*bytes size:bytes];
    [encoder copyFromBuffer:g_metal->buf_combine_params sourceOffset:0 toBuffer:dst destinationOffset:11*bytes size:10*sizeof(float)];
    [encoder endEncoding];sd_combine_capture=dst;
    NSMutableArray *experts=[NSMutableArray array];for(int k=0;k<8;k++)[experts addObject:@(ids[k])];
    sd_combine_capture_metadata=@{@"trace_identity":sd_identity,@"layer":@(layer),@"input_position":@(pos),@"expert_ids":experts,@"hidden_dim":@(HIDDEN_DIM),@"layout":@"h_mid, shared_out, expert_out[8], combined_out, combine_params[10]; native float32"};
}
static void sd_progress(const char *phase,int position);
static BOOL sd_enabled(void) {
    const char *p=getenv("FLASH_SESSION_TOKEN_TRACE_DIR");return p && *p;
}
static NSString *sd_sha(const void *data,size_t bytes) {
    unsigned char sum[CC_SHA256_DIGEST_LENGTH];CC_SHA256(data,(CC_LONG)bytes,sum);
    char text[65];for(int i=0;i<32;i++)snprintf(text+2*i,3,"%02x",sum[i]);
    return @(text);
}
static BOOL sd_write(NSString *name,id object) {
    const char *folder=getenv("FLASH_SESSION_TOKEN_TRACE_DIR");if(!folder)return NO;
    NSData *data=[NSJSONSerialization dataWithJSONObject:object options:0 error:NULL];
    NSString *path=[@(folder) stringByAppendingPathComponent:name];NSError *error=nil;
    BOOL ok=data && [data writeToFile:path options:NSDataWritingAtomic error:&error];
    if(!ok)fprintf(stderr,"[session-state] diagnostic write failed: %s\n",error.localizedDescription.UTF8String);
    return ok;
}
static NSDictionary *sd_component(const char *kind,int layer,const void *data,size_t bytes,BOOL active,int position) {
    NSUInteger nonfinite=0;const float *f=data;
    for(size_t i=0;i<bytes/sizeof(float);i++)if(!isfinite(f[i]))nonfinite++;
    const char *filter=getenv("FLASH_SESSION_STATE_DUMP_COMPONENT");
    const char *at=getenv("FLASH_SESSION_STATE_DUMP_POSITION");
    char component[80];snprintf(component,sizeof(component),"%s:%d",kind,layer);
    if(filter && at && atoi(at)==position && sd_identity && sd_dump_identity_selected() &&
       (!strcmp(filter,component) || (!strcmp(filter,"active") && active && position<=512))) {
        NSString *name=[NSString stringWithFormat:@"%@-p%d-%s-%d.f32",sd_identity,position,kind,layer];
        NSString *path=[@(getenv("FLASH_SESSION_TOKEN_TRACE_DIR")) stringByAppendingPathComponent:name];
        [[NSData dataWithBytes:data length:bytes] writeToFile:path atomically:YES];
    }
    return @{@"component":@(kind),@"layer":@(layer),@"bytes":@(bytes),
             @"sha256":sd_sha(data,bytes),@"nonfinite":@(nonfinite),@"active":@(active)};
}
static NSDictionary *sd_fingerprint(KVCache **kv,void **states,int pos,const char *phase) {
    if(!state_snapshot_restore_fence())return @{@"position":@(pos),@"error":@"GPU fence failed"};
    if(sd_combine_capture && [sd_combine_capture_metadata[@"input_position"] intValue]+1==pos &&
       [sd_combine_capture_metadata[@"trace_identity"] isEqual:sd_identity]) {
        NSString *name=[NSString stringWithFormat:@"%@-combine-p%d-l%@",sd_identity,pos,sd_combine_capture_metadata[@"layer"]];
        NSString *path=[@(getenv("FLASH_SESSION_TOKEN_TRACE_DIR")) stringByAppendingPathComponent:[name stringByAppendingString:@".f32"]];
        [[NSData dataWithBytes:sd_combine_capture.contents length:sd_combine_capture.length] writeToFile:path atomically:YES];
        sd_write([name stringByAppendingString:@".json"],sd_combine_capture_metadata);
        sd_combine_capture=nil;sd_combine_capture_metadata=nil;
    }
    NSMutableArray *parts=[NSMutableArray array];BOOL lengths=YES;
    const size_t kv_unit=NUM_KV_HEADS*HEAD_DIM*sizeof(float);
    const size_t ssm=LINEAR_NUM_V_HEADS*LINEAR_VALUE_DIM*LINEAR_KEY_DIM*sizeof(float);
    const size_t conv=(CONV_KERNEL_SIZE-1)*LINEAR_CONV_DIM*sizeof(float);
    BOOL gpu=snapshot_uses_gpu_linear_state();int li=0;
    for(int l=0;l<NUM_LAYERS;l++) {
        if(kv[l]) {
            lengths &= kv[l]->len==pos;
            if(kv[l]->len<0 || kv[l]->len>sd_state_limit)return @{@"error":@"KV length outside diagnostic bound"};
            size_t bytes=kv[l]->len*kv_unit;
            [parts addObject:sd_component("cpu_k",l,kv[l]->k_cache,bytes,YES,pos)];
            [parts addObject:sd_component("cpu_v",l,kv[l]->v_cache,bytes,YES,pos)];
            int fa=(l+1)/FULL_ATTN_INTERVAL-1;
            if(g_metal && g_metal->buf_kv_k[fa]) {
                if(bytes>g_metal->buf_kv_k[fa].length || bytes>g_metal->buf_kv_v[fa].length)return @{@"position":@(pos),@"error":@"GPU mirror extent outside diagnostic range"};
                [parts addObject:sd_component("gpu_k",l,g_metal->buf_kv_k[fa].contents,bytes,YES,pos)];
                [parts addObject:sd_component("gpu_v",l,g_metal->buf_kv_v[fa].contents,bytes,YES,pos)];
            }
        } else if(states[l]) {
            LinearAttnState *la=states[l];
            [parts addObject:sd_component("cpu_gdn",l,la->ssm_state,ssm,!gpu,pos)];
            [parts addObject:sd_component("cpu_conv",l,la->conv_state,conv,!gpu,pos)];
            if(gpu) {
                if(g_metal->buf_delta_state[li].length<ssm || g_metal->buf_conv_state[li].length<conv)return @{@"error":@"GPU geometry exceeds buffers"};
                [parts addObject:sd_component("gpu_gdn",l,g_metal->buf_delta_state[li].contents,ssm,YES,pos)];
                [parts addObject:sd_component("gpu_conv",l,g_metal->buf_conv_state[li].contents,conv,YES,pos)];
            }
            li++;
        }
    }
    NSMutableString *key=[NSMutableString string];
    for(NSDictionary *part in parts)[key appendFormat:@"%@:%@:%@;",part[@"component"],part[@"layer"],part[@"sha256"]];
    NSData *keyBytes=[key dataUsingEncoding:NSUTF8StringEncoding];
    return @{@"position":@(pos),@"phase":@(phase),@"kv_lengths_match":@(lengths),@"components":parts,@"digest":sd_sha(keyBytes.bytes,keyBytes.length)};
}
static void sd_begin(NSString *identity,BOOL continuation,int pos,PromptTokens *prefix,KVCache **kv,void **states) {
    if(!sd_enabled())return;
    if(getenv("FLASH_SESSION_COMBINE_CAPTURE") && !g_fe_combine_gpu)g_fe_combine_gpu=sd_capture_combine;
    sd_identity=identity;sd_steps=[NSMutableArray array];sd_initial_pos=pos;sd_polled_layers=0;
    if(!continuation) {
        sd_history=[NSMutableArray array];sd_history_complete=YES;
        if(pos) {
            if(prefix && prefix->count>=pos)for(int i=0;i<pos;i++)[sd_history addObject:@(prefix->ids[i])];
            else if(sd_base_tokens.count==(NSUInteger)pos)[sd_history addObjectsFromArray:sd_base_tokens];
            else sd_history_complete=NO;
        }
    } else if(sd_history.count!=(NSUInteger)pos)sd_history_complete=NO;
    if(pos<=SESSION_DIAG_LIMIT)[sd_steps addObject:sd_fingerprint(kv,states,pos,"request_boundary")];
}
static void sd_complete(uint32_t token,int position,const char *phase,KVCache **kv,void **states) {
    if(!sd_enabled() || !sd_steps)return;
    if(position>=SESSION_DIAG_LIMIT || sd_history.count!=(NSUInteger)position){sd_history_complete=NO;return;}
    [sd_history addObject:@(token)];
    if(!sd_should_observe(position+1,phase)){sd_progress(phase,position+1);return;}
    NSMutableDictionary *row=[sd_fingerprint(kv,states,position+1,phase) mutableCopy];row[@"token_id"]=@(token);[sd_steps addObject:row];sd_progress(phase,position+1);
}
// A slab exposes its completed endpoint, not intermediate row states.
static void sd_complete_batch(const uint32_t *ids,int count,int position,KVCache **kv,void **states) {
    if(!sd_enabled() || !sd_steps)return;
    if(count<=0 || position<0 || count>SESSION_DIAG_LIMIT-position || sd_history.count!=(NSUInteger)position) {sd_history_complete=NO;return;}
    for(int row=0;row<count;row++)[sd_history addObject:@(ids[row])];
    NSMutableDictionary *step=[sd_fingerprint(kv,states,position+count,"prefill_batch_endpoint") mutableCopy];
    step[@"batch_start"]=@(position);step[@"batch_rows"]=@(count);
    [sd_steps addObject:step];
}
static void sd_end(int position,BOOL accepted,BOOL failed) {
    if(!sd_enabled() || !sd_identity || !sd_steps)return;
    sd_write([sd_identity stringByAppendingString:@"-state.json"],
       @{@"trace_identity":sd_identity,@"initial_position":@(sd_initial_pos),@"end_position":@(position),
         @"accepted":@(accepted),@"failed":@(failed),@"last_completed_position":@(sd_history.count),@"history_complete":@(sd_history_complete),
         @"effective_token_ids":sd_history?:@[],@"steps":sd_steps,
         @"gpu_linear":@(snapshot_uses_gpu_linear_state()),@"active_gdn_floats":@(LINEAR_NUM_V_HEADS*LINEAR_VALUE_DIM*LINEAR_KEY_DIM),
         @"active_conv_floats":@((CONV_KERNEL_SIZE-1)*LINEAR_CONV_DIM),
         @"geometry":@"native float32; active tensors only; GPU allocation padding excluded"});
    sd_steps=nil;
}
static void sd_progress(const char *phase,int position) {
    if(!getenv("FLASH_SESSION_STATE_PROGRESS") || !sd_identity)return;
    if(!strcmp(phase,"prefill_nrow_poll"))sd_polled_layers++;
    sd_write([sd_identity stringByAppendingString:@"-progress.json"],@{@"phase":@(phase),@"position":@(position),@"polls":@(sd_polled_layers)});
}
static void sd_abort_record(const char *reason,KVCache **kv,void **states) {
    if(!sd_enabled() || !sd_identity)return;
    sd_write([sd_identity stringByAppendingString:@"-abort.json"],@{@"reason":@(reason),@"session_invalidated":@YES,@"last_completed_position":@(sd_history.count),@"partial_state":sd_fingerprint(kv,states,(int)sd_history.count,"invalidated_partial_state")});
}
static int sd_replay(WeightFile *wf,KVCache **kv,void **states,void **maps,int *fds,int K,float *hidden) {
    const char *input=getenv("FLASH_SESSION_REPLAY_INPUT");if(!input)return -1;
    NSData *bytes=[NSData dataWithContentsOfFile:@(input)];
    if(!bytes || bytes.length>MAX((size_t)65536,(size_t)SESSION_DIAG_LIMIT*32))return 2;
    id object=[NSJSONSerialization JSONObjectWithData:bytes options:0 error:NULL];
    NSArray *ids=[object isKindOfClass:[NSDictionary class]]?object[@"token_ids"]:nil;
    if(![ids isKindOfClass:[NSArray class]] || !ids.count || ids.count>SESSION_DIAG_LIMIT || !sd_enabled())return 2;
    for(id n in ids)if(![n isKindOfClass:[NSNumber class]] || [n intValue]<0 || [n intValue]>=VOCAB_SIZE)return 2;
    id expected_digests=object[@"expected_digests"];
    if(expected_digests && ![expected_digests isKindOfClass:[NSDictionary class]])return 2;
#if SESSION_PREFILL_OBSERVE_STRIDE > 1
    // Never silently omit the final state from a sparse continuous reference.
    if(!sd_sparse_points_valid(expected_digests,ids.count))return 2;
    sd_replay_expected_points=expected_digests;
#endif
    reset_delta_net_state();g_forward_error=0;
    sd_begin(@"continuous-replay",NO,0,NULL,kv,states);
    NSString *initial_expected=expected_digests[@"0"];
    if(initial_expected && ![initial_expected isEqual:sd_steps.lastObject[@"digest"]]) {
        sd_end(0,NO,NO);fprintf(stderr,"[session-state] FIRST_DIVERGENCE position=0\n");return 3;
    }
    for(NSUInteger i=0;i<ids.count;i++) {
        int token=[ids[i] intValue];embed_lookup(wf,token,hidden);cache_telemetry_note_token();
        if(!run_all_layers_checked(wf,hidden,kv,states,maps,fds,(int)i,K) || !complete_deferred_experts()) {sd_end((int)i,NO,YES);return 1;}
        sd_complete(token,(int)i,"continuous",kv,states);
        NSString *expected=expected_digests[[NSString stringWithFormat:@"%lu",(unsigned long)i+1]];
        if(expected && ![expected isEqual:sd_steps.lastObject[@"digest"]]) {
            sd_end((int)i+1,NO,NO);fprintf(stderr,"[session-state] FIRST_DIVERGENCE position=%lu\n",(unsigned long)i+1);return 3;
        }
    }
    sd_end((int)ids.count,YES,NO);
    sd_replay_expected_points=nil;
    fprintf(stderr,"[session-state] continuous completed=%lu\n",(unsigned long)ids.count);
    return 0;
}
