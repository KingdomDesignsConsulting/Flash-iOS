#!/usr/bin/env python3
"""Extract actual checked-forward, abort cleanup and error serialization; stub only model work/IO."""
import pathlib,subprocess,tempfile,json,hashlib
R=pathlib.Path(__file__).resolve().parents[1];s=(R/'metal_infer/infer.m').read_text()
def block(marker):
 a=s.index(marker);i=s.index('{',a)+1;depth=1
 while depth:depth+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[a:i]
forward=block('static int run_all_layers_checked(')
error=block('static int send_session_invalidated_error(int fd, int stream_response, NSString *message)')
preabort=block('if (g_forward_error || prefill_client_disconnected)')
a=s.index('// ---- Save session state ----');start=s.index('if (request_state_failed || !session_reusable)',a);cleanup=block(s[start:s.index('{',start)])
code=r'''
#import <Foundation/Foundation.h>
#include <sys/mman.h>
#include "flash_serve_admission.h"
#define NUM_LAYERS 40
#define FULL_ATTN_INTERVAL 4
typedef struct {int unused;} WeightFile;
typedef struct {int unused;} KVCache;
static int g_forward_error,forwarded,discarded,fail_at;
static FlashServeResourceGuard guard;
static int flash_qualified_resource_poll(void){return flash_serve_guard_sample(&guard,forwarded*250.0,1,forwarded>=fail_at?0:FLASH_SERVE_MIN_HOST_AVAILABLE_BYTES,1,1);}
static int discard_deferred_experts(void){discarded++;return 1;}
static void fused_layer_forward(WeightFile*w,int l,float*h,KVCache*k,void*v,int pos,void*m,int K,int fd){(void)w;(void)l;(void)h;(void)k;(void)v;(void)pos;(void)m;(void)K;(void)fd;forwarded++;}
static NSMutableData *wire;
static int http_write(int fd,const void *p,int n){(void)fd;[wire appendBytes:p length:n];return n;}
static int http_write_str(int fd,const char *p){return http_write(fd,p,(int)strlen(p));}
static int fake_close(int fd){(void)fd;return 0;}
#define close fake_close
'''+forward+'\n'+error+r'''
int main(){@autoreleasepool{
 int checks=0;
#define REQUIRE(x) do{checks++;if(!(x)){fprintf(stderr,"FAIL line%d\n",__LINE__);return 1;}}while(0)
 for(int mode=0;mode<3;mode++){
  WeightFile w={0};float h=0;KVCache *kv[40]={0};void *states[40]={0},*maps[40]={0};int fds[40]={0};
  forwarded=discarded=0;fail_at=5;flash_serve_guard_begin(&guard,1);
  REQUIRE(!run_all_layers_checked(&w,&h,kv,states,maps,fds,10,8));REQUIRE(g_forward_error&&forwarded==5&&discarded==1&&guard.failure==2);
  char active_session_id[64]="existing-session";uint64_t active_session_tool_sig=123;int active_session_tool_sig_valid=1;
  NSMutableArray *active_session_pending_tool_ids=[NSMutableArray arrayWithObject:@"pending"];
  NSString *active_session_profile=@"test";int session_pos=10,session_ended_with_eos=1;
  wire=[NSMutableData data];int client_fd=99,stream_response=mode;
  if(mode!=1){
   int prefill_client_disconnected=(mode==2),prefill_completed_tokens=5;if(mode==2)g_forward_error=0;const char *request_id="audit";
   float *serve_embed_batch=NULL;typedef struct {int count;int *ids;} Tokens;Tokens *pt=calloc(1,sizeof(*pt)),*request_prefix_pt=NULL;pt->count=10;pt->ids=malloc(4);char *reqbuf=malloc(4);
   for(int once=0;once<1;once++){
'''+preabort+r'''
   }
  }else{
   int request_state_failed=1,session_reusable=0;
   REQUIRE(send_session_invalidated_error(client_fd,stream_response,@"generation failed")>=0);
'''+cleanup+r'''
  }
  REQUIRE(!active_session_id[0]&&session_pos==0&&!session_ended_with_eos&&!active_session_tool_sig_valid&&active_session_pending_tool_ids.count==0);
  NSString *text=[[NSString alloc]initWithData:wire encoding:NSUTF8StringEncoding];
  if(mode==2){REQUIRE(wire.length==0);}else{
  REQUIRE([text containsString:@"session_invalidated"]&&[text containsString:@"resend_full_history"]);
  if(mode)REQUIRE([text hasSuffix:@"data: [DONE]\n\n"]&&![text containsString:@"finish_reason"]);else REQUIRE([text containsString:@"500 Internal Server Error"]);
  }
  // Explicit new request resets the latch; discarded request is never resumed.
  forwarded=discarded=0;fail_at=100;flash_serve_guard_begin(&guard,1);
  REQUIRE(run_all_layers_checked(&w,&h,kv,states,maps,fds,0,8)&&forwarded==40);
 }
 printf("{\"status\":\"PASS\",\"checks\":%d,\"scope\":\"actual source error/cleanup paths with deterministic model stubs\"}\n",checks);
 return 0;
}}
'''
with tempfile.TemporaryDirectory(prefix='c11-abort-') as d:
 p=pathlib.Path(d);(p/'test.m').write_text(code);compile=subprocess.run(['clang','-fobjc-arc','-framework','Foundation','-I',str(R/'metal_infer'),str(p/'test.m'),'-o',str(p/'test')],capture_output=True,text=True)
 if compile.returncode:raise RuntimeError(compile.stderr)
 result=subprocess.run([str(p/'test')],text=True,capture_output=True,check=True);report=json.loads(result.stdout)
report['extracted_sha256']=hashlib.sha256((forward+error+preabort+cleanup).encode()).hexdigest()
(R/'docs/results/c11-20261116-abort.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
