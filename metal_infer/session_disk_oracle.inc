// Native persistent warm-state save/restart/restore oracle, diagnostic build only.
static int sn_disk(WeightFile *wf,KVCache **kv,void **states,void **maps,int *fds,int K,float *hidden,
    const char *weights,const char *manifest,const char *vocab) {
    NSData *data=[NSData dataWithContentsOfFile:@(getenv("FLASH_SESSION_DISK_INPUT"))];
    if(!data || data.length>65536 || !sd_enabled())return 2;
    NSDictionary *in=[NSJSONSerialization JSONObjectWithData:data options:0 error:NULL];
    if(![in isKindOfClass:NSDictionary.class] || ![in[@"token_ids"] isKindOfClass:NSArray.class] || ![in[@"checkpoint"] isKindOfClass:NSString.class])return 2;
    NSArray *tokens=in[@"token_ids"];int count=(int)tokens.count,prefix=[in[@"prefix"] intValue];
    if(count>SESSION_DIAG_LIMIT || prefix<1 || prefix>count)return 2;
    uint32_t ids[SESSION_DIAG_LIMIT];for(int i=0;i<count;i++){if(![tokens[i] isKindOfClass:NSNumber.class] || [tokens[i] intValue]<0 || [tokens[i] intValue]>=VOCAB_SIZE)return 2;ids[i]=[tokens[i] intValue];}
    PromptTokens pt={.ids=ids,.count=prefix};uint64_t sig=prompt_tokens_signature(&pt),compat=0;
    uint64_t profile=warm_hash_string(UINT64_C(14695981039346656037),"diagnostic/n128-restoration");
    if(!warm_state_compatibility(weights,manifest,vocab,wf,fds,K,&compat))return 2;
    ToolPrefixCacheEntry expected={.token_count=prefix,.token_sig=sig,.tool_sig=profile},entry={0};
    NSString *mode=in[@"mode"],*path=in[@"checkpoint"];g_warm_state_zstd_enabled=1;
    NSMutableArray *rows=[NSMutableArray array];int ok=1;double transfer_ms=0;
    reset_delta_net_state();g_forward_error=0;
    if([mode isEqual:@"save"]) {
        int pos=0;NSArray *starts=in[@"batch_starts"];
        while(pos<prefix && ok) {int batch=[starts containsObject:@(pos)];int n=batch?PREFILL_NROW_CAPTURE_ROWS:1;if(pos+n>prefix)return 2;ok=sn_forward(wf,kv,states,maps,fds,K,hidden,ids+pos,pos,n,batch);pos+=n;}
        entry=expected;
        if(ok)ok=serve_state_snapshot_capture(&entry.snapshot,kv,states,prefix);
        double t=now_ms();if(ok)ok=warm_state_save_selected(path,&entry,kv,states,compat,sig,profile);transfer_ms=now_ms()-t;
    } else if([mode isEqual:@"load"]) {
        double t=now_ms();int repair=0;ok=warm_state_load_selected(path,&entry,kv,states,compat,sig,profile,&expected,&repair) && serve_state_snapshot_restore(&entry.snapshot,kv,states);transfer_ms=now_ms()-t;
        if(ok) {
            // Wrong effective prefix and wrong execution mode must reject without
            // touching the current live state. Keep the valid loaded entry separate.
            ToolPrefixCacheEntry bad_expected=expected,bad={0};bad_expected.token_sig^=1;
            int rejected=!warm_state_load_selected(path,&bad,kv,states,compat,sig,profile,&bad_expected,NULL);
            serve_state_snapshot_free(&bad.snapshot);
            uint64_t other=0;
            g_prefill_nrow_runtime_enabled^=1;
            int mode_ok=warm_state_compatibility(weights,manifest,vocab,wf,fds,K,&other);
            g_prefill_nrow_runtime_enabled^=1;
            rejected&=mode_ok && other!=compat && !warm_state_load_selected(path,&bad,kv,states,other,sig,profile,&expected,NULL);
            serve_state_snapshot_free(&bad.snapshot);ok&=rejected;
        }
    } else return 2;
    if(ok)[rows addObject:sd_fingerprint(kv,states,prefix,"disk_prefix")];
    for(int pos=prefix;pos<count && ok;pos++) {
        ok=sn_forward(wf,kv,states,maps,fds,K,hidden,ids+pos,pos,1,0);
        if(ok)[rows addObject:sd_fingerprint(kv,states,pos+1,"disk_continuation")];
    }
    NSString *stored=warm_state_zstd_path(warm_state_identity_path(path));struct stat st={0};stat(stored.fileSystemRepresentation,&st);
    sd_write([NSString stringWithFormat:@"disk-%@.json",mode],@{@"status":ok?@"PASS":@"FAIL",@"mode":mode,@"prefix":@(prefix),@"end_position":@(count),@"compatibility":[NSString stringWithFormat:@"%016llx",(unsigned long long)compat],@"prefix_signature":[NSString stringWithFormat:@"%016llx",(unsigned long long)sig],@"checkpoint":stored,@"checkpoint_bytes":@(st.st_size),@"transfer_ms":@(transfer_ms),@"rows":rows});
    serve_state_snapshot_free(&entry.snapshot);return ok?0:3;
}
