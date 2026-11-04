const test=require('node:test'),assert=require('node:assert/strict');
const {server,ctl}=require('./protocol-fixture.cjs');
const {generate}=require('../dist/generator');
const {completionEvents}=require('../dist/transport');
const {Chat}=require('@lmstudio/sdk');
const event=x=>'data: '+JSON.stringify({choices:[{index:0,...x}]})+'\n\n';
const d=delta=>event({delta,finish_reason:null});
const end=reason=>event({delta:{},finish_reason:reason})+'data: [DONE]\n\n';
const schema={type:'object',required:['payload'],additionalProperties:false,properties:{payload:{type:'object',required:['text'],additionalProperties:false,properties:{text:{type:'string'},count:{type:'integer'}}}}};
const definition={type:'function',function:{name:'read',parameters:schema}};
const call=(index=0,id='a',name='read',args=JSON.stringify({payload:{text:'雪😀 <tool_call> "read" \\n'}}))=>({index,id,type:'function',function:{name,arguments:args}});
async function run(wire,check){return server(wire,async url=>{const c=ctl(url);c.getToolDefinitions=()=>[definition];return check(c,()=>generate(c,Chat.from([{role:'user',content:'synthetic fixture'}])));});}
for(const [name,calls,reason] of [
 ['unknown name',[call(0,'a','ghost')],'tool_calls'],
 ['duplicate IDs',[call(),call(1)],'tool_calls'],
 ['missing arguments',[{index:0,id:'a',function:{name:'read'}}],'tool_calls'],
 ['missing nested required',[call(0,'a','read','{"payload":{}}')],'tool_calls'],
 ['wrong nested type',[call(0,'a','read','{"payload":{"text":4}}')],'tool_calls'],
 ['extra property',[call(0,'a','read','{"payload":{"text":"ok"},"extra":1}')],'tool_calls'],
 ['valid then malformed',[call(),call(1,'b','read','{"payload":')],'tool_calls'],
 ['truncated at length',[call(0,'a','read','{"payload":')],'length'],
 ['array arguments',[call(0,'a','read','[]')],'tool_calls'],
 ['duplicate index',[call(),call()],'tool_calls'],
 ['non-string arguments',[call(0,'a','read',{})],'tool_calls'],
 ['empty tool finish',[],'tool_calls'],
])test('atomic tool rejection: '+name,async()=>run(d({tool_calls:calls})+end(reason),async(c,invoke)=>{await assert.rejects(invoke());assert.deepEqual(c.calls,[]);}));
test('reasoning/content/parallel calls preserve literal markers and nested JSON',async()=>run(d({reasoning_content:'private'})+d({content:'before <think>'})+d({tool_calls:[call(1,'b'),call()]})+d({content:'after </tool_call>'})+end('tool_calls'),async(c,invoke)=>{await invoke();assert.deepEqual(c.fragments,['private','before <think>','after </tool_call>']);assert.deepEqual(c.calls.filter(x=>x[0]==='end').map(x=>x[1].id),['a','b']);}));
for(const [name,wire] of [
 ['content after finish',event({delta:{},finish_reason:'stop'})+d({content:'late'})+'data: [DONE]\n\n'],
 ['duplicate finish',event({delta:{},finish_reason:'stop'})+end('stop')],
 ['multiple choices', 'data: '+JSON.stringify({choices:[{index:0,delta:{content:'one'}},{index:1,delta:{content:'two'}}]})+'\n\n'+end('stop')],
])test('invalid terminal sequence: '+name,async()=>server(wire,async url=>{await assert.rejects(async()=>{for await(const x of completionEvents(url,'',{},new AbortController().signal)){} });}));
test('every UTF8 byte split preserves channel fields and markers',async()=>{const wire=Buffer.from(d({reasoning_content:'思考😀'})+d({content:'quoted <think> </tool_call> 雪'})+end('stop'));for(let split=1;split<wire.length;split++)await server(res=>{res.write(wire.subarray(0,split));setImmediate(()=>res.end(wire.subarray(split)));},async url=>{const out=[];for await(const x of completionEvents(url,'',{},new AbortController().signal))out.push(x);assert.equal(out[0].choices[0].delta.reasoning_content,'思考😀');assert.equal(out[1].choices[0].delta.content,'quoted <think> </tool_call> 雪');});});
test('tool name and argument fragments assemble at every character boundary',async()=>{const args=call().function.arguments;for(let i=0;i<=args.length;i++)await run(d({tool_calls:[{index:0,id:'a',type:'function',function:{name:'re',arguments:args.slice(0,i)}}]})+d({tool_calls:[{index:0,function:{name:'ad',arguments:args.slice(i)}}]})+end('tool_calls'),async(c,invoke)=>{await invoke();assert.deepEqual(c.calls[1][1].arguments,JSON.parse(args));});});
test('valid call then later invalid call publishes neither',async()=>run(d({tool_calls:[call()]})+d({tool_calls:[call(1,'b','ghost')]})+end('tool_calls'),async(c,invoke)=>{await assert.rejects(invoke());assert.deepEqual(c.calls,[]);}));
test('usage-only event after finish remains supported',async()=>server(d({content:'OK'})+event({delta:{},finish_reason:'stop'})+'data: {"choices":[],"usage":{"prompt_tokens":9,"completion_tokens":1,"total_tokens":10}}\n\n'+'data: [DONE]\n\n',async url=>{const events=[];for await(const x of completionEvents(url,'',{},new AbortController().signal))events.push(x);assert.equal(events.at(-1).usage.total_tokens,10);}));
for(const usage of [{prompt_tokens:2,completion_tokens:1,total_tokens:2},{prompt_tokens:2,completion_tokens:1,total_tokens:3,prompt_tokens_details:{cached_tokens:3}},{prompt_tokens:-1,completion_tokens:1,total_tokens:0}])test('inconsistent usage rejected '+JSON.stringify(usage),async()=>server(d({content:'OK'})+event({delta:{},finish_reason:'stop'})+'data: '+JSON.stringify({choices:[],usage})+'\n\ndata: [DONE]\n\n',async url=>assert.rejects(async()=>{for await(const x of completionEvents(url,'',{},new AbortController().signal)){} })));
