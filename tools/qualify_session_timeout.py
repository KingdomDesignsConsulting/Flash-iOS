#!/usr/bin/env python3
"""Real client receive timeout during streaming prefill; compare exact recovery."""
import argparse,socket,struct,uuid
from session_gate_support import *
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=P,required=True);p.add_argument('--reference',type=P,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 reference=load(a.reference);expected={r['position']:r['digest'] for r in reference['steps']}
 with server(a.out/'server') as s:
  sid='timeout-'+uuid.uuid4().hex;b=body([{'role':'user','content':' x'*128+' Write a long list.'}],sid,True);b['stream']=True;b['max_tokens']=128
  data=json.dumps(b).encode();sock=socket.create_connection(('127.0.0.1',11243));sock.settimeout(.05)
  sock.sendall(b'POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: '+str(len(data)).encode()+b'\r\n\r\n'+data)
  timed_out=False
  try:
   while sock.recv(4096):pass
  except socket.timeout:timed_out=True
  finally:sock.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack('ii',1,0));sock.close()
  assert timed_out
  failed=state(s,b);assert failed['failed'] and not failed['accepted'] and failed['end_position']==0
  status,reply=call(body([FOLLOW],sid));assert status==409
  fresh='recover-'+uuid.uuid4().hex;final=None
  for n,msgs in enumerate([[USER],[FOLLOW]]):
   req=body(msgs,fresh,n==0);status,reply=call(req);assert status==200
   final=state(s,req)
   for row in final['steps']:assert expected[row['position']]==row['digest']
  assert final['effective_token_ids']==reference['effective_token_ids']
 write(a.out/'result.json',dict(status='PASS',client_timeout_ms=50,stream=True,session_invalidated=True,stale_status=409,recovery_exact=True,method='Real socket receive deadline followed by TCP RST; not a server-compute timeout injection'))
 return 0
if __name__=='__main__':raise SystemExit(main())
