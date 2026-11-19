import {test} from 'node:test';import assert from 'node:assert/strict';import {mkdtemp,rm} from 'node:fs/promises';import {tmpdir} from 'node:os';import {join} from 'node:path';
import {runtime,client,command,upload} from './helpers.mjs';
test('persist through worker restart and restore an open focus as frozen pause in another instance',async()=>{
 const root=await mkdtemp(join(tmpdir(),'ritmo-web-'));let mf,target;try{
  mf=await runtime(root+'/source');let call=client(mf);await call('/api/action',command(0,'subject.save',{id:'a',name:'Sintética',goal:30}));let res=await call('/api/upload',upload(1,'a',new TextEncoder().encode('Texto sintético.'),'a.txt'));assert.equal(res.status,200);res=await call('/api/action',command(2,'session.start',{id:'s',subject:'a'}));assert.equal(res.status,200);const doc=res.body.state.documents[0].id;await mf.dispose();mf=await runtime(root+'/source');call=client(mf);const reopened=await call();assert.equal(reopened.body.state.sessions[0].status,'focus');assert.equal((await call('/api/documents/'+doc)).status,200);
  const backup=(await call('/api/backup')).body;target=await runtime(root+'/target');const restore=client(target);res=await restore('/api/restore',{version:0,request_id:crypto.randomUUID(),backup});assert.equal(res.status,200);assert.equal(res.body.state.sessions[0].status,'pause');assert.equal(res.body.state.sessions[0].events.at(-1).at,backup.exported);
 }finally{await mf?.dispose();await target?.dispose();await rm(root,{recursive:true,force:true});}
});
