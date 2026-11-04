#include <metal_stdlib>
using namespace metal;
// Diagnostic replay only. Rounded products are counterfactual intermediates;
// accumulation uses explicit FMA, validated against the unchanged scalar kernel.
kernel void fe027_combine_trace(device const float *data [[buffer(0)]],
    device float *trace [[buffer(1)]],constant uint &dim [[buffer(2)]],
    uint i [[thread_position_in_grid]]) {
    if(i>=dim)return;
    device const float *params=data+11*dim;
    float sum=0;
    for(uint k=0;k<8;k++) {
        float x=data[(2+k)*dim+i];
        trace[k*dim+i]=params[k]*x;
        sum=fma(params[k],x,sum);
        trace[(8+k)*dim+i]=sum;
    }
    float gate=1.0f/(1.0f+exp(-params[8]));
    trace[16*dim+i]=gate;
    trace[17*dim+i]=gate*data[dim+i];
    trace[18*dim+i]=data[i]+sum;
    trace[19*dim+i]=fma(gate,data[dim+i],data[i]+sum);
}
