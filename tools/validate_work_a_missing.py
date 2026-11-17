"""Fail-closed acceptance of the frozen missing-only 32K performance cohort."""
import argparse, hashlib, json, pathlib, math
P = pathlib.Path

def load(p):
    return json.loads(p.read_text())

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def validate_trial(row, binary):
    if not row['binary_sha256'] == binary:
        raise ValueError('Release evidence rejected at original line 9')
    if not (row['host_free_before'] >= 35 and len(row['post_gpu']) >= 3 and all((x is not None and 0 <= x < 30 for x in row['post_gpu'][-3:]))):
        raise ValueError('Release evidence rejected at original line 10')
    if not (row['budget']['stop_reason'] is None and row['budget']['exit'] == -15 and (0 < row['budget']['peak_rss_bytes'] <= 16 * 1024 ** 3)):
        raise ValueError('Release evidence rejected at original line 11')
    if not row['memory']['samples'] > 0:
        raise ValueError('Release evidence rejected at original line 12')
    if not [c['label'] for c in row['cases']] == ['cold', 'warm']:
        raise ValueError('Release evidence rejected at original line 13')
    for c in row['cases']:
        t = c['timings']
        if not all((math.isfinite(t[k]) and t[k] > 0 for k in ['prefill_ms', 'decode_ms', 'prefill_tokens_per_second', 'decode_tokens_per_second'])):
            raise ValueError('Release evidence rejected at original line 15')
        if not (t['context_tokens'] == t['prefill_tokens'] == 32768 and t['cached_prefix_tokens'] == 0 and (t['generated_tokens'] == 32)):
            raise ValueError('Release evidence rejected at original line 16')
        if not c['usage'] == dict(prompt_tokens=32768, completion_tokens=32, total_tokens=32800):
            raise ValueError('Release evidence rejected at original line 17')
        a = c['allocation']
        if not (a['gpu_capacity'] == 32768 and a['cpu_capacity'] == 65536 and (a['resident_pos'] == 32800)):
            raise ValueError('Release evidence rejected at original line 18')
        if not ({int(k) for k in a['kv_lengths']} == set(range(3, 40, 4)) and all((v == 32800 for v in a['kv_lengths'].values()))):
            raise ValueError('Release evidence rejected at original line 19')
    for (n, backend) in [(32768, 'GPU'), (32769, 'CPU')]:
        if not {x['layer'] for x in row['boundary_routes'] if x['length'] == n and x['backend'] == backend and (x['cap'] == 32768)} == set(range(3, 40, 4)):
            raise ValueError('Release evidence rejected at original line 21')

def validate(report, manifest, binaries, input_hash, render_hash):
    if not report['status'] == 'COMPLETED_EXPLORATORY':
        raise ValueError('Incomplete cohort')
    if not (report['release_manifest_sha256'] == manifest and report['input_sha256'] == input_hash and (report['rendered_ids_sha256'] == render_hash)):
        raise ValueError('Release evidence rejected at original line 25')
    if not (report['count'] == 32768 and report['repeats'] == 1):
        raise ValueError('Release evidence rejected at original line 26')
    if not report['selected_modes'] == ['mask63', 'scalar']:
        raise ValueError('Release evidence rejected at original line 27')
    rows = report['rows']
    if not (len(rows) == 2 and [r['mode'] for r in rows] == ['mask63', 'scalar']):
        raise ValueError('Release evidence rejected at original line 28')
    for row in rows:
        validate_trial(row, binaries[row['mode']])
    return dict(status='ACCEPTED_EXPLORATORY_N1', modes=['mask63', 'scalar'], full_logical_context=True, complete_cold_warm_pairs=True, all_ten_boundary_routes=True, no_watchdog_event=True, variance_measured=False)

def validate_split(mask_report, scalar_report, manifest, binaries, input_hash, render_hash):
    if not mask_report['status'] == 'STOPPED':
        raise ValueError('Release evidence rejected at original line 33')
    if not scalar_report['status'] == 'COMPLETED_EXPLORATORY':
        raise ValueError('Release evidence rejected at original line 34')
    if not mask_report['selected_modes'] == ['mask63', 'scalar']:
        raise ValueError('Release evidence rejected at original line 35')
    if not scalar_report['selected_modes'] == ['scalar']:
        raise ValueError('Release evidence rejected at original line 36')
    if not [row['mode'] for row in mask_report['rows']] == ['mask63']:
        raise ValueError('Release evidence rejected at original line 37')
    if not [row['mode'] for row in scalar_report['rows']] == ['scalar']:
        raise ValueError('Release evidence rejected at original line 38')
    if not mask_report['runner_sha256'] == scalar_report['runner_sha256']:
        raise ValueError('Release evidence rejected at original line 39')
    for report in [mask_report, scalar_report]:
        if not report['release_manifest_sha256'] == manifest:
            raise ValueError('Release evidence rejected at original line 41')
        if not report['input_sha256'] == input_hash:
            raise ValueError('Release evidence rejected at original line 42')
        if not report['rendered_ids_sha256'] == render_hash:
            raise ValueError('Release evidence rejected at original line 43')
        if not (report['count'] == 32768 and report['repeats'] == 1):
            raise ValueError('Release evidence rejected at original line 44')
        for row in report['rows']:
            validate_trial(row, binaries[row['mode']])
    return dict(status='ACCEPTED_EXPLORATORY_N1', modes=['mask63', 'scalar'], full_logical_context=True, complete_cold_warm_pairs=True, all_ten_boundary_routes=True, accepted_trials_no_watchdog_event=True, variance_measured=False, scope='Two independently complete process trials across phases', original_report_statuses=[mask_report['status'], scalar_report['status']])

