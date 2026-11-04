#!/usr/bin/env python3
"""Run the six independent, complete native-rendered histories sequentially.
Large histories are deliberately reserved for qualify_release_long.py.
"""
import argparse,json,os,pathlib,subprocess,sys
from run_session_state_mission import stamp,sha
P=pathlib.Path

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',required=True,type=P);p.add_argument('--corpus',required=True,type=P);p.add_argument('--out',required=True,type=P);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);repo=P(__file__).resolve().parents[1]
 cases=[x for x in json.loads(a.corpus.read_text())['cases'] if x['count']<4096];assert len(cases)==6
 fingerprint=sha(a.binary);report=dict(status='RUNNING',started=stamp(),binary_sha256=fingerprint,cases=[])
 for c in cases:
  assert sha(a.binary)==fingerprint and sha(P(c['fixture']))==c['fixture_sha256'],'Build/fixture changed during qualification'
  cmd=[sys.executable,str(repo/'tools/qualify_session_accumulation.py'),'--binary',str(a.binary.resolve()),'--fixture',c['fixture'],'--count',str(c['count']),'--numerics','63','--gpu-wait','60','--timeout','1200','--max-rss-gib','16','--out',str(a.out/c['name'])]
  if c['count']%128==0:cmd+=['--full-final-slab']
  print('HISTORY_START',stamp(),c['name'],'COMMAND',json.dumps(cmd),flush=True)
  with (a.out/(c['name']+'-driver.log')).open('w') as log:r=subprocess.run(cmd,cwd=repo,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=1400)
  entry=dict(name=c['name'],command=cmd,exit=r.returncode,fixture_sha256=c['fixture_sha256']);report['cases'].append(entry)
  if r.returncode:report['status']='STOPPED';break
  native=json.loads((a.out/c['name']/'nrow-oracle.json').read_text())
  if not native['rows'] or not all(x.get('candidate_digest') and x['candidate_digest']==x.get('reference_digest') for x in native['rows']):
   entry['exact_fingerprint_failure']=True;report['status']='STOPPED';break
  (a.out/'suite.json').write_text(json.dumps(report,indent=2)+'\n');print('HISTORY_STOP',stamp(),c['name'],'exit',r.returncode,flush=True)
 else:report['status']='PASS'
 report['ended']=stamp();(a.out/'suite.json').write_text(json.dumps(report,indent=2)+'\n');return 0 if report['status']=='PASS' else 3
if __name__=='__main__':raise SystemExit(main())
