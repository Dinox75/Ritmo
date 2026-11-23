import {test} from 'node:test';import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';import {tmpdir} from 'node:os';import {join} from 'node:path';
import {runtime,client,command} from './helpers.mjs';import {emptyState,mutate} from '../src/domain.mjs';import {fingerprint} from '../src/store.mjs';
test('new audit migration preserves a legacy snapshot, receipt, original and linked note',async()=>{
 const root=await mkdtemp(join(tmpdir(),'ritmo-pi-migration-'));let mf;try{
  mf=await runtime(root,{through:0});let db=await mf.getD1Database('DB');const bucket=await mf.getR2Bucket('BUCKET'),now=Date.now()-10000;
  let state=mutate(emptyState(),{action:'subject.save',id:'s',name:'Legacy synthetic',goal:45},now);state=mutate(state,{action:'session.start',id:'session',subject:'s'},now+1000);
  await bucket.put('legacy/file',new TextEncoder().encode('Legacy reference text'));await bucket.put('legacy/file.text',JSON.stringify({format:'txt',blocks:['Legacy reference text'],pages:null}));
  state.documents.push({id:'doc',subject:'s',name:'legacy.txt',size:21,blocks:1,format:'txt',key:'legacy/file',textKey:'legacy/file.text',created:now});state=mutate(state,{action:'note.save',id:'note',subject:'s',body:'Retained synthetic note',document:'doc',block:0,quote:'Legacy'},now+2000);
  const replay=command(0,'subject.save',{id:'s',name:'Legacy synthetic',goal:45});await db.prepare('INSERT INTO accounts(owner,version,state) VALUES (?,?,?)').bind('legacy',7,JSON.stringify(state)).run();await db.prepare('INSERT INTO requests(owner,id,hash,version) VALUES (?,?,?,?)').bind('legacy',replay.request_id,await fingerprint(replay),1).run();
  await mf.dispose();mf=await runtime(root);db=await mf.getD1Database('DB');const raw=await db.prepare('SELECT version,state FROM accounts WHERE owner=?').bind('legacy').first();assert.equal(raw.version,7);assert.deepEqual(JSON.parse(raw.state),state);
  const call=client(mf,'legacy');assert.equal((await call('/api/documents/doc')).body.blocks[0],'Legacy reference text');assert.equal((await call('/api/action',replay)).body.replayed,true);assert.equal((await call('/api/audit')).body.events.length,0);
  const response=await mf.dispatchFetch('https://ritmo.test/api/download/doc',{headers:{'oai-authenticated-user-id':'legacy','oai-authenticated-user-email':'legacy@synthetic.invalid'}});assert.equal(await response.text(),'Legacy reference text');
  assert.equal((await call('/api/action',command(7,'session.pause',{id:'session'}))).status,200);const log=(await call('/api/audit')).body.events;assert.equal(log.length,1);assert.equal(log[0].action,'session.pause');assert.equal((await call()).body.state.notes[0].body,'Retained synthetic note');
 }finally{await mf?.dispose();await rm(root,{recursive:true,force:true});}
});
