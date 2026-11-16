#include <stdio.h>
#include "flash_serve_admission.h"
static int failures=0,checks=0;
#define CHECK(x) do{checks++;if(!(x)){fprintf(stderr,"FAIL line%d: %s\n",__LINE__,#x);failures++;}}while(0)
int main(void){
 FlashServeResourceGuard g;uint64_t reserve=FLASH_SERVE_MIN_HOST_AVAILABLE_BYTES,rss=FLASH_SERVE_MAX_PROCESS_RSS_BYTES;
 flash_serve_guard_begin(&g,0);CHECK(flash_serve_guard_sample(&g,0,0,0,0,0));
 flash_serve_guard_begin(&g,1);CHECK(flash_serve_guard_due(&g,0));CHECK(flash_serve_guard_sample(&g,0,1,reserve,1,rss-1));CHECK(!flash_serve_guard_due(&g,249));
 CHECK(flash_serve_guard_sample(&g,249,0,0,0,0));CHECK(!flash_serve_guard_sample(&g,250,1,reserve-1,1,1));CHECK(g.failure==2);
 CHECK(!flash_serve_guard_sample(&g,1000,1,reserve+1,1,1));
 flash_serve_guard_begin(&g,1);CHECK(flash_serve_guard_sample(&g,0,1,reserve+1,1,1));CHECK(!g.failure);
 CHECK(!flash_serve_guard_sample(&g,250,0,reserve,1,1));CHECK(g.failure==1);
 flash_serve_guard_begin(&g,1);CHECK(!flash_serve_guard_sample(&g,0,1,reserve,0,0));CHECK(g.failure==1);
 flash_serve_guard_begin(&g,1);CHECK(!flash_serve_guard_sample(&g,0,1,reserve,1,rss));CHECK(g.failure==3);
 flash_serve_guard_begin(&g,0);CHECK(flash_serve_guard_sample(&g,0,0,0,0,0));
 CHECK(!flash_serve_host_reserve_admitted(reserve-1));CHECK(flash_serve_host_reserve_admitted(reserve));CHECK(flash_serve_host_reserve_admitted(reserve+1));
 printf("resource guard: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
