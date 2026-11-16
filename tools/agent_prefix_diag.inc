// Test-only replacement for release_render_diag.inc in a temporary source copy.
// Uses production parse/render/tokenize helpers; no weights or Metal initialization.
static int release_render_only(const char *input_path,const char *output_path) {
    if(!input_path || !output_path || access(output_path,F_OK)==0)return 2;
    NSData *data=[NSData dataWithContentsOfFile:@(input_path)];
    if(!data || data.length>1024*1024)return 2;
    id root=[NSJSONSerialization JSONObjectWithData:data options:0 error:NULL];
    NSArray *cases=[root isKindOfClass:NSDictionary.class]?root[@"cases"]:nil;
    if(![cases isKindOfClass:NSArray.class] || !cases.count || cases.count>32)return 2;
    NSMutableArray *rows=[NSMutableArray array];
    ToolPrefixCacheEntry metadata_cache[TOOL_PREFIX_CACHE_SLOTS]={0},budget_cache[TOOL_PREFIX_CACHE_SLOTS]={0};
    for(NSDictionary *c in cases) {
        NSArray *messages=parse_chat_messages(c);
        NSString *last=messages.lastObject[@"role"];
        if(!messages || !([last isEqual:@"user"] || [last isEqual:@"tool"])) {
            [rows addObject:@{@"name":c[@"name"],@"status":@"REJECTED_INVALID_MESSAGES",@"original_messages":c[@"messages"]}];continue;
        }
        BOOL valid=YES;NSString *error=nil;
        NSArray *tools=parse_request_tools(c,&valid,&error);
        if(!valid || !validate_chat_tool_history(messages,&error))return 2;
        NSString *rendered=render_chat_prompt_with_tools(messages,tools,YES,NO);
        PromptTokens *pt=rendered?encode_prompt_text_to_tokens(rendered.UTF8String):NULL;
        if(!pt || pt->count<1 || pt->count>65536)return 2;
        NSString *prefix_text=render_chat_prompt_with_tools(@[messages.firstObject],tools,NO,NO);
        PromptTokens *prefix=prefix_text?encode_prompt_text_to_tokens(prefix_text.UTF8String):NULL;
        if(!prefix)return 2;
        uint64_t token_sig=prompt_tokens_signature(prefix),context_sig=tool_context_signature(tools,@"auto");
        BOOL starts=pt->count>=prefix->count && memcmp(pt->ids,prefix->ids,(size_t)prefix->count*sizeof(uint32_t))==0;
        // Synthetic metadata only: exercise the actual selector, never restore a snapshot.
        if(rows.count==0){metadata_cache[0].snapshot.valid=1;metadata_cache[0].tool_sig=context_sig;metadata_cache[0].token_sig=token_sig;metadata_cache[0].token_count=prefix->count;}
        int slot=tool_prefix_cache_find(metadata_cache,context_sig,token_sig,prefix->count);
        int budget_slot=-2;
        if([c[@"name"] isEqual:@"leading-budget-12000"]){budget_cache[0].snapshot.valid=1;budget_cache[0].tool_sig=context_sig;budget_cache[0].token_sig=token_sig;budget_cache[0].token_count=prefix->count;}
        if([c[@"name"] hasPrefix:@"leading-budget-"])budget_slot=tool_prefix_cache_find(budget_cache,context_sig,token_sig,prefix->count);
        int prefix_count=prefix->count;free(prefix->ids);free(prefix);
        NSMutableArray *ids=[NSMutableArray arrayWithCapacity:pt->count];
        for(int i=0;i<pt->count;i++)[ids addObject:@(pt->ids[i])];
        [rows addObject:@{@"name":c[@"name"],@"status":@"ACCEPTED",@"original_messages":c[@"messages"],@"normalized_messages":messages,@"tools":tools?:@[],@"rendered":rendered,@"token_ids":ids,@"count":@(pt->count),@"system_tools_prefix_tokens":@(prefix_count),@"full_starts_with_prefix":@(starts),@"metadata_cache_lookup":@(slot),@"budget_pair_lookup":@(budget_slot)}];
        free(pt->ids);free(pt);
    }
    NSData *json=[NSJSONSerialization dataWithJSONObject:@{@"status":@"PARSE_RENDER_ONLY",@"cases":rows,@"model_loaded":@NO,@"metal_initialized":@NO} options:NSJSONWritingSortedKeys error:NULL];
    return [json writeToFile:@(output_path) options:NSDataWritingWithoutOverwriting error:NULL]?0:2;
}
