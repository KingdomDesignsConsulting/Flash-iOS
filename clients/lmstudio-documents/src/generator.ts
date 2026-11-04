import type { Chat, GeneratorController } from '@lmstudio/sdk';
import {configSchematics,globalConfigSchematics} from './config';
import {completionEvents} from './transport';
import {ResidentProtocol} from './resident';
const protocol=new ResidentProtocol();
export async function generate(ctl:GeneratorController, chat:Chat) {
 const settings=ctl.getPluginConfig(configSchematics),global=ctl.getGlobalPluginConfig(globalConfigSchematics);
 const messages:any[]=[];
 for(const message of chat) {
  const role:string=message.getRole();
  if(typeof message.getFiles==='function' && message.getFiles(ctl.client).length)throw new Error('Unprocessed attachment remains; run document preprocessor. Images are unsupported by this text endpoint.');
  if(['system','developer','user'].includes(role))messages.push({role,content:message.getText()});
  else if(role==='assistant') {
   const calls=message.getToolCallRequests().map(c=>({id:c.id||'',type:'function',function:{name:c.name,arguments:JSON.stringify(c.arguments||{})}}));
   messages.push({role,content:message.getText(),...(calls.length?{tool_calls:calls}:{})});
  } else if(role==='tool')for(const r of message.getToolCallResults())messages.push({role,tool_call_id:r.toolCallId||'',content:r.content});
  else throw new Error('Unsupported history role: '+role);
 }
 const maxOutputTokens=settings.get('maxOutputTokens');
 const tools=ctl.getToolDefinitions().map(t=>({type:'function',function:{name:t.function.name,description:t.function.description,parameters:t.function.parameters||{}}}));
 const inputBytes=Buffer.byteLength(JSON.stringify({messages,tools}),'utf8'),limit=32768-maxOutputTokens-2048;
 if(inputBytes>limit)throw new Error(`Context safety cap exceeded (${inputBytes} serialized bytes; limit ${limit}). No document truncated.`);
 const abort=new AbortController();ctl.onAborted(()=>abort.abort());
 if(settings.get('debug'))console.info('[flash-ios-documents]',{mode:'stateless',reason:'SDK has no verified conversation identity',messages:messages.length,serializedBytes:inputBytes,model:settings.get('model')});
 try {
  // No guessed identity or SDK-object WeakMap: SDK may supply copies on each
  // generation/regeneration. Full canonical messages remain authoritative.
  await protocol.execute(undefined,messages,{model:settings.get('model'),stream:true,stream_options:{include_usage:true},temperature:settings.get('temperature'),max_tokens:maxOutputTokens,...(tools.length?{tools}:{})},async body=>{
   let content='',finishReason='';const calls=new Map<number,{id:string;name:string;args:string}>();
   for await(const part of completionEvents(global.get('baseUrl'),global.get('apiKey'),body,abort.signal)) {
    if(part.choices?.[0]?.finish_reason)finishReason=part.choices[0].finish_reason;
    const delta=part.choices?.[0]?.delta;
    if(!delta)continue;
    if(delta.content!=null){if(typeof delta.content!=='string')throw new Error('Invalid content delta');content+=delta.content;ctl.fragmentGenerated(delta.content);}
    if(delta.reasoning_content){if(typeof delta.reasoning_content!=='string')throw new Error('Invalid reasoning delta');ctl.fragmentGenerated(delta.reasoning_content,{reasoningType:'reasoning'});}
    for(const call of delta.tool_calls||[]) {
     if(!Number.isInteger(call.index)||call.index<0||call.index>63)throw new Error('Invalid tool-call index');
     let active=calls.get(call.index);if(!active){active={id:'',name:'',args:''};calls.set(call.index,active);}
     if(call.id){if(active.id&&active.id!==call.id)throw new Error('Tool call ID changed');active.id=call.id;}
     active.name+=call.function?.name||'';active.args+=call.function?.arguments||'';
     if(active.args.length>1024*1024)throw new Error('Tool argument size limit');
    }
   }
   if(abort.signal.aborted)throw new Error('Generation cancelled');
   if((calls.size>0 && finishReason!=='tool_calls') || (finishReason==='tool_calls' && !calls.size))throw new Error('Incomplete tool-call completion');
   if(!calls.size && !content.length)throw new Error('No visible assistant completion');
   // No partial tool request is made executable until transport completion AND
   // all tool arguments have validated. Parallel calls keep their stream index.
   const complete=[...calls.entries()].sort(([a],[b])=>a-b).map(([,c])=>{
    if(!c.id||!c.name)throw new Error('Incomplete tool call');
    const args=JSON.parse(c.args||'{}');if(!args||Array.isArray(args)||typeof args!=='object')throw new Error('Invalid tool argument object');
    return {...c,arguments:args};
   });
   for(const c of complete){ctl.toolCallGenerationStarted({toolCallId:c.id});ctl.toolCallGenerationNameReceived(c.name);ctl.toolCallGenerationArgumentFragmentGenerated(c.args);ctl.toolCallGenerationEnded({id:c.id,name:c.name,type:'function',arguments:c.arguments});}
   return {role:'assistant',content,...(complete.length?{tool_calls:complete.map(c=>({id:c.id,type:'function',function:{name:c.name,arguments:c.args}}))}:{})};
  });
 } catch(error) {
  if(abort.signal.aborted)return; // SDK owns the aborted/unsuccessful prediction
  throw error; // partial UI fragments never imply a successful prediction
 }
}
