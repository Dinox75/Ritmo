import {emptyState,need,Problem} from './domain.mjs';
import {sha} from './documents.mjs';
import {auditInsert,auditPrune} from './audit.mjs';
export const makeId=()=>crypto.randomUUID();
export class CommitOutcomeUnknown extends Error {}
export async function account(db,owner){await db.prepare('INSERT OR IGNORE INTO accounts (owner,version,state) VALUES (?,0,?)').bind(owner,JSON.stringify(emptyState())).run();const row=await db.prepare('SELECT version,state FROM accounts WHERE owner=?').bind(owner).first();return {version:row.version,state:JSON.parse(row.state)};}
export async function rate(db,owner,kind,limit,now=Date.now()){
 const row=await db.prepare('INSERT INTO rates (owner,bucket,count,reset) VALUES (?,?,1,?) ON CONFLICT(owner,bucket) DO UPDATE SET count=CASE WHEN reset<=? THEN 1 ELSE count+1 END, reset=CASE WHEN reset<=? THEN ? ELSE reset END RETURNING count').bind(owner,kind,now+60000,now,now,now+60000).first();need(row.count<=limit,'Muitas requisições. Aguarde um minuto.',429);
}
export async function fingerprint(value){return sha(new TextEncoder().encode(JSON.stringify(value)));}
export async function prior(db,owner,requestId,hash){const old=await db.prepare('SELECT hash,version FROM requests WHERE owner=? AND id=?').bind(owner,requestId).first();if(old){need(old.hash===hash,'A chave deste envio já foi usada com outro conteúdo.',409);return old;}return null;}
export async function commit(db,owner,before,state,requestId,hash,audit){
 need(JSON.stringify(state).length<1500000,'Dados da conta excedem o limite.',413);
 const results=await db.batch([
  db.prepare('UPDATE accounts SET version=version+1,state=? WHERE owner=? AND version=?').bind(JSON.stringify(state),owner,before.version),
  db.prepare('INSERT INTO requests (owner,id,hash,version) SELECT ?,?,?,? WHERE changes()=1').bind(owner,requestId,hash,before.version+1),
  auditInsert(db,{owner,...audit,correlation:requestId,version:before.version+1},true),
  auditPrune(db,owner)
 ]).catch(async error=>{
  let receipt;
  try{receipt=await prior(db,owner,requestId,hash);}catch(readError){if(readError instanceof Problem)throw readError;throw new CommitOutcomeUnknown();}
  if(receipt)return null;
  throw error;
 });
 if(!results){try{return {replayed:true,...await account(db,owner)};}catch{throw new CommitOutcomeUnknown();}}
 if(results[0].meta.changes!==1){if(await prior(db,owner,requestId,hash))return {replayed:true,...await account(db,owner)};throw new Problem('Outra aba alterou seus dados. Atualize e revise antes de reenviar.',409);}
 return {version:before.version+1,state};
}
export function publicState(result,now=Date.now()){return {...result,state:{...result.state,documents:result.state.documents.map(({key,textKey,...doc})=>doc)},now};}
