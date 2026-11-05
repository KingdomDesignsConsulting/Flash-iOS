#!/usr/bin/env python3
"""Execute the pinned official Jinja reference for the exact text-only SDK case.
Uses an existing Jinja2 environment; never edits Flash's template or model.
"""
import argparse,hashlib,json,pathlib

def main():
 import jinja2
 from jinja2.sandbox import ImmutableSandboxedEnvironment
 p=argparse.ArgumentParser(description=__doc__)
 for key in ['official_template','source_meta','sdk_record','native_render','tokenizer','out']:p.add_argument('--'+key.replace('_','-'),required=True,type=pathlib.Path)
 a=p.parse_args();source=a.official_template.read_bytes();meta=json.loads(a.source_meta.read_text());assert hashlib.sha256(source).hexdigest()==meta['sha256'];sdk=json.loads(a.sdk_record.read_text());messages=sdk['requests'][1]['messages'];assert all(isinstance(m['content'],str) and m['role'] in ['system','user','assistant'] for m in messages)
 def fail(message):raise ValueError(message)
 env=ImmutableSandboxedEnvironment(trim_blocks=True,lstrip_blocks=True);env.globals['raise_exception']=fail
 expected=env.from_string(source.decode()).render(messages=messages,tools=[],add_generation_prompt=True,enable_thinking=False,add_vision_id=False)
 native=next(x for x in json.loads(a.native_render.read_text())['cases'] if x['name']=='1-False');equal=expected==native['rendered'];tokenizer=json.loads(a.tokenizer.read_text());markers=['<|im_start|>','<|im_end|>','<|endoftext|>','<think>','</think>'];mapping={x['content']:x['id'] for x in tokenizer['added_tokens']};counts={name:dict(expected=expected.count(name),native_token_occurrences=native['token_ids'].count(mapping[name])) for name in markers};ids_ok=all(x['expected']==x['native_token_occurrences'] for x in counts.values())
 result=dict(status='MATCH' if equal and ids_ok else 'MISMATCH',official_url=meta['url'],official_repo_commit=meta['repo_commit'],official_template_sha256=meta['sha256'],jinja2_version=jinja2.__version__,environment='ImmutableSandboxedEnvironment(trim_blocks=True,lstrip_blocks=True)',request_index=1,thinking=False,rendered_bytes=len(expected.encode()),native_prompt_tokens=len(native['token_ids']),rendered_text_exact=equal,special_marker_token_counts_match=ids_ok,marker_counts=counts,expected_render_sha256=hashlib.sha256(expected.encode()).hexdigest(),native_render_sha256=hashlib.sha256(native['rendered'].encode()).hexdigest(),template_changed=False,scope='This exact text-only/no-tools nonthinking conversation against current official reference; original quantization export revision and general tools/vision branches not inferred')
 if not equal:result['first_mismatch_character']=next((i for i,(x,y) in enumerate(zip(expected,native['rendered'])) if x!=y),min(len(expected),len(native['rendered'])))
 with a.out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print('OFFICIAL_TEMPLATE',result['status'],'native_prompt_tokens',len(native['token_ids']));return 0 if equal and ids_ok else 3
if __name__=='__main__':raise SystemExit(main())
