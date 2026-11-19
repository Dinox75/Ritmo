import {need,LIMITS,emptyState,mutate,totals} from './domain.mjs';
import {base64,from64,sha,extract} from './documents.mjs';
import {makeId} from './store.mjs';

export async function exportBackup(current,bucket,now){
 const files=[];for(const doc of current.state.documents){const object=await bucket.get(doc.key);need(object,'Um original não está disponível; backup incompleto, tente novamente.',503);const bytes=new Uint8Array(await object.arrayBuffer());need(await sha(bytes)===doc.hash,'Original não confere com o hash registrado.',503);files.push({id:doc.id,base64:base64(bytes),hash:doc.hash});}
 return {format:'ritmo-web',version:1,exported:now,state:{...current.state,documents:current.state.documents.map(({key,textKey,...d})=>d)},files};
}
export async function prepareRestore(backup,bucket,owner,now){
 need(backup?.format==='ritmo-web'&&backup.version===1,'Backup incompatível. Use uma exportação Ritmo web versão 1.');need(Number.isSafeInteger(backup.exported)&&backup.exported>0&&backup.exported<=now+300000,'Data do backup inválida.');
 const raw=backup.state;need(raw&&Array.isArray(raw.subjects)&&Array.isArray(raw.sessions)&&Array.isArray(raw.notes)&&Array.isArray(raw.documents)&&Array.isArray(backup.files),'Estrutura do backup inválida.');
 need(raw.subjects.length<=LIMITS.subjects&&raw.notes.length<=LIMITS.notes&&raw.sessions.length<=LIMITS.sessions&&raw.documents.length<=LIMITS.documents,'Backup excede as cotas.',413);need(backup.files.length===raw.documents.length,'Lista de originais incompleta.');
 let state=emptyState();const remap=new Map(),keys=[];function assign(old){need(typeof old==='string'&&!remap.has(old),'IDs ausentes ou duplicados no backup.');const v=makeId();remap.set(old,v);return v;}
 try{
  for(const sub of raw.subjects)state=mutate(state,{action:'subject.save',id:assign(sub.id),name:sub.name,goal:sub.goal},now);
  let sum=0;for(const doc of raw.documents){const subject=remap.get(doc.subject);need(subject,'Matéria do material ausente.');const file=backup.files.filter(f=>f.id===doc.id);need(file.length===1,'Original ausente ou duplicado.');const bytes=from64(file[0].base64);sum+=bytes.length;need(sum<=LIMITS.storage,'Backup excede o armazenamento.',413);const hash=await sha(bytes);need(hash===file[0].hash&&hash===doc.hash,'Hash do original incorreto.');const parsed=await extract(bytes,doc.name);const key=`${owner}/${makeId()}`;keys.push(key,key+'.text');await bucket.put(key,bytes);await bucket.put(key+'.text',JSON.stringify(parsed));state.documents.push({id:assign(doc.id),subject,name:doc.name,size:bytes.length,format:parsed.format,blocks:parsed.blocks.length,created:now,key,textKey:key+'.text',hash});}
  for(const note of raw.notes){const document=note.document?remap.get(note.document):null;need(!note.document||document,'Nota aponta para material inexistente.');if(document){const doc=state.documents.find(d=>d.id===document);const parsed=await (await bucket.get(doc.textKey)).json();const b=parsed.blocks[note.block];need(b&&((typeof b==='string'?b:b.text).includes(note.quote)),'Seleção da nota não corresponde ao original.');}
   state=mutate(state,{action:'note.save',id:assign(note.id),subject:remap.get(note.subject),body:note.body,document,block:note.block,quote:note.quote},now);}
  const intervals=[];for(const s of raw.sessions){need(state.subjects.some(sub=>sub.id===remap.get(s.subject)),'Sessão sem matéria.');need(Array.isArray(s.events)&&s.events.length>0&&s.events.length<=1001,'Eventos da sessão inválidos.');let prev=null,at=-1;
   for(const e of s.events){need(Number.isSafeInteger(e.at)&&e.at>=0&&e.at>=at&&e.at<=backup.exported,'Instante de evento inválido.');need(['focus','pause','complete'].includes(e.kind)&&e.kind!==prev&&prev!=='complete'&&(!prev?e.kind==='focus':true),'Sequência de eventos inválida.');at=e.at;prev=e.kind;}
   need(s.status===prev&&s.started===s.events[0].at&&(prev==='complete'?s.ended===at:s.ended===null),'Estado e eventos divergem.');const item={id:assign(s.id),subject:remap.get(s.subject),started:s.started,ended:s.ended,status:s.status,events:structuredClone(s.events)};intervals.push([s.started,prev==='complete'?at:backup.exported]);
   const gaps=s.restoreGaps??[];need(Array.isArray(gaps)&&gaps.length<=100,'Intervalos de restauração inválidos.');let lastGap=0;for(const gap of gaps){need(Number.isSafeInteger(gap.start)&&Number.isSafeInteger(gap.end)&&gap.start>=lastGap&&gap.end>=gap.start&&gap.end<=backup.exported,'Intervalo de restauração inválido.');need(item.events.some((e,i)=>e.kind==='pause'&&e.at<=gap.start&&(item.events[i+1]?.at??backup.exported)>=gap.end),'Intervalo de restauração fora de uma pausa.');lastGap=gap.end;}
   item.restoreGaps=structuredClone(gaps);
   // Freeze focus at export; exclude the time spent outside this instance.
   if(item.status!=='complete'){need(item.restoreGaps.length<100,'Limite de restaurações de uma sessão aberta. Conclua-a antes de exportar.');if(item.status==='focus')item.events.push({kind:'pause',at:backup.exported});item.status='pause';item.restoreGaps.push({start:backup.exported,end:now});}
   state.sessions.push(item);
  }
  intervals.sort((a,b)=>a[0]-b[0]);for(let i=1;i<intervals.length;i++)need(intervals[i][0]>=intervals[i-1][1],'Sessões sobrepostas no backup.');need(state.sessions.filter(s=>s.status!=='complete').length<=1,'Mais de uma sessão aberta.');
  state.theme=['dark','light'].includes(raw.theme)?raw.theme:'dark';need(JSON.stringify(state).length<1500000,'Backup excede o limite de registros.',413);return {state,keys};
 }catch(error){for(const key of keys)await bucket.delete(key).catch(()=>{});throw error;}
}
