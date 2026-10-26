// Fail-closed HTTP/SSE client. Deliberately no retry for ambiguous transport
// failures: the server may already have advanced its resident state.
static int g_stream_invalidated, g_stream_ok, g_stream_any_output;
static volatile sig_atomic_t g_chat_cancelled;
static void chat_cancel(int signal_number) { (void)signal_number; g_chat_cancelled=1; }

static BOOL invalidation_signal(NSDictionary *body) {
    id error=body[@"error"];
    NSDictionary *nested=[error isKindOfClass:[NSDictionary class]]?error:@{};
    return [body[@"session_invalidated"] isEqual:@YES] ||
           [body[@"resend_full_history"] isEqual:@YES] ||
           [nested[@"session_invalidated"] isEqual:@YES] ||
           [nested[@"resend_full_history"] isEqual:@YES];
}

static char *stream_response(int sock, int show_thinking) {
    g_stream_ok=g_stream_invalidated=g_stream_any_output=0;
    FILE *stream=fdopen(sock,"r");
    if(!stream){close(sock);return NULL;}
    NSMutableData *content=[NSMutableData data], *event=[NSMutableData data];
    NSMutableData *errorBody=[NSMutableData data];
    int status=0,headers=0,done=0,finish=0,failed=0;
    BOOL sse=NO;
    size_t wire=0,headerBytes=0,bodyBytes=0;long long contentLength=-1;
    double start=now_ms(),first=0;
    char line[65536];
    md_reset();
    while(!g_chat_cancelled && now_ms()-start<600000 && fgets(line,sizeof(line),stream)) {
        size_t len=strlen(line);wire+=len;
        if(wire>8*MAX_RESPONSE || (len==sizeof(line)-1 && line[len-1]!='\n')){failed=1;break;}
        if(!headers) {
            headerBytes+=len;if(headerBytes>32768){failed=1;break;}
            if(!status){if(sscanf(line,"HTTP/1.%*d %d",&status)!=1){failed=1;break;}continue;}
            if(!strcmp(line,"\r\n") || !strcmp(line,"\n")){headers=1;continue;}
            NSString *h=[@(line) lowercaseString];
            if([h hasPrefix:@"content-type:"] && [h containsString:@"text/event-stream"])sse=YES;
            if([h hasPrefix:@"content-length:"]) {
                NSScanner *scanner=[NSScanner scannerWithString:[h substringFromIndex:15]];
                long long value=0;
                if(contentLength>=0 || ![scanner scanLongLong:&value] || !scanner.isAtEnd || value<0 || value>8*MAX_RESPONSE){failed=1;break;}
                contentLength=value;
            }
            // The engine serves connection-close SSE. Unsupported framing must
            // fail visibly rather than parsing chunk-length lines as SSE data.
            if([h hasPrefix:@"transfer-encoding:"] && ![h containsString:@"identity"]){failed=1;break;}
            continue;
        }
        bodyBytes+=len;
        if(contentLength>=0 && bodyBytes>(size_t)contentLength){failed=1;break;}
        if(status!=200){if(errorBody.length+len>MAX_RESPONSE){failed=1;break;}[errorBody appendBytes:line length:len];continue;}
        if(!sse){failed=1;break;}
        while(len && (line[len-1]=='\n'||line[len-1]=='\r'))len--;
        if(len) {
            if(len>=5 && !memcmp(line,"data:",5)) {
                size_t offset=5;if(offset<len && line[offset]==' ')offset++;
                if(event.length)[event appendBytes:"\n" length:1];
                if(event.length+len-offset>MAX_RESPONSE){failed=1;break;}
                [event appendBytes:line+offset length:len-offset];
            }
            continue;
        }
        if(!event.length)continue;
        NSString *text=[[NSString alloc] initWithData:event encoding:NSUTF8StringEncoding];
        if([text isEqual:@"[DONE]"]){done=1;break;}
        id parsed=[NSJSONSerialization JSONObjectWithData:event options:0 error:NULL];
        [event setLength:0];
        if(![parsed isKindOfClass:[NSDictionary class]]){failed=1;break;}
        NSDictionary *body=parsed;
        if(failed)continue;
        if(invalidation_signal(body)){g_stream_invalidated=1;failed=1;continue;}
        if(body[@"error"]){failed=1;continue;}
        id choices=body[@"choices"];
        if(![choices isKindOfClass:[NSArray class]]){failed=1;break;}
        for(id item in choices) {
            if(![item isKindOfClass:[NSDictionary class]]){failed=1;break;}
            NSDictionary *choice=item;id reason=choice[@"finish_reason"];
            if(reason && reason!=[NSNull null]) {
                if(![@[@"stop",@"length"] containsObject:reason]){failed=1;break;}
                finish=1;
            }
            id delta=choice[@"delta"];
            if(![delta isKindOfClass:[NSDictionary class]]){failed=1;break;}
            id calls=delta[@"tool_calls"];
            if(calls && calls!=[NSNull null] && (![calls isKindOfClass:[NSArray class]] || [calls count])) {fprintf(stderr,"[chat] Structured tool calls unsupported by this terminal; no command executed.\n");failed=1;break;}
            for(NSString *key in @[@"content",@"reasoning_content"]) {
                id fragment=delta[key];if(!fragment || fragment==[NSNull null])continue;
                if(![fragment isKindOfClass:[NSString class]]){failed=1;break;}
                NSData *bytes=[fragment dataUsingEncoding:NSUTF8StringEncoding];
                if(bytes.length) {g_stream_any_output=1;if(!first)first=now_ms();}
                if([key isEqual:@"content"]) {
                    if(content.length+bytes.length>=MAX_RESPONSE || memchr(bytes.bytes,0,bytes.length)){failed=1;break;}
                    [content appendData:bytes];md_print([fragment UTF8String]);
                } else if(show_thinking)printf(ANSI_DIM "%s" ANSI_RESET,[fragment UTF8String]);
            }
            if(failed)break;
        }
        if(failed)break;
        fflush(stdout);
    }
    BOOL framingOK=contentLength<0 || bodyBytes==(size_t)contentLength;
    if(!framingOK || !headers || (status==200 && !done))g_stream_invalidated=0;
    if(status!=200 && errorBody.length && headers && framingOK && !failed) {
        id error=[NSJSONSerialization JSONObjectWithData:errorBody options:0 error:NULL];
        if([error isKindOfClass:[NSDictionary class]])g_stream_invalidated=invalidation_signal(error);
    }
    fclose(stream);
    g_stream_ok=status==200 && headers && sse && done && finish && framingOK && !failed && !g_chat_cancelled && content.length>0;
    printf(ANSI_RESET "\n\n");
    if(first)printf("[TTFT %.3fs]\n",(first-start)/1000.0);
    if(!g_stream_ok){fprintf(stderr,"[chat] Incomplete/failed response (HTTP %d); partial text not committed.\n",status);return NULL;}
    char *result=calloc(content.length+1,1);
    if(result)memcpy(result,content.bytes,content.length);
    return result;
}

static char *perform_turn(int port, NSArray *history, NSDictionary *turn, int max_tokens,
                          char *remote_id, int *resident, int show_thinking) {
    int create=!*resident;
    g_chat_cancelled=0;
    for(int attempt=0;attempt<2;attempt++) {
        g_stream_ok=g_stream_invalidated=g_stream_any_output=0;
        if(create)generate_session_id(remote_id,65);
        int fd=send_chat_request(port,create?history:@[turn],max_tokens,remote_id,create);
        char *reply=fd<0?NULL:stream_response(fd,show_thinking);
        if(g_stream_ok && reply){*resident=1;return reply;}
        free(reply);*resident=0;
        if(!g_stream_invalidated || g_stream_any_output || g_chat_cancelled || attempt)break;
        create=1;
        fprintf(stderr,"[chat] Session invalidated; replaying full local history.\n");
    }
    return NULL;
}
