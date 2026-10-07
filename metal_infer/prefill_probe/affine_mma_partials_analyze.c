// CPU-only diagnostic for the benchmark-only MMA partial dumps.
// Compile: clang -O2 -Wall -Wextra -std=c11 -lm this-file.c -o analyzer
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint32_t bits(float x) { uint32_t u; memcpy(&u,&x,4); return u; }
static float bf16(uint16_t x) { uint32_t u=(uint32_t)x<<16; float f;memcpy(&f,&u,4);return f; }
static int read_items(FILE *f,void *p,size_t size,size_t n) { return fread(p,size,n,f)==n; }
static float reduce8(float *a) {
    float v[8];memcpy(v,a,sizeof(v));
    for(int width=1;width<8;width*=2)
        for(int k=0;k<8;k+=2*width)v[k]=fmaf(v[k+width],1.0f,v[k]);
    return v[0];
}
static float mma_xsum(const float *x,int row,int g,int fm) {
    float v[8],next[8];
    for(int block=0;block<8;block++) {
        float sum=0.0f;
        for(int j=0;j<8;j++)sum=fmaf(x[row*2048+g*64+block*8+j],1.0f,sum);
        v[block]=sum;
    }
    for(int mask=1;mask<=4;mask*=2) {
        for(int block=0;block<8;block++)next[block]=fmaf(v[block^mask],1.0f,v[block]);
        memcpy(v,next,sizeof(v));
    }
    return v[fm];
}
static size_t pidx(int g,int s,int row,int n) {return (size_t)((((g*8+s)*8+row)*16)+n);}
typedef struct {size_t exact,total;double max_abs,sum_sq;} Metrics;
static void observe(Metrics *m,float candidate,float reference) {
    m->exact+=bits(candidate)==bits(reference);m->total++;
    double d=fabs((double)candidate-(double)reference);
    if(d>m->max_abs)m->max_abs=d;m->sum_sq+=d*d;
}
static void report(const char *name,Metrics m) {
    printf("  %-30s bitwise=%zu/%zu max_abs=%.9g rms=%.9g\n",name,m.exact,m.total,m.max_abs,sqrt(m.sum_sq/(double)m.total));
}
int main(int argc,char **argv) {
    if(argc!=2){fprintf(stderr,"usage: %s affine-mma-partials-SHAPE.bin\n",argv[0]);return 2;}
    FILE *f=fopen(argv[1],"rb");if(!f){perror(argv[1]);return 1;}
    uint32_t h[4];if(!read_items(f,h,4,4)||h[0]!=0x33414d4du||h[2]!=2048u||h[3]!=16u||!(h[1]==8192u||h[1]==4096u)){
        fprintf(stderr,"ERROR: invalid dump header\n");return 1;
    }
    size_t in_count=8u*h[2],w_count=16u*(h[2]/8u),sb_count=16u*(h[2]/64u),p_count=32u*8u*8u*16u;
    float *x=calloc(in_count,4),*p=calloc(p_count,4),*ref=calloc(8u*16u,4),*mma=calloc(8u*16u,4);
    uint32_t *w=calloc(w_count,4);uint16_t *sc=calloc(sb_count,2),*bi=calloc(sb_count,2);
    if(!x||!p||!ref||!mma||!w||!sc||!bi)return 1;
    int ok=read_items(f,x,4,in_count)&&read_items(f,w,4,w_count)&&read_items(f,sc,2,sb_count)&&read_items(f,bi,2,sb_count)&&read_items(f,p,4,p_count)&&read_items(f,ref,4,8u*16u)&&read_items(f,mma,4,8u*16u);
    if(!ok||fgetc(f)!=EOF){fprintf(stderr,"ERROR: truncated/trailing dump data\n");return 1;}fclose(f);
    printf("shape=%ux%u first_outputs=16 rows=8\n",h[1],h[2]);
    Metrics asc={0},desc={0},muladd={0},pairwise={0};
    for(int g=0;g<32;g++)for(int s=0;s<8;s++)for(int row=0;row<8;row++)for(int n=0;n<16;n++) {
        float old=s?p[pidx(g,s-1,row,n)]:0.0f;
        float actual=p[pidx(g,s,row,n)];
        float q[8],xscaled[8],products[8],ps=ldexpf(1.0f,-4*s);
        for(int k=0;k<8;k++) {
            q[k]=(float)(w[n*256+g*8+k]&(15u<<(4*s)));
            xscaled[k]=x[row*2048+g*64+k*8+s]*ps;
            products[k]=q[k]*xscaled[k];
        }
        float a=old,d=old,m=old;
        for(int k=0;k<8;k++){a=fmaf(q[k],xscaled[k],a);m+=products[k];}
        for(int k=7;k>=0;k--)d=fmaf(q[k],xscaled[k],d);
        float tree[8];memcpy(tree,products,sizeof(tree));
        float t=fmaf(reduce8(tree),1.0f,old);
        observe(&asc,a,actual);observe(&desc,d,actual);
        observe(&muladd,m,actual);observe(&pairwise,t,actual);
    }
    report("MMA step ascending FMA",asc);
    report("MMA step descending FMA",desc);
    report("MMA step ascending mul+add",muladd);
    report("MMA step pairwise products",pairwise);
    Metrics prod_pairwise={0},prod_sequential={0};
    for(int row=0;row<8;row++)for(int n=0;n<16;n++){
        float lanes[32]={0};
        for(int lane=0;lane<32;lane++)for(int col=lane;col<256;col+=32){
            int g=col/8;float scale=bf16(sc[n*32+g]),bias=bf16(bi[n*32+g]);
            uint32_t packed=w[n*256+col];
            for(int j=0;j<8;j++){
                float xv=x[row*2048+col*8+j];
                float q=(float)((packed>>(4*j))&15u);
                lanes[lane]+=fmaf(q,scale*xv,bias*xv);
            }
        }
        float a[32];memcpy(a,lanes,sizeof(a));
        for(int width=1;width<32;width*=2)for(int k=0;k<32;k+=2*width)a[k]=fmaf(a[k+width],1.0f,a[k]);
        float seq=0;for(int lane=0;lane<32;lane++)seq+=lanes[lane];
        float target=ref[row*16+n];
        observe(&prod_pairwise,a[0],target);observe(&prod_sequential,seq,target);
    }
    report("M1 CPU lanes pairwise",prod_pairwise);
    report("M1 CPU lanes sequential",prod_sequential);
    Metrics base={0},bias_element={0},scale_unfused={0},bias_first={0},group_sequential={0},group_tree={0};
    for(int row=0;row<8;row++)for(int n=0;n<16;n++) {
        float lane_base[8]={0},lane_q[8]={0},lane_unfused[8]={0},lane_bias_first[8]={0};
        float group_contribution[32];
        for(int c=0;c<8;c++)for(int g=c;g<32;g+=8) {
            float pg=p[pidx(g,7,row,n)];
            float scale=bf16(sc[n*32+g]),bias=bf16(bi[n*32+g]);
            float xs=mma_xsum(x,row,g,n%8);
            lane_base[c]=fmaf(bias,xs,fmaf(scale,pg,lane_base[c]));
            lane_q[c]=fmaf(scale,pg,lane_q[c]);
            lane_unfused[c]+=scale*pg+bias*xs;
            lane_bias_first[c]=fmaf(scale,pg,fmaf(bias,xs,lane_bias_first[c]));
            group_contribution[g]=fmaf(bias,xs,scale*pg);
        }
        float base_value=reduce8(lane_base);
        observe(&base,base_value,mma[row*16+n]);
        // Flash-style bias products: visit packed columns in the same lane
        // order as M1 and multiply bias by each individual activation.
        float bias_lanes[32]={0};
        for(int lane=0;lane<32;lane++)for(int col=lane;col<256;col+=32){
            float bias=bf16(bi[n*32+col/8]);
            for(int j=0;j<8;j++){
                volatile float product=bias*x[row*2048+col*8+j];
                bias_lanes[lane]+=product;
            }
        }
        float bias_total[32];memcpy(bias_total,bias_lanes,sizeof(bias_total));
        for(int width=1;width<32;width*=2)
            for(int k=0;k<32;k+=2*width)bias_total[k]=fmaf(bias_total[k+width],1.0f,bias_total[k]);
        observe(&bias_element,reduce8(lane_q)+bias_total[0],ref[row*16+n]);
        observe(&scale_unfused,reduce8(lane_unfused),ref[row*16+n]);
        observe(&bias_first,reduce8(lane_bias_first),ref[row*16+n]);
        float seq=0;for(int g=0;g<32;g++)seq+=group_contribution[g];
        observe(&group_sequential,seq,ref[row*16+n]);
        float tree[32];memcpy(tree,group_contribution,sizeof(tree));
        for(int width=1;width<32;width*=2)
            for(int k=0;k<32;k+=2*width)tree[k]=fmaf(tree[k+width],1.0f,tree[k]);
        observe(&group_tree,tree[0],ref[row*16+n]);
    }
    report("reconstructed M8 vs GPU M8",base);
    report("MMA q*x + elementwise bias",bias_element);
    report("unfused scale/group terms",scale_unfused);
    report("bias before scaled P",bias_first);
    report("group partials sequential",group_sequential);
    report("group partials pairwise tree",group_tree);
    return base.exact==base.total?0:1;
}
