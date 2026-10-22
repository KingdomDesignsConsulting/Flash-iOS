// Benchmark-only counters adapted from the historical attention_diag.inc.
// Primary throughput runs leave counter sampling disabled.
#include <mach/mach.h>
#include <sys/resource.h>
static int kv_perf_active=0,kv_perf_observer=0,kv_perf_count=0,kv_perf_samples=0,kv_perf_stage=0;
static double kv_perf_cpu_ms[MAX_LAYERS],kv_perf_layer_ms[MAX_LAYERS];
static int kv_perf_gpu_route[MAX_LAYERS];
static id<MTLCounterSampleBuffer> kv_perf_counter;
static id<MTLDevice> kv_perf_device;
static uint64_t kv_perf_cpu_stamp,kv_perf_gpu_stamp;
static struct {int layer,len,start,end;} kv_perf_records[16];
static void kv_perf_init(id<MTLDevice> device) {
    kv_perf_device=device;
    BOOL dispatch=[device supportsCounterSampling:MTLCounterSamplingPointAtDispatchBoundary];
    BOOL stage=[device supportsCounterSampling:MTLCounterSamplingPointAtStageBoundary];
    kv_perf_stage=!dispatch&&stage;
    if(dispatch||stage)for(id<MTLCounterSet> set in device.counterSets)
        if([set.name isEqualToString:MTLCommonCounterSetTimestamp]) {
            MTLCounterSampleBufferDescriptor *d=[MTLCounterSampleBufferDescriptor new];
            d.counterSet=set;d.sampleCount=32;d.storageMode=MTLStorageModeShared;
            kv_perf_counter=[device newCounterSampleBufferWithDescriptor:d error:NULL];
        }
    fprintf(stderr,"[kv-perf-counter] available=%d stage=%d\n",kv_perf_counter!=nil,kv_perf_stage);
}
static void kv_perf_reset(int observer) {
    kv_perf_active=1;kv_perf_observer=observer;kv_perf_count=kv_perf_samples=0;
    memset(kv_perf_cpu_ms,0,sizeof(kv_perf_cpu_ms));memset(kv_perf_layer_ms,0,sizeof(kv_perf_layer_ms));
    memset(kv_perf_gpu_route,0,sizeof(kv_perf_gpu_route));
    if(observer&&kv_perf_counter)[kv_perf_device sampleTimestamps:&kv_perf_cpu_stamp gpuTimestamp:&kv_perf_gpu_stamp];
}
static id<MTLComputeCommandEncoder> kv_perf_encoder(id<MTLCommandBuffer> cmd,int begin,int layer,int len) {
    if(!kv_perf_active||!kv_perf_observer||!kv_perf_counter)return [cmd computeCommandEncoder];
    if(begin) {
        if(kv_perf_count>=16)abort();
        int i=kv_perf_count++;kv_perf_records[i].layer=layer;kv_perf_records[i].len=len;
        kv_perf_records[i].start=kv_perf_samples++;kv_perf_records[i].end=kv_perf_samples++;
    }
    int i=kv_perf_count-1;
    if(kv_perf_stage) {
        MTLComputePassDescriptor *d=[MTLComputePassDescriptor computePassDescriptor];
        d.sampleBufferAttachments[0].sampleBuffer=kv_perf_counter;
        d.sampleBufferAttachments[0].startOfEncoderSampleIndex=begin?kv_perf_records[i].start:MTLCounterDontSample;
        d.sampleBufferAttachments[0].endOfEncoderSampleIndex=begin?MTLCounterDontSample:kv_perf_records[i].end;
        return [cmd computeCommandEncoderWithDescriptor:d];
    }
    id<MTLComputeCommandEncoder> enc=[cmd computeCommandEncoder];
    if(begin)[enc sampleCountersInBuffer:kv_perf_counter atSampleIndex:kv_perf_records[i].start withBarrier:YES];
    return enc;
}
static void kv_perf_encoder_end(id<MTLComputeCommandEncoder> enc) {
    if(kv_perf_active&&kv_perf_observer&&kv_perf_counter&&!kv_perf_stage&&kv_perf_count)
        [enc sampleCountersInBuffer:kv_perf_counter atSampleIndex:kv_perf_records[kv_perf_count-1].end withBarrier:YES];
}
static int kv_perf_resolve(double gpu_ms[MAX_LAYERS]) {
    memset(gpu_ms,0,MAX_LAYERS*sizeof(double));
    if(!kv_perf_observer||!kv_perf_counter||!kv_perf_samples)return 1;
    uint64_t c,g;[kv_perf_device sampleTimestamps:&c gpuTimestamp:&g];
    if(g<=kv_perf_gpu_stamp||c<=kv_perf_cpu_stamp)return 0;
    double ns_per_tick=(double)(c-kv_perf_cpu_stamp)/(g-kv_perf_gpu_stamp);
    NSData *data=[kv_perf_counter resolveCounterRange:NSMakeRange(0,kv_perf_samples)];
    if(data.length<(NSUInteger)kv_perf_samples*sizeof(MTLCounterResultTimestamp))return 0;
    const MTLCounterResultTimestamp *r=data.bytes;
    for(int i=0;i<kv_perf_count;i++) {
        uint64_t a=r[kv_perf_records[i].start].timestamp,b=r[kv_perf_records[i].end].timestamp;
        if(!a||!b||a==MTLCounterErrorValue||b==MTLCounterErrorValue||b<a)return 0;
        gpu_ms[kv_perf_records[i].layer]=(b-a)*ns_per_tick/1e6;
    }
    return 1;
}
