export class UpstreamError extends Error {
 constructor(message:string, public invalidated=false,public partial=false){super(message);}
}
function invalidated(x:any):boolean {
 return x?.session_invalidated===true || x?.resend_full_history===true ||
  x?.error?.session_invalidated===true || x?.error?.resend_full_history===true;
}
// Read raw SSE rather than relying on an SDK iterator which can treat EOF as
// completion. No implicit HTTP retries; an unknown execution state is not replayed.
export async function* completionEvents(base:string,key:string,body:any,signal:AbortSignal,
 idleMs=120000,totalMs=600000):AsyncGenerator<any> {
 const abort=new AbortController();
 const cancelled=()=>abort.abort(signal.reason);
 signal.addEventListener('abort',cancelled,{once:true});if(signal.aborted)cancelled();
 let idle:ReturnType<typeof setTimeout>|undefined;
 const total=setTimeout(()=>abort.abort(new Error('Request total timeout')),totalMs);
 const touch=()=>{if(idle)clearTimeout(idle);idle=setTimeout(()=>abort.abort(new Error('Stream idle timeout')),idleMs);};
 let reader:ReadableStreamDefaultReader<Uint8Array>|undefined;let emitted=false;
 try {
  touch();
  const response=await fetch(base.replace(/\/$/,'')+'/chat/completions',{
   method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+(key||'local')},
   body:JSON.stringify(body),signal:abort.signal});
  reader=response.body?.getReader();if(!reader)throw new UpstreamError('Missing response body');
  const decoder=new TextDecoder('utf-8',{fatal:true});let buffer='',data:string[]=[];
  let done=false,finished=false,bytes=0,errorText='';
  if(response.ok && !response.headers.get('content-type')?.includes('text/event-stream'))throw new UpstreamError('Expected SSE content type');
  while(!done) {
   const part=await reader.read();touch();
   if(part.done)break;
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
     if(raw==='[DONE]'){done=true;break;}
     let event:any;try{event=JSON.parse(raw);}catch{throw new UpstreamError('Malformed SSE JSON');}
     if(invalidated(event))throw new UpstreamError('Resident session invalidated',true);
     if(event?.error)throw new UpstreamError('Upstream SSE error');
     if(!Array.isArray(event?.choices))throw new UpstreamError('Invalid completion choices');
     for(const c of event.choices) {
      if(c.finish_reason!=null){if(!['stop','length','tool_calls'].includes(c.finish_reason))throw new UpstreamError('Unsuccessful finish reason');finished=true;}
     }
     if(event.choices.some((c:any)=>c.delta?.content || c.delta?.reasoning_content || c.delta?.tool_calls?.length))emitted=true;
     yield event;
    }
   }
  }
  decoder.decode(); // reject truncated UTF-8 too
  if(!response.ok){let error:any;try{error=JSON.parse(errorText);}catch{}throw new UpstreamError('Upstream HTTP '+response.status,invalidated(error));}
  if(!done || !finished)throw new UpstreamError('Incomplete SSE: finish and [DONE] required');
 } catch(error) {
  if(error instanceof UpstreamError)error.partial=emitted;
  throw error;
 } finally {
  clearTimeout(total);if(idle)clearTimeout(idle);signal.removeEventListener('abort',cancelled);
  await reader?.cancel().catch(()=>{});
 }
}
