#!/usr/bin/env python3
"""Extract unchanged candidate kernels, build standalone bounded Metal probe, gate GPU."""
import argparse,pathlib,hashlib,subprocess,json,time
R=pathlib.Path(__file__).resolve().parents[1]
def kernel(s,name):
 a=s.index('kernel void '+name+'(');i=s.index('{',a)+1;depth=1
 while depth:depth+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[a:i]
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 s=(R/'metal_infer/shaders.metal').read_text();c=(R/'metal_infer/prefill_probe/chunk_kernels.metal').read_text();chunk=c[:c.index('// Keep the production QKV layout')]
 source=chunk+'\ninline float bf16_to_f32(ushort v){return as_type<float>(uint(v)<<16);}\n'+'\n'.join(kernel(s,n) for n in ['dequant_matvec_4bit_fast','compute_decay_beta','gated_delta_net_step'])
 src=a.out/'kernels.metal';src.write_text(source);binary=a.out/'probe'
 subprocess.run(['clang','-O2','-fobjc-arc','-framework','Foundation','-framework','Metal',str(R/'tools/gdn_shape_probe/probe.m'),'-o',str(binary)],check=True)
 from run_session_state_mission import gpu
 readings=[]
 for _ in range(3):readings.append(gpu());time.sleep(1)
 meta=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),source_sha256={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [R/'metal_infer/shaders.metal',R/'metal_infer/prefill_probe/chunk_kernels.metal',R/'tools/gdn_shape_probe/probe.m']},kernel_sha256=hashlib.sha256(source.encode()).hexdigest(),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),gpu_before=readings)
 if any(x is None or x>=30 for x in readings):meta.update(status='BLOCKED_GPU');(a.out/'build.json').write_text(json.dumps(meta,indent=2));return 2
 with (a.out/'probe.log').open('w') as log:
  run=subprocess.run([str(binary),str(src),str(a.out/'result.json')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=90)
 code=run.returncode
 if code==0:
  try:
   result=json.loads((a.out/'result.json').read_text())
   if result['status']!='PASS' or len(result['cases'])!=24 or not all(x['pass'] for x in result['cases']):raise ValueError('incomplete component evidence')
  except Exception as e:meta['evidence_error']=str(e);code=3
 meta.update(exit=code,status='PASS' if code==0 else 'FAIL');(a.out/'build.json').write_text(json.dumps(meta,indent=2)+'\n');print(meta);return code
if __name__=='__main__':raise SystemExit(main())
