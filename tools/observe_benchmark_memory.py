#!/usr/bin/env python3
"""Read-only OS footprint sampling for benchmark-owned model children.
Does not start/stop models; charged footprint and RSS are overlapping metrics.
"""
import argparse,datetime,json,pathlib,re,subprocess,time
P=pathlib.Path

def classify_mode(command):
 flags=re.findall(r'(?<!\S)--(?:no-)?prefill-nrow(?!\S)',command)
 return 'candidate' if 'infer-release-prefetch-performance' in command else 'scalar' if flags and flags[-1]=='--no-prefill-nrow' else 'control'

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence-root',type=P,required=True);p.add_argument('--probe',type=P,required=True);p.add_argument('--out',type=P,required=True);p.add_argument('--timeout',type=int,default=7200);a=p.parse_args();assert 1<=a.timeout<=10800;root=a.evidence_root.resolve();deadline=time.monotonic()+a.timeout;count=0
 with a.out.open('x') as out:
  def record(value):out.write(json.dumps(dict(at=datetime.datetime.now().astimezone().isoformat(),**value))+'\n');out.flush()
  record(dict(kind='BEGIN',scope='Only direct native model children of the matching benchmark drivers; no task instrumentation'))
  while time.monotonic()<deadline:
   r=subprocess.run(['ps','-ww','-axo','pid=,ppid=,command='],capture_output=True,text=True,timeout=5);assert r.returncode==0
   processes=[]
   for line in r.stdout.splitlines():
    fields=line.strip().split(None,2)
    if len(fields)==3:processes.append((int(fields[0]),int(fields[1]),fields[2]))
   parents={}
   for pid,ppid,command in processes:
    if 'tools/benchmark_fe027.py' in command and str(root/'performance/') in command:
     match=re.search(r'--count (\d+)',command);parents[pid]='cli-'+match[1] if match else 'cli-unknown'
    elif 'tools/benchmark_release_http.py' in command and str(root/'performance-http') in command:parents[pid]='http'
   for pid,ppid,command in processes:
    if ppid not in parents or ' --model ' not in command:continue
    result=subprocess.run([str(a.probe),str(pid)],capture_output=True,text=True,timeout=5)
    if result.returncode:
     if subprocess.run(['ps','-p',str(pid),'-o','stat='],capture_output=True,text=True,timeout=5).stdout.strip() not in ('','Z'):
      record(dict(kind='PROBE_ERROR',pid=pid,scope=parents[ppid],exit=result.returncode))
     continue
    values=json.loads(result.stdout);assert values['start_abstime']>0
    # Helpers may prepend a default and append its override. CLI parsing uses
    # the final flag; searching for mere presence mislabels ordinary HTTP runs.
    mode=classify_mode(command)
    record(dict(kind='SAMPLE',pid=pid,parent_pid=ppid,scope=parents[ppid],mode=mode,**values));count+=1
   try:suite=json.loads((root/'performance/suite.json').read_text())
   except (OSError,ValueError):suite={}
   if suite.get('status') in ('COMPLETED_EXPLORATORY','STOPPED'):
    record(dict(kind='END',samples=count,reason=suite['status']));return 0
   time.sleep(1)
  record(dict(kind='END',samples=count,reason='OBSERVER_TIMEOUT'));return 4
if __name__=='__main__':raise SystemExit(main())
