/* Read host availability plus ONLY an explicitly supplied owned child's usage. */
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <libproc.h>
#include "flash_serve_admission.h"
int main(int argc,char **argv) {
    if(argc!=2)return 2;
    char *end=NULL;errno=0;long pid=strtol(argv[1],&end,10);
    if(errno || !end || *end || pid<0 || pid>INT_MAX)return 2;
    uint64_t available=0;
    if(!flash_serve_host_available_bytes(&available))return 1;
    struct rusage_info_v4 r={0};
    if(pid && proc_pid_rusage((int)pid,RUSAGE_INFO_V4,(rusage_info_t *)&r))return 1;
    printf("{\"host_available_bytes\":%llu,\"rss_bytes\":%llu,\"physical_bytes\":%llu,\"start_abstime\":%llu}\n",
           (unsigned long long)available,r.ri_resident_size,r.ri_phys_footprint,r.ri_proc_start_abstime);
    return 0;
}
