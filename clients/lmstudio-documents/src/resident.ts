import {randomUUID} from 'node:crypto';
import {UpstreamError} from './transport';
type Entry={id:string;history:any[];config:string};
// SDK 1.4.0 does not expose a stable scope. The shipped generator passes no
// scope and is stateless. This adapter is for independently verified identities.
export class ResidentProtocol {
 private entries=new Map<string,Entry>();
 private busy=new Set<string>();
 clear(scope?:string){if(scope)this.entries.delete(scope);else this.entries.clear();}
 async execute(scope:string|undefined,messages:any[],config:any,
  send:(request:any)=>Promise<any>,endpointIdentity=''):Promise<any> {
  const full=structuredClone(messages),settings=structuredClone(config),signature=JSON.stringify([endpointIdentity,settings]);
  if(!scope)return send({...settings,messages:full});
  if(this.busy.has(scope))throw new Error('Concurrent generation in one resident scope');
  this.busy.add(scope);
  try {
   const old=this.entries.get(scope);let id:string=randomUUID();let outgoing=full;let create=true;
   if(old && old.config===signature && full.length>old.history.length &&
      JSON.stringify(full.slice(0,old.history.length))===JSON.stringify(old.history)) {
    const delta=full.slice(old.history.length);
    const pending=old.history.at(-1)?.tool_calls?.map((c:any)=>c.id)||[];
    if((!pending.length && delta.length===1 && delta[0].role==='user') ||
       (pending.length===delta.length && pending.length>0 &&
        delta.every((m:any,i:number)=>m.role==='tool' && m.tool_call_id===pending[i]))) {id=old.id;outgoing=delta;create=false;}
   }
   this.entries.delete(scope);
   let reply:any;
   for(let attempt=0;attempt<2;attempt++) {
    try {reply=await send({...settings,messages:outgoing,session_id:id,...(create?{flash_session_create:true}:{})});break;}
    catch(error) {
     if(!(error instanceof UpstreamError) || !error.invalidated || error.partial || attempt)throw error;
     id=randomUUID();outgoing=full;create=true;
    }
   }
   if(!reply || reply.role!=='assistant')throw new Error('Missing complete assistant acknowledgement');
   if(this.entries.size>=128)this.entries.delete(this.entries.keys().next().value!);
   this.entries.set(scope,{id,history:[...full,structuredClone(reply)],config:signature});
   return reply;
  } finally {this.busy.delete(scope);}
 }
}
