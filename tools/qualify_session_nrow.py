#!/usr/bin/env python3
"""Sequential bounded HTTP + matched-token numerical N128 qualification.
Raw token artifacts are private. Use a fresh --out in Drive. Never touches 11241.
"""
import argparse,json,pathlib,subprocess,sys
P=pathlib.Path

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=P,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 scripts=P(__file__).resolve().parent;summary=[]
 for name,case,words,starts in [('threshold-scalar','implicit',98,[]),('minimum-batch','implicit',99,[13]),('batch-tail-eos','implicit',128,[13]),('two-slabs','implicit',227,[13,141]),('explicit-zero','explicit',128,[0])]:
  http=a.out/(name+'-http');cmd=[sys.executable,str(scripts/'run_session_state_mission.py'),'--nrow','--words',str(words),'--case',case,'--out',str(http)]
  if not starts:cmd+=['--allow-scalar-only']
  print('HTTP_CASE',name,flush=True)
  with (a.out/(name+'-driver.log')).open('w') as f:r=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
  result=json.loads((http/'result.json').read_text());summary.append({'case':name,'http':result})
  (a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
  if r.returncode not in (0,3) or (not starts and r.returncode!=0):return r.returncode or 3
  assert [x['start'] for x in result['batch_endpoints']]==starts,result['batch_endpoints']
  if starts:
   oracle=a.out/(name+'-oracle');cmd=[sys.executable,str(scripts/'run_session_nrow_oracle.py'),'--history',str(http/'http-records.json'),'--starts',','.join(map(str,starts)),'--out',str(oracle)]
   with (a.out/(name+'-oracle-driver.log')).open('w') as f:r=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
   if (oracle/'nrow-oracle.json').exists():summary[-1]['oracle']=json.loads((oracle/'nrow-oracle.json').read_text())
   (a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
   print('NUMERIC_CASE',name,'exit',r.returncode,flush=True)
   if r.returncode:return r.returncode
 print('N128_MATRIX_PASS',flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
