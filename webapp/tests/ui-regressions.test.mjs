import {test} from 'node:test';import {chromium,expect} from '@playwright/test';import {mkdtemp,rm} from 'node:fs/promises';import {tmpdir} from 'node:os';import {join} from 'node:path';import {startPreview} from '../scripts/dev.mjs';
async function setup(run){const dir=await mkdtemp(join(tmpdir(),'ritmo-draft-'));let p,b;try{p=await startPreview({persist:dir});b=await chromium.launch({channel:'msedge',headless:true});const c=await b.newContext(),page=await c.newPage();await page.goto(p.url+'/__qa/login?user=alice');await expect(page.locator('#app')).toBeVisible();for(const [i,name] of ['A','B'].entries())await c.request.post(p.url+'/api/action',{headers:{Origin:p.url,'X-Ritmo-Request':'1'},data:{version:i,request_id:crypto.randomUUID(),action:'subject.save',id:name,name,goal:60}});await page.reload();await expect(page.locator('#subjects article')).toHaveCount(2);await page.getByRole('button',{name:'Estudar esta matéria'}).first().click();await run(page);}finally{await b?.close();await p?.close();await rm(dir,{recursive:true,force:true});}}
test('a delayed note confirmation never clears newer local edits',()=>setup(async page=>{
 let release;const gate=new Promise(r=>release=r);let entered;const arrived=new Promise(r=>entered=r);await page.route('**/api/action',async route=>{const res=await route.fetch();entered();await gate;await route.fulfill({response:res});});
 try{await page.locator('#note-body').fill('Texto enviado');await page.locator('#save-note').click();await arrived;await page.locator('#note-body').fill('Texto posterior ainda não enviado');release();await expect(page.locator('#note-body')).toHaveValue('Texto posterior ainda não enviado');await expect(page.locator('#draft-status')).toContainText('alterações posteriores');}finally{release();}
}));
test('subject cards cannot reassign a local draft to another subject',()=>setup(async page=>{
 await page.locator('#note-body').fill('Nota pertence à matéria A');await page.getByRole('link',{name:'Início',exact:true}).click();await page.getByRole('button',{name:'Estudar esta matéria'}).last().click();await expect(page.locator('#study-subject')).toHaveValue('A');await expect(page.locator('#note-body')).toHaveValue('Nota pertence à matéria A');await expect(page.locator('#message')).toContainText('rascunho');
}));
test('a rejected upload reports completion of the failed attempt, not ongoing work',()=>setup(async page=>{
 await page.getByRole('link',{name:'Materiais',exact:true}).click();
 await page.locator('#upload-file').setInputFiles({name:'invalid.pdf',mimeType:'application/pdf',buffer:Buffer.from('not a PDF')});
 await page.locator('#upload-form button').click();await expect(page.locator('#message')).toContainText('Assinatura PDF inválida');
 await expect(page.locator('#upload-status')).toHaveText('Importação não concluída. Confira o erro e tente novamente.');
}));
test('a prepared backup is communicated as confirmed status, not an error',()=>setup(async page=>{
 await page.getByRole('link',{name:'Configurações',exact:true}).click();const file=page.waitForEvent('download');await page.locator('#export-backup').click();await file;
 await expect(page.locator('#message')).toHaveAttribute('role','status');await expect(page.locator('#message')).toHaveAttribute('data-tone','success');
}));
test('own activity view labels retention and shows only technical entries',()=>setup(async page=>{
 await page.getByRole('link',{name:'Configurações',exact:true}).click();await page.getByText('Atividades recentes da sua conta',{exact:true}).click();await page.getByRole('button',{name:'Consultar atividades',exact:true}).click();
 await expect(page.locator('#audit-events li')).toHaveCount(2);await expect(page.locator('#audit-events')).toContainText('subject.save');await expect(page.locator('#audit-status')).toContainText('30 dias');
}));
test('a 503 after note commit preserves the exact request for safe replay',()=>setup(async page=>{
 const ids=[];let first=true;
 await page.route('**/api/action',async route=>{ids.push(route.request().postDataJSON().request_id);const response=await route.fetch();if(first){first=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Resultado ainda não confirmado.'})});}else await route.fulfill({response});});
 await page.locator('#note-body').fill('Synthetic pending note');await page.locator('#save-note').click();await expect(page.locator('#message')).toContainText('Resultado ainda');await expect(page.locator('#pending-bar')).toBeVisible();
 await page.locator('#retry-request').click();await expect(page.locator('#pending-bar')).not.toBeVisible();expect(ids.length).toBe(2);expect(ids[0]).toBe(ids[1]);const data=await page.evaluate(async()=>await(await fetch('/api/state')).json());expect(data.state.notes.length).toBe(1);
}));
test('material loading is explicit and search waits for confirmed text',()=>setup(async page=>{
 const origin=new URL(page.url()).origin;const imported=await page.context().request.post(origin+'/api/upload',{headers:{Origin:origin,'X-Ritmo-Request':'1'},multipart:{version:'2',request_id:crypto.randomUUID(),subject:'A',file:{name:'loading.txt',mimeType:'text/plain',buffer:Buffer.from('Uma condição E. Uma condição OU.')}}});expect(imported.status(),await imported.text()).toBe(200);
 await page.goto(origin+'/#materiais');await page.reload();await expect(page.locator('#app')).toBeVisible();let release;const gate=new Promise(r=>release=r);await page.route('**/api/documents/*',async route=>{await gate;await route.continue();});
 try{await page.getByRole('button',{name:'Abrir leitura'}).click();await expect(page.locator('#reader-status')).toHaveText('Carregando material…');await expect(page.locator('#search')).toBeDisabled();release();await expect(page.locator('#reader')).toContainText('Uma condição E');await expect(page.locator('#search')).toBeEnabled();await page.locator('#search').fill('condição');await expect(page.locator('#reader mark')).toHaveCount(2);}finally{release();}
}));
