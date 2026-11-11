// Mock fetch only: no sockets, model, or service. Preserve actual Work B transport.
const assert=require('node:assert/strict');
const {completionEvents}=require(process.argv[2]);
let comments=0,timer;
global.fetch=async(_url,options)=>({ok:true,headers:new Headers({'content-type':'text/event-stream'}),body:new ReadableStream({start(c){timer=setInterval(()=>{comments++;c.enqueue(new TextEncoder().encode(': working\n\n'));},5);options.signal.addEventListener('abort',()=>{clearInterval(timer);c.error(options.signal.reason);},{once:true});},cancel(){clearInterval(timer);}})});
(async()=>{const start=Date.now();await assert.rejects(async()=>{for await(const _ of completionEvents('http://fixture.invalid','',{},new AbortController().signal,40,100)){}},/Request total timeout/);assert(comments>3);console.log(JSON.stringify({status:'PASS',finding:'Total timeout fires despite frequent keepalives',idle_ms:40,total_ms:100,elapsed_ms:Date.now()-start,keepalives:comments}));})().catch(e=>{clearInterval(timer);console.error(e);process.exitCode=1});
