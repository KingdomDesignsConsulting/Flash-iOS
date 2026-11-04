// Diagnostic inventory only. Lengths are reservations, not physical residency.
// Metal-backed host aliases MUST NOT be summed again as independent allocations.
#include <mach/mach.h>
static void rm_buffer(NSString *category,NSString *name,id<MTLBuffer> b,NSMutableSet *seen,NSMutableArray *parts) {
    if(!b)return;
    NSValue *identity=[NSValue valueWithPointer:(__bridge const void *)b];
    if([seen containsObject:identity])return;
    [seen addObject:identity];
    [parts addObject:@{@"category":category,@"name":name,@"length_bytes":@(b.length),@"allocated_bytes":@(b.allocatedSize),@"storage_mode":@(b.storageMode)}];
}
static size_t rm_snapshot(const ServeStateSnapshot *s) {
    size_t n=0;
    for(int l=0;l<NUM_LAYERS;l++)n+=malloc_size(s->k_snapshot[l])+malloc_size(s->v_snapshot[l])+malloc_size(s->la_ssm_snapshot[l])+malloc_size(s->la_conv_snapshot[l]);
    for(int l=0;l<48;l++)n+=malloc_size(s->gpu_delta_snapshot[l])+malloc_size(s->gpu_conv_snapshot[l]);
    return n;
}
static NSDictionary *rm_observe(KVCache **kv,void **states,const ServeStateSnapshot *ref,const ServeStateSnapshot *cand,int pos) {
    task_vm_info_data_t vm={0};mach_msg_type_number_t count=TASK_VM_INFO_COUNT;
    kern_return_t status=task_info(mach_task_self(),TASK_VM_INFO,(task_info_t)&vm,&count);
    NSMutableSet *seen=[NSMutableSet set];NSMutableArray *parts=[NSMutableArray array];
    rm_buffer(@"scalar_workspace",@"MetalCtx.argmax_result",g_metal->argmax_result,seen,parts);
    rm_buffer(@"immutable_weights",@"MetalCtx.nax_w_half",g_metal->nax_w_half,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.nax_x_half",g_metal->nax_x_half,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.nax_c_buf",g_metal->nax_c_buf,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_input",g_metal->buf_input,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_output",g_metal->buf_output,seen,parts);
    rm_buffer(@"immutable_weights",@"MetalCtx.wf_buf",g_metal->wf_buf,seen,parts);
    rm_buffer(@"immutable_weights",@"MetalCtx.gguf_qkv_buf",g_metal->gguf_qkv_buf,seen,parts);
    rm_buffer(@"immutable_weights",@"MetalCtx.gguf_full_attn_buf",g_metal->gguf_full_attn_buf,seen,parts);
    rm_buffer(@"immutable_weights",@"MetalCtx.gguf_linear_buf",g_metal->gguf_linear_buf,seen,parts);
    rm_buffer(@"immutable_weights",@"MetalCtx.gguf_shared_buf",g_metal->gguf_shared_buf,seen,parts);
    rm_buffer(@"immutable_weights",@"MetalCtx.gguf_lm_head_buf",g_metal->gguf_lm_head_buf,seen,parts);
    for(int i=0;i<MAX_BATCH_SLOTS;i++)rm_buffer(@"scalar_workspace",@"MetalCtx.batch_out",g_metal->batch_out[i],seen,parts);
    rm_buffer(@"expert_staging",@"MetalCtx.buf_expert_data",g_metal->buf_expert_data,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_expert_input",g_metal->buf_expert_input,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_expert_gate",g_metal->buf_expert_gate,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_expert_up",g_metal->buf_expert_up,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_expert_act",g_metal->buf_expert_act,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_expert_out",g_metal->buf_expert_out,seen,parts);
    for(int i=0;i<MAX_K;i++)rm_buffer(@"expert_staging",@"MetalCtx.buf_multi_expert_data",g_metal->buf_multi_expert_data[i],seen,parts);
    for(int i=0;i<MAX_K;i++)rm_buffer(@"expert_staging",@"MetalCtx.buf_multi_expert_data_B",g_metal->buf_multi_expert_data_B[i],seen,parts);
    for(int i=0;i<MAX_K;i++)rm_buffer(@"scalar_workspace",@"MetalCtx.buf_multi_expert_gate",g_metal->buf_multi_expert_gate[i],seen,parts);
    for(int i=0;i<MAX_K;i++)rm_buffer(@"scalar_workspace",@"MetalCtx.buf_multi_expert_up",g_metal->buf_multi_expert_up[i],seen,parts);
    for(int i=0;i<MAX_K;i++)rm_buffer(@"scalar_workspace",@"MetalCtx.buf_multi_expert_act",g_metal->buf_multi_expert_act[i],seen,parts);
    for(int i=0;i<MAX_K;i++)rm_buffer(@"scalar_workspace",@"MetalCtx.buf_multi_expert_out",g_metal->buf_multi_expert_out[i],seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_multi_expert_input",g_metal->buf_multi_expert_input,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_shared_gate",g_metal->buf_shared_gate,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_shared_up",g_metal->buf_shared_up,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_shared_act",g_metal->buf_shared_act,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_shared_out",g_metal->buf_shared_out,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_residual",g_metal->buf_residual,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_h_mid",g_metal->buf_h_mid,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_sum_sq",g_metal->buf_sum_sq,seen,parts);
    for(int i=0;i<16;i++)rm_buffer(@"attention_kv",@"MetalCtx.buf_kv_k",g_metal->buf_kv_k[i],seen,parts);
    for(int i=0;i<16;i++)rm_buffer(@"attention_kv",@"MetalCtx.buf_kv_v",g_metal->buf_kv_v[i],seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_attn_q",g_metal->buf_attn_q,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_attn_scores",g_metal->buf_attn_scores,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_attn_out",g_metal->buf_attn_out,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_attn_gate",g_metal->buf_attn_gate,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_moe_hidden",g_metal->buf_moe_hidden,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_combine_params",g_metal->buf_combine_params,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_cmd3_sum_sq",g_metal->buf_cmd3_sum_sq,seen,parts);
    for(int i=0;i<48;i++)rm_buffer(@"gdn_state",@"MetalCtx.buf_delta_state",g_metal->buf_delta_state[i],seen,parts);
    for(int i=0;i<48;i++)rm_buffer(@"convolution_state",@"MetalCtx.buf_conv_state",g_metal->buf_conv_state[i],seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_delta_q",g_metal->buf_delta_q,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_delta_k",g_metal->buf_delta_k,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_delta_v",g_metal->buf_delta_v,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_delta_g_decay",g_metal->buf_delta_g_decay,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_delta_beta",g_metal->buf_delta_beta,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_delta_output",g_metal->buf_delta_output,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_conv_input",g_metal->buf_conv_input,seen,parts);
    rm_buffer(@"scalar_workspace",@"MetalCtx.buf_conv_output",g_metal->buf_conv_output,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.input",g_prefill_nrow_runtime_pipes.input,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.gate",g_prefill_nrow_runtime_pipes.gate,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.up",g_prefill_nrow_runtime_pipes.up,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.act",g_prefill_nrow_runtime_pipes.act,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.output",g_prefill_nrow_runtime_pipes.output,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.shared_act_rows",g_prefill_nrow_runtime_pipes.shared_act_rows,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.shared_out_rows",g_prefill_nrow_runtime_pipes.shared_out_rows,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.shared_gate_rows",g_prefill_nrow_runtime_pipes.shared_gate_rows,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.shared_up_rows",g_prefill_nrow_runtime_pipes.shared_up_rows,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.normed_rows",g_prefill_nrow_runtime_pipes.normed_rows,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.full_qproj_rows",g_prefill_nrow_runtime_pipes.full_qproj_rows,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.full_k_rows",g_prefill_nrow_runtime_pipes.full_k_rows,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.full_v_rows",g_prefill_nrow_runtime_pipes.full_v_rows,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.full_q_rows",g_prefill_nrow_runtime_pipes.full_q_rows,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.full_gate_rows",g_prefill_nrow_runtime_pipes.full_gate_rows,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.full_attn_rows",g_prefill_nrow_runtime_pipes.full_attn_rows,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.linear_oproj_rows",g_prefill_nrow_runtime_pipes.linear_oproj_rows,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.linear_hpost_rows",g_prefill_nrow_runtime_pipes.linear_hpost_rows,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.linear_gate_scores",g_prefill_nrow_runtime_pipes.linear_gate_scores,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.linear_shared_scores",g_prefill_nrow_runtime_pipes.linear_shared_scores,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.expert_stage",g_prefill_nrow_runtime_pipes.expert_stage,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.conv_input",g_prefill_nrow_runtime_pipes.conv_input,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.conv_output",g_prefill_nrow_runtime_pipes.conv_output,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.q",g_prefill_nrow_runtime_pipes.q,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.k",g_prefill_nrow_runtime_pipes.k,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.v",g_prefill_nrow_runtime_pipes.v,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.z",g_prefill_nrow_runtime_pipes.z,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.alpha",g_prefill_nrow_runtime_pipes.alpha,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.beta",g_prefill_nrow_runtime_pipes.beta,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.decay",g_prefill_nrow_runtime_pipes.decay,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.beta_gate",g_prefill_nrow_runtime_pipes.beta_gate,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.gdn_output",g_prefill_nrow_runtime_pipes.gdn_output,seen,parts);
    rm_buffer(@"n128_workspace",@"N128.attn_output",g_prefill_nrow_runtime_pipes.attn_output,seen,parts);
    if(g_malloc_cache)for(int i=0;i<g_malloc_cache->num_entries;i++)rm_buffer(@"expert_cache",@"malloc_cache_wrapper",g_malloc_cache->metal_bufs[i],seen,parts);
    if(g_expert_cache)for(int i=0;i<g_expert_cache->num_entries;i++)rm_buffer(@"expert_cache",@"metal_lru",g_expert_cache->entries[i].buffer,seen,parts);
    size_t cpu_gdn=0,cpu_conv=0,cpu_kv_reservation=0,aliased_kv=0,active_kv=0;
    int fi=0;
    for(int l=0;l<NUM_LAYERS;l++) {
        if(kv[l]) {
            size_t reserved=(size_t)g_kv_seq_len*NUM_KV_HEADS*HEAD_DIM*sizeof(float)*2;
            cpu_kv_reservation+=reserved;active_kv+=(size_t)kv[l]->len*NUM_KV_HEADS*HEAD_DIM*sizeof(float)*2;
            if(kv[l]->k_cache==g_metal->buf_kv_k[fi].contents && kv[l]->v_cache==g_metal->buf_kv_v[fi].contents) {
                size_t wrapped=g_metal->buf_kv_k[fi].length+g_metal->buf_kv_v[fi].length;
                aliased_kv+=reserved<wrapped?reserved:wrapped;
            }
            fi++;
        } else if(states[l]) {LinearAttnState *la=states[l];cpu_gdn+=malloc_size(la->ssm_state);cpu_conv+=malloc_size(la->conv_state);}
    }
    NSMutableDictionary *categories=[NSMutableDictionary dictionary];size_t inventory=0;
    for(NSDictionary *p in parts){NSString *c=p[@"category"];size_t bytes=[p[@"length_bytes"] unsignedLongLongValue];categories[c]=@([categories[c] unsignedLongLongValue]+bytes);inventory+=bytes;}
    return @{@"memory_schema":@2,@"position":@(pos),@"task_info_status":@(status),@"physical_footprint_bytes":@(status==KERN_SUCCESS?vm.phys_footprint:0),@"physical_footprint_peak_bytes":@(status==KERN_SUCCESS?vm.ledger_phys_footprint_peak:0),@"resident_bytes":@(status==KERN_SUCCESS?vm.resident_size:0),@"metal_current_allocated_bytes":@(g_metal->device.currentAllocatedSize),@"metal_recommended_working_set_bytes":@(g_metal->device.recommendedMaxWorkingSetSize),@"metal_inventory_reserved_bytes":@(inventory),@"metal_categories_reserved_bytes":categories,@"metal_buffers":parts,@"cpu_gdn_malloc_bytes":@(cpu_gdn),@"cpu_convolution_malloc_bytes":@(cpu_conv),@"cpu_kv_reserved_bytes":@(cpu_kv_reservation),@"cpu_kv_aliases_metal_reserved_bytes":@(aliased_kv),@"active_kv_bytes":@(active_kv),@"two_oracle_snapshots_malloc_bytes":@(rm_snapshot(ref)+rm_snapshot(cand)),@"future_speculative_state_bytes":@0,@"interpretation":@"Do not sum footprint, RSS, Metal allocation, CPU aliases or reserved lengths. Host runtime/allocator overhead and unmapped/paged expert backing are not fully attributed. This is measurement, not a production admission guarantee."};
}
