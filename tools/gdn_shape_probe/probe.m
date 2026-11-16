#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <CommonCrypto/CommonDigest.h>
#include <math.h>
#include <string.h>
static id<MTLDevice> dev;static id<MTLCommandQueue> queue;
static id<MTLComputePipelineState> project,decay,scalar,chunk,conv;
static id<MTLBuffer> weights,scales,biases,input,alpha,beta,gs,bs,alog,dt,q,k,v,state,output,convstate,convinput,convweights,convout;
static const uint32_t IN=2048,OUT=32,GROUP=64,VD=4096,QD=2048,CD=8192,N=129;
static uint32_t seed=7719;static float rnd(void){seed=1664525*seed+1013904223;return ((int)(seed>>16)-32768)/32768.0f;}
static id<MTLBuffer> buf(NSUInteger n){id<MTLBuffer>b=[dev newBufferWithLength:n options:MTLResourceStorageModeShared];if(!b){fprintf(stderr,"allocation failed\n");exit(2);}memset(b.contents,0,n);return b;}
static void finish(id<MTLCommandBuffer>cmd){[cmd commit];[cmd waitUntilCompleted];if(cmd.status!=MTLCommandBufferStatusCompleted){fprintf(stderr,"GPU failed %s\n",cmd.error.description.UTF8String);exit(2);}}
static id<MTLComputePipelineState> makePipeline(id<MTLLibrary> lib,NSString*n){NSError*e=nil;id<MTLComputePipelineState>p=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:n] error:&e];if(!p){fprintf(stderr,"pipeline %s %s\n",n.UTF8String,e.description.UTF8String);exit(2);}return p;}
static NSDictionary *diff(NSData*a,const void*b){const float*x=a.bytes,*y=b;double max=0;NSUInteger different=0,nonfinite=0;for(NSUInteger i=0;i<a.length/4;i++){if(!isfinite(x[i])||!isfinite(y[i]))nonfinite++;max=fmax(max,fabs((double)x[i]-y[i]));different+=memcmp(x+i,y+i,4)!=0;}return @{@"max_abs":@(max),@"different":@(different),@"nonfinite":@(nonfinite)};}
static NSString *hash(const void*p,size_t n){unsigned char h[32];CC_SHA256(p,(CC_LONG)n,h);NSMutableString*s=[NSMutableString string];for(int i=0;i<32;i++)[s appendFormat:@"%02x",h[i]];return s;}
static void projections(uint32_t n,uint32_t partition){
 for(uint32_t base=0;base<n;base+=partition){uint32_t end=MIN(n,base+partition);id<MTLCommandBuffer>cmd=[queue commandBuffer];id<MTLComputeCommandEncoder>e=[cmd computeCommandEncoder];
  for(uint32_t t=base;t<end;t++){
   [e setComputePipelineState:project];[e setBuffer:weights offset:0 atIndex:0];[e setBuffer:scales offset:0 atIndex:1];[e setBuffer:biases offset:0 atIndex:2];[e setBuffer:input offset:(size_t)t*IN*4 atIndex:3];[e setBuffer:alpha offset:(size_t)t*OUT*4 atIndex:4];[e setBytes:&OUT length:4 atIndex:5];[e setBytes:&IN length:4 atIndex:6];[e setBytes:&GROUP length:4 atIndex:7];[e dispatchThreadgroups:MTLSizeMake(OUT,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];
   [e setBuffer:input offset:(size_t)t*IN*4 atIndex:3];[e setBuffer:beta offset:(size_t)t*OUT*4 atIndex:4];[e dispatchThreadgroups:MTLSizeMake(OUT,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];
   [e setComputePipelineState:decay];[e setBuffer:alpha offset:(size_t)t*OUT*4 atIndex:0];[e setBuffer:beta offset:(size_t)t*OUT*4 atIndex:1];[e setBuffer:alog offset:0 atIndex:2];[e setBuffer:dt offset:0 atIndex:3];[e setBuffer:gs offset:(size_t)t*OUT*4 atIndex:4];[e setBuffer:bs offset:(size_t)t*OUT*4 atIndex:5];[e dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(OUT,1,1)];
  }[e endEncoding];finish(cmd);
 }
}
static void advance(uint32_t start,uint32_t n,uint32_t width){
 for(uint32_t base=start;base<n;base+=width){uint32_t count=MIN(width,n-base);id<MTLCommandBuffer>cmd=[queue commandBuffer];id<MTLComputeCommandEncoder>e=[cmd computeCommandEncoder];
  [e setComputePipelineState:conv];[e setBuffer:convstate offset:0 atIndex:0];[e setBuffer:convinput offset:(size_t)base*CD*4 atIndex:1];[e setBuffer:convweights offset:0 atIndex:2];[e setBuffer:convout offset:(size_t)base*CD*4 atIndex:3];[e setBytes:&count length:4 atIndex:4];[e dispatchThreads:MTLSizeMake(CD,1,1) threadsPerThreadgroup:MTLSizeMake(128,1,1)];[e endEncoding];e=[cmd computeCommandEncoder];
  [e setComputePipelineState:width==1?scalar:chunk];[e setBuffer:state offset:0 atIndex:0];[e setBuffer:q offset:(size_t)base*QD*4 atIndex:1];[e setBuffer:k offset:(size_t)base*QD*4 atIndex:2];[e setBuffer:v offset:(size_t)base*VD*4 atIndex:3];[e setBuffer:gs offset:(size_t)base*OUT*4 atIndex:4];[e setBuffer:bs offset:(size_t)base*OUT*4 atIndex:5];[e setBuffer:output offset:(size_t)base*VD*4 atIndex:6];uint32_t ratio=2;[e setBytes:width==1?&ratio:&count length:4 atIndex:7];
  if(width==1)[e dispatchThreadgroups:MTLSizeMake(OUT,1,1) threadsPerThreadgroup:MTLSizeMake(128,1,1)];else [e dispatchThreads:MTLSizeMake(VD,1,1) threadsPerThreadgroup:MTLSizeMake(128,1,1)];[e endEncoding];finish(cmd);
 }
}
int main(int argc,const char**argv){@autoreleasepool{
 if(argc!=3)return 2;dev=MTLCreateSystemDefaultDevice();if(!dev){fprintf(stderr,"No Metal device\n");return 2;}queue=[dev newCommandQueue];NSError*err=nil;
 NSString*src=[NSString stringWithContentsOfFile:@(argv[1]) encoding:NSUTF8StringEncoding error:&err];MTLCompileOptions*opts=[MTLCompileOptions new];opts.mathMode=MTLMathModeFast;opts.languageVersion=MTLLanguageVersion3_1;
 id<MTLLibrary>lib=[dev newLibraryWithSource:src options:opts error:&err];if(!lib){fprintf(stderr,"Metal compile %s\n",err.description.UTF8String);return 2;}
 project=makePipeline(lib,@"dequant_matvec_4bit_fast");decay=makePipeline(lib,@"compute_decay_beta");scalar=makePipeline(lib,@"gated_delta_net_step");chunk=makePipeline(lib,@"gdn_chunk");conv=makePipeline(lib,@"conv_chunk");
 weights=buf(OUT*IN/8*4);scales=buf(OUT*IN/GROUP*2);biases=buf(scales.length);input=buf(N*IN*4);alpha=buf(N*OUT*4);beta=buf(alpha.length);gs=buf(alpha.length);bs=buf(alpha.length);alog=buf(OUT*4);dt=buf(OUT*2);
 q=buf(N*QD*4);k=buf(q.length);v=buf(N*VD*4);state=buf(OUT*128*128*4);output=buf(v.length);convstate=buf(3*CD*4);convinput=buf(N*CD*4);convweights=buf(4*CD*2);convout=buf(convinput.length);
 for(size_t i=0;i<weights.length/4;i++){seed=1664525*seed+1013904223;((uint32_t*)weights.contents)[i]=seed;}
 for(size_t i=0;i<scales.length/2;i++){((uint16_t*)scales.contents)[i]=0x3b80;((uint16_t*)biases.contents)[i]=0xbd00;}
 for(size_t i=0;i<input.length/4;i++)((float*)input.contents)[i]=rnd()*.1f;
 for(size_t i=0;i<q.length/4;i++){((float*)q.contents)[i]=rnd()*.01f;((float*)k.contents)[i]=rnd()*.01f;}
 for(size_t i=0;i<v.length/4;i++)((float*)v.contents)[i]=rnd()*.1f;
 for(size_t i=0;i<convinput.length/4;i++)((float*)convinput.contents)[i]=rnd()*.1f;
 for(size_t i=0;i<convweights.length/2;i++)((uint16_t*)convweights.contents)[i]=0x3e00;
 for(uint32_t i=0;i<OUT;i++){((float*)alog.contents)[i]=-2;((uint16_t*)dt.contents)[i]=0x3e00;}
 NSMutableArray*rows=[NSMutableArray array];NSMutableArray*prefixRows=[NSMutableArray array];NSData*prefixRef=nil;int failed=0;uint32_t widths[]={1,8,16,32,64,128};
 for(uint32_t ncase=0;ncase<4;ncase++){uint32_t counts[]={17,32,33,129};uint32_t n=counts[ncase];projections(n,1);if(!prefixRef)prefixRef=[NSData dataWithBytes:alpha.contents length:17*OUT*4];[prefixRows addObject:@{@"rows":@(n),@"first_17_projection":diff(prefixRef,alpha.contents)}];NSData*pa=[NSData dataWithBytes:alpha.contents length:n*OUT*4];NSData*pb=[NSData dataWithBytes:beta.contents length:n*OUT*4];memset(state.contents,0,state.length);memset(convstate.contents,0,convstate.length);advance(0,n,1);NSData*rs=[NSData dataWithBytes:state.contents length:state.length],*rc=[NSData dataWithBytes:convstate.contents length:convstate.length],*ro=[NSData dataWithBytes:output.contents length:n*VD*4];
  for(uint32_t w=0;w<6;w++){projections(n,widths[w]);NSDictionary*da=diff(pa,alpha.contents),*db=diff(pb,beta.contents);memset(state.contents,0,state.length);memset(convstate.contents,0,convstate.length);advance(0,n,widths[w]);NSDictionary*ds=diff(rs,state.contents),*dc=diff(rc,convstate.contents),*dout=diff(ro,output.contents);BOOL exact=[da[@"different"] intValue]==0&&[db[@"different"] intValue]==0&&[ds[@"different"] intValue]==0&&[dc[@"different"] intValue]==0&&[dout[@"different"] intValue]==0;BOOL finite=![da[@"nonfinite"] intValue]&&![db[@"nonfinite"] intValue]&&![ds[@"nonfinite"] intValue]&&![dc[@"nonfinite"] intValue]&&![dout[@"nonfinite"] intValue];BOOL pass=finite&&[ds[@"max_abs"] doubleValue]<1e-3&&[dc[@"max_abs"] doubleValue]<1e-3&&[dout[@"max_abs"] doubleValue]<=1e-3;
   [rows addObject:@{@"tokens":@(n),@"chunk":@(widths[w]),@"projection_alpha":da,@"projection_beta":db,@"gdn_state":ds,@"conv_tail":dc,@"gdn_output":dout,@"bit_exact":@(exact),@"pass":@(pass),@"gdn_sha256":hash(state.contents,state.length),@"conv_sha256":hash(convstate.contents,convstate.length)}];if(!pass){failed=1;break;}
  }if(failed)break;
 }
 // Completed-boundary RAM capture/restore plus a common appended suffix.
 memset(state.contents,0,state.length);memset(convstate.contents,0,convstate.length);advance(0,64,16);NSData*anchor=[NSData dataWithBytes:state.contents length:state.length],*tail=[NSData dataWithBytes:convstate.contents length:convstate.length];advance(64,N,32);NSData*end=[NSData dataWithBytes:state.contents length:state.length],*endConv=[NSData dataWithBytes:convstate.contents length:convstate.length];memcpy(state.contents,anchor.bytes,state.length);memcpy(convstate.contents,tail.bytes,convstate.length);advance(64,N,8);NSDictionary*restore=diff(end,state.contents),*restoreConv=diff(endConv,convstate.contents);if([restoreConv[@"different"] intValue])failed=1;if([restore[@"nonfinite"] intValue]||[restore[@"max_abs"] doubleValue]>=1e-3)failed=1;
 NSDictionary*report=@{@"status":failed?@"FAIL":@"PASS",@"scope":@"Synthetic inputs, exact current Metal gate/recurrence/conv kernels; not full model or disk checkpoint",@"seed":@7719,@"cases":rows,@"ram_restore_common_suffix":restore,@"ram_restore_conv":restoreConv,@"prefix_independence":prefixRows,@"metal_allocated_bytes":@(dev.currentAllocatedSize),@"model_loaded":@NO};NSData*data=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:&err];[data writeToFile:@(argv[2]) atomically:YES];printf("GDN_SYNTHETIC %s cases=%lu restore_different=%d buffers=%lu\n",failed?"FAIL":"PASS",(unsigned long)rows.count,[restore[@"different"] intValue],(unsigned long)dev.currentAllocatedSize);return failed?3:0;
}}
