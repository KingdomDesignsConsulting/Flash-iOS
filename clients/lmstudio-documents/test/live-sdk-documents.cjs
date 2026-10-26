// Opt-in real LM Studio file service test. Prediction controller is a mock,
// not the GUI; no inference, installation, or user file access occurs.
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const {LMStudioClient,Chat}=require('@lmstudio/sdk');
const {injectDocuments}=require('../dist/documents'),{generate}=require('../dist/generator');
if(!process.argv.includes('--out'))throw new Error('--out required');
const out=process.argv[process.argv.indexOf('--out')+1];
(async()=>{
 const client=new LMStudioClient(),folder=fs.mkdtempSync(path.join(os.tmpdir(),'flash-sdk-doc-'));let server;
 try {
  const version=await Promise.race([client.system.getLMStudioVersion(),new Promise((_,rej)=>setTimeout(()=>rej(new Error('LM Studio connection timeout')),7000))]);
  const source='DOC-73941\nUnicode: 雪 😀 café\n',file=path.join(folder,'synthetic-document.txt');fs.writeFileSync(file,source);
  const handle=await client.files.prepareFile(file);let text='Remember my document.',consumed=0;
  const message={getText:()=>text,getFiles:()=>consumed?[]:[handle],consumeFiles:()=>consumed++,replaceText:x=>text=x};
  await injectDocuments({client,abortSignal:new AbortController().signal},message);
  assert.equal(consumed,1);assert.ok(text.includes('DOC-73941')&&text.includes('雪 😀 café'));
  const once=text;await injectDocuments({client,abortSignal:new AbortController().signal},message);assert.equal(text,once);
  const requests=[];
  server=http.createServer(async(req,res)=>{let raw='';for await(const b of req)raw+=b;requests.push(JSON.parse(raw));res.setHeader('Content-Type','text/event-stream');res.end('data: {"choices":[{"delta":{"content":"ACK"},"finish_reason":null}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n');});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));const url='http://127.0.0.1:'+server.address().port+'/v1';
  const ctl={client,getPluginConfig:()=>({get:k=>({maxOutputTokens:256,model:'qwen3.5',temperature:0}[k])}),getGlobalPluginConfig:()=>({get:k=>({baseUrl:url,apiKey:''}[k])}),getToolDefinitions:()=>[],onAborted:()=>{},fragmentGenerated:()=>{}};
  const history=Chat.from([{role:'user',content:text}]);await generate(ctl,history);history.append('assistant','ACK');history.append('user','What is my document identifier?');await generate(ctl,history);
  for(const r of requests){assert.equal(r.messages[0].content,text);assert.equal(r.session_id,undefined);assert.equal(r.flash_session_create,undefined);assert.equal(JSON.stringify(r.messages).split('DOC-73941').length-1,1);}
  const report={result:'PASS',LMStudio:version,real_document_parser:true,real_SDK_Chat:true,prediction_controller:'mock; not GUI',GUI:'NOT TESTED',source_sha256:crypto.createHash('sha256').update(source).digest('hex'),injected_characters:text.length,document_copies_per_request:1,forwarded_stateless:true,requests:requests.length,model_inference:false};
  fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 } finally {
  if(server){server.closeAllConnections();await new Promise(r=>server.close(r));}
  await client[Symbol.asyncDispose]();fs.rmSync(folder,{recursive:true,force:true});
 }
})().then(()=>process.exit(0)).catch(e=>{console.error(e.message);process.exit(1)});
