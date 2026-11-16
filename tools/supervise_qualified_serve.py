#!/usr/bin/env python3
"""Opt-in candidate-only supervisor. Never inventories/kills unrelated processes."""
import argparse,fcntl,json,math,os,pathlib,signal,stat,subprocess,threading,time
GIB=1024**3
HOST_MIN=6*GIB
RSS_MAX=16*GIB
LOCK=pathlib.Path('/private/tmp')/f'flash-ios-qualified-model-{os.getuid()}.lock'
def telemetry(probe,pid):
    result=subprocess.run([str(probe),str(pid)],capture_output=True,text=True,timeout=3,check=True)
    data=json.loads(result.stdout)
    for k in ['host_available_bytes','rss_bytes','start_abstime']:
        if type(data.get(k)) is not int or data[k]<0:raise ValueError('invalid '+k)
    if pid and not data['start_abstime']:raise ValueError('missing process birth identity')
    return data

def supervise(command,env,out,sample,*,interval=0.5,max_seconds=21600,lock_path=LOCK,stop=None):
    """sample(pid) injection exists for no-model tests, never a CLI bypass."""
    if not math.isfinite(interval) or not 0.05<=interval<=1:raise ValueError('interval must be0.05..1s')
    if not math.isfinite(max_seconds) or not 0<max_seconds<=21600:raise ValueError('invalid lifetime')
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=False)
    report=dict(status='BLOCKED',model_started=False,command=command,started=time.time(),samples=0)
    child=None;lockfd=None;stop=stop or threading.Event()
    def save():
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    try:
        lockfd=os.open(lock_path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        info=os.fstat(lockfd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid():raise ValueError('unsafe lock owner/type')
        fcntl.flock(lockfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        first=sample(0)
        if first['host_available_bytes']<HOST_MIN:raise ValueError('prelaunch host reserve')
        report['prelaunch']=first
        # The child inherits the same lock: parent death does not release it
        # while the model is still alive. The supervisor never unlinks the lock.
        with (out/'child.log').open('x') as log,(out/'telemetry.jsonl').open('x') as trace:
            child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                                   env=env,start_new_session=True,pass_fds=(lockfd,))
            report.update(model_started=True,pid=child.pid,status='RUNNING');save()
            begin=time.monotonic();birth=None
            while child.poll() is None:
                if stop.is_set():report['stop_reason']='operator_cancel';break
                if time.monotonic()-begin>=max_seconds:report['stop_reason']='lifetime_deadline';break
                try:
                    data=sample(child.pid)
                    if birth is None:birth=data['start_abstime']
                    if birth!=data['start_abstime']:raise ValueError('child identity changed')
                    trace.write(json.dumps(dict(at=time.time(),**data))+'\n');trace.flush();report['samples']+=1
                    if data['host_available_bytes']<HOST_MIN:report['stop_reason']='host_reserve';break
                    if data['rss_bytes']>=RSS_MAX:report['stop_reason']='process_rss';break
                except Exception as e:
                    if child.poll() is not None:break
                    report['stop_reason']='telemetry_unavailable';report['detail']=str(e);break
                stop.wait(interval)
            if child.poll() is None:
                # Only our Popen child/new process group. No discovery or takeover.
                try:os.killpg(child.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:os.killpg(child.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    child.wait(timeout=3)
            report['exit']=child.returncode
            report['status']='STOPPED' if report.get('stop_reason') else ('EXITED' if child.returncode==0 else 'CHILD_FAILED')
    except Exception as e:
        report['detail']=str(e)
        if child is not None and child.poll() is None:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait(timeout=3)
    finally:
        report['ended']=time.time();save()
        if lockfd is not None:os.close(lockfd)
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=pathlib.Path,required=True);p.add_argument('--model',required=True)
    p.add_argument('--probe',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True)
    p.add_argument('--port',type=int,default=11248);p.add_argument('--max-seconds',type=float,default=21600)
    p.add_argument('--operator-exclusive-model',action='store_true');p.add_argument('engine_args',nargs=argparse.REMAINDER)
    a=p.parse_args();root=pathlib.Path(__file__).resolve().parents[1]
    if not a.operator_exclusive_model:p.error('operator must confirm no other heavyweight model; no process inventory is performed')
    if not 1024<=a.port<=65535 or a.port==11241:p.error('isolated non-production port required')
    binary=a.binary.resolve();probe=a.probe.resolve()
    if binary.parent!=(root/'metal_infer').resolve() or binary.name=='infer':p.error('separately named candidate binary in this isolated checkout required')
    if not binary.is_file() or not probe.is_file():p.error('build candidate and probe first')
    args=a.engine_args[1:] if a.engine_args[:1]==['--'] else a.engine_args
    if any(x.startswith('--serve') or x.startswith('-s') for x in args):p.error('server port is owned by supervisor')
    env=os.environ.copy();env['FLASH_SERVE_QUALIFIED_GPU_ONLY']='1';env['FLASH_FE027_NUMERICS']='63'
    # Existing safeguard: three low GPU samples before any model launch.
    from run_session_state_mission import gpu
    readings=[gpu() for _ in range(3)]
    if any(x is None or x>=30 for x in readings):p.error('GPU admission unavailable: '+str(readings))
    stop=threading.Event()
    for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,lambda *_:stop.set())
    report=supervise([str(binary),'--model',a.model,'--tiered','--prefill-nrow','--serve',str(a.port),*args],env,a.out,
        lambda pid:telemetry(probe,pid),max_seconds=a.max_seconds,stop=stop)
    print(json.dumps(report,indent=2))
    return 0 if report['status']=='EXITED' else 1
if __name__=='__main__':raise SystemExit(main())
