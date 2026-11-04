#!/usr/bin/env python3
"""Capture synthetic direct/announce prompt IDs with the unchanged native renderer.
Render-only path; generated/model tool-choice behavior is deliberately NOT tested.
"""
import argparse, hashlib, json, os, pathlib, subprocess

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',required=True,type=pathlib.Path)
    p.add_argument('--model',required=True)
    p.add_argument('--out',required=True,type=pathlib.Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    tool=dict(type='function',function=dict(name='lookup',description='Synthetic fixture only',parameters=dict(type='object',properties={'key':{'type':'string'}},required=['key'],additionalProperties=False)))
    cases=[]
    for thinking in [False,True]:
        for style,instruction in [('direct','Invoke lookup directly.'),('announce','Announce the intended action before invoking lookup.')]:
            cases.append(dict(name=f'{style}-{thinking}',thinking=thinking,tools=[tool],messages=[dict(role='system',content=instruction),dict(role='user',content='Look up synthetic key A17.')]))
    inp=a.out/'input.json';out=a.out/'native-render.json';inp.write_text(json.dumps(dict(cases=cases)))
    env=dict(os.environ,FLASH_SESSION_RENDER_INPUT=str(inp.resolve()),FLASH_SESSION_RENDER_OUTPUT=str(out.resolve()))
    subprocess.run([str(a.binary.resolve()),'--model',a.model,'--tiered'],env=env,check=True,timeout=60,stdout=subprocess.DEVNULL)
    report=json.loads(out.read_text());assert report['model_loaded'] is False and report['metal_initialized'] is False
    rows=report['cases'];assert len(rows)==4
    for c,r in zip(cases,rows):
        suffix='<|im_start|>assistant\n<think>\n' if c['thinking'] else '<|im_start|>assistant\n<think>\n\n</think>\n\n'
        assert r['rendered'].endswith(suffix)
        assert 248068 in r['token_ids'] # genuine think-start ID
        assert (248069 in r['token_ids']) is (not c['thinking'])
    summary=dict(status='PASS',scope='Native render/tokenization only; no model generation or HTTP inference',cases=[dict(name=r['name'],count=r['count'],token_ids_sha256=hashlib.sha256(json.dumps(r['token_ids'],separators=(',',':')).encode()).hexdigest()) for r in rows])
    (a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
