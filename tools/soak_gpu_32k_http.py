#!/usr/bin/env python3
"""Native-Mac opt-in HTTP smoke/soak for Flash 32K. Never touches production infer.
Runs sequentially with the standard expert cache/prefetch enabled. Saves logs and JSON.
"""
import argparse, hashlib, json, os, pathlib, signal, socket, subprocess, time, urllib.request, urllib.error
P=pathlib.Path
MODEL="/Users/Shared/Main Hard Drive/AI Storage/AI Models/Reasoning/alexintosh/Qwen3.5-35B-A3B-Q4-Tiered-FlashMoE"
def sha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1048576),b""):h.update(b)
 return h.hexdigest()
def request(url,payload=None,timeout=25):
 data=None if payload is None else json.dumps(payload).encode()
 req=urllib.request.Request(url,data=data,headers={"Content-Type":"application/json"})
 with urllib.request.urlopen(req,timeout=timeout) as r:
  return r.status,json.loads(r.read())
def free_port():
 with socket.socket() as s:s.bind(("127.0.0.1",0));return s.getsockname()[1]
def rss_kb(pid):
 try:return int(subprocess.check_output(["ps","-o","rss=","-p",str(pid)],text=True).strip())
 except (ValueError,subprocess.CalledProcessError):return None
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--repo",type=P,default=P(__file__).resolve().parents[1])
 ap.add_argument("--out",required=True,type=P)
 ap.add_argument("--model",default=MODEL)
 ap.add_argument("--rounds",type=int,default=3)
 ap.add_argument("--timeout",type=int,default=180)
 ap.add_argument("--startup-timeout",type=int,default=90)
 ap.add_argument("--build",action="store_true")
 a=ap.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 result={"head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=a.repo,text=True).strip(),"model":a.model,"rounds":[],"status":"INCOMPLETE"}
 (out/"report.json").write_text(json.dumps(result,indent=2))
 if a.build:
  subprocess.run(["make","-C","metal_infer","lazy16k-experiment","lazy32k-experiment"],cwd=a.repo,check=True,stdout=(out/"build.log").open("w"),stderr=subprocess.STDOUT)
 for arm in ("lazy16k","lazy32k"):
  binary=a.repo/"metal_infer"/("infer-"+arm+"-experiment")
  assert binary.is_file(),f"Missing {binary}; rerun with --build"
  result.setdefault("binaries",{})[arm]=sha(binary)
  port=free_port()
  command=[str(binary),"--model",a.model,"--serve",str(port)]
  log=(out/(arm+".log")).open("w")
  proc=subprocess.Popen(command,cwd=a.repo/"metal_infer",stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  arm_result={"arm":arm,"pid":proc.pid,"command":command,"requests":[],"rss_kb":[]}
  result["rounds"].append(arm_result)
  try:
   deadline=time.monotonic()+a.startup_timeout
   while time.monotonic()<deadline:
    if proc.poll() is not None:raise RuntimeError(f"{arm} terminated during startup: {proc.returncode}")
    try:
     status,health=request(f"http://127.0.0.1:{port}/health",timeout=2)
     if status==200:break
    except (OSError,ValueError):pass
    time.sleep(0.5)
   else:raise TimeoutError(f"{arm} startup timeout")
   for roundno in range(a.rounds):
    for label,prompt in (("A","Give one brief fact about gravity."),("B","Explain why a bicycle stays balanced when moving."),("A","Give one brief fact about gravity.")):
     payload={"model":"qwen3.5","messages":[{"role":"system","content":"Answer in one short sentence."},{"role":"user","content":prompt}],"max_tokens":12,"temperature":0,"reasoning_effort":"off","stream":False}
     start=time.monotonic()
     status,body=request(f"http://127.0.0.1:{port}/v1/chat/completions",payload,timeout=a.timeout)
     elapsed=time.monotonic()-start
     if status!=200 or "choices" not in body or not body["choices"]:raise RuntimeError(f"{arm}/{label} invalid HTTP result: {body}")
     choice=body["choices"][0];msg=choice.get("message",{})
     text=msg.get("content","")
     if not isinstance(text,str):raise RuntimeError(f"{arm}/{label} non-string completion")
     digest=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
     row={"round":roundno,"case":label,"elapsed_s":round(elapsed,3),"content":text,"body_sha256":digest,"usage":body.get("usage"),"rss_kb":rss_kb(proc.pid)}
     arm_result["requests"].append(row)
     arm_result["rss_kb"].append(row["rss_kb"])
     print(arm,label,roundno,round(elapsed,2),"s",repr(text[:90]),flush=True)
   # Determinism within each arm; A appears twice in each round.
   a_texts=[r["content"] for r in arm_result["requests"] if r["case"]=="A"]
   if len(set(a_texts))!=1:raise RuntimeError(f"{arm} A/B/A non-deterministic: {a_texts}")
   arm_result["status"]="PASS"
  except Exception as exc:
   arm_result["status"]="FAIL";arm_result["error"]=str(exc)
   result["status"]="FAIL"
   raise
  finally:
   if proc.poll() is None:
    os.killpg(proc.pid,signal.SIGTERM)
    try:proc.wait(timeout=12)
    except subprocess.TimeoutExpired:
     os.killpg(proc.pid,signal.SIGKILL);proc.wait()
   arm_result["exit_after_signal"]=proc.returncode;log.close()
   (out/"report.json").write_text(json.dumps(result,indent=2))
 arms=result["rounds"]
 # Token equality across arms requires same deterministic outputs, not response IDs.
 for case in ("A","B"):
  l=[r["content"] for r in arms[0]["requests"] if r["case"]==case]
  r=[r["content"] for r in arms[1]["requests"] if r["case"]==case]
  if l!=r:result["status"]="FAIL";result.setdefault("errors",[]).append(f"content mismatch case {case}")
 if result["status"]!="FAIL":result["status"]="PASS"
 (out/"report.json").write_text(json.dumps(result,indent=2))
 print(result["status"],out)
 if result["status"]!="PASS":raise SystemExit(1)
if __name__=="__main__":main()
