import {html,css,js,notices} from './assets.mjs';
import {need,Problem,mutate,id,LIMITS} from './domain.mjs';
import {bounded,sha,extract} from './documents.mjs';
import {account,rate,prior,fingerprint,commit,publicState,makeId} from './store.mjs';
import {exportBackup,prepareRestore} from './backup.mjs';

const secureHeaders={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin','Permissions-Policy':'camera=(), microphone=(), geolocation=()','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; media-src 'self' blob:; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'self' https://chatgpt.com"};
const json=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{...secureHeaders,'Content-Type':'application/json; charset=utf-8'}});
async function body(request,max=20000){need(request.body,'Pedido vazio.');const bytes=await bounded(request.body,max);try{return JSON.parse(new TextDecoder().decode(bytes));}catch(error){throw new Problem('JSON inválido.');}}
function findDoc(state,key){const doc=state.documents.find(x=>x.id===key);need(doc,'Material não encontrado.',404);return doc;}
async function route(request,env){
 const url=new URL(request.url),path=url.pathname;
 if(path==='/third-party.txt')return new Response(notices,{headers:{...secureHeaders,'Content-Type':'text/plain; charset=utf-8'}});
 if(path==='/app.css')return new Response(css,{headers:{...secureHeaders,'Content-Type':'text/css; charset=utf-8'}});
 if(path==='/app.js')return new Response(js,{headers:{...secureHeaders,'Content-Type':'text/javascript; charset=utf-8'}});
 if(path==='/'&&request.method==='GET')return new Response(html,{headers:{...secureHeaders,'Content-Type':'text/html; charset=utf-8'}});
 if(!path.startsWith('/api/'))return json({error:'Página não encontrada.'},404);
 const owner=request.headers.get('oai-authenticated-user-id'),email=request.headers.get('oai-authenticated-user-email');need(owner&&email,'Entre na sua conta para continuar.',401);
 need(env.DB&&env.BUCKET,'Armazenamento indisponível. Nenhuma alteração foi confirmada.',503);
 const writing=request.method!=='GET';if(writing){need(request.method==='POST','Método não permitido.',405);need(request.headers.get('Origin')===url.origin&&request.headers.get('X-Ritmo-Request')==='1'&&request.headers.get('Sec-Fetch-Site')!=='cross-site','Origem do pedido não autorizada.',403);}
 await rate(env.DB,owner,'all',240);if(writing)await rate(env.DB,owner,'write',60);
 const current=await account(env.DB,owner);
 if(path==='/api/state'&&request.method==='GET')return json({...publicState(current),user:{email},limits:LIMITS,tutor:{available:false,reason:'Tutor generativo indisponível nesta versão web. Não há modelo remoto contratado nem conexão com seu PC.'}});
 if(path==='/api/backup'&&request.method==='GET'){await rate(env.DB,owner,'backup',3);return new Response(JSON.stringify(await exportBackup(current,env.BUCKET,Date.now())),{headers:{...secureHeaders,'Content-Type':'application/json','Content-Disposition':'attachment; filename="ritmo-web-backup.json"'}});}
 const match=path.match(/^\/api\/(documents|download)\/([a-zA-Z0-9_-]+)$/);
 if(match&&request.method==='GET'){const doc=findDoc(current.state,match[2]);const object=await env.BUCKET.get(match[1]==='download'?doc.key:doc.textKey);need(object,'Arquivo temporariamente indisponível.',503);if(match[1]==='download')return new Response(object.body,{headers:{...secureHeaders,'Content-Type':'application/octet-stream','Content-Disposition':`attachment; filename="material.${doc.format}"; filename*=UTF-8''${encodeURIComponent(doc.name)}`}});return json({id:doc.id,name:doc.name,...await object.json()});}
 need(writing&&['/api/action','/api/upload','/api/restore'].includes(path),'Operação não encontrada.',404);
 let payload,bytes,name,parsed;
 if(path==='/api/upload'){
  await rate(env.DB,owner,'upload',6);need(request.headers.get('Content-Type')?.startsWith('multipart/form-data;'),'Envie um formulário de arquivo.');
  const raw=await bounded(request.body,LIMITS.file+16000);const form=await new Response(raw,{headers:{'Content-Type':request.headers.get('Content-Type')}}).formData();const file=form.get('file');need(file&&typeof file.arrayBuffer==='function','Selecione um arquivo.');bytes=new Uint8Array(await file.arrayBuffer());name=file.name;payload={request_id:form.get('request_id'),version:Number(form.get('version')),subject:form.get('subject'),name,hash:await sha(bytes)};
 }else payload=await body(request,path==='/api/restore'?32*1024*1024:24000);
 id(payload.request_id);need(Number.isSafeInteger(payload.version)&&payload.version>=0,'Versão ausente.');const hash=await fingerprint(payload);
 if(await prior(env.DB,owner,payload.request_id,hash))return json(publicState({...await account(env.DB,owner),replayed:true}));
 need(payload.version===current.version,'Outra aba alterou seus dados. Atualize e revise antes de reenviar.',409);
 let state,keys=[];
 try{
  if(path==='/api/action'){
   if(payload.action==='note.save'&&payload.document){const doc=findDoc(current.state,payload.document);const object=await env.BUCKET.get(doc.textKey);need(object,'Material indisponível.',503);const b=(await object.json()).blocks[payload.block];need(b&&typeof payload.quote==='string'&&(typeof b==='string'?b:b.text).includes(payload.quote),'A seleção não corresponde a este trecho.');}
   state=mutate(current.state,payload,Date.now());
  }else if(path==='/api/upload'){
   need(current.state.subjects.some(s=>s.id===payload.subject),'Matéria não encontrada.',404);need(current.state.documents.length<LIMITS.documents,'Limite de materiais atingido.',413);need(current.state.documents.reduce((n,d)=>n+d.size,0)+bytes.length<=LIMITS.storage,'Limite de 20 MiB de originais atingido.',413);
   parsed=await extract(bytes,name);const key=`${owner}/${makeId()}`;keys=[key,key+'.text'];await env.BUCKET.put(key,bytes);await env.BUCKET.put(key+'.text',JSON.stringify(parsed));state=structuredClone(current.state);state.documents.push({id:makeId(),subject:payload.subject,name,size:bytes.length,hash:payload.hash,format:parsed.format,blocks:parsed.blocks.length,created:Date.now(),key,textKey:key+'.text'});
  }else{
   need(current.state.subjects.length===0&&current.state.documents.length===0&&current.state.sessions.length===0&&current.state.notes.length===0,'Restaure somente numa conta vazia. Seus dados atuais foram preservados.',409);await rate(env.DB,owner,'restore',2);const restored=await prepareRestore(payload.backup,env.BUCKET,owner,Date.now());state=restored.state;keys=restored.keys;
  }
  const result=await commit(env.DB,owner,current,state,payload.request_id,hash);if(result.replayed){for(const key of keys)await env.BUCKET.delete(key).catch(()=>{});}return json(publicState(result));
 }catch(error){for(const key of keys)await env.BUCKET.delete(key).catch(()=>{});throw error;}
}
export default {async fetch(request,env){try{return await route(request,env);}catch(error){if(error instanceof Problem)return json({error:error.message},error.status);return json({error:'O serviço não conseguiu confirmar esta operação. Atualize o estado antes de repetir. Seu rascunho foi mantido.'},503);}}};
