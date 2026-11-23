import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {runtime,client,command,upload} from './helpers.mjs';
let mf,db;
before(async()=>{mf=await runtime();db=await mf.getD1Database('DB');});after(async()=>{await mf?.dispose();});
test('business audit is atomic, correlated and not duplicated by replay or conflict',async()=>{
 const call=client(mf,'audit-flow');let r=await call('/api/action',command(0,'subject.save',{id:'subject',name:'SYNTHETIC_NAME_NOT_IN_AUDIT',goal:30}));assert.equal(r.status,200);
 const start=command(r.body.version,'session.start',{id:'session',subject:'subject'});
 const results=await Promise.all([call('/api/action',start),call('/api/action',start)]);assert.deepEqual(results.map(r=>r.status),[200,200]);
 let v=results[0].body.version;
 for(const action of ['session.pause','session.resume','session.finish']){r=await call('/api/action',command(v,action,{id:'session'}));assert.equal(r.status,200);v=r.body.version;}
 assert.equal((await call('/api/action',command(0,'session.start',{id:'stale',subject:'subject'}))).status,409);
 const log=await call('/api/audit');assert.equal(log.status,200);const entries=log.body.events;
 assert.equal(entries.filter(e=>e.action==='session.start').length,1);assert.equal(entries.length,5);
 const event=entries.find(e=>e.action==='session.start');assert.equal(event.correlation,start.request_id);assert.equal(event.resource,'session');assert.equal(event.result,'committed');assert.equal(event.owner,'audit-flow');assert.ok(Number.isSafeInteger(event.at));assert.ok(event.id);assert.equal(JSON.stringify(entries).includes('SYNTHETIC_NAME_NOT_IN_AUDIT'),false);
});
test('material, note deletion, prepared export and restore contain only technical metadata',async()=>{
 const call=client(mf,'audit-docs');await call('/api/action',command(0,'subject.save',{id:'s',name:'Source',goal:0}));
 let r=await call('/api/upload',upload(1,'s',new TextEncoder().encode('PRIVATE_MATERIAL_CANARY'),'PRIVATE_FILENAME_CANARY.txt'));assert.equal(r.status,200);const doc=r.body.state.documents[0];
 r=await call('/api/action',command(r.body.version,'note.save',{id:'note',subject:'s',body:'PRIVATE_NOTE_CANARY',document:doc.id,block:0,quote:'PRIVATE_MATERIAL_CANARY'}));assert.equal(r.status,200);
 r=await call('/api/action',command(r.body.version,'note.delete',{id:'note'}));assert.equal(r.status,200);const version=r.body.version;
 const backup=await call('/api/backup');assert.equal(backup.status,200);assert.equal((await call()).body.version,version);
 const log=(await call('/api/audit')).body.events;assert.ok(log.some(e=>e.action==='material.import'&&e.resource===doc.id));assert.ok(log.some(e=>e.action==='note.delete'&&e.resource==='note'));assert.ok(log.some(e=>e.action==='backup.prepared'&&e.version===version&&e.result==='prepared'));
 const serialized=JSON.stringify(log);for(const canary of ['PRIVATE_MATERIAL_CANARY','PRIVATE_FILENAME_CANARY','PRIVATE_NOTE_CANARY','synthetic.invalid','base64','cookie','token'])assert.equal(serialized.includes(canary),false);
 const restored=client(mf,'audit-restored');assert.equal((await restored('/api/restore',{request_id:crypto.randomUUID(),version:0,backup:backup.body})).status,200);const targetLog=(await restored('/api/audit')).body.events;assert.equal(targetLog.length,1);assert.equal(targetLog[0].action,'backup.restore');assert.equal(targetLog[0].owner,'audit-restored');
});
test('audit failure rolls back state and receipt and cleans provisional R2 objects',async()=>{
 const call=client(mf,'audit-fail');await call('/api/action',command(0,'subject.save',{id:'s',name:'S',goal:1}));
 await db.prepare("CREATE TRIGGER fail_audit BEFORE INSERT ON audit_events WHEN NEW.owner='audit-fail' BEGIN SELECT RAISE(ABORT, 'private path C:/secret TOKEN_DO_NOT_LEAK'); END").run();
 const body=command(1,'session.start',{id:'session',subject:'s'});const r=await call('/api/action',body);assert.equal(r.status,503);assert.equal(JSON.stringify(r.body).includes('TOKEN_DO_NOT_LEAK'),false);
 let state=await call();assert.equal(state.body.version,1);assert.equal(state.body.state.sessions.length,0);assert.equal(await db.prepare('SELECT id FROM requests WHERE owner=? AND id=?').bind('audit-fail',body.request_id).first(),null);
 assert.equal((await call('/api/upload',upload(1,'s',new TextEncoder().encode('provisional text')))).status,503);const bucket=await mf.getR2Bucket('BUCKET');assert.equal((await bucket.list({prefix:'audit-fail/'})).objects.length,0);
 assert.equal((await call('/api/backup')).status,503);assert.equal((await call()).body.version,1);await db.prepare('DROP TRIGGER fail_audit').run();
});
test('audit is private, bounded and has stable pagination even for identical instants',async()=>{
 const owner='audit-page',call=client(mf,owner),now=Date.now();await call();
 await db.batch(Array.from({length:6},(_,i)=>db.prepare('INSERT INTO audit_events (id,owner,at,action,result,resource,correlation,version) VALUES (?,?,?,?,?,?,?,?)').bind('tie-'+i,owner,now,'note.delete','committed','n','c-'+i,0)));
 const first=await call('/api/audit?limit=2');assert.equal(first.status,200);assert.equal(first.body.events.length,2);assert.ok(first.body.next);
 const second=await call('/api/audit?limit=2&before='+encodeURIComponent(first.body.next));assert.equal(second.body.events.length,2);assert.equal(new Set([...first.body.events,...second.body.events].map(e=>e.id)).size,4);
 assert.equal((await client(mf,'audit-other')('/api/audit')).body.events.length,0);assert.equal((await call('/api/audit?owner=audit-other')).status,400);assert.equal((await call('/api/audit?limit=51')).status,400);assert.equal((await call('/api/audit?before=invalid')).status,400);assert.equal((await client(mf,null)('/api/audit')).status,401);
});
test('audit hides expired rows and prunes to 200 upon a successful new write',async()=>{
 const owner='audit-retention',call=client(mf,owner),now=Date.now();await call();const insert=(id,at)=>db.prepare('INSERT INTO audit_events (id,owner,at,action,result,resource,correlation,version) VALUES (?,?,?,?,?,?,?,?)').bind(id,owner,at,'note.delete','committed','n',id,0);
 await db.batch([insert('expired',now-31*86400000),...Array.from({length:205},(_,i)=>insert('fresh-'+i,now+i))]);
 const view=await call('/api/audit?limit=50');assert.equal(view.body.events.length,50);assert.equal(view.body.events.some(e=>e.id==='expired'),false);
 assert.equal((await call('/api/action',command(0,'theme',{theme:'light'}))).status,200);
 const count=await db.prepare('SELECT count(*) AS n FROM audit_events WHERE owner=?').bind(owner).first();assert.equal(count.n,200);assert.equal(await db.prepare('SELECT id FROM audit_events WHERE owner=? AND id=?').bind(owner,'expired').first(),null);
});
test('concurrent distinct starts commit one business event and a completed session rejects changes',async()=>{
 const call=client(mf,'audit-race');await call('/api/action',command(0,'subject.save',{id:'s',name:'Race',goal:0}));
 const results=await Promise.all(['one','two'].map(key=>call('/api/action',command(1,'session.start',{id:key,subject:'s'}))));assert.deepEqual(results.map(r=>r.status).sort(),[200,409]);
 let state=(await call()).body;const session=state.state.sessions[0];assert.equal((await call('/api/audit')).body.events.filter(e=>e.action==='session.start').length,1);
 let done=await call('/api/action',command(state.version,'session.finish',{id:session.id}));assert.equal(done.status,200);
 for(const action of ['session.pause','session.resume','session.finish'])assert.equal((await call('/api/action',command(done.body.version,action,{id:session.id}))).status,409);
 assert.equal((await call('/api/audit')).body.events.length,3);
});
