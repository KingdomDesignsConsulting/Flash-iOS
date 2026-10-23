const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const out=path.join(process.cwd(),'capture-results');fs.mkdirSync(out,{recursive:true});let n=0;
const server=http.createServer((req,res)=>{
 if(req.method!=='POST'||req.url!=='/v1/chat/completions'){res.writeHead(404);res.end();return}
 const chunks=[];req.on('data',chunk=>chunks.push(chunk));req.on('end',()=>{
  const raw=Buffer.concat(chunks);
  const filename=path.join(out,'request-'+String(++n).padStart(3,'0')+'.json');
  fs.writeFileSync(filename,raw);console.log('Captured',raw.length,'bytes to',filename);
  let json;try{json=JSON.parse(raw.toString('utf8'))}catch{res.writeHead(400);res.end();return}
  if(json.stream){res.writeHead(200,{'content-type':'text/event-stream','cache-control':'no-cache'});res.write('data: '+JSON.stringify({id:'capture',object:'chat.completion.chunk',choices:[{index:0,delta:{role:'assistant',content:'Capture complete.'},finish_reason:null}]})+'\n\n');res.write('data: '+JSON.stringify({id:'capture',object:'chat.completion.chunk',choices:[{index:0,delta:{},finish_reason:'stop'}]})+'\n\n');res.end('data: [DONE]\n\n')}
  else{res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify({id:'capture',object:'chat.completion',choices:[{index:0,message:{role:'assistant',content:'Capture complete.'},finish_reason:'stop'}]}))}
 })
});server.listen(11242,'127.0.0.1',()=>console.log('Capture listening on 127.0.0.1:11242'));
