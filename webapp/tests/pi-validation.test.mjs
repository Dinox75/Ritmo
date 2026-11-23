import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {runtime,client,command} from './helpers.mjs';
let mf;
before(async()=>{mf=await runtime();});after(async()=>{await mf?.dispose();});
test('invalid JSON shapes return 400 instead of reporting a storage outage',async()=>{
 for(const payload of ['null','[]','"invalid"']){
  const res=await mf.dispatchFetch('https://ritmo.test/api/action',{method:'POST',headers:{'oai-authenticated-user-id':'synthetic-shape','oai-authenticated-user-email':'shape@synthetic.invalid','Origin':'https://ritmo.test','X-Ritmo-Request':'1','Content-Type':'application/json'},body:payload});
  assert.equal(res.status,400);assert.deepEqual((await client(mf,'synthetic-shape')()).body.state.subjects,[]);
 }
});
test('direct foreign note IDs and backup selectors never expose or delete another account',async()=>{
 const a=client(mf,'isolation-a'),b=client(mf,'isolation-b');await a('/api/action',command(0,'subject.save',{id:'a',name:'A',goal:0}));await a('/api/action',command(1,'note.save',{id:'foreign-note',subject:'a',body:'SYNTHETIC_PRIVATE_CANARY'}));
 assert.equal((await b('/api/action',command(0,'note.delete',{id:'foreign-note'}))).status,404);assert.equal((await a()).body.state.notes.length,1);
 const backup=await b('/api/backup?owner=isolation-a');assert.equal(backup.status,200);assert.equal(backup.body.state.notes.length,0);assert.equal(JSON.stringify(backup.body).includes('SYNTHETIC_PRIVATE_CANARY'),false);assert.equal((await b('/api/backup/isolation-a')).status,404);
});
