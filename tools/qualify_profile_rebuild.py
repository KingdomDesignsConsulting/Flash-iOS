#!/usr/bin/env python3
"""Prove an unrelated executable rebuild preserves a compatible test profile."""
import argparse
from session_gate_support import *
from qualify_named_profile_http import conversation

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--previous',type=P,required=True);p.add_argument('--out',type=P,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 profile=load(a.previous/'result.json')['profile'];assert profile.startswith('qual-')
 launch=load(a.previous/'capture/launch.json');prior=launch['binary_sha256'];now=sha(BINARY);assert prior!=now,'This test requires a rebuilt executable'
 args=launch['command'][launch['command'].index('11243')+1:];assert all(x in ['--cpu-linear','--no-cmd12-chain','--no-cmd12-full-chain'] for x in args)
 paths=sorted((a.previous/'capture/trace').glob('*-state.json'),key=lambda p:p.stat().st_mtime_ns);baseline=[load(p) for p in paths];assert len(baseline)==2
 with server(a.out/'server',a.previous/'cache',args=[*args,'--flash-profile',profile]) as s:
  _,records=conversation(s,profile)
  for x,y in zip(baseline,records):equal(x,y)
  assert 'valid snapshot:' in (s['out']/'server.log').read_text()
 write(a.out/'result.json',dict(status='PASS',different_executable_sha256=True,prior_binary_sha256=prior,current_binary_sha256=now,compatible_disk_restore=True,state_exact=True,checkpoint_rebuilt=False))
 return 0
if __name__=='__main__':raise SystemExit(main())
