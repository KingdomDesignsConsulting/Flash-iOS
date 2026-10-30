#!/usr/bin/env python3
"""Sequential FE-027 mandatory combine regressions. Private fresh output only.
Stops on first failure; no larger cases or timing work after a numerical failure.
"""
import argparse,json,os,pathlib,subprocess,sys
from run_session_state_mission import stamp
from summarize_fe027_combine import summarize
P=pathlib.Path
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=P,required=True);p.add_argument('--binary',type=P,required=True);p.add_argument('--history',type=P,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False);repo=P(__file__).resolve().parents[1];binary=a.binary.resolve();summary=dict(started=stamp(),mask=63,cases=[],status='INCOMPLETE')
    def save(): (a.out/'suite.json').write_text(json.dumps(summary,indent=2)+'\n')
    def run(name,args,combine=False):
        cmd=[sys.executable]+args;env=dict(os.environ,FLASH_FE027_NUMERICS='63');env.pop('FLASH_FE027_COMBINE',None)
        if combine:env['FLASH_FE027_COMBINE']='1'
        print('CASE_START',stamp(),name,'COMMAND',json.dumps(cmd),flush=True)
        with (a.out/(name+'-driver.log')).open('w') as f:r=subprocess.run(cmd,cwd=repo,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=1100)
        print('CASE_STOP',stamp(),name,'exit',r.returncode,flush=True)
        case=dict(name=name,command=cmd,exit=r.returncode,ended=stamp());summary['cases'].append(case);save()
        if r.returncode:raise RuntimeError((name,r.returncode))
        native=json.loads((a.out/name/'nrow-oracle.json').read_text());assert native['status']=='NUMERICAL_PASS'
        case.update(position=native['completed_position'],bit_exact=native['bit_exact'],state_max=max(x['state_max_abs'] for x in native['rows']),hidden_max=max(x['hidden']['max_abs'] for x in native['rows']),logits_max=max(x['logits']['max_abs'] for x in native['rows']));save()
    def accumulation(name,count,full=False,combine=False):
        args=['tools/qualify_session_accumulation.py','--binary',str(binary),'--numerics','63','--count',str(count),'--gpu-wait','60','--timeout','900','--out',str(a.out/name)]
        if full:args+=['--full-final-slab']
        run(name,args,combine)
    try:
        accumulation('short-129',129,combine=True)
        directory=a.out/'short-129';load=lambda n:json.loads((directory/n).read_text())
        operators=summarize(load('combine-operators.json'),load('combine-replay-state.json'))
        (directory/'sanitized-combine.json').write_text(json.dumps(operators,indent=2)+'\n');assert operators['causal_validation_pass'],operators['validation_failures']
        run('resident-304',['tools/run_session_nrow_oracle.py','--binary',str(binary),'--history',str(a.history),'--history-for-tokens-only','--count','304','--starts','13,141','--out',str(a.out/'resident-304')])
        accumulation('original-2057',2057)
        accumulation('extended-2305',2305)
        accumulation('former-failure-3456',3456,full=True)
        accumulation('full-4096',4096,full=True)
        summary['status']='MANDATORY_PASS'
    except Exception as e:
        summary['status']='STOPPED';summary['error']=str(e);print('SUITE_STOP',stamp(),str(e),flush=True)
    summary['ended']=stamp();save();return 0 if summary['status']=='MANDATORY_PASS' else 3
if __name__=='__main__':raise SystemExit(main())
