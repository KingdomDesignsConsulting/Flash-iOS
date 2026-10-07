// CPU-only full-output analysis of real M8 MMA group partials.
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint32_t bits(float x){uint32_t u;memcpy(&u,&x,4);return u;}
static float bf16(uint16_t x){uint32_t u=(uint32_t)x<<16;float f;memcpy(&f,&u,4);return f;}
static int get(FILE *f,void *p,size_t sz,size_t n){return fread(p,sz,n,f)==n;}
static float reduce8(const float *a){float v[8];memcpy(v,a,sizeof(v));for(int w=1;w<8;w*=2)for(int k=0;k<8;k+=2*w)v[k]=fmaf(v[k+w],1.0f,v[k]);return v[0];}
static float xsum(const float *x,int row,int g,int fm){
    float v[8],next[8];
    for(int block=0;block<8;block++){float sum=0.0f;for(int j=0;j<8;j++)sum=fmaf(x[row*2048+g*64+block*8+j],1.0f,sum);v[block]=sum;}
    for(int mask=1;mask<=4;mask*=2){for(int block=0;block<8;block++)next[block]=fmaf(v[block^mask],1.0f,v[block]);memcpy(v,next,sizeof(v));}
    return v[fm];
}
typedef struct{size_t exact,total,nan,inf;double max_abs,sum_sq,row_max[8];}Metric;
static void note(Metric *m,float got,float ref,int row){
    m->total++;m->exact+=bits(got)==bits(ref);
    if(isnan(got)||isnan(ref)){m->nan++;return;}if(isinf(got)||isinf(ref)){m->inf++;return;}
    double d=fabs((double)got-(double)ref);if(d>m->max_abs)m->max_abs=d;if(d>m->row_max[row])m->row_max[row]=d;m->sum_sq+=d*d;
}
static void report(const char *name,const Metric *m){
    printf("%-31s bitwise=%zu/%zu max_abs=%.9g rms=%.9g nan=%zu inf=%zu\n",name,m->exact,m->total,m->max_abs,sqrt(m->sum_sq/(double)m->total),m->nan,m->inf);
    printf("  row_max=[%.3g %.3g %.3g %.3g %.3g %.3g %.3g %.3g]\n",m->row_max[0],m->row_max[1],m->row_max[2],m->row_max[3],m->row_max[4],m->row_max[5],m->row_max[6],m->row_max[7]);
}
int main(int argc,char **argv){
    if(argc!=2){fprintf(stderr,"usage: %s affine-mma-full-SHAPE.bin\n",argv[0]);return 2;}
    FILE *f=fopen(argv[1],"rb");if(!f){perror(argv[1]);return 1;}
    uint32_t h[4];if(!get(f,h,4,4)||h[0]!=0x34414d4du||h[2]!=2048u||h[3]!=16u||!(h[1]==8192u||h[1]==4096u)){fprintf(stderr,"ERROR: invalid dump header\n");return 1;}
    size_t N=h[1],groups=32,rows=8;
    float *x=calloc(rows*2048u,4),*P=calloc(groups*rows*N,4),*ref=calloc(rows*N,4),*mma=calloc(rows*N,4);
    uint16_t *sc=calloc(N*groups,2),*bi=calloc(N*groups,2);
    if(!x||!P||!ref||!mma||!sc||!bi)return 1;
    int ok=get(f,x,4,rows*2048u)&&get(f,sc,2,N*groups)&&get(f,bi,2,N*groups)&&get(f,P,4,groups*rows*N)&&get(f,ref,4,rows*N)&&get(f,mma,4,rows*N);
    if(!ok||fgetc(f)!=EOF){fprintf(stderr,"ERROR: truncated/trailing dump data\n");return 1;}fclose(f);
    float xs[8][32][8];for(int row=0;row<8;row++)for(int g=0;g<32;g++)for(int fm=0;fm<8;fm++)xs[row][g][fm]=xsum(x,row,g,fm);
    Metric baseline={0},m8_vs_m1={0},bias_element={0},scale_unfused={0},bias_first={0},group_seq={0},group_tree={0};
    for(int row=0;row<8;row++)for(size_t n=0;n<N;n++){
        float lane_base[8]={0},lane_q[8]={0},lane_unfused[8]={0},lane_bias_first[8]={0};
        float group[32];
        for(int c=0;c<8;c++)for(int g=c;g<32;g+=8){
            float p=P[((size_t)g*8u+(size_t)row)*N+n];
            float scale=bf16(sc[n*32u+(size_t)g]),bias=bf16(bi[n*32u+(size_t)g]),sum=xs[row][g][n%8u];
            lane_base[c]=fmaf(bias,sum,fmaf(scale,p,lane_base[c]));
            lane_q[c]=fmaf(scale,p,lane_q[c]);
            volatile float scaled=scale*p,bias_term=bias*sum;
            lane_unfused[c]+=scaled+bias_term;
            lane_bias_first[c]=fmaf(scale,p,fmaf(bias,sum,lane_bias_first[c]));
            group[g]=fmaf(bias,sum,scale*p);
        }
        size_t idx=(size_t)row*N+n;
        note(&baseline,reduce8(lane_base),mma[idx],row);
        note(&m8_vs_m1,mma[idx],ref[idx],row);
        float bias_lanes[32]={0};
        for(int lane=0;lane<32;lane++)for(int col=lane;col<256;col+=32){
            float bias=bf16(bi[n*32u+(size_t)(col/8)]);
            for(int j=0;j<8;j++){
                volatile float product=bias*x[row*2048+col*8+j];
                bias_lanes[lane]+=product;
            }
        }
        for(int width=1;width<32;width*=2)
            for(int k=0;k<32;k+=2*width)bias_lanes[k]=fmaf(bias_lanes[k+width],1.0f,bias_lanes[k]);
        note(&bias_element,reduce8(lane_q)+bias_lanes[0],ref[idx],row);
        note(&scale_unfused,reduce8(lane_unfused),ref[idx],row);
        note(&bias_first,reduce8(lane_bias_first),ref[idx],row);
        float sequential=0;for(int g=0;g<32;g++)sequential+=group[g];
        note(&group_seq,sequential,ref[idx],row);
        for(int width=1;width<32;width*=2)for(int k=0;k<32;k+=2*width)group[k]=fmaf(group[k+width],1.0f,group[k]);
        note(&group_tree,group[0],ref[idx],row);
    }
    printf("shape=%ux%u outputs=%zu\n",h[1],h[2],rows*N);
    report("reconstructed M8 vs GPU M8",&baseline);
    report("GPU M8 vs production M1",&m8_vs_m1);
    report("MMA q*x + elementwise bias",&bias_element);
    report("unfused scale/group terms",&scale_unfused);
    report("bias before scaled P",&bias_first);
    report("MMA group partials sequential",&group_seq);
    report("MMA group partials pairwise",&group_tree);
    return baseline.exact==baseline.total&&baseline.nan==0&&baseline.inf==0?0:1;
}
