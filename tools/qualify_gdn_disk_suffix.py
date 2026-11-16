#!/usr/bin/env python3
"""New isolated diagnostic checkpoint only: batched prefix, restart, identical scalar suffix."""
import argparse,hashlib,json,os,pathlib,struct,subprocess,sys,time,datetime
R=pathlib.Path(__file__).resolve().parents[1]
def stamp():return datetime.datetime.now().astimezone().isoformat()
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=pathlib.Path);p.add_argument('--checkpoint-root',required=True,type=pathlib.Path);p.add_argument('--fixture',required=True,type=pathlib.Path);p.add_argument('--supervisor-tools',required=True,type=pathlib.Path);p.add_argument('--probe',required=True,type=pathlib.Path);p.add_argument('--operator-exclusive-model',action='store_true');a=p.parse_args()
 if not a.operator_exclusive_model:p.error('exclusive window required')
 a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False);a.checkpoint_root=a.checkpoint_root.resolve();a.checkpoint_root.mkdir(parents=True,exist_ok=False)
 sys.path.insert(0,str(a.supervisor_tools.resolve()));from supervise_qualified_serve import supervise,telemetry
 from run_session_state_mission import MODEL,gpu
 raw=a.fixture.read_bytes();ids=list(struct.unpack_from('<257I',raw,4));binary=R/'metal_infer/infer-gdn-shape-128';report=dict(status='INCOMPLETE',started=stamp(),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),fixture_sha256=hashlib.sha256(raw).hexdigest(),runs=[],production_access=False)
 for mode in ['save','load']:
  readings=[];stable=0
  for _ in range(60):
   value=gpu();readings.append(value);stable=stable+1 if value is not None and value<30 else 0
   if stable==3:break
   time.sleep(1)
  if stable<3:report['status']='BLOCKED_GPU';break
  folder=a.out/mode;folder.mkdir();inp=folder/'input.json';inp.write_text(json.dumps(dict(token_ids=ids,prefix=128,batch_starts=[0],mode=mode,checkpoint=str(a.checkpoint_root/'flash-gdn-diagnostic-0000000000000001.state'))));env=os.environ.copy();env.update(FLASH_SESSION_DISK_INPUT=str(inp),FLASH_SESSION_TOKEN_TRACE_DIR=str(folder),FLASH_FE027_NUMERICS='63');env.pop('FLASH_SERVE_QUALIFIED_GPU_ONLY',None)
  print('GDN_DISK_START',stamp(),mode,flush=True);budget=supervise([str(binary),'--model',MODEL,'--tiered','--prefill-nrow'],env,folder/'supervision',lambda pid:telemetry(a.probe,pid),max_seconds=300);print('GDN_DISK_STOP',stamp(),mode,budget.get('exit'),budget.get('stop_reason'),flush=True);report['runs'].append(dict(mode=mode,gpu=readings,budget=budget))
  if budget['status']!='EXITED':report['status']='BLOCKED_OR_FAILED';break
 else:
  saved=json.loads((a.out/'save/disk-save.json').read_text());loaded=json.loads((a.out/'load/disk-load.json').read_text())
  ok=saved['status']==loaded['status']=='PASS' and saved['compatibility']==loaded['compatibility'] and saved['prefix_signature']==loaded['prefix_signature'] and len(saved['rows'])==len(loaded['rows'])==130
  for x,y in zip(saved['rows'],loaded['rows']):
   ok=ok and x['position']==y['position'] and x['digest']==y['digest'] and x['kv_lengths_match'] and y['kv_lengths_match'] and all(not part['nonfinite'] for row in [x,y] for part in row['components'])
  cp=pathlib.Path(saved['checkpoint'])
  if not cp.is_relative_to(a.checkpoint_root):raise RuntimeError('checkpoint escaped isolated directory')
  report.update(status='PASS' if ok else 'FAIL',prefix=128,end=257,matched_positions=len(saved['rows']),checkpoint_bytes=cp.stat().st_size,checkpoint_sha256=hashlib.sha256(cp.read_bytes()).hexdigest(),compatibility=saved['compatibility'],prefix_signature=saved['prefix_signature'],raw_save_sha256=hashlib.sha256((a.out/'save/disk-save.json').read_bytes()).hexdigest(),raw_load_sha256=hashlib.sha256((a.out/'load/disk-load.json').read_bytes()).hexdigest())
 report['ended']=stamp();(a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print('GDN_DISK_RESULT',report['status'],flush=True);return 0 if report['status']=='PASS' else 3
if __name__=='__main__':raise SystemExit(main())
