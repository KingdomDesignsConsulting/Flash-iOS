#!/usr/bin/env python3
"""Summarize existing footprint samples; repair labels against launch evidence.

Never launches inference or changes raw evidence. HTTP launches must be sequential.
"""
import argparse, collections, datetime, json, pathlib, statistics

def stamp(value):
    return datetime.datetime.fromisoformat(value)

def summarize(root, samples):
    launches=[]
    for path in (root/'performance-http').glob('*/launch.json'):
        data=json.loads(path.read_text()); command=data['command']
        flags=[x for x in command if x in ('--prefill-nrow','--no-prefill-nrow')]
        assert flags
        mode='candidate' if 'infer-release-prefetch-performance' in command[0] else 'scalar' if flags[-1]=='--no-prefill-nrow' else 'control'
        launches.append((stamp(data['started']),mode))
    launches.sort(); groups=collections.defaultdict(dict); corrected=0
    for line in samples.read_text().splitlines():
        row=json.loads(line)
        if row.get('kind')!='SAMPLE': continue
        mode=row['mode']
        if row['scope']=='http':
            eligible=[x for x in launches if x[0]<=stamp(row['at'])]
            assert eligible, 'HTTP sample predates every recorded launch'
            mode=eligible[-1][1]; corrected+=mode!=row['mode']
        identity=(row['pid'],row['start_abstime'])
        item=groups[(row['scope'],mode)].setdefault(identity,dict(samples=0,physical=0,peak=0,rss=0))
        item['samples']+=1
        for key,field in [('physical','physical_bytes'),('peak','peak_physical_bytes'),('rss','rss_bytes')]:
            item[key]=max(item[key],row[field])
    result=[]
    for (scope,mode),instances in sorted(groups.items()):
        rows=list(instances.values())
        result.append(dict(scope=scope,mode=mode,process_count=len(rows),samples=sum(x['samples'] for x in rows),
            metrics={key:dict(median=statistics.median(x[key] for x in rows),min=min(x[key] for x in rows),max=max(x[key] for x in rows)) for key in ['physical','peak','rss']},instances=rows))
    return dict(scope='Sampled charged process footprint; overlapping RSS is not total unified memory',
        coverage='No 1K physical samples; 4K ordinary has two processes, other paths three. HTTP has three processes/path. Observer ended with completed suite.',
        label_correction='HTTP labels use final CLI flag from sequential recorded launch times. Raw samples remain unchanged.',
        corrected_sample_count=corrected,groups=result)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=pathlib.Path,required=True);p.add_argument('--samples',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args()
    a.out.write_text(json.dumps(summarize(a.root,a.samples),indent=2,allow_nan=False)+'\n')
if __name__=='__main__':main()
