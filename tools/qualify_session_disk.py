#!/usr/bin/env python3
"""Native Zstd warm-state save/restart/load and exact continuation comparison."""
import argparse,json,os,pathlib,subprocess,time
from run_session_state_mission import gpu,stamp,MODEL,sha
P=pathlib.Path

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--history',required=True,type=P);p.add_argument('--out',required=True,type=P);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 repo=P(__file__).resolve().parents[1];binary=repo/'metal_infer/infer-session-state-experiment';ids=json.loads(a.history.read_text())['traces'][-1]['state']['effective_token_ids'];assert 141<len(ids)<=512
 checkpoint=a.out/'checkpoint';checkpoint.mkdir();path=checkpoint/'flash-diagnostic-0000000000000000.state';commands=[];gates=[]
 for mode in ['save','load']:
  phase=a.out/mode;phase.mkdir();inputfile=phase/'input.json';inputfile.write_text(json.dumps(dict(mode=mode,token_ids=ids,prefix=141,batch_starts=[13],checkpoint=str(path))))
  stable=0;readings=[]
  for _ in range(10):
   g=gpu();readings.append(g);stable=stable+1 if g is not None and g<30 else 0
   if stable==3:break
   time.sleep(1)
  gates.append(readings)
  if stable<3:(a.out/'result.json').write_text(json.dumps({'status':'GPU_GATE_NOT_RUN','phase':mode,'pre_gpu':gates}));return 4
  assert not subprocess.run(['lsof','-t','-nP','-iTCP:11243','-sTCP:LISTEN'],capture_output=True).stdout
  command=[str(binary),'--model',MODEL,'--tiered','--prefill-nrow'];commands.append(command)
  env=dict(os.environ,FLASH_SESSION_TOKEN_TRACE_DIR=str(phase),FLASH_SESSION_DISK_INPUT=str(inputfile));print('DISK_'+mode.upper()+'_START',stamp(),flush=True)
  with (phase/'engine.log').open('w') as f:r=subprocess.run(command,cwd=binary.parent,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=240)
  print('DISK_'+mode.upper()+'_STOP',stamp(),'exit',r.returncode,flush=True)
  if r.returncode:return r.returncode
 save=json.loads((a.out/'save/disk-save.json').read_text());load=json.loads((a.out/'load/disk-load.json').read_text())
 assert save['status']==load['status']=='PASS' and save['compatibility']==load['compatibility'] and save['prefix_signature']==load['prefix_signature']
 assert len(save['rows'])==len(load['rows'])
 for x,y in zip(save['rows'],load['rows']):
  assert x['position']==y['position'] and x['kv_lengths_match'] and y['kv_lengths_match']
  assert x['digest']==y['digest'],('state mismatch',x['position'])
  assert not any(c['nonfinite'] for c in x['components']+y['components'])
 result=dict(status='EXACT_RESTART_PASS',prefix=141,end_position=len(ids),positions_compared=len(save['rows']),checkpoint=save['checkpoint'],checkpoint_bytes=save['checkpoint_bytes'],save_ms=save['transfer_ms'],restore_ms=load['transfer_ms'],wrong_prefix_and_mode_rejected=True,commands=commands,pre_gpu=gates,binary_sha256=sha(binary),source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip())
 (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
