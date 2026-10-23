import OpenAI from "openai";
import type { Chat, GeneratorController } from "@lmstudio/sdk";
import {configSchematics,globalConfigSchematics} from "./config";
export async function generate(ctl:GeneratorController, chat:Chat) {
 const settings=ctl.getPluginConfig(configSchematics), global=ctl.getGlobalPluginConfig(globalConfigSchematics);
 const messages: any[]=[];
 for(const message of chat){
  const role=message.getRole();
  if(role==="system"||role==="user") messages.push({role,content:message.getText()});
  else if(role==="assistant") {
   const calls=message.getToolCallRequests().map(c=>({id:c.id||"",type:"function",function:{name:c.name,arguments:JSON.stringify(c.arguments||{})}}));
   messages.push({role:"assistant",content:message.getText(),...(calls.length?{tool_calls:calls}:{})});
  } else if(role==="tool") for(const r of message.getToolCallResults()) messages.push({role:"tool",tool_call_id:r.toolCallId||"",content:r.content});
 }
 const chars=messages.reduce((n,m)=>n+JSON.stringify(m).length,0);
 const maxOutputTokens=settings.get("maxOutputTokens");
 if(chars > (32768-maxOutputTokens-2048)*2) throw new Error(`Context safety cap exceeded (${chars} serialized chars). Split or shorten attachments; none were silently truncated.`);
 const api=new OpenAI({baseURL:global.get("baseUrl"),apiKey:global.get("apiKey")||"local",timeout:120000});
 const tools=ctl.getToolDefinitions().map(t=>({type:"function" as const,function:{name:t.function.name,description:t.function.description,parameters:t.function.parameters||{}}}));
 const controller=new AbortController();
 ctl.onAborted(()=>controller.abort());
 if(settings.get("debug")) console.info("[flash-ios-documents]",{messages:messages.length,serializedChars:chars,model:settings.get("model")});
 try {
  const stream=await api.chat.completions.create({model:settings.get("model"),messages,stream:true,stream_options:{include_usage:true},temperature:settings.get("temperature"),max_tokens:maxOutputTokens,...(tools.length?{tools}:{})},{signal:controller.signal});
  let active: {id:string;name:string;args:string}|undefined;
  for await(const part of stream){
   if(controller.signal.aborted) break;
   const delta=part.choices?.[0]?.delta as (typeof part.choices)[number]["delta"] & {reasoning_content?:string};
   if(delta?.content) ctl.fragmentGenerated(delta.content);
   for(const call of delta?.tool_calls||[]){
    if(call.id){if(active?.name) ctl.toolCallGenerationEnded({id:active.id,name:active.name,type:"function",arguments:JSON.parse(active.args||"{}")}); active={id:call.id,name:"",args:""};ctl.toolCallGenerationStarted();}
    if(active&&call.function?.name){active.name+=call.function.name;ctl.toolCallGenerationNameReceived(call.function.name);}
    if(active&&call.function?.arguments){active.args+=call.function.arguments;ctl.toolCallGenerationArgumentFragmentGenerated(call.function.arguments);}
   }
  }
  if(active?.name) ctl.toolCallGenerationEnded({id:active.id,name:active.name,type:"function",arguments:JSON.parse(active.args||"{}")});
 }catch(e){if(controller.signal.aborted)return;console.error("[flash-ios-documents] upstream error",e); throw e;}
}