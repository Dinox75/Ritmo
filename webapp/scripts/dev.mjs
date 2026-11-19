// Loopback QA adapter. Deliberately NOT imported by the production Worker/build.
import {createServer} from 'node:http';import {fileURLToPath} from 'node:url';
import {runtime} from '../tests/helpers.mjs';
export async function startPreview({persist='.wrangler/local',port=0}={}){
 const mf=await runtime(persist);const sessions=new Map();
 const server=createServer(async(req,res)=>{try{
  const origin=`http://127.0.0.1:${server.address().port}`;if(req.headers.host!==new URL(origin).host){res.writeHead(403).end();return;}
  const u=new URL(req.url,origin);if(u.pathname==='/__qa/login'){
   const user=u.searchParams.get('user');if(!['alice','bob','charlie'].includes(user)){res.writeHead(400).end();return;}const token=crypto.randomUUID();sessions.set(token,{user,expires:Date.now()+3600000});res.writeHead(302,{'Set-Cookie':`ritmo_qa=${token}; HttpOnly; SameSite=Strict; Path=/`,'Location':'/','Cache-Control':'no-store'}).end();return;
  }
  if(u.pathname==='/signin-with-chatgpt'){res.writeHead(302,{Location:'/__qa/login?user=alice'}).end();return;}
  const cookie=(req.headers.cookie||'').split(';').map(v=>v.trim()).find(v=>v.startsWith('ritmo_qa='))?.slice(9),identity=sessions.get(cookie);
  if(u.pathname==='/signout-with-chatgpt'){sessions.delete(cookie);res.writeHead(302,{'Set-Cookie':'ritmo_qa=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/','Location':'/'}).end();return;}
  const headers={...req.headers};for(const name of Object.keys(headers))if(name.startsWith('oai-authenticated-'))delete headers[name];if(identity&&identity.expires>Date.now()){headers['oai-authenticated-user-id']=identity.user;headers['oai-authenticated-user-email']=identity.user+'@synthetic.invalid';}
  const chunks=[];let total=0;for await(const chunk of req){total+=chunk.length;if(total>34*1024*1024){res.writeHead(413).end();return;}chunks.push(chunk);}const response=await mf.dispatchFetch(u.toString(),{method:req.method,headers,...(chunks.length?{body:Buffer.concat(chunks)}:{})});res.writeHead(response.status,Object.fromEntries(response.headers));res.end(Buffer.from(await response.arrayBuffer()));
 }catch{res.writeHead(503,{'Content-Type':'application/json'}).end('{"error":"QA adapter unavailable"}');}});
 await new Promise(resolve=>server.listen(port,'127.0.0.1',resolve));return {url:`http://127.0.0.1:${server.address().port}`,mf,sessions,close:async()=>{await new Promise(resolve=>server.close(resolve));await mf.dispose();}};
}
if(process.argv[1]===fileURLToPath(import.meta.url)){const p=await startPreview({port:8787});console.log('Local synthetic preview: '+p.url+' (login simulation, not production evidence)');for(const signal of ['SIGINT','SIGTERM'])process.on(signal,async()=>{await p.close();process.exit(0);});}
