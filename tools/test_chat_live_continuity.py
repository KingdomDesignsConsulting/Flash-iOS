#!/usr/bin/env python3
"""Actual terminal binary + isolated server, transcript counts/replay/resume.
A local relay sets one fixed reasoning-off policy, preserving all session fields
and streaming bytes. No model starts/stops, shell tools, or production access.
"""
import argparse,http.server,json,os,pathlib,subprocess,tempfile,threading,time,urllib.request,urllib.error,urllib.parse,uuid
P=pathlib.Path
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--base',default='http://127.0.0.1:11243/v1');ap.add_argument('--binary',type=P,default=P(__file__).resolve().parents[1]/'metal_infer/chat');ap.add_argument('--out',type=P,required=True);a=ap.parse_args()
 u=urllib.parse.urlparse(a.base);assert u.hostname=='127.0.0.1' and u.port!=11241,'Production forbidden'
 records=[]
 class Relay(http.server.BaseHTTPRequestHandler):
  protocol_version='HTTP/1.1'
  def log_message(self,*args):pass
  def do_POST(self):
   body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));body['reasoning_effort']='off'
   req=urllib.request.Request(a.base.rstrip('/')+'/chat/completions',json.dumps(body).encode(),{'Content-Type':'application/json'})
   try:
    try:up=urllib.request.urlopen(req,timeout=300)
    except urllib.error.HTTPError as exc:up=exc
    with up:
     self.send_response(up.status);self.send_header('Content-Type',up.headers.get('Content-Type','application/json'));self.send_header('Connection','close');self.end_headers();raw=b''
     for line in up:raw+=line;self.wfile.write(line);self.wfile.flush()
     records.append(dict(request=body,status=up.status,response=raw.decode()))
   except Exception as exc:records.append(dict(error=type(exc).__name__))
   self.close_connection=True
 relay=http.server.ThreadingHTTPServer(('127.0.0.1',0),Relay);thread=threading.Thread(target=relay.serve_forever,daemon=True);thread.start()
 child=None
 try:
  with tempfile.TemporaryDirectory(prefix='flash-chat-live-') as folder:
   env=dict(os.environ,FLASH_CHAT_STATE_DIR=folder)
   args=[str(a.binary.resolve()),'--port',str(relay.server_address[1]),'--max-tokens','32']
   child=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
   def turn(text,count):
    child.stdin.write((text+'\n').encode());child.stdin.flush();deadline=time.monotonic()+120
    while time.monotonic()<deadline:
     files=list(P(folder).glob('*.jsonl'))
     if files:
      turns=[json.loads(x) for x in files[0].read_text().splitlines()]
      if len(turns)==count:return files[0],turns
     if child.poll() is not None:raise RuntimeError('Native client exited before transcript commit')
     time.sleep(.1)
    raise TimeoutError('Native transcript commit timeout')
   turn('Remember identifier ORBIT-73941. Reply exactly READY.',2)
   _,turns=turn('What identifier? Reply only the identifier.',4);assert turns[-1]['content'].strip()=='ORBIT-73941'
   eviction={'model':'qwen3.5','messages':[{'role':'user','content':'Reply exactly READY.'}],'session_id':'external-'+uuid.uuid4().hex,'flash_session_create':True,'max_tokens':16,'temperature':0,'reasoning_effort':'off'}
   req=urllib.request.Request(a.base.rstrip('/')+'/chat/completions',json.dumps(eviction).encode(),{'Content-Type':'application/json'})
   with urllib.request.urlopen(req,timeout=120) as r:assert r.status==200
   file,turns=turn('Repeat the identifier exactly.',6);assert turns[-1]['content'].strip()=='ORBIT-73941'
   child.stdin.write(b'/quit\n');child.stdin.flush();_,err=child.communicate(timeout=15);assert child.returncode==0 and err.count(b'Session invalidated; replaying')==1,err
   resumed=subprocess.run(args+['--resume',file.stem],input=b'Repeat the identifier exactly.\n/quit\n',capture_output=True,env=env,timeout=120)
   assert resumed.returncode==0,resumed.stderr
   turns=[json.loads(x) for x in file.read_text().splitlines()];assert len(turns)==8 and turns[-1]['content'].strip()=='ORBIT-73941'
   assert [x['role'] for x in turns]==['user','assistant']*4
   assert len(records)==5,records
   assert len(records[0]['request']['messages'])==1 and records[0]['request']['flash_session_create']
   assert len(records[1]['request']['messages'])==1 and not records[1]['request']['flash_session_create']
   assert records[3]['request']['flash_session_create'] and len(records[3]['request']['messages'])==5
   assert records[4]['request']['flash_session_create'] and len(records[4]['request']['messages'])==7
   assert records[3]['request']['session_id']!=records[4]['request']['session_id']
   report=dict(result='PASS',turns=turns,requests=records,automatic_replays=1,server_restarts=0,model_starts=0,shell_tools_executed=False,relay_policy='reasoning_effort off',state_oracle='transcript counts/output, not internal KV')
   a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2));print('LIVE_NATIVE_PASS',a.out)
 finally:
  if child and child.poll() is None:child.terminate();child.wait(timeout=5)
  relay.shutdown();relay.server_close();thread.join()
if __name__=='__main__':main()
