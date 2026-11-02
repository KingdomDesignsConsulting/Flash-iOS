#!/usr/bin/env python3
"""Bounded host-pressure guard for a uniquely identified owned native oracle.
Does not stop unrelated processes or interpret RSS as total unified memory.
"""
import argparse,datetime,json,os,pathlib,re,signal,subprocess,time
P=pathlib.Path
def stamp():return datetime.datetime.now().astimezone().isoformat()
def processes():
 text=subprocess.check_output(['ps','-ww','-axo','pid=,ppid=,args='],text=True,timeout=5)
 return [(int(a),int(b),c) for a,b,c in (line.strip().split(None,2) for line in text.splitlines() if line.strip())]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',required=True,type=P);p.add_argument('--binary',required=True,type=P);p.add_argument('--out',required=True,type=P);p.add_argument('--timeout',type=int,default=10860);p.add_argument('--owner-script',choices=['qualify_session_accumulation.py','qualify_release_long_http.py'],default='qualify_session_accumulation.py');a=p.parse_args();assert not a.out.exists()
 rows=processes();owners=[x for x in rows if 'python' in x[2].split()[0].lower() and len(x[2].split(None,2))>=2 and P(x[2].split(None,2)[1]).name==a.owner_script and (x[2].endswith('--out '+str(a.case.resolve())) or '--out '+str(a.case.resolve())+' ' in x[2])];assert len(owners)==1
 owner=owners[0][0];native=[x for x in rows if x[1]==owner and x[2].startswith(str(a.binary.resolve())+' ')];assert len(native)==1
 pid=native[0][0];assert os.getpgid(pid)==pid
 report=dict(status='RUNNING',started=stamp(),watchdog_pid=owner,native_pid=pid,minimum_host_free_percent=None,samples=0,threshold_percent=15,required_low_samples=3)
 end=time.monotonic()+a.timeout;low=0
 while time.monotonic()<end:
  now=processes();valid=[x for x in now if x[0]==pid and x[1]==owner and x[2].startswith(str(a.binary.resolve())+' ')]
  if not valid:report['status']='MODEL_EXITED';break
  r=subprocess.run(['memory_pressure','-Q'],capture_output=True,text=True,timeout=10);m=re.search(r'free percentage: (\d+)%',r.stdout)
  if r.returncode or not m:report['status']='MONITOR_UNAVAILABLE';break
  free=int(m[1]);report['samples']+=1;old=report['minimum_host_free_percent'];report['minimum_host_free_percent']=free if old is None else min(old,free);report['last_host_free_percent']=free;report['last_sample']=stamp();low=low+1 if free<15 else 0
  if low==3:
   # Revalidate ownership immediately before signalling the process group.
   current=[x for x in processes() if x[0]==pid and x[1]==owner and x[2].startswith(str(a.binary.resolve())+' ')]
   if current and os.getpgid(pid)==pid:os.killpg(pid,signal.SIGTERM);report['status']='GLOBAL_MEMORY_PRESSURE_STOP';report['signal']='SIGTERM to owned native group only'
   else:report['status']='MODEL_EXITED'
   break
  a.out.write_text(json.dumps(report,indent=2)+'\n');time.sleep(10)
 else:report['status']='GUARD_TIMEOUT_NO_SIGNAL'
 report['ended']=stamp();a.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
 return 3 if report['status']=='GLOBAL_MEMORY_PRESSURE_STOP' else 0
if __name__=='__main__':raise SystemExit(main())
