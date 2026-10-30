#!/usr/bin/env python3
"""Isolated live restart/replay test for hardened Flash-iOS.

Only manages the server process this script starts. Requires a free dedicated
port and an already-built hardened experimental binary. Never touches 11241.
"""
import argparse,json,os,pathlib,signal,socket,subprocess,time,urllib.error,urllib.request,uuid

def open_port(port):
    with socket.socket() as s:
        s.settimeout(.3)
        return s.connect_ex(("127.0.0.1",port))==0

def send(port,messages,sid=None,create=False):
    data={"model":"qwen3.5","messages":messages,"stream":False,
          "max_tokens":70,"temperature":0,"reasoning_effort":"off"}
    if sid: data["session_id"]=sid
    if create: data["flash_session_create"]=True
    req=urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
         json.dumps(data).encode(),{"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=300) as resp:
            status=resp.status;body=json.load(resp)
    except urllib.error.HTTPError as e:
        status=e.code;body=json.loads(e.read())
    return {"status":status,"body":body}

def answer(result):
    return result["body"].get("choices",[{}])[0].get("message",{}).get("content","")

def start(binary,model,port,logpath):
    f=open(logpath,"w")
    p=subprocess.Popen([str(binary),"--model",str(model),"--tiered",
                        "--serve",str(port),"--prefill-nrow"],
                        stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    for _ in range(360):
        if p.poll() is not None:
            f.close();raise RuntimeError(f"server failed: {logpath}")
        if open_port(port):return p,f
        time.sleep(.5)
    stop(p,f)
    raise TimeoutError(f"server did not listen: {logpath}")

def stop(p,f):
    try:
        if p.poll() is None:
            os.killpg(p.pid,signal.SIGTERM)
            try:p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=10)
    finally:f.close()
    for _ in range(60):
        if not open_port(PORT):return
        time.sleep(.2)
    raise RuntimeError("test port remained occupied after shutdown")

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--binary",required=True,type=pathlib.Path)
    a.add_argument("--model",required=True,type=pathlib.Path)
    a.add_argument("--port",type=int,default=11243)
    a.add_argument("--out",default="Testing/HTTP-Prefix-Reuse/restart-recovery.json")
    args=a.parse_args()
    global PORT
    PORT=args.port
    binary=args.binary.expanduser().resolve()
    model=args.model.expanduser().resolve()
    if args.port==11241 or open_port(args.port):a.error("dedicated test port must be free and not 11241")
    if not binary.is_file() or not os.access(binary,os.X_OK):a.error("binary not executable")
    if not model.is_dir():a.error("model not found")
    output=pathlib.Path(args.out).expanduser().resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    sentinel="RESTART-"+uuid.uuid4().hex[:12].upper()
    sid="restart-"+uuid.uuid4().hex
    initial={"role":"user","content":f"Remember identifier {sentinel}. Acknowledge in a short sentence."}
    follow={"role":"user","content":"What is the identifier given earlier? Answer with only the identifier."}
    results={"sentinel":sentinel,"session_id":sid,"steps":{}}
    def persist(): output.write_text(json.dumps(results,indent=2)+"\n")
    p,f=start(binary,model,args.port,output.with_name(output.stem+"-before.log"))
    try:
        first=send(args.port,[initial],sid,create=True)
        second=send(args.port,[follow],sid)
        results["steps"]["initial"]=first
        results["steps"]["continuation"]=second
    finally:stop(p,f)
    persist()
    p,f=start(binary,model,args.port,output.with_name(output.stem+"-after.log"))
    try:
        stale=send(args.port,[follow],sid)
        # Safe recovery from client's retained full transcript uses NEW session id.
        replay=send(args.port,[initial,{"role":"assistant","content":answer(first)},follow],
                    sid+"-replay",create=True)
        result={"stale_after_restart":stale,"replay_new_session":replay}
        results["steps"].update(result)
        flags=stale["body"]
        results["checks"]={
            "initial_created":first["status"]==200,
            "prior_session_reused":second["status"]==200 and
                second["body"].get("flash_timings",{}).get("session_reused")==1,
            "prior_context_retained":sentinel in answer(second),
            "stale_after_restart_rejected":stale["status"]==409 and
                flags.get("session_invalidated") is True and
                flags.get("resend_full_history") is True,
            "new_session_replay_recovers_code":replay["status"]==200 and
                sentinel in answer(replay),
        }
        results["passed"]=all(results["checks"].values())
    finally:stop(p,f);persist()
    print(json.dumps({"checks":results["checks"],"passed":results["passed"],
                      "output":str(output)},indent=2))
    return 0 if results["passed"] else 2

if __name__=="__main__":
    raise SystemExit(main())
