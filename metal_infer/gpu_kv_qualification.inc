// Qualification-only adapter of the historical q_load/q_forward fixture path.
// Original checkpoints are read-only; all generated files live in FLASH_QUAL_OUT.
#include <CommonCrypto/CommonDigest.h>
static int qual_write(const char *name, int step, const void *p, size_t bytes) {
    NSString *path = [NSString stringWithFormat:@"%s/step-%d-%s.f32", getenv("FLASH_QUAL_OUT"), step, name];
    FILE *f = fopen(path.fileSystemRepresentation, "ab");
    if (!f) return 0;
    int ok = fwrite(p, 1, bytes, f) == bytes;
    return fclose(f) == 0 && ok;
}
static int qual_equal(const ServeStateSnapshot *a, KVCache **kv, void **states) {
    const size_t kd = NUM_KV_HEADS * HEAD_DIM * sizeof(float);
    for (int i=0;i<NUM_LAYERS;i++) {
        if(kv[i] && (kv[i]->len!=a->kv_len[i] ||
            memcmp(kv[i]->k_cache,a->k_snapshot[i],kd*a->kv_len[i]) ||
            memcmp(kv[i]->v_cache,a->v_snapshot[i],kd*a->kv_len[i]))) return 0;
        if(states[i]) {
            LinearAttnState *la=states[i];
            if(memcmp(la->conv_state,a->la_conv_snapshot[i],(CONV_KERNEL_SIZE-1)*LINEAR_CONV_DIM*4) ||
               memcmp(la->ssm_state,a->la_ssm_snapshot[i],LINEAR_NUM_V_HEADS*LINEAR_VALUE_DIM*LINEAR_KEY_DIM*4))return 0;
        }
    }
    if(snapshot_uses_gpu_linear_state())for(int i=0;i<g_cfg.num_linear_layers;i++) {
        if(memcmp([g_metal->buf_delta_state[i] contents],a->gpu_delta_snapshot[i],gpu_delta_state_bytes()) ||
           memcmp([g_metal->buf_conv_state[i] contents],a->gpu_conv_snapshot[i],3ULL*12288*4))return 0;
    }
    return 1;
}
static int qual_forward(WeightFile *wf, KVCache **kv,void **states,void **maps,int *fds,int K,
                        float *h,float *logits,uint16_t *fn,int pos) {
    float norm[HIDDEN_DIM]; memcpy(norm,h,sizeof(norm));
    apply_final_norm_inplace(norm,fn); lm_head_forward(wf,norm,logits);
    int token=cpu_argmax(logits,VOCAB_SIZE);
    embed_lookup(wf,token,h);
    if(!run_all_layers_checked(wf,h,kv,states,maps,fds,pos,K)||!complete_deferred_experts())return -1;
    return token;
}
static int qual_mirror(KVCache **kv) {
    size_t unit=NUM_KV_HEADS*HEAD_DIM*sizeof(float);
    for(int l=0;l<NUM_LAYERS;l++)if(kv[l]) {
        int idx=(l+1)/FULL_ATTN_INTERVAL-1;
        size_t count=kv[l]->len<GPU_KV_SEQ?kv[l]->len:GPU_KV_SEQ;
        if(memcmp(kv[l]->k_cache,[g_metal->buf_kv_k[idx] contents],count*unit)||
           memcmp(kv[l]->v_cache,[g_metal->buf_kv_v[idx] contents],count*unit))return 0;
    }
    return 1;
}
static int qual_lifetime(void) {
#if defined(FLASH_EXPERIMENTAL_LAZY_SHARED_GPU_KV) || defined(FLASH_EXPERIMENTAL_LAZY_SHARED_GPU_KV_32K)
    id<MTLBuffer> oldk=g_metal->buf_kv_k[0],oldv=g_metal->buf_kv_v[0];
    int capacity=g_kv_seq_len; g_kv_seq_len=64;
    for(int repeat=0;repeat<3;repeat++) {@autoreleasepool {
        KVCache *a=kv_cache_new(0),*b=kv_cache_new(0);
        if(!a||!b)return 0;
        if(a->k_cache[0]!=0 || a->k_cache[63*NUM_KV_HEADS*HEAD_DIM]!=0)return 0;
        id<MTLBuffer> retained=a->k_view;
        id<MTLCommandBuffer> cmd=[g_metal->queue commandBuffer];
        id<MTLBlitCommandEncoder> enc=[cmd blitCommandEncoder];
        [enc fillBuffer:retained range:NSMakeRange(0,retained.length) value:0x3c];
        [enc endEncoding]; [cmd commit];
        kv_cache_free(a); // queued work and retained view still own the mmap
        if(g_metal->buf_kv_k[0]!=b->k_view)return 0;
        if(!metal_wait_command_buffer_checked(cmd,"qualification lifetime"))return 0;
        if(((uint32_t *)retained.contents)[0]!=0x3c3c3c3cu)return 0;
        retained=nil; kv_cache_free(b);
    }}
    g_kv_seq_len=capacity;g_metal->buf_kv_k[0]=oldk;g_metal->buf_kv_v[0]=oldv;
#endif
    fprintf(stderr,"[qual] lifetime=PASS\n");return 1;
}
// Historical fixtures persist only active GDN geometry (2 MiB for this model).
// Import read-only data without weakening the production persistence validator.
static int qual_load_fixture(NSString *path, ToolPrefixCacheEntry *entry,
    KVCache **kv, void **states, int pos) {
    int fd=open(path.fileSystemRepresentation,O_RDONLY);
    if(fd<0)return 0;
    WarmStateHeader head={0};struct stat st;
    int ok=fstat(fd,&st)==0 && warm_read_all(fd,&head,sizeof(head),NULL);
    uint64_t expected_full=0, source=UINT64_C(0x1810CA8000000000)+pos;
    WarmStateHeader validated=head;
    if(ok)ok=warm_payload_bytes(&head,kv,states,&expected_full);
    // Current-engine fixtures store the complete GPU recurrent allocation;
    // historical fixtures below store only its active geometry.
    if(ok && head.payload_bytes==expected_full) {
        close(fd);
        ToolPrefixCacheEntry expected={0};
        expected.tool_sig=0xCA8;expected.token_sig=source;expected.token_count=pos;
        return warm_state_load(path,entry,kv,states,0xCA818,source,0x181018,&expected);
    }
    validated.payload_bytes=expected_full;
    if(ok)ok=head.version==WARM_STATE_VERSION &&
        warm_state_header_valid(&validated,0xCA818,source,0x181018,kv,states) &&
        head.pos==(uint32_t)pos && head.tool_sig==0xCA8 && head.token_sig==source &&
        head.ssm_bytes<=gpu_delta_state_bytes() &&
        head.payload_bytes==expected_full-head.gpu_layers*(gpu_delta_state_bytes()-head.ssm_bytes) &&
        (uint64_t)st.st_size==sizeof(head)+head.payload_bytes;
    uint64_t hash=UINT64_C(14695981039346656037);
    ServeStateSnapshot *snap=&entry->snapshot;
    for(int l=0;ok && l<NUM_LAYERS;l++) {
        snap->kv_len[l]=head.kv_len[l];
        if(kv[l]) {
            size_t bytes=(size_t)head.kv_len[l]*head.kv_dim*4;
            ok=warm_transfer_buffer(fd,(void **)&snap->k_snapshot[l],bytes,0,&hash) &&
               warm_transfer_buffer(fd,(void **)&snap->v_snapshot[l],bytes,0,&hash);
        }
        if(ok && states[l])ok=warm_transfer_buffer(fd,(void **)&snap->la_conv_snapshot[l],head.conv_bytes,0,&hash) &&
            warm_transfer_buffer(fd,(void **)&snap->la_ssm_snapshot[l],head.ssm_bytes,0,&hash);
    }
    for(unsigned l=0;ok && l<head.gpu_layers;l++) {
        snap->gpu_delta_snapshot[l]=calloc(1,gpu_delta_state_bytes());
        ok=snap->gpu_delta_snapshot[l] && warm_read_all(fd,snap->gpu_delta_snapshot[l],head.ssm_bytes,&hash) &&
           warm_transfer_buffer(fd,&snap->gpu_conv_snapshot[l],3ULL*12288*4,0,&hash);
    }
    if(close(fd)!=0)ok=0;
    if(hash!=head.payload_hash)ok=0;
    if(!ok){serve_state_snapshot_free(snap);return 0;}
    snap->pos=pos;snap->valid=1;entry->tool_sig=head.tool_sig;entry->token_sig=head.token_sig;entry->token_count=pos;
    fprintf(stderr,"[qual] historical_fixture_checksum=PASS active_gdn_bytes=%u padded_gdn_bytes=%zu\n",head.ssm_bytes,gpu_delta_state_bytes());
    return 1;
}
// Qualification-only fixture extension. The driver atomically publishes the
// completed output directory, so a killed writer never replaces a resume point.
static int qual_extend_fixture(WeightFile *wf,KVCache **kv,void **states,void **maps,
    int *fds,int K,float *h) {
    int pos=atoi(getenv("FLASH_QUAL_POS"));
    int target=atoi(getenv("FLASH_QUAL_EXTEND_TO"));
    if(target<=pos||target>32766||!getenv("FLASH_QUAL_OUT"))return 21;
    ToolPrefixCacheEntry entry={0};
    if(!qual_load_fixture([NSString stringWithUTF8String:getenv("FLASH_QUAL_ANCHOR")],&entry,kv,states,pos)||
       !serve_state_snapshot_restore(&entry.snapshot,kv,states))return 22;
    FILE *f=fopen(getenv("FLASH_QUAL_HIDDEN"),"rb");if(!f)return 23;
    int ok=fread(h,4,HIDDEN_DIM,f)==(size_t)HIDDEN_DIM;fclose(f);if(!ok)return 23;
    serve_state_snapshot_free(&entry.snapshot);
    double start=now_ms();
    while(pos<target) {@autoreleasepool {
        if(target-pos>=PREFILL_NROW_CAPTURE_ROWS &&
           prefill_nrow_runtime_cache_range_eligible(kv) && prefill_nrow_runtime_prepare(K)) {
            uint32_t ids[PREFILL_NROW_CAPTURE_ROWS];
            for(int i=0;i<PREFILL_NROW_CAPTURE_ROWS;i++)ids[i]=1000+((pos+i)*73)%1000;
            if(!prefill_nrow_runtime_chunk(wf,kv,states,maps,fds,K,pos,ids,NULL,h,NULL,NULL))return 24;
            pos+=PREFILL_NROW_CAPTURE_ROWS;
        } else {
            embed_lookup(wf,1000+(pos*73)%1000,h);
            if(!run_all_layers_checked(wf,h,kv,states,maps,fds,pos,K)||!complete_deferred_experts())return 24;
            pos++;
        }
        fprintf(stderr,"[qual-extend] pos=%d target=%d elapsed_ms=%.3f\n",pos,target,now_ms()-start);
    }}
    if(!complete_deferred_experts()||!qual_mirror(kv))return 25;
    for(int l=3;l<NUM_LAYERS;l+=FULL_ATTN_INTERVAL)if(kv[l]->len!=target)return 25;
    if(!serve_state_snapshot_capture(&entry.snapshot,kv,states,target))return 26;
    entry.tool_sig=0xCA8;entry.token_sig=UINT64_C(0x1810CA8000000000)+target;entry.token_count=target;
    NSString *path=[NSString stringWithFormat:@"%s/anchor.state",getenv("FLASH_QUAL_OUT")];
    g_warm_state_zstd_enabled=0;
    if(!warm_state_save(path,&entry,kv,states,0xCA818,entry.token_sig,0x181018))return 27;
    ToolPrefixCacheEntry loaded={0};
    if(!qual_load_fixture(path,&loaded,kv,states,target)||!qual_equal(&loaded.snapshot,kv,states))return 28;
    serve_state_snapshot_free(&loaded.snapshot);serve_state_snapshot_free(&entry.snapshot);
    NSString *hidden=[NSString stringWithFormat:@"%s/hidden.bin",getenv("FLASH_QUAL_OUT")];
    int fd=open(hidden.fileSystemRepresentation,O_WRONLY|O_CREAT|O_EXCL,0600);
    if(fd<0)return 29;
    ok=warm_write_all(fd,h,HIDDEN_DIM*sizeof(float),NULL)&&fsync(fd)==0;
    if(close(fd)!=0)ok=0;
    fprintf(stderr,"[qual-extend] RESULT=%s pos=%d elapsed_ms=%.3f\n",ok?"PASS":"FAIL",target,now_ms()-start);
    return ok?0:29;
}
static int gpu_kv_qualification(WeightFile *wf,KVCache **kv,void **states,void **maps,int *fds,int K,
                                 float *h,float *logits,uint16_t *fn) {
    int pos=atoi(getenv("FLASH_QUAL_POS")), steps=5;
    const char *anchor_path=getenv("FLASH_QUAL_ANCHOR"),*hidden_path=getenv("FLASH_QUAL_HIDDEN");
    if(!anchor_path||!hidden_path||!getenv("FLASH_QUAL_OUT")||pos<=0)return 1;
    if(getenv("FLASH_QUAL_EXTEND_TO"))return qual_extend_fixture(wf,kv,states,maps,fds,K,h);
    if(!qual_lifetime())return 2;
    ToolPrefixCacheEntry entry={0},expected={0};
    expected.tool_sig=0xCA8;expected.token_sig=UINT64_C(0x1810CA8000000000)+pos;expected.token_count=pos;
    if(!qual_load_fixture([NSString stringWithUTF8String:anchor_path],&entry,kv,states,pos))return 3;
    ServeStateSnapshot *anchor=&entry.snapshot;
    FILE *hf=fopen(hidden_path,"rb");if(!hf)return 4;
    float ah[HIDDEN_DIM];int read_ok=fread(ah,4,HIDDEN_DIM,hf)==(size_t)HIDDEN_DIM;fclose(hf);if(!read_ok)return 4;
    if(!serve_state_snapshot_restore(anchor,kv,states)||!qual_equal(anchor,kv,states)||!qual_mirror(kv))return 5;
    // Reject malformed later-layer state before earlier layers can be modified.
    int last=g_cfg.num_full_attn_layers*FULL_ATTN_INTERVAL-1;
    int saved_len=anchor->kv_len[last];
    int first=FULL_ATTN_INTERVAL-1;
    float original=anchor->k_snapshot[first][0];
    anchor->k_snapshot[first][0]=original+1.0f; // would visibly corrupt an early layer
    anchor->kv_len[last]=g_kv_seq_len+1;       // failure is discovered at a later layer
    int rejected=!serve_state_snapshot_restore(anchor,kv,states);
    anchor->kv_len[last]=saved_len;anchor->k_snapshot[first][0]=original;
    if(!rejected||!qual_equal(anchor,kv,states))return 6;
    g_forward_error=1;
    int recovered=serve_state_snapshot_restore(anchor,kv,states);
    g_forward_error=0;
    if(!recovered || !qual_equal(anchor,kv,states))return 6;
    fprintf(stderr,"[qual] fixture_restore=exact malformed_restore=transactional error_latch_restore=exact\n");
    // Exercise actual current persistence code, then compare every saved byte.
    NSString *roundtrip=[NSString stringWithFormat:@"%s/roundtrip.state",getenv("FLASH_QUAL_OUT")];
    g_warm_state_zstd_enabled=0;
    if(!warm_state_save(roundtrip,&entry,kv,states,0xCA818,expected.token_sig,0x181018))return 7;
    ToolPrefixCacheEntry loaded={0};
    if(!warm_state_load(roundtrip,&loaded,kv,states,0xCA818,expected.token_sig,0x181018,&expected) ||
       !serve_state_snapshot_restore(&loaded.snapshot,kv,states)||!qual_equal(anchor,kv,states))return 8;
    serve_state_snapshot_free(&loaded.snapshot);unlink(roundtrip.fileSystemRepresentation);
    fprintf(stderr,"[qual] persistence_roundtrip=exact\n");
    memcpy(h,ah,sizeof(ah));
    for(int step=0;step<steps;step++) {@autoreleasepool {
        int token=qual_forward(wf,kv,states,maps,fds,K,h,logits,fn,pos+step);
        if(token<0||!qual_mirror(kv))return 9;
        if(!qual_write("hidden",step,h,HIDDEN_DIM*4)||!qual_write("logits",step,logits,VOCAB_SIZE*4))return 10;
        for(int l=0;l<NUM_LAYERS;l++) {
            if(kv[l]) {
                size_t unit=NUM_KV_HEADS*HEAD_DIM*sizeof(float);
                if(kv[l]->len!=pos+step+1 || memcmp(kv[l]->k_cache,anchor->k_snapshot[l],pos*unit) ||
                   memcmp(kv[l]->v_cache,anchor->v_snapshot[l],pos*unit))return 11;
                if(!qual_write("kv",step,(char *)kv[l]->k_cache+pos*unit,(step+1)*unit)||
                   !qual_write("kv",step,(char *)kv[l]->v_cache+pos*unit,(step+1)*unit))return 10;
            }
            if(states[l]) {
                LinearAttnState *la=states[l];
                if(!qual_write("cpu-recurrent",step,la->conv_state,(CONV_KERNEL_SIZE-1)*LINEAR_CONV_DIM*4)||
                   !qual_write("cpu-recurrent",step,la->ssm_state,LINEAR_NUM_V_HEADS*LINEAR_VALUE_DIM*LINEAR_KEY_DIM*4))return 10;
            }
        }
        for(int l=0;l<g_cfg.num_linear_layers;l++) {
            if(!qual_write("gpu-recurrent",step,[g_metal->buf_delta_state[l] contents],gpu_delta_state_bytes())||
               !qual_write("gpu-recurrent",step,[g_metal->buf_conv_state[l] contents],3ULL*12288*4))return 10;
        }
        fprintf(stderr,"[qual-step] {\"step\":%d,\"pos\":%d,\"len\":%d,\"token\":%d,\"prefix_exact\":true}\n",step,pos+step,pos+step+1,token);
        // First-step rollback and replay must recover every state bit and hidden.
        if(step==0) {
            ServeStateSnapshot after={0};float hh[HIDDEN_DIM];memcpy(hh,h,sizeof(hh));
            if(!serve_state_snapshot_capture(&after,kv,states,pos+1) ||
               !serve_state_snapshot_restore(anchor,kv,states))return 12;
            memcpy(h,ah,sizeof(ah));g_pred_valid=0;
            int replay=qual_forward(wf,kv,states,maps,fds,K,h,logits,fn,pos);
            int exact=replay==token && !memcmp(h,hh,sizeof(hh))&&qual_equal(&after,kv,states);
            serve_state_snapshot_free(&after);
            if(!exact)return 13;
            fprintf(stderr,"[qual] rollback_replay=exact\n");
        }
    }}
    serve_state_snapshot_free(anchor);
    // Persist the post-transition state too, then prove its next continuation
    // is byte-exact after restore. At 32K this includes KV beyond the GPU view.
    int tail_pos=pos+steps;
    entry.tool_sig=0xCA8;entry.token_sig=UINT64_C(0x1810CA8000000000)+tail_pos;
    entry.token_count=tail_pos;
    float tail_hidden[HIDDEN_DIM];memcpy(tail_hidden,h,sizeof(tail_hidden));
    if(!serve_state_snapshot_capture(anchor,kv,states,tail_pos)||
       !warm_state_save(roundtrip,&entry,kv,states,0xCA818,entry.token_sig,0x181018))return 14;
    ToolPrefixCacheEntry tail={0};
    if(!qual_load_fixture(roundtrip,&tail,kv,states,tail_pos)||!qual_equal(&tail.snapshot,kv,states))return 14;
    unlink(roundtrip.fileSystemRepresentation);serve_state_snapshot_free(anchor);
    int next=qual_forward(wf,kv,states,maps,fds,K,h,logits,fn,tail_pos);
    ServeStateSnapshot next_state={0};float next_hidden[HIDDEN_DIM];memcpy(next_hidden,h,sizeof(next_hidden));
    if(next<0||!serve_state_snapshot_capture(&next_state,kv,states,tail_pos+1)||
       !serve_state_snapshot_restore(&tail.snapshot,kv,states))return 15;
    memcpy(h,tail_hidden,sizeof(tail_hidden));g_pred_valid=0;
    int replay=qual_forward(wf,kv,states,maps,fds,K,h,logits,fn,tail_pos);
    int exact=next==replay&&!memcmp(h,next_hidden,sizeof(next_hidden))&&
        qual_equal(&next_state,kv,states)&&qual_mirror(kv);
    serve_state_snapshot_free(&next_state);serve_state_snapshot_free(&tail.snapshot);
    if(!exact)return 15;
    fprintf(stderr,"[qual-tail] {\"saved_pos\":%d,\"continuation_len\":%d,\"token\":%d,\"state_hidden_exact\":true}\n",tail_pos,tail_pos+1,next);
    fprintf(stderr,"[qual] RESULT=PASS cap=%d\n",GPU_KV_SEQ);return 0;
}
