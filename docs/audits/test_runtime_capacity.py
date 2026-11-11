#!/usr/bin/env python3
"""Compile actual candidate admission function with synthetic capacities, no model."""
import pathlib,subprocess,tempfile,json
root=pathlib.Path(__file__).resolve().parents[2];s=(root/'metal_infer/infer.m').read_text();a=s.index('static int context_preflight(');b=s.index('static float *s_cpu_attn_scores',a)
cases=[(65536,0,32768,1,1),(65536,32768,1,1,1),(65536,0,65535,1,1),(65536,0,65536,1,0),(65536,2147483647,2147483647,2147483647,0),(65536,-1,1,1,0),(32768,0,32767,1,1),(32768,0,32768,1,0)]
code='#include <stdio.h>\nstatic int g_kv_seq_len;\n'+s[a:b]+'\nint main(){\n'
for cap,pos,inp,gen,expected in cases:code+=f'g_kv_seq_len={cap}; if(context_preflight("audit",{pos},{inp},{gen})!={expected})return 1;\n'
code+='return 0;}\n'
with tempfile.TemporaryDirectory(prefix='mask63-capacity-') as d:
 p=pathlib.Path(d);(p/'test.c').write_text(code);subprocess.run(['clang','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],check=True);subprocess.run([str(p/'test')],check=True,capture_output=True)
r=dict(status='PASS',cases=[dict(capacity=c,position=p,input=i,generation=g,accepted=bool(e)) for c,p,i,g,e in cases],conclusion='Native allocation admission is enforced; 32769 is accepted under service default 65536. This is not a buffer overflow; it exceeds the qualified GPU-only release envelope.')
(root/'docs/audits/evidence/capacity.json').write_text(json.dumps(r,indent=2)+'\n');print('PASS: 8 actual-source capacity boundary cases')
