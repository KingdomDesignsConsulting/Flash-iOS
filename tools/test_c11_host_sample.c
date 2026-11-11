#include <stdio.h>
#include "flash_serve_admission.h"
int main(void){uint64_t available=0;int ok=flash_serve_host_available_bytes(&available);printf("{\"sample_available\":%s,\"bytes\":%llu,\"reserve_admitted\":%s}\n",ok?"true":"false",(unsigned long long)available,ok&&flash_serve_host_reserve_admitted(available)?"true":"false");return ok?0:1;}
