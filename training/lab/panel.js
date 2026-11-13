const $ = id => document.getElementById(id);
const names = {collect:'Coletar',prepare:'Preparar',validate:'Validar',diagnose:'Diagnosticar',train:'Treinar',evaluate:'Avaliar',report:'Relatório'};
const labels = {waiting:'Aguardando',running:'Trabalhando',blocked:'Bloqueado',stale:'Sem sinal recente',failed:'Falhou',completed:'Concluído',interrupted:'Interrompido'};
function node(tag,text,cls){const el=document.createElement(tag);el.textContent=text;if(cls)el.className=cls;return el;}
function pretty(value){return JSON.stringify(value,null,2);}
const kindNames={hint:'Dica',correction:'Correção',explanation:'Explicação'};
const reasonNames={pergunta_sem_verificacao_contextual:'Pergunta genérica, repetitiva ou sem pedir raciocínio',juiz_nao_executado_pretriagem:'Juiz não chamado: falha em regra anterior',explicacao_sem_exemplo_distinto:'Explicação sem exemplo distinto',correcao_sem_acerto_e_limite:'Correção sem reconhecer acerto e limite',correcao_sem_identificar_erro:'Correção sem identificar o erro',correcao_sem_fundamento:'Correção sem explicar por quê',dica_entrega_solucao:'Possível antecipação da resposta (detector conservador)',correcao_sem_acerto_especifico:'Correção sem reconhecer o acerto específico',correcao_sem_acerto_parcial:'Correção sem reconhecer a parte correta',regra_logica_incorreta:'Regra lógica incorreta',juiz_nao_aprovou:'Verificador não aprovou; confira a justificativa',exercicio_nao_preservado_ou_nao_verificavel:'Exercício alterado ou sem preservação verificável',tamanho_campos_invalido:'Campos ausentes ou com tamanho inadequado',campos_intervencao_pergunta_misturados:'Intervenção e pergunta misturadas'};
function generationPanel(g){
 if(!g)return;
 const old=g.summaries.legacy||{},now=g.summaries.two_stage||{};
 $('generation-status').textContent=`Anterior: ${old.approved||0}/${old.total||0} · Duas etapas: ${now.approved||0}/${now.total||0}. ${g.recommendation||'Piloto em andamento; decisões ainda parciais.'}`;
 const table=node('table',''),head=node('tr','');for(const label of ['Família','Dica · anterior / nova','Correção · anterior / nova','Explicação · anterior / nova'])head.append(node('th',label));table.append(head);
 for(const [family,value] of Object.entries(now.by_family||{})){const tr=node('tr','');tr.append(node('td',value.label));for(const kind of Object.keys(kindNames)){const counts=method=>g.pairs.filter(p=>p.family===family&&p.kind===kind&&p[method]?.accepted).length;const total=g.pairs.filter(p=>p.family===family&&p.kind===kind).length;tr.append(node('td',`${counts('legacy')}/${total} · ${counts('two_stage')}/${total}`));}table.append(tr);}
 $('family-results').replaceChildren(table);
 $('kind-results').replaceChildren(...Object.entries(now.by_kind||{}).map(([kind,v])=>node('p',`${kindNames[kind]}: ${v.approved}/${v.generated} aprovados; ${v.rejected} descartados.`)));
 $('generation-reasons').replaceChildren(...Object.entries(now.reasons||{}).slice(0,8).map(([reason,count])=>node('p',`${count} · ${reasonNames[reason]||reason}`)));
 const passed=g.pairs.filter(p=>p.two_stage?.accepted).slice(0,3),failed=g.pairs.filter(p=>p.two_stage?.accepted===false).slice(0,3);
 const observed=(g.observations||[]).map(o=>({pair:g.pairs.find(p=>p.id===o.pair_id),note:o})).filter(o=>o.pair);
 const open=new Set(Array.from(document.querySelectorAll('#generation-examples details[open]')).map(x=>x.dataset.id));
 const examples=[];if(!passed.length)examples.push(node('p','Nenhum candidato aprovado. Não há acerto completo demonstrado; os acertos abaixo são parciais.'));
 for(const {pair,note} of observed){const d=node('details','');d.dataset.id='audit-'+pair.id;d.open=open.has(d.dataset.id);d.append(node('summary',note.label+' · '+pair.family+' / '+kindNames[pair.kind]),node('p',note.reason),node('p',pair.task.exercise),node('p','Intervenção real: '+pair.two_stage.candidate?.intervention),node('p','Pergunta real: '+pair.two_stage.candidate?.verification_question),node('p','Triagem: '+pair.two_stage.reasons.join(', ')));examples.push(d);}
 for(const pair of [...passed,...failed]){const d=node('details','');d.dataset.id=pair.id;d.open=open.has(pair.id);d.append(node('summary',`${pair.two_stage.accepted?'Aprovado na triagem estimada':'Descartado'} · ${pair.family} / ${kindNames[pair.kind]}`),node('p',pair.task.exercise),node('p','Tentativa construída: '+pair.task.student.text),node('p','Gabarito privado do laboratório: '+pair.task.expected));const grid=node('div','','pair');for(const method of ['legacy','two_stage']){const item=pair[method],col=node('div','');col.append(node('h3',method==='legacy'?'Abordagem anterior':'Duas etapas'),node('p','Intervenção: '+(item.candidate?.intervention||'Campo inválido/ausente')),node('p','Pergunta: '+(item.candidate?.verification_question||'Ausente')),node('p','Decisão: '+(item.reasons||[]).join(', ')),node('p','Juiz (estimativa): '+(item.judge?.reason||'Não executado')));const raw=node('details','');raw.append(node('summary','Resposta bruta'),node('pre',item.raw||'Não recebida'));col.append(raw);grid.append(col);}d.append(grid);examples.push(d);}
 $('generation-examples').replaceChildren(...examples);
}
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
 generationPanel(data.generation);
 const openedCandidates=new Set(Array.from(document.querySelectorAll('#candidates details[open]')).map(x=>x.dataset.id));
 $('candidates').replaceChildren(...data.candidates.map(item=>{const d=node('details','');d.dataset.id=String(item.index);d.open=openedCandidates.has(d.dataset.id);d.append(node('summary',`#${item.index+1} · ${item.accepted==null?'Aguardando triagem':item.accepted?'Aprovado na triagem':'Descartado'} · ${item.seconds}s · ${(item.reasons||[]).join(', ')}`));d.append(node('pre',pretty({candidate:item.candidate,judge:item.judge,raw:item.raw})));return d;}));
 if(data.comparison){$('comparison').replaceChildren(...data.comparison.pairs.map(pair=>{const d=node('details','');d.append(node('summary',`${pair.id} · ${pair.category} · ${pair.change||'inconclusivo'}`),node('p',pair.prompt),node('p','Esperado: '+pair.expected));const grid=node('div','','pair');for(const key of ['base','adapter']){const col=node('div','');col.append(node('h3',key==='base'?'Modelo base':'Adaptador'),node('pre',pair[key]?.raw||'Não executado'),node('p',pretty(pair[key]?.judgment)));grid.append(col);}d.append(grid);return d;}));}
 }catch(error){$('error').textContent=error.message;$('status').textContent='Sem conexão';}}
refresh();setInterval(refresh,3000);
