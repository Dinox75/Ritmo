const $ = id => document.getElementById(id);
const names = {collect:'Coletar',prepare:'Preparar',validate:'Validar',diagnose:'Diagnosticar',train:'Treinar',evaluate:'Avaliar',report:'Relatório'};
const labels = {waiting:'Aguardando',running:'Trabalhando',blocked:'Bloqueado',stale:'Sem sinal recente',failed:'Falhou',completed:'Concluído',interrupted:'Interrompido'};
function node(tag,text,cls){const el=document.createElement(tag);el.textContent=text;if(cls)el.className=cls;return el;}
function pretty(value){return JSON.stringify(value,null,2);}
async function refresh(){try{
 const response=await fetch('/api',{cache:'no-store'});if(!response.ok)throw Error('Painel indisponível. Confira o processo e o túnel SSH.');
 const data=await response.json(),s=data.state,c=s.counts||{};$('error').textContent='';
 $('status').textContent=labels[s.status]||s.status;$('simulation').hidden=!s.simulation;
 $('message').textContent=s.message||'Aguardando';$('action').textContent=s.action||'';
 $('phases').replaceChildren(...Object.entries(names).map(([key,name])=>{const el=node('div',name,'phase'+(key===s.phase?' active':''));el.append(node('small',labels[s.phases?.[key]]||'Aguardando'));return el;}));
 $('metrics').replaceChildren(...[['Fontes lidas',c.sources_read||0],['Gerados',c.generated||0],['Aprovados na triagem',c.approved||0],['Descartados',c.rejected||0]].map(([name,n])=>{const el=node('div',name,'metric');el.append(node('strong',n));return el;}));
 $('heartbeat').textContent=`Último sinal há ${s.age_seconds} s · tempo total ${Math.round(s.elapsed_seconds/60)} min`;
 $('resources').textContent=s.resources?.gpu||'VRAM ainda não medida.';
 const t=data.training;$('checkpoint').textContent='Último checkpoint: '+(t.last_checkpoint||'nenhum');$('progress').max=t.max_steps||10;$('progress').value=t.step||0;$('training').textContent=Object.keys(t).length?pretty(t):'Nenhum treino real registrado.';
 $('approval').textContent=s.training_real?(s.approval||'Inconclusivo'):'Não avaliado — sem treino real';
 $('decision').textContent=data.comparison?.conclusion||'Não há pares de um adaptador treinado. Triagem e geração não demonstram aprendizagem.';
 $('criteria').textContent=c.missing?'Faltam para os mínimos 200/30/30:\n'+pretty(c.missing):'A prova e os critérios são fixados antes da geração.';
 const table=node('table',''),head=node('tr','');for(const x of ['Fonte / categoria','Autoria / licença','Acesso / hash'])head.append(node('th',x));table.append(head);
 for(const source of data.sources.accepted){const row=node('tr','');const first=node('td',source.title+' · '+source.category+' ');const link=node('a','Abrir fonte');link.href=source.url;link.target='_blank';link.rel='noreferrer';first.append(link);const license=node('td',source.author+' · ');const a=node('a',source.license);a.href=source.license_url;a.target='_blank';a.rel='noreferrer';license.append(a);row.append(first,license,node('td',(source.accessed||'local')+' · '+source.sha256));table.append(row);}
 $('sources').replaceChildren(table,...data.sources.refused.map(x=>node('p',`Recusada: ${x.id} — ${x.reason}`)));
 $('reasons').textContent=pretty(c.reasons||{});
 $('candidates').replaceChildren(...data.candidates.map(item=>{const d=node('details','');d.append(node('summary',`#${item.index+1} · ${item.accepted?'Aprovado na triagem':'Descartado'} · ${item.seconds}s · ${(item.reasons||[]).join(', ')}`));d.append(node('pre',pretty({candidate:item.candidate,judge:item.judge,raw:item.raw})));return d;}));
 if(data.comparison){$('comparison').replaceChildren(...data.comparison.pairs.map(pair=>{const d=node('details','');d.append(node('summary',`${pair.id} · ${pair.category} · ${pair.change||'inconclusivo'}`),node('p',pair.prompt),node('p','Esperado: '+pair.expected));const grid=node('div','','pair');for(const key of ['base','adapter']){const col=node('div','');col.append(node('h3',key==='base'?'Modelo base':'Adaptador'),node('pre',pair[key]?.raw||'Não executado'),node('p',pretty(pair[key]?.judgment)));grid.append(col);}d.append(grid);return d;}));}
 }catch(error){$('error').textContent=error.message;$('status').textContent='Sem conexão';}}
refresh();setInterval(refresh,3000);
