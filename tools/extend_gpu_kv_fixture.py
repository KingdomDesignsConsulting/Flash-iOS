#!/usr/bin/env python3
"""Resumable deterministic qualification fixture extension; never changes input."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from qualify_gpu_32k import MODEL, sha


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--anchor', type=Path, required=True)
    ap.add_argument('--pos', type=int, default=16382)
    ap.add_argument('--target', type=int, default=32766)
    ap.add_argument('--chunk', type=int, default=1024)
    ap.add_argument('--idle-wait', type=int, default=60)
    a = ap.parse_args()
    repo = Path(__file__).resolve().parents[1]
    a.root.mkdir(parents=True, exist_ok=True)
    anchor, pos = a.anchor.resolve(), a.pos
    # Only fully published directories with completion metadata are resumable.
    completed = sorted(int(p.name) for p in a.root.iterdir() if p.name.isdigit() and (p/'complete.json').exists())
    if completed:
        pos = completed[-1]
        anchor = a.root/str(pos)/'anchor.state'
        m = json.loads(anchor.with_name('complete.json').read_text())
        if sha(anchor) != m['anchor_sha256'] or sha(anchor.with_name('hidden.bin')) != m['hidden_sha256']:
            raise RuntimeError('Resume checkpoint checksum mismatch')
    while pos < a.target:
        deadline=time.monotonic()+a.idle_wait
        while True:
            readings = []
            for _ in range(3):
                text = subprocess.check_output(['ioreg','-r','-c','AGXAccelerator','-d','1'],text=True)
                m = re.search(r'"Device Utilization %"\s*=\s*(\d+)', text)
                readings.append(int(m[1]) if m else 100)
                time.sleep(.3)
            if max(readings)<30 or time.monotonic()>=deadline:break
            print(f'WAIT GPU {readings}',flush=True);time.sleep(2)
        if max(readings) >= 30:
            raise RuntimeError(f'GPU busy {readings}; safe to resume same command')
        target = min(pos+a.chunk, a.target, 24574 if pos<24574 else a.target)
        staging = a.root/f'{target}.partial-{os.getpid()}'
        staging.mkdir()
        binary = repo/'metal_infer/infer-qual-lazy32k'
        command = [str(binary),'--model',MODEL,'--tiered','--no-malloc-cache','--no-expert-prefetch']
        env = dict(os.environ, FLASH_QUAL_ANCHOR=str(anchor), FLASH_QUAL_HIDDEN=str(anchor.with_name('hidden.bin')),
                   FLASH_QUAL_POS=str(pos), FLASH_QUAL_OUT=str(staging), FLASH_QUAL_EXTEND_TO=str(target))
        print(f'EXTEND {pos} -> {target}, GPU={readings}',flush=True)
        begin=time.time()
        shader_hash=sha(repo/'metal_infer/prefill_probe/chunk_kernels.metal')
        with (staging/'extension.log').open('w') as log:
            r=subprocess.run(command,cwd=binary.parent,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
        if r.returncode or 'RESULT=PASS' not in (staging/'extension.log').read_text():
            raise RuntimeError(f'Extension failed exit={r.returncode}; retained {staging}')
        meta=dict(pos=target,parent_pos=pos,parent_anchor=str(anchor),parent_sha256=sha(anchor),
                  anchor_sha256=sha(staging/'anchor.state'),hidden_sha256=sha(staging/'hidden.bin'),
                  binary_sha256=sha(binary),prefill_shader_sha256=shader_hash,command=command,elapsed_seconds=time.time()-begin,
                  token_recipe='1000 + (absolute_position * 73) % 1000',prefill_rows=128)
        with (staging/'complete.json').open('w') as f:
            json.dump(meta,f,indent=2);f.flush();os.fsync(f.fileno())
        destination=a.root/str(target)
        fd=os.open(staging,os.O_RDONLY);os.fsync(fd);os.close(fd)
        os.rename(staging,destination)
        fd=os.open(a.root,os.O_RDONLY);os.fsync(fd);os.close(fd)
        print(f'CHECKPOINT {target} bytes={(destination/"anchor.state").stat().st_size} seconds={meta["elapsed_seconds"]:.2f}',flush=True)
        # Keep the previous recovery point until the next checkpoint is durable;
        # preserve the 24K landmark for matched performance measurements.
        for old in completed[:-1]:
            if old != 24574:
                history=a.root/'history'/str(old);history.mkdir(parents=True,exist_ok=True)
                for name in ('complete.json','extension.log'):
                    shutil.copy2(a.root/str(old)/name,history/name)
                shutil.rmtree(a.root/str(old))
        completed=[x for x in completed if (a.root/str(x)).exists()]+[target]
        anchor,pos=destination/'anchor.state',target


if __name__=='__main__':
    main()
