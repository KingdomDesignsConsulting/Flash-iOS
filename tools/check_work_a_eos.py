#!/usr/bin/env python3
"""Read-only EOS/continuation audit of completed private Work A profile traces."""
import argparse,hashlib,json,pathlib,re
P=pathlib.Path

def audit(root):
 result=dict(status='PASS',scope='Saved first three capture/restart turns; no new inference',stages={})
 for stage in ['capture','restart']:
  directory=root/stage/'trace';found={}
  for path in directory.iterdir():
   if not path.name.endswith('-generated.json'):continue
   g=json.loads(path.read_text());request=int(g['request_id'].rsplit('-',1)[1])
   if request not in [1,2,3]:continue
   state_path=directory/(path.name[:-15]+'-state.json');s=json.loads(state_path.read_text())
   assert s['accepted'] and s['history_complete'] and not s['failed']
   assert g['session_reusable'] and not g['request_state_failed'] and g['ended_with_eos']
   assert g['completed_token_ids'] and g['completed_token_ids'][-1]==g['ended_with_eos']==s['effective_token_ids'][-1]
   assert g['end_pos']==s['end_position']==len(s['effective_token_ids'])
   assert all(x['kv_lengths_match'] and not any(y['nonfinite'] for y in x['components']) for x in s['steps'])
   assert len(g['completed_positions'])==len(g['completed_token_ids'])
   found[request]=dict(initial_position=s['initial_position'],end_position=s['end_position'],eos_committed=True,completed_tokens=len(g['completed_token_ids']),last_digest=s['steps'][-1]['digest'],generated_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),state_sha256=hashlib.sha256(state_path.read_bytes()).hexdigest())
  assert sorted(found)==[1,2,3]
  rows=[found[i] for i in [1,2,3]]
  if stage=='capture':assert rows[0]['initial_position']==0
  else:
   restored=re.findall(r'valid snapshot: format=\S+ tokens=(\d+)',(root/stage/'server.log').read_text());assert len(restored)==1 and rows[0]['initial_position']==int(restored[0])>0
  assert all(b['initial_position']==a['end_position'] for a,b in zip(rows,rows[1:]))
  result['stages'][stage]=rows
 assert [x['last_digest'] for x in result['stages']['capture']]==[x['last_digest'] for x in result['stages']['restart']]
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile-root',required=True,type=P);p.add_argument('--out',required=True,type=P);a=p.parse_args();d=audit(a.profile_root)
 with a.out.open('x') as f:json.dump(d,f,indent=2);f.write('\n')
 print('EOS_CONTINUATION',d['status'],[x['end_position'] for x in d['stages']['capture']])
if __name__=='__main__':main()
