// Checkpoint-assisted matched performance runs. No snapshot/hash observer in timing.
static void kv_perf_memory(uint64_t *physical,uint64_t *peak,uint64_t *rss) {
    task_vm_info_data_t vm={0};mach_msg_type_number_t n=TASK_VM_INFO_COUNT;
    if(task_info(mach_task_self(),TASK_VM_INFO,(task_info_t)&vm,&n)!=KERN_SUCCESS)abort();
    struct rusage ru={0};getrusage(RUSAGE_SELF,&ru);
    *physical=vm.phys_footprint;*peak=vm.ledger_phys_footprint_peak;*rss=ru.ru_maxrss;
}
static int kv_perf_forward(WeightFile *wf,KVCache **kv,void **states,void **maps,int *fds,int K,
    float *h,float *logits,uint16_t *fn,int pos) {
    float norm[HIDDEN_DIM];memcpy(norm,h,sizeof(norm));apply_final_norm_inplace(norm,fn);
    int token=lm_head_forward_greedy(wf,norm,logits);
    embed_lookup(wf,token,h);
    if(!run_all_layers_checked(wf,h,kv,states,maps,fds,pos,K)||!complete_deferred_experts())return -1;
    return token;
}
static int gpu_kv_performance(WeightFile *wf,KVCache **kv,void **states,void **maps,int *fds,int K,
    float *h,float *logits,uint16_t *fn) {
    int pos=atoi(getenv("FLASH_QUAL_POS"));
    int repeats=getenv("FLASH_PERF_REPEATS")?atoi(getenv("FLASH_PERF_REPEATS")):3;
    int steps=getenv("FLASH_PERF_STEPS")?atoi(getenv("FLASH_PERF_STEPS")):4;
    int suffix=getenv("FLASH_PERF_SUFFIX")?atoi(getenv("FLASH_PERF_SUFFIX")):8;
    if(repeats<1||repeats>10||steps<1||steps>16||suffix<1||suffix>32)return 1;
    ToolPrefixCacheEntry entry={0};double load_start=now_ms();
    if(!qual_load_fixture([NSString stringWithUTF8String:getenv("FLASH_QUAL_ANCHOR")],&entry,kv,states,pos))return 2;
    float ah[HIDDEN_DIM];FILE *f=fopen(getenv("FLASH_QUAL_HIDDEN"),"rb");if(!f)return 3;
    int ok=fread(ah,4,HIDDEN_DIM,f)==(size_t)HIDDEN_DIM;fclose(f);if(!ok)return 3;
    double fixture_load_ms=now_ms()-load_start;
    kv_perf_init(g_metal->device);
    uint64_t phy,peak,rss;kv_perf_memory(&phy,&peak,&rss);
    fprintf(stderr,"[kv-perf-meta] {\"pos\":%d,\"cap\":%d,\"fixture_load_ms\":%.6f,\"snapshot_bytes\":%zu,\"physical_bytes\":%llu,\"metal_allocated_bytes\":%llu,\"counters\":%s}\n",pos,GPU_KV_SEQ,fixture_load_ms,serve_state_snapshot_bytes(&entry.snapshot),(unsigned long long)phy,(unsigned long long)g_metal->device.currentAllocatedSize,kv_perf_counter?"true":"false");
    int expected[16]={0},expected_prefill=-1;
    // Alternate observer order across repetitions; each mode has an untimed warm run.
    for(int rep=-1;rep<repeats;rep++)for(int order=0;order<3;order++) {@autoreleasepool {
        int mode=(order+(rep+1)%3)%3; // 0 decode, 1 counter pass, 2 suffix prefill
        kv_perf_active=0;double restore_begin=now_ms();
        if(!serve_state_snapshot_restore(&entry.snapshot,kv,states))return 4;
        memcpy(h,ah,sizeof(ah));g_pred_valid=0;
        double restore_ms=now_ms()-restore_begin;
        if(mode==2) {
            double started=now_ms();
            for(int j=0;j<suffix;j++) {@autoreleasepool {
                embed_lookup(wf,(uint32_t)(1000+(j*73)%1000),h);
                if(!run_all_layers_checked(wf,h,kv,states,maps,fds,pos+j,K))return 5;
                if(j+1==suffix){if(!complete_deferred_experts())return 5;}
                else if(!discard_deferred_experts())return 5;
            }}
            double prefill_ms=now_ms()-started;
            float norm[HIDDEN_DIM];memcpy(norm,h,sizeof(norm));apply_final_norm_inplace(norm,fn);
            int next=lm_head_forward_greedy(wf,norm,logits);
            double ttft_ms=restore_ms+now_ms()-started;
            if(rep<0)expected_prefill=next;else if(next!=expected_prefill)return 6;
            kv_perf_memory(&phy,&peak,&rss);
            if(rep>=0)fprintf(stderr,"[kv-perf-prefill] {\"repeat\":%d,\"pos\":%d,\"suffix_tokens\":%d,\"prefill_ms\":%.6f,\"ttft_ms\":%.6f,\"restore_ms\":%.6f,\"next_token\":%d,\"physical_bytes\":%llu,\"peak_physical_bytes\":%llu,\"peak_rss_bytes\":%llu}\n",rep,pos,suffix,prefill_ms,ttft_ms,restore_ms,next,(unsigned long long)phy,(unsigned long long)peak,(unsigned long long)rss);
        } else {
            double total=0;
            for(int step=0;step<steps;step++) {@autoreleasepool {
                kv_perf_reset(mode==1);double start=now_ms();
                int token=kv_perf_forward(wf,kv,states,maps,fds,K,h,logits,fn,pos+step);
                double elapsed=now_ms()-start;total+=elapsed;
                if(token<0)return 7;
                if(rep<0&&mode==0)expected[step]=token;
                if(rep>=0&&token!=expected[step])return 8;
                double gpu_ms[MAX_LAYERS];if(!kv_perf_resolve(gpu_ms))return 9;
                double gpu_total=0,cpu_total=0,layer_total=0;int gpu_layers=0;
                for(int l=3;l<NUM_LAYERS;l+=FULL_ATTN_INTERVAL) {
                    gpu_total+=gpu_ms[l];cpu_total+=kv_perf_cpu_ms[l];layer_total+=kv_perf_layer_ms[l];gpu_layers+=kv_perf_gpu_route[l];
                    if(rep>=0&&mode==1)fprintf(stderr,"[kv-perf-layer] {\"repeat\":%d,\"step\":%d,\"len\":%d,\"layer\":%d,\"gpu\":%d,\"attention_gpu_ms\":%.6f,\"attention_cpu_ms\":%.6f,\"layer_host_ms\":%.6f}\n",rep,step,pos+step+1,l,kv_perf_gpu_route[l],gpu_ms[l],kv_perf_cpu_ms[l],kv_perf_layer_ms[l]);
                }
                kv_perf_memory(&phy,&peak,&rss);
                if(rep>=0)fprintf(stderr,"[kv-perf-step] {\"repeat\":%d,\"observer\":%d,\"step\":%d,\"len\":%d,\"token\":%d,\"wall_ms\":%.6f,\"attention_gpu_ms\":%.6f,\"attention_cpu_ms\":%.6f,\"full_layer_host_ms\":%.6f,\"gpu_layers\":%d,\"physical_bytes\":%llu,\"peak_physical_bytes\":%llu,\"peak_rss_bytes\":%llu}\n",rep,mode,step,pos+step+1,token,elapsed,gpu_total,cpu_total,layer_total,gpu_layers,(unsigned long long)phy,(unsigned long long)peak,(unsigned long long)rss);
            }}
            if(rep>=0)fprintf(stderr,"[kv-perf-decode] {\"repeat\":%d,\"observer\":%d,\"pos\":%d,\"tokens\":%d,\"wall_ms\":%.6f,\"tokens_per_second\":%.6f,\"restore_ms\":%.6f}\n",rep,mode,pos,steps,total,steps*1000.0/total,restore_ms);
        }
    }}
    kv_perf_active=0;serve_state_snapshot_free(&entry.snapshot);
    fprintf(stderr,"[kv-perf] RESULT=PASS\n");return 0;
}
