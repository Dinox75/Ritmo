import {test} from 'node:test';
import assert from 'node:assert/strict';
import {emptyState, mutate, totals} from '../src/domain.mjs';
import {prepareRestore} from '../src/backup.mjs';

test('server events separate focus and pause, and keep running after disconnect',()=>{
 let s=emptyState(); s=mutate(s,{action:'subject.save',id:'math',name:'Lógica',goal:90},1000);
 s=mutate(s,{action:'session.start',id:'s1',subject:'math'},2000);
 assert.equal(totals(s.sessions[0],12000).focus,10000);
 s=mutate(s,{action:'session.pause',id:'s1'},12000);
 s=mutate(s,{action:'session.resume',id:'s1'},17000);
 s=mutate(s,{action:'session.finish',id:'s1'},25000);
 assert.deepEqual(totals(s.sessions[0],99999),{focus:18000,pause:5000});
 assert.equal(s.sessions[0].status,'complete');
});
test('one active session, valid state transitions, bounds and ownership references',()=>{
 let s=mutate(emptyState(),{action:'subject.save',id:'a',name:'A',goal:60},1);
 assert.throws(()=>mutate(s,{action:'session.start',id:'s',subject:'other'},2));
 s=mutate(s,{action:'session.start',id:'s',subject:'a'},3);
 assert.throws(()=>mutate(s,{action:'session.start',id:'s2',subject:'a'},4));
 assert.throws(()=>mutate(s,{action:'session.resume',id:'s'},4));
 assert.throws(()=>mutate(s,{action:'subject.save',id:'a',name:'A',goal:-1},5));
 assert.throws(()=>mutate(s,{action:'note.save',id:'n',subject:'a',body:'x',document:'foreign',block:0,quote:'x'},5));
});
test('specific anchor must actually exist; plain text stays plain',()=>{
 let s=mutate(emptyState(),{action:'subject.save',id:'a',name:'<script>',goal:0},1);
 s.documents.push({id:'d',subject:'a',blocks:1});
 assert.throws(()=>mutate(s,{action:'note.save',id:'n',subject:'a',body:'x',document:'d',block:8,quote:'x'},5));
 s=mutate(s,{action:'note.save',id:'n',subject:'a',body:'<img onerror=x>',document:null,quote:'',block:null},5);
 assert.equal(s.notes[0].body,'<img onerror=x>');
});
test('event cap never traps an open session: finishing stays possible',()=>{
 let s=mutate(emptyState(),{action:'subject.save',id:'a',name:'A',goal:1},1);s=mutate(s,{action:'session.start',id:'s',subject:'a'},2);
 s.sessions[0].events=Array.from({length:1000},(_,i)=>({kind:i%2?'pause':'focus',at:i+2}));s.sessions[0].status='pause';
 assert.throws(()=>mutate(s,{action:'session.resume',id:'s'},1002));
 const done=mutate(s,{action:'session.finish',id:'s'},1002);assert.equal(done.sessions[0].status,'complete');
});
test('restore freezes elapsed focus and excludes backup/restore downtime from pause',async()=>{
 let state=mutate(emptyState(),{action:'subject.save',id:'a',name:'A',goal:1},1);state=mutate(state,{action:'session.start',id:'s',subject:'a'},10);
 const result=await prepareRestore({format:'ritmo-web',version:1,exported:100,state,files:[]},{},'test',100000);
 assert.deepEqual(totals(result.state.sessions[0],100000),{focus:90,pause:0});assert.deepEqual(totals(result.state.sessions[0],100500),{focus:90,pause:500});
});
