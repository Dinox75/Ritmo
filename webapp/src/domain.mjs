export class Problem extends Error { constructor(message,status=400){super(message);this.status=status;} }
export const LIMITS={file:2*1024*1024,storage:20*1024*1024,documents:50,subjects:50,notes:500,sessions:500,text:120000,pages:100,expanded:8*1024*1024};
export function need(ok,message,status=400){if(!ok)throw new Problem(message,status);}
export function text(value,max,label='Texto'){need(typeof value==='string'&&value.trim().length>0&&value.length<=max,`${label}: informe de 1 a ${max} caracteres.`);return value.trim();}
export function id(value){need(typeof value==='string'&&/^[a-zA-Z0-9_-]{1,80}$/.test(value),'Identificador inválido.');return value;}
export function emptyState(){return {subjects:[],sessions:[],documents:[],notes:[],theme:'dark'};}
export function totals(session,now){const result={focus:0,pause:0};for(let i=0;i<session.events.length;i++){const ev=session.events[i],end=session.events[i+1]?.at??(session.status==='complete'?ev.at:now);if(ev.kind==='focus'||ev.kind==='pause'){let duration=Math.max(0,end-ev.at);if(ev.kind==='pause')for(const gap of session.restoreGaps||[])duration-=Math.max(0,Math.min(end,gap.end)-Math.max(ev.at,gap.start));result[ev.kind]+=Math.max(0,duration);}}return result;}
export function mutate(before,body,now){
 const s=structuredClone(before);need(body&&typeof body==='object','Pedido inválido.');
 const action=body.action;
 if(action==='subject.save'){
  const key=id(body.id),name=text(body.name,100,'Matéria');need(Number.isInteger(body.goal)&&body.goal>=0&&body.goal<=10080,'Meta semanal inválida.');
  const found=s.subjects.find(x=>x.id===key);if(found)Object.assign(found,{name,goal:body.goal});else{need(s.subjects.length<LIMITS.subjects,'Limite de matérias atingido.',413);s.subjects.push({id:key,name,goal:body.goal,created:now});}
 }else if(action==='session.start'){
  need(s.subjects.some(x=>x.id===body.subject),'Matéria não encontrada.',404);need(!s.sessions.some(x=>x.status!=='complete'),'Já existe uma sessão aberta.',409);
  need(s.sessions.length<LIMITS.sessions,'Limite de 500 sessões: exporte um backup.',413);const key=id(body.id);need(!s.sessions.some(x=>x.id===key),'Sessão já existe.',409);
  s.sessions.push({id:key,subject:body.subject,status:'focus',started:now,ended:null,events:[{kind:'focus',at:now}]});
 }else if(['session.pause','session.resume','session.finish'].includes(action)){
  const item=s.sessions.find(x=>x.id===body.id);need(item,'Sessão não encontrada.',404);need(item.status!=='complete','Sessão já concluída.',409);
  const next=action==='session.pause'?'pause':action==='session.resume'?'focus':'complete';need(next!==item.status,'A sessão já está neste estado.',409);need(next==='complete'||item.events.length<1000,'Limite de eventos: conclua a sessão.',413);
  need(now>=item.events.at(-1).at,'Relógio do serviço indisponível; tente novamente.',503);item.events.push({kind:next,at:now});item.status=next;if(next==='complete')item.ended=now;
 }else if(action==='note.save'){
  const key=id(body.id);need(s.subjects.some(x=>x.id===body.subject),'Matéria não encontrada.',404);const note={id:key,subject:body.subject,body:text(body.body,10000,'Nota'),document:body.document??null,block:body.block??null,quote:body.quote??'',updated:now};
  if(note.document){const doc=s.documents.find(x=>x.id===note.document&&x.subject===note.subject);need(doc,'Material não encontrado.',404);need(Number.isInteger(note.block)&&note.block>=0&&note.block<doc.blocks,'Trecho não encontrado.');text(note.quote,2000,'Seleção');}else{note.block=null;note.quote='';}
  const old=s.notes.find(x=>x.id===key);if(old)Object.assign(old,note);else{need(s.notes.length<LIMITS.notes,'Limite de notas atingido.',413);s.notes.push(note);}
 }else if(action==='note.delete'){const index=s.notes.findIndex(x=>x.id===body.id);need(index>=0,'Nota não encontrada.',404);s.notes.splice(index,1);
 }else if(action==='theme'){need(['dark','light'].includes(body.theme),'Tema inválido.');s.theme=body.theme;
 }else throw new Problem('Ação não disponível.');
 need(JSON.stringify(s).length<1500000,'Limite de dados do piloto atingido. Exporte um backup.',413);return s;
}
