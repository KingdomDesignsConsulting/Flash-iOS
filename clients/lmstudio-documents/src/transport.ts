export class UpstreamError extends Error {
 constructor(message:string, public invalidated=false,public partial=false){super(message);}
}
export const DEFAULT_IDLE_MS=120000, DEFAULT_TOTAL_MS=600000, MAX_DEADLINE_MS=86400000;
export class DeadlineError extends UpstreamError {
 constructor(public deadline:'idle'|'total',public phase:'headers'|'body') {
  super(`Request ${deadline} deadline expired while waiting for ${phase}`);
 }
}
function validDeadline(ms:number):boolean{return Number.isSafeInteger(ms)&&ms>=1&&ms<=MAX_DEADLINE_MS;}
export function requestDeadlines(totalSeconds:unknown=600,idleSeconds:unknown=120) {
 for(const value of [totalSeconds,idleSeconds])if(typeof value!=='number'||!Number.isSafeInteger(value)||value<1||value>86400)throw new Error('Request deadlines must be whole seconds between 1 and 86400');
 return {totalMs:(totalSeconds as number)*1000,idleMs:(idleSeconds as number)*1000};
}
function invalidated(x:any):boolean {
 return x?.session_invalidated===true || x?.resend_full_history===true ||
  x?.error?.session_invalidated===true || x?.error?.resend_full_history===true;
}
// Read raw SSE rather than relying on an SDK iterator which can treat EOF as
// completion. No implicit HTTP retries; an unknown execution state is not replayed.
export async function* completionEvents(base:string,key:string,body:any,signal:AbortSignal,
 idleMs=DEFAULT_IDLE_MS,totalMs=DEFAULT_TOTAL_MS):AsyncGenerator<any> {
 if(!validDeadline(idleMs)||!validDeadline(totalMs))throw new Error('Request deadlines must be integer milliseconds between 1 and 86400000');
 const started=performance.now();let lastActivity=started;let phase:'headers'|'body'='headers';
 const abort=new AbortController();
 const cancelled=()=>abort.abort(signal.reason);
 signal.addEventListener('abort',cancelled,{once:true});if(signal.aborted)cancelled();
 let idle:ReturnType<typeof setTimeout>|undefined;
 const total=setTimeout(()=>abort.abort(new DeadlineError('total',phase)),totalMs);
 const check=()=>{
  if(!abort.signal.aborted && performance.now()-started>=totalMs)abort.abort(new DeadlineError('total',phase));
  if(!abort.signal.aborted && performance.now()-lastActivity>=idleMs)abort.abort(new DeadlineError('idle',phase));
  if(abort.signal.aborted)throw abort.signal.reason;
 };
 const touch=()=>{lastActivity=performance.now();if(idle)clearTimeout(idle);idle=setTimeout(()=>abort.abort(new DeadlineError('idle',phase)),idleMs);};
 let reader:ReadableStreamDefaultReader<Uint8Array>|undefined;let emitted=false;
 try {
  check();touch();
  const response=await fetch(base.replace(/\/$/,'')+'/chat/completions',{
   method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+(key||'local')},
   body:JSON.stringify(body),signal:abort.signal});
  check();phase='body';touch();
  reader=response.body?.getReader();if(!reader)throw new UpstreamError('Missing response body');
  const decoder=new TextDecoder('utf-8',{fatal:true});let buffer='',data:string[]=[];
  let done=false,finished=false,bytes=0,errorText='';
  if(response.ok && !response.headers.get('content-type')?.includes('text/event-stream'))throw new UpstreamError('Expected SSE content type');
  while(!done) {
   check();const part=await reader.read();check();
   if(part.done)break;
   if(part.value.byteLength)touch();
   bytes+=part.value.byteLength;if(bytes>8*1024*1024)throw new UpstreamError('Response byte limit exceeded');
   const text=decoder.decode(part.value,{stream:true});
   if(!response.ok){errorText+=text;if(errorText.length>65536)throw new UpstreamError('Oversized error body');continue;}
   buffer+=text;if(buffer.length>1024*1024)throw new UpstreamError('SSE event limit exceeded');
   let end:number;
   while((end=buffer.indexOf('\n'))>=0) {
    const line=buffer.slice(0,end).replace(/\r$/,'');buffer=buffer.slice(end+1);
    if(line.startsWith('data:'))data.push(line.slice(5).replace(/^ /,''));
    else if(line==='' && data.length) {
     const raw=data.join('\n');data=[];
     check();
     if(raw==='[DONE]'){done=true;break;}
     let event:any;try{event=JSON.parse(raw);}catch{throw new UpstreamError('Malformed SSE JSON');}
     if(invalidated(event))throw new UpstreamError('Resident session invalidated',true);
     if(event?.error)throw new UpstreamError('Upstream SSE error');
     if(event.usage!=null){
      const u=event.usage;
      if(!['prompt_tokens','completion_tokens','total_tokens'].every(k=>Number.isSafeInteger(u[k])&&u[k]>=0) || u.total_tokens!==u.prompt_tokens+u.completion_tokens)throw new UpstreamError('Invalid token usage');
      const cached=u.prompt_tokens_details?.cached_tokens;
      if(cached!=null && (!Number.isSafeInteger(cached)||cached<0||cached>u.prompt_tokens))throw new UpstreamError('Invalid cached token usage');
     }
     if(!Array.isArray(event?.choices))throw new UpstreamError('Invalid completion choices');
     if(event.choices.length>1)throw new UpstreamError('Multiple completion choices unsupported');
     for(const c of event.choices) {
      if(c==null || typeof c!=='object' || (c.index!=null && c.index!==0))throw new UpstreamError('Invalid completion choice');
      if(finished)throw new UpstreamError('Completion event after finish');
      if(c.finish_reason!=null){if(!['stop','length','tool_calls'].includes(c.finish_reason))throw new UpstreamError('Unsuccessful finish reason');finished=true;}
     }
     if(event.choices.some((c:any)=>c.delta?.content || c.delta?.reasoning_content || c.delta?.tool_calls?.length))emitted=true;
     yield event;
    }
   }
  }
  check();
  decoder.decode(); // reject truncated UTF-8 too
  if(!response.ok){let error:any;try{error=JSON.parse(errorText);}catch{}throw new UpstreamError('Upstream HTTP '+response.status,invalidated(error));}
  if(!done || !finished)throw new UpstreamError('Incomplete SSE: finish and [DONE] required');
 } catch(error) {
  if(abort.signal.aborted)error=abort.signal.reason;
  if(error instanceof UpstreamError)error.partial=emitted;
  throw error;
 } finally {
  clearTimeout(total);if(idle)clearTimeout(idle);signal.removeEventListener('abort',cancelled);
  await reader?.cancel().catch(()=>{});
 }
}
