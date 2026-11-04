// Diagnostic-only legal corpus serialization, before model/Metal allocation.
// Calls the unchanged renderer and tokenizer; never substitutes a chat template.
static int release_render_only(const char *input_path,const char *output_path) {
    if(!input_path || !output_path || access(output_path,F_OK)==0)return 2;
    NSData *data=[NSData dataWithContentsOfFile:@(input_path)];
    if(!data || data.length>1024*1024)return 2;
    id root=[NSJSONSerialization JSONObjectWithData:data options:0 error:NULL];
    NSArray *cases=[root isKindOfClass:NSDictionary.class]?root[@"cases"]:nil;
    if(![cases isKindOfClass:NSArray.class] || !cases.count || cases.count>32)return 2;
    NSMutableArray *rows=[NSMutableArray array];
    for(NSDictionary *c in cases) {
        if(![c isKindOfClass:NSDictionary.class] || ![c[@"name"] isKindOfClass:NSString.class])return 2;
        NSString *rendered=render_chat_prompt_with_tools(c[@"messages"],c[@"tools"],YES,[c[@"thinking"] boolValue]);
        PromptTokens *pt=rendered?encode_prompt_text_to_tokens(rendered.UTF8String):NULL;
        if(!pt || pt->count<1 || pt->count>65536)return 2;
        NSMutableArray *ids=[NSMutableArray arrayWithCapacity:pt->count];
        for(int i=0;i<pt->count;i++) {
            if(pt->ids[i]>=(uint32_t)VOCAB_SIZE){free(pt->ids);free(pt);return 2;}
            [ids addObject:@(pt->ids[i])];
        }
        [rows addObject:@{@"name":c[@"name"],@"rendered":rendered,@"token_ids":ids,@"count":@(pt->count)}];
        free(pt->ids);free(pt);
    }
    NSData *json=[NSJSONSerialization dataWithJSONObject:@{@"status":@"RENDER_ONLY",@"cases":rows,@"model_loaded":@NO,@"metal_initialized":@NO} options:0 error:NULL];
    return [json writeToFile:@(output_path) options:NSDataWritingWithoutOverwriting error:NULL]?0:2;
}
