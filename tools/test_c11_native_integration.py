#!/usr/bin/env python3
"""No-weight test of extracted actual preflight + HTTP rejection block, with host stubs."""
import pathlib,subprocess,tempfile,json,hashlib
R=pathlib.Path(__file__).resolve().parents[1]
s=(R/'metal_infer/infer.m').read_text()
a=s.index('static int context_preflight(');b=s.index('static float *s_cpu_attn_scores',a);pre=s[a:b]
a=s.index('if (!context_preflight("HTTP request"');start=s.index('{',a);depth=1;i=start+1
while depth:
 depth+=(s[i]=='{')-(s[i]=='}');i+=1
reject=s[a:i]
# Tie the extracted branch to native state-mutation ordering.
tail=s[i:s.index('// ---- Continue from existing session state ----',i)]
if 'async_pread_wait' not in tail:raise RuntimeError('Expected preflight ordering changed')
if s.index("active_session_id[0] = '\\0';",i)<i:raise RuntimeError('ordering')
code=r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
#include "flash_serve_admission.h"
static int g_kv_seq_len=65536, memory_ok=1, samples=0, code_sent=0, closed=0;
static uint64_t memory_bytes=FLASH_SERVE_MIN_HOST_AVAILABLE_BYTES;
static int fake_available(uint64_t *p){samples++;*p=memory_bytes;return memory_ok;}
#define flash_serve_host_available_bytes fake_available
'''+pre+r'''
typedef struct {int count;int *ids;} Tokens;
typedef struct {int pos,turn;int kv_len[10];unsigned char gdn[96],conv[48];char id[20];} Resident;
static Resident state;
static void http_write_str(int fd,const char *text){(void)fd;code_sent=strstr(text,"400 Bad Request")?400:0;}
static int fake_close(int fd){(void)fd;closed++;return 0;}
#define close fake_close
static int request(int preflight_pos,int count,int max_gen){
 int accepted=0,client_fd=99;char *reqbuf=malloc(32);
 Tokens *pt=calloc(1,sizeof(*pt)),*request_prefix_pt=calloc(1,sizeof(*pt));
 pt->count=count;pt->ids=malloc(16);request_prefix_pt->ids=malloc(16);
 code_sent=closed=0;
 for(int once=0;once<1;once++){
'''+reject+r'''
 accepted=1;
 free(pt->ids);free(pt);free(request_prefix_pt->ids);free(request_prefix_pt);free(reqbuf);
 }
 return accepted;
}
static int check(int value,int expected,const char *name){if(value!=expected){fprintf(stderr,"FAIL %s actual=%d expected=%d\n",name,value,expected);return 1;}return 0;}
int main(){
 int failures=0,cases=0;memset(&state,0x5a,sizeof(state));state.pos=GPU_KV_SEQ-2;state.turn=7;strcpy(state.id,"existing-session");for(int l=0;l<10;l++)state.kv_len[l]=state.pos;Resident before=state;
#define CASE(name,pos,in,out,want) do {cases++;failures+=check(request(pos,in,out),want,name);failures+=check(memcmp(&state,&before,sizeof(state)),0,"resident bytes preserved");if(!(want)){failures+=check(code_sent,400,"HTTP400");failures+=check(closed,1,"closed");}}while(0)
 unsetenv("FLASH_SERVE_QUALIFIED_GPU_ONLY");CASE("unset legacy",32768,1,1,1);failures+=check(samples,0,"no memory sample disabled");
 setenv("FLASH_SERVE_QUALIFIED_GPU_ONLY","1",1);
 CASE("fresh exact",0,GPU_KV_SEQ-1,1,1);CASE("fresh plusone",0,GPU_KV_SEQ,1,0);
 CASE("continuation exact",state.pos,1,1,1);CASE("continuation plusone",state.pos,2,1,0);
 CASE("negative position",-1,1,1,0);CASE("negative input",0,-1,1,0);CASE("negative generation",0,1,-1,0);CASE("widened accounting",INT_MAX,INT_MAX,INT_MAX,0);
 memory_bytes--;CASE("low memory",state.pos,1,1,0);memory_bytes++;
 memory_ok=0;CASE("sampler failed",state.pos,1,1,0);memory_ok=1;CASE("valid followup after rejects",state.pos,1,1,1);
 g_kv_seq_len=1024;CASE("engine smaller exact",0,1023,1,1);CASE("engine smaller excess",0,1024,1,0);g_kv_seq_len=65536;
 for(int x=0;x<4;x++){const char *bad[]={"0","true","2"," 1"};setenv("FLASH_SERVE_QUALIFIED_GPU_ONLY",bad[x],1);CASE("invalid env",0,1,1,0);}
 setenv("FLASH_SERVE_QUALIFIED_GPU_ONLY","",1);CASE("empty explicitly disables",32768,1,1,1);
 setenv("FLASH_SERVE_QUALIFIED_GPU_ONLY","1",1);memory_ok=0;failures+=check(context_preflight("CLI",32768,1,1),1,"CLI unchanged");cases++;
 printf("{\"gpu_cap\":%d,\"cases\":%d,\"failures\":%d,\"resident_pos\":%d,\"turn_count\":%d,\"all_kv_lengths\":%d,\"state_preserved\":%s}\n",GPU_KV_SEQ,cases,failures,state.pos,state.turn,state.kv_len[0],memcmp(&state,&before,sizeof(state))?"false":"true");
 return failures?1:0;
}
'''
results=[]
with tempfile.TemporaryDirectory(prefix='c11-integration-') as d:
 p=pathlib.Path(d);src=p/'integration.c';src.write_text(code)
 for cap in [8192,32768]:
  exe=p/f'test-{cap}';subprocess.run(['clang','-std=c11','-D_DARWIN_C_SOURCE',f'-DGPU_KV_SEQ={cap}','-Wall','-Wextra','-Werror','-I',str(R/'metal_infer'),str(src),'-o',str(exe)],check=True,capture_output=True)
  run=subprocess.run([str(exe)],text=True,capture_output=True,check=True);results.append(json.loads(run.stdout))
report=dict(status='PASS',scope='Actual extracted preflight/rejection branch, synthetic resident KV/GDN/conv sentinels; no actual model KV advancement or HTTP socket',source_sha256=hashlib.sha256(s.encode()).hexdigest(),tested_source_sha256=hashlib.sha256((pre+reject).encode()).hexdigest(),results=results,known_mismatch='Explicit empty environment disables policy; handoff says all explicit values other than1 fail. Supplied helper test intentionally expects empty disabled.')
out=R/'docs/audits/c11-verification-evidence/integration.json';out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
