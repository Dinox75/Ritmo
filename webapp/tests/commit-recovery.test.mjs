import {test} from 'node:test';import assert from 'node:assert/strict';
import worker from '../dist/server/index.js';
import {runtime,client,command,upload} from './helpers.mjs';
test('a reply lost after a real commit never deletes a referenced R2 original',async()=>{
 const mf=await runtime();try{
  const db=await mf.getD1Database('DB'),bucket=await mf.getR2Bucket('BUCKET');
  const source=client(mf,'recovery-source');await source('/api/action',command(0,'subject.save',{id:'s',name:'Synthetic',goal:1}));await source('/api/upload',upload(1,'s',new TextEncoder().encode('Original preserved after reply loss'),'recovery.txt'));const backup=(await source('/api/backup')).body;
  for(const operation of ['upload','restore'])for(const receiptReadable of [true,false]){
   const owner=operation+(receiptReadable?'-lost-readable':'-lost-uncertain'),call=client(mf,owner);if(operation==='upload')assert.equal((await call('/api/action',command(0,'subject.save',{id:'s',name:'Synthetic',goal:1}))).status,200);
   let committed=false;
   const wrapped={prepare(sql){if(committed&&!receiptReadable&&sql.startsWith('SELECT hash,version FROM requests'))throw Error('synthetic receipt read unavailable');return db.prepare(sql);},async batch(statements){const result=await db.batch(statements);committed=true;throw Error('synthetic reply lost after confirmed real D1 batch');}};
   const form=operation==='upload'?upload(1,'s',new TextEncoder().encode('Original preserved after reply loss'),'recovery.txt'):{request_id:crypto.randomUUID(),version:0,backup};const path='/api/'+operation;const request=new Request('https://ritmo.test'+path,{method:'POST',headers:{Origin:'https://ritmo.test','X-Ritmo-Request':'1','oai-authenticated-user-id':owner,'oai-authenticated-user-email':owner+'@synthetic.invalid',...(operation==='restore'?{'Content-Type':'application/json'}:{})},body:operation==='upload'?form:JSON.stringify(form)});
   const response=await worker.fetch(request,{DB:wrapped,BUCKET:bucket});assert.equal(response.status,receiptReadable?200:503);
   const state=(await call()).body;assert.equal(state.version,operation==='upload'?2:1);assert.equal(state.state.documents.length,1);const doc=state.state.documents[0];
   const stored=await mf.dispatchFetch('https://ritmo.test/api/download/'+doc.id,{headers:{'oai-authenticated-user-id':owner,'oai-authenticated-user-email':owner+'@synthetic.invalid'}});assert.equal(stored.status,200);assert.equal(await stored.text(),'Original preserved after reply loss');
   const event=operation==='upload'?'material.import':'backup.restore';assert.equal((await call('/api/audit')).body.events.filter(e=>e.action===event).length,1);
   const replay=await call(path,form);assert.equal(replay.status,200);assert.equal(replay.body.replayed,true);assert.equal((await call('/api/audit')).body.events.filter(e=>e.action===event).length,1);
  }
 }finally{await mf.dispose();}
});
