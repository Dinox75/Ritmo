import {test} from 'node:test';import assert from 'node:assert/strict';
import {extract} from '../src/documents.mjs';import {zipSync,strToU8} from 'fflate';import {docx,pdf} from './helpers.mjs';
test('real parsers extract synthetic TXT, DOCX and PDF',async()=>{assert.equal((await extract(strToU8('Olá mundo.'),'a.txt')).blocks[0],'Olá mundo.');assert.match((await extract(docx(),'a.docx')).blocks[0],/Condições/);assert.match((await extract(pdf(),'a.pdf')).blocks[0].text,/Boolean/);});
test('invalid, encrypted/empty, XML entities and expanded DOCX blocked',async()=>{
 for(const [bytes,name] of [[strToU8('bad'),'x.pdf'],[strToU8('bad'),'x.docx'],[strToU8(''),'x.txt'],[new Uint8Array([0xff]),'x.txt'],[strToU8('x'),'../x.txt'],[new Uint8Array(2*1024*1024+1),'x.txt'],[zipSync({'word/document.xml':strToU8('<!DOCTYPE a [<!ENTITY e SYSTEM "file:///etc/passwd">]><a>&e;</a>')}),'x.docx'],[zipSync({'word/document.xml':new Uint8Array(9*1024*1024)}),'x.docx']])await assert.rejects(()=>extract(bytes,name));
});
test('forged ZIP expansion size aborts before processing later entries',async()=>{
 const bomb=zipSync({'word/document.xml':strToU8('a'.repeat(9*1024*1024)),'../later':strToU8('unsafe')});
 new DataView(bomb.buffer,bomb.byteOffset,bomb.byteLength).setUint32(22,0,true);
 await assert.rejects(()=>extract(bomb,'forged.docx'),error=>error.status===413);
});
