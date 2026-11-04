#!/usr/bin/env python3
"""Reject a private pre-repair GPU-N128 checkpoint without altering its bytes."""
import argparse
from session_gate_support import *
from qualify_session_accumulation import wait_bounded_process
ACTIVE_OUT=None

def main():
 global ACTIVE_OUT
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',required=True,type=P);p.add_argument('--old-load-input',required=True,type=P);p.add_argument('--old-save-result',required=True,type=P);p.add_argument('--out',required=True,type=P);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);ACTIVE_OUT=a.out
 old=load(a.old_save_result);inp=load(a.old_load_input);assert old['status']=='PASS' and inp['mode']=='load';checkpoint=P(old['checkpoint']);before=sha(checkpoint);source=a.out/'load-input.json';write(source,inp);pre=gate()
 for port in [11241,11243]:assert not subprocess.run(['lsof','-t','-nP',f'-iTCP:{port}','-sTCP:LISTEN'],capture_output=True).stdout,'MODEL_PORT_BUSY_NOT_RUN'
 binary=a.binary.resolve();cmd=[str(binary),'--model',MODEL,'--tiered','--prefill-nrow'];env=dict(os.environ,FLASH_FE027_NUMERICS='63',FLASH_SESSION_TOKEN_TRACE_DIR=str(a.out),FLASH_SESSION_DISK_INPUT=str(source));print('OLD_N128_CACHE_REJECT_START',stamp(),'COMMAND',json.dumps(cmd),flush=True)
 with (a.out/'engine.log').open('w') as log:
  proc=subprocess.Popen(cmd,cwd=binary.parent,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);code,peak,reason=wait_bounded_process(proc,240,16*1024**3,host_free_floor=15)
 print('OLD_N128_CACHE_REJECT_STOP',stamp(),'exit',code,flush=True);report=load(a.out/'disk-load.json');assert code==3 and reason is None and report['status']=='FAIL' and not report['rows'];assert report['compatibility']!=old['compatibility'] and sha(checkpoint)==before;assert 'cache invalid:' in (a.out/'engine.log').read_text()
 write(a.out/'result.json',dict(status='PASS',expected_rejection_exit=code,old_checkpoint_preserved=True,old_checkpoint_sha256=before,old_compatibility=old['compatibility'],new_compatibility=report['compatibility'],new_binary_sha256=sha(binary),pre_gpu=pre,observed_rss_bytes=peak,format_changed=False,global_execution_version=3,selective_marker='nrow-prefetch-ownership-v2'));return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as error:
  if ACTIVE_OUT:write(ACTIVE_OUT/'result.json',dict(status='FAIL',error_type=type(error).__name__,error=str(error)))
  raise
