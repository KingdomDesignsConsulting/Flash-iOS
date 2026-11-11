#!/usr/bin/env python3
"""Bounded proof that current Work A assert gates disappear under python -O."""
import pathlib,subprocess,sys,json
root=pathlib.Path(__file__).resolve().parents[2]
code="import sys;sys.path.insert(0,'tools');from test_work_a_gate import Gate;t=Gate();t.setUp();t.native['rows'][0]['state_max_abs']=1.0\ntry:\n t.check();print('ACCEPT')\nexcept AssertionError:\n print('REJECT')\nfinally:\n t.tearDown()"
r={}
for mode,flags in [('normal',[]),('optimized',['-O'])]:r[mode]=subprocess.check_output([sys.executable,*flags,'-c',code],cwd=root,text=True).strip()
if r!={'normal':'REJECT','optimized':'ACCEPT'}:raise RuntimeError(r)
(root/'docs/audits/evidence/optimized-gate.json').write_text(json.dumps(dict(status='REPRODUCED',**r),indent=2)+'\n');print(r)
