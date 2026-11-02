// Model-free native unit test of the real diagnostic accounting function.
// Compile through the actual release Makefile flags; fake descriptors never
// allocate Metal resources or dereference their nominal buffer spans.
#define main infer_original_entry
#include "../metal_infer/infer.m"
#undef main
@interface ReleaseMemoryFakeBuffer : NSObject
@property(nonatomic) NSUInteger length;
@property(nonatomic) void *contents;
@end
@implementation ReleaseMemoryFakeBuffer
- (NSUInteger)allocatedSize { return self.length; }
- (MTLStorageMode)storageMode { return MTLStorageModeShared; }
@end
int main(int argc,char **argv) {
    @autoreleasepool {
        if(argc!=2)return 2;
        // Match main: defaults, config.json, then manifest fallback/override.
        config_init_defaults();
        load_config_from_config_json(argv[1]);
        NSString *manifest=[@(argv[1]) stringByAppendingPathComponent:@"model_weights.json"];
        load_config_from_manifest(manifest.fileSystemRepresentation);
        if(!g_config_loaded || NUM_KV_HEADS<=0 || HEAD_DIM<=0)return 2;
        g_metal=calloc(1,sizeof(*g_metal));if(!g_metal)return 2;
        float k=0,v=0,other=0;
        ReleaseMemoryFakeBuffer *kb=[ReleaseMemoryFakeBuffer new],*vb=[ReleaseMemoryFakeBuffer new];
        kb.length=vb.length=(size_t)128*NUM_KV_HEADS*HEAD_DIM*sizeof(float);
        kb.contents=&k;vb.contents=&v;
        g_metal->buf_kv_k[0]=(id<MTLBuffer>)kb;g_metal->buf_kv_v[0]=(id<MTLBuffer>)vb;
        KVCache cache={0};cache.k_cache=&k;cache.v_cache=&v;
        KVCache *kv[MAX_LAYERS]={0};void *states[MAX_LAYERS]={0};kv[3]=&cache;
        ServeStateSnapshot ref={0},cand={0};
        g_kv_seq_len=65536;
        NSDictionary *partial=rm_observe(kv,states,&ref,&cand,0);
        BOOL pass=[partial[@"cpu_kv_aliases_metal_reserved_bytes"] unsignedLongLongValue]==kb.length+vb.length &&
            [partial[@"cpu_kv_reserved_bytes"] unsignedLongLongValue]>kb.length+vb.length;
        g_kv_seq_len=128;
        NSDictionary *full=rm_observe(kv,states,&ref,&cand,0);
        pass&=[full[@"cpu_kv_aliases_metal_reserved_bytes"] unsignedLongLongValue]==[full[@"cpu_kv_reserved_bytes"] unsignedLongLongValue];
        cache.k_cache=&other;
        NSDictionary *separate=rm_observe(kv,states,&ref,&cand,0);
        pass&=[separate[@"cpu_kv_aliases_metal_reserved_bytes"] unsignedLongLongValue]==0;
        pass&=g_metal->device==nil && [partial[@"future_speculative_state_bytes"] unsignedLongLongValue]==0;
#if SESSION_PREFILL_OBSERVE_STRIDE > 1
        pass&=!sd_should_observe(129,"prefill") && sd_should_observe(128,"prefill");
        pass&=sd_should_observe(129,"prefill_final") && sd_should_observe(129,"decode_eos");
        pass&=!sd_sparse_points_valid(@{},141) && !sd_sparse_points_valid(@{@"141":@"short"},141);
        NSString *digest=[@"" stringByPaddingToLength:64 withString:@"a" startingAtIndex:0];
        pass&=sd_sparse_points_valid(@{@"141":digest},141);
        sd_replay_expected_points=@{@"141":digest};
        pass&=sd_should_observe(141,"continuous") && !sd_should_observe(128,"continuous");
        sd_replay_expected_points=nil;
#endif
        printf("[release-memory-test] partial/full/non-alias span: %s; metal_device_created=no weights_loaded=no\n",pass?"PASS":"FAIL");
        g_metal->buf_kv_k[0]=nil;g_metal->buf_kv_v[0]=nil;free(g_metal);g_metal=NULL;
        return pass?0:3;
    }
}
