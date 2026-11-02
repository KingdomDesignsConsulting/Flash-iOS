// Real adapter + SDK Chat + Flash HTTP. UI controller is a mock; no documents
// or external tool actions are accessed/executed. Run only on isolated 11243.
const fs=require('node:fs'),assert=require('node:assert/strict');
const {Chat}=require('@lmstudio/sdk'),transport=require('../dist/transport');
const original=transport.completionEvents,requests=[],events=[];
transport.completionEvents=async function*(base,key,body,...rest){
 assert.equal(base,'http://127.0.0.1:11243/v1');requests.push(body);const seen=[];events.push(seen);
 for await(const part of original(base,key,body,...rest)){seen.push(part);yield part;}
};
const {generate}=require('../dist/generator');
const out=process.argv[process.argv.indexOf('--out')+1];if(!out)throw Error('--out required');
(async()=>{
 const visible=[],reasoning=[];let cancel;
 const ctl={client:{},getPluginConfig:()=>({get:k=>({model:'qwen3.5',temperature:0,maxOutputTokens:256,debug:false}[k])}),getGlobalPluginConfig:()=>({get:k=>({baseUrl:'http://127.0.0.1:11243/v1',apiKey:''}[k])}),getToolDefinitions:()=>[],onAborted:cb=>cancel=cb,fragmentGenerated:(t,o)=>o?.reasoningType?reasoning.push(t):visible.push(t)};
 const chat=Chat.from([{role:'system',content:'You are a helpful assistant.'},{role:'user',content:'Context:'+(' x'.repeat(128))+'\nReply exactly ADAPTER_73941.'}]);
 const timer=setTimeout(()=>cancel?.(),140000);
 try {
  await generate(ctl,chat);const first=visible.join('');assert.ok(first.includes('ADAPTER_73941'));visible.length=0;
  chat.append('assistant',first);chat.append('user','Reply exactly ADAPTER_FOLLOWUP_73941.');await generate(ctl,chat);const second=visible.join('');assert.ok(second.includes('ADAPTER_FOLLOWUP_73941'));
  assert.equal(requests.length,2);for(const r of requests){assert.equal(r.session_id,undefined);assert.equal(r.flash_session_create,undefined);}
  const ids=events.map(es=>es.find(e=>e.id)?.id);assert.ok(ids.every(Boolean));
  fs.writeFileSync(out,JSON.stringify({status:'PASS',real_Flash_inference:true,real_SDK_Chat:true,mock_prediction_controller:true,GUI_tested:false,documents_accessed:false,external_tools_executed:false,stateless_full_history:true,requests,events,request_ids:ids,visible:[first,second],reasoning_fragments:reasoning.length},null,2));
 } catch(error) {
  fs.writeFileSync(out,JSON.stringify({status:'FAIL',error:String(error),requests,events,visible,reasoning_fragments:reasoning.length},null,2));throw error;
 } finally {clearTimeout(timer);}
})().then(()=>process.exit(0)).catch(e=>{console.error(e.stack);process.exit(1)});
