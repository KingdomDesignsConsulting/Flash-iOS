// Reusable MCP JSON-RPC fixtures for the external Gateway. No registry implementation.
const http=require('node:http');
async function mcpFixture({endpoint='A',pages=2,fault='',delayMs=100}={}) {
 const requests=[];
 const s=http.createServer(async(req,res)=>{
  let raw='';for await(const chunk of req){raw+=chunk;if(raw.length>65536){res.writeHead(413);res.end();return;}}
  let q;try{q=JSON.parse(raw);}catch{res.writeHead(400);res.end();return;}
  requests.push(q);res.setHeader('Content-Type','application/json');
  const send=result=>res.end(JSON.stringify({jsonrpc:'2.0',id:q.id,result}));
  const fail=(code,message)=>res.end(JSON.stringify({jsonrpc:'2.0',id:q.id,error:{code,message}}));
  if(q.method==='initialize')return send({protocolVersion:'2024-11-05',capabilities:{tools:{}},serverInfo:{name:'duplicate-fixture',version:'1'}});
  if(q.method==='notifications/initialized'){res.writeHead(202);return res.end();}
  if(q.method==='tools/list') {
   const cursor=q.params?.cursor,page=cursor==null?0:Number(cursor);
   if(!Number.isInteger(page)||page<0||page>=pages||cursor!=null&&String(page)!==cursor)return fail(-32602,'Invalid cursor');
   if(page>0&&fault==='error')return fail(-32603,'Synthetic later-page error');
   if(page>0&&fault==='timeout'){setTimeout(()=>send({tools:[]}),delayMs);return;}
   const name=fault==='duplicate-tool'?'shared':page===0?'shared':`${endpoint}_page_${page}`;
   const tool={name,description:`Synthetic endpoint ${endpoint} page ${page}`,inputSchema:{type:'object',properties:{[endpoint]:{type:'string'}},required:[endpoint],additionalProperties:false}};
   return send({tools:fault==='empty-middle'&&page===1?[]:[tool],...(page<pages-1?{nextCursor:fault==='cycle'?'0':String(page+1)}:{})});
  }
  if(q.method==='tools/call')return send({content:[{type:'text',text:JSON.stringify({endpoint,name:q.params?.name,synthetic:true})}]});
  return fail(-32601,'Method not found');
 });
 await new Promise(r=>s.listen(0,'127.0.0.1',r));
 return {url:'http://127.0.0.1:'+s.address().port,requests,close:async()=>{s.closeAllConnections();await new Promise(r=>s.close(r));}};
}
module.exports={mcpFixture};