def validate_lifecycle(text, completion, mode, binary):
    if not sum(('SERVER_START' in line and line.endswith('0-' + mode) for line in text.splitlines())) == 1:
        raise ValueError('Release evidence rejected at original line 55')
    if not sum(('SERVER_STOP' in line and line.endswith('0-' + mode + ' exit -15') for line in text.splitlines())) == 1:
        raise ValueError('Release evidence rejected at original line 56')
    launch = load(completion / ('0-' + mode) / 'launch.json')
    if not (launch['binary_sha256'] == binary and all((0 <= x < 30 for x in launch['pre_gpu'][-3:])) and (len(launch['pre_gpu']) >= 3)):
        raise ValueError('Release evidence rejected at original line 57')
    args = launch['command']
    if not ('--tiered' in args and '--serve' in args and (args[args.index('--serve') + 1] == '11243')):
        raise ValueError('Release evidence rejected at original line 58')
    if not [x for x in args if x in ['--prefill-nrow', '--no-prefill-nrow']][-1] == ('--prefill-nrow' if mode == 'mask63' else '--no-prefill-nrow'):
        raise ValueError('Release evidence rejected at original line 59')
    if not launch['test_environment']['FLASH_FE027_NUMERICS'] == ('63' if mode == 'mask63' else '0'):
        raise ValueError('Release evidence rejected at original line 60')
    start = next((i for (i, l) in enumerate(text.splitlines()) if 'SERVER_START' in l and l.endswith('0-' + mode)))
    stop = next((i for (i, l) in enumerate(text.splitlines()) if 'SERVER_STOP' in l and l.endswith('0-' + mode + ' exit -15')))
    if not start < stop:
        raise ValueError('Release evidence rejected at original line 61')
    if not sum(('LONG_PERF_CASE' in l for l in text.splitlines()[start:stop])) == 2:
        raise ValueError('Release evidence rejected at original line 62')
    return (start, stop)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for n in ['root', 'completion', 'driver_log', 'out']:
        p.add_argument('--' + n.replace('_', '-'), required=True, type=P)
    p.add_argument('--scalar-completion', type=P)
    p.add_argument('--scalar-driver-log', type=P)
    a = p.parse_args()
    root = a.root
    manifest = root / 'release-manifest.json'
    variants = load(root / 'build-variants.json')
    if not variants['release_manifest_sha256'] == sha(manifest):
        raise ValueError('Release evidence rejected at original line 70')
    digests = {m: variants['variants'][n]['sha256'] for (m, n) in [('mask63', 'infer-work-a-performance'), ('scalar', 'infer-work-a-control')]}
    report = load(a.completion / 'result.json')
    common = (sha(manifest), digests, sha(root / 'long-32768-input.json'), sha(root / 'long-32768-render.json'))
    text = a.driver_log.read_text()
    if a.scalar_completion is not None:
        if not a.scalar_driver_log is not None:
            raise ValueError('Release evidence rejected at original line 76')
        scalar = load(a.scalar_completion / 'result.json')
        result = validate_split(report, scalar, *common)
        from datetime import datetime
        if not datetime.fromisoformat(scalar['started']) > datetime.fromisoformat(report['ended']):
            raise ValueError('Release evidence rejected at original line 80')
        validate_lifecycle(text, a.completion, 'mask63', digests['mask63'])
        validate_lifecycle(a.scalar_driver_log.read_text(), a.scalar_completion, 'scalar', digests['scalar'])
        result.update(scalar_result_sha256=sha(a.scalar_completion / 'result.json'), scalar_driver_log_sha256=sha(a.scalar_driver_log))
    else:
        if not a.scalar_driver_log is None:
            raise ValueError('Release evidence rejected at original line 85')
        result = validate(report, *common)
        order = [validate_lifecycle(text, a.completion, mode, digests[mode]) for mode in ['mask63', 'scalar']]
        if not order[0][1] < order[1][0]:
            raise ValueError('Release evidence rejected at original line 88')
        if not sum(('LONG_PERF_CASE' in line for line in text.splitlines())) == 4:
            raise ValueError('Release evidence rejected at original line 89')
    result.update(result_sha256=sha(a.completion / 'result.json'), driver_log_sha256=sha(a.driver_log), release_manifest_sha256=sha(manifest), source_head=report['source_head'], runner_sha256=report['runner_sha256'])
    a.out.write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'])
if __name__ == '__main__':
    main()
