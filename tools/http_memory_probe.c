#include <libproc.h>
#include <sys/resource.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv) {
    struct rusage_info_v4 r={0};
    if(argc!=2||proc_pid_rusage(atoi(argv[1]),RUSAGE_INFO_V4,(rusage_info_t *)&r))return 1;
    printf("{\"physical_bytes\":%llu,\"peak_physical_bytes\":%llu,\"rss_bytes\":%llu}\n",
        r.ri_phys_footprint,r.ri_lifetime_max_phys_footprint,r.ri_resident_size);
    return 0;
}
