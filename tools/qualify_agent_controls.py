#!/usr/bin/env python3
"""CPU-only characterization of the actual HTTP thinking-resolution source.
Does not start a server, load weights, or claim endpoint/lifecycle coverage.
"""
import argparse, hashlib, itertools, json, pathlib, subprocess, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=pathlib.Path)
    args = parser.parse_args()
    source = (ROOT / 'metal_infer/infer.m').read_text()
    start = source.index('static int effective_think_budget(int max_gen) {')
    policy = source[start:source.index('static int automatic_no_think_for_prompt', start)]
    start = source.index('            id requested_budget_value = request[@"thinking_token_budget"];')
    resolution = source[start:source.index('            NSString *debug_max_completion', start)]
    cases = []
    expected = []
    for stream, budget, effort in itertools.product([False, True], [None, 0, 1, 999], [None, 'off', 'none', 'low', 'medium', 'high']):
        request = {'stream': stream, 'enable_thinking': False}
        if budget is not None:
            request['thinking_token_budget'] = budget
        if effort is not None:
            request['reasoning_effort'] = effort
        cases.append(request)
        value = -1 if effort == 'off' else min(budget, 64) if budget is not None else -1
        expected.append((value, effort == 'off' or budget is not None))
    # Alias precedence, null primary fallback and clamps, plus unsupported explicit flag.
    for request, value, explicit in [
        ({'reasoning_budget_tokens': 2}, 2, True),
        ({'thinking_token_budget': None, 'reasoning_budget_tokens': 3}, 3, True),
        ({'thinking_token_budget': 1, 'reasoning_budget_tokens': 3}, 1, True),
        ({'thinking_token_budget': -1}, 0, True),
        ({'enable_thinking': True}, -1, False),
    ]:
        cases.append(request)
        expected.append((value, explicit))
    with tempfile.TemporaryDirectory(prefix='flash-controls-') as folder:
        directory = pathlib.Path(folder)
        inputs = directory / 'input.json'
        inputs.write_text(json.dumps(cases))
        code = '#import <Foundation/Foundation.h>\nstatic int g_think_budget=-1;\n' + policy
        code += 'int main(int argc,const char **argv){@autoreleasepool{int max_gen=64; NSArray *requests=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[1])] options:0 error:NULL]; for(NSDictionary *request in requests){\n'
        code += resolution
        code += 'printf("%d %d %d\\n",request_think_budget,request_think_budget_explicit,request_enable_thinking);}}return 0;}'
        path = directory / 'controls.m'
        path.write_text(code)
        binary = directory / 'controls'
        subprocess.run(['clang', '-fobjc-arc', '-framework', 'Foundation', str(path), '-o', str(binary)], check=True, capture_output=True)
        lines = subprocess.check_output([str(binary), str(inputs)], text=True).splitlines()
    assert len(lines) == len(cases)
    results = []
    for request, (value, explicit), line in zip(cases, expected, lines):
        actual = tuple(map(int, line.split()))
        assert actual == (value, int(explicit), int(value >= 0)), (request, actual)
        results.append(dict(request=request, budget=value, explicit=explicit, thinking=value >= 0))
    report = dict(status='PASS', cases=results, source_sha256=hashlib.sha256((policy + resolution).encode()).hexdigest(), scope='Actual source extracted and compiled; not live HTTP, profile restore, or prompt tokenization', unsupported_controls_silently_ignored=['enable_thinking', 'reasoning_effort none/low/medium/high'])
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {len(results)} native control-resolution cases; unsupported controls remain a documented gap')

if __name__ == '__main__':
    main()
