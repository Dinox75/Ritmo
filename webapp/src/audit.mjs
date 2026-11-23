import {need,id} from './domain.mjs';

export const AUDIT_RETENTION={count:200,days:30,page:20,maxPage:50};
const ACTIONS=new Set(['subject.save','session.start','session.pause','session.resume','session.finish','material.import','note.save','note.delete','theme','backup.restore','backup.prepared']);
const cutoff=now=>now-AUDIT_RETENTION.days*86400000;

// Metadata only. Never accept the original request or content as an argument.
export function auditInsert(db,{owner,action,resource,correlation,version,at=Date.now(),result='committed'},conditional=false){
 need(ACTIONS.has(action)&&['committed','prepared'].includes(result),'Metadados de auditoria inválidos.');
 id(resource);id(correlation);need(Number.isSafeInteger(version)&&version>=0,'Versão de auditoria inválida.');
 return db.prepare('INSERT INTO audit_events (id,owner,at,action,result,resource,correlation,version) SELECT ?,?,?,?,?,?,?,?'+(conditional?' WHERE changes()=1':''))
  .bind(crypto.randomUUID(),owner,at,action,result,resource,correlation,version);
}
export function auditPrune(db,owner,now=Date.now()){
 // changes() observes the preceding audit INSERT, not a successful zero-row CAS.
 return db.prepare('DELETE FROM audit_events WHERE owner=? AND changes()=1 AND (at<? OR id NOT IN (SELECT id FROM audit_events WHERE owner=? ORDER BY at DESC,id DESC LIMIT 200))')
  .bind(owner,cutoff(now),owner);
}
export async function recordPreparedBackup(db,owner,version){
 const now=Date.now();
 await db.batch([auditInsert(db,{owner,action:'backup.prepared',resource:'account',correlation:crypto.randomUUID(),version,at:now,result:'prepared'}),auditPrune(db,owner,now)]);
}
export async function auditPage(db,owner,params,now=Date.now()){
 need([...params.keys()].every(key=>['limit','before'].includes(key))&&params.getAll('limit').length<=1&&params.getAll('before').length<=1,'Parâmetro de auditoria inválido.');
 const limit=params.has('limit')?Number(params.get('limit')):AUDIT_RETENTION.page;
 need(Number.isInteger(limit)&&limit>0&&limit<=AUDIT_RETENTION.maxPage,'Limite de consulta deve estar entre 1 e 50.');
 let before=null;
 if(params.has('before')){
  const match=/^(\d{1,16}):([A-Za-z0-9_-]{1,80})$/.exec(params.get('before'));
  need(match&&Number.isSafeInteger(Number(match[1])),'Cursor de auditoria inválido.');before={at:Number(match[1]),id:match[2]};
 }
 const where=before?' AND (at<? OR (at=? AND id<?))':'';
 const values=[owner,cutoff(now),...(before?[before.at,before.at,before.id]:[]),limit+1];
 const rows=(await db.prepare('SELECT id,owner,at,action,result,resource,correlation,version FROM audit_events WHERE owner=? AND at>=?'+where+' ORDER BY at DESC,id DESC LIMIT ?').bind(...values).all()).results;
 const more=rows.length>limit,events=rows.slice(0,limit),last=events.at(-1);
 return {events,next:more?`${last.at}:${last.id}`:null,retention:AUDIT_RETENTION};
}
