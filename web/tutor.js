/* Chat do tutor local. Trechos importados entram apenas como nós de texto. */
let tutorThread = null, tutorThreads = [], tutorContextKey = '', tutorRequestId = null;
let tutorPending = false, tutorLoadRevision = 0, tutorFailedDraft = '';
let memoryItems = [], memoryEditing = null;

function tutorError(text) { $('tutor-error').textContent = text || ''; }

function renderTutorStatus(status) {
  $('tutor-model').value = status.model;
  $('tutor-model-root').value = status.model_root;
  $('tutor-config-status').textContent = status.configured
    ? `Modelo instalado em ${status.model_root}. ${status.running ? 'Motor em execução.' : 'Será carregado ao enviar a primeira mensagem.'}`
    : 'Modelo ainda não instalado. Escolha uma pasta e clique em Instalar modelo escolhido.';
  $('tutor-availability').textContent = status.configured
    ? `Tutor local · ${status.model}. Conversa processada neste computador, sem custo de API.`
    : 'Tutor local ainda não instalado. Leitura, busca e anotações continuam disponíveis.';
}

async function loadTutorStatus() {
  try { renderTutorStatus(await api('/tutor/config')); }
  catch (error) { $('tutor-availability').textContent = 'Falha ao consultar o modelo: ' + error.message; }
}

function tutorSubjectOptions(chosen) {
  const select = $('tutor-subject');
  select.replaceChildren(new Option('Escolha uma matéria', ''));
  [...subjects, ...archivedSubjects].forEach(item => select.add(new Option(item.name, item.id)));
  select.value = chosen || '';
  select.disabled = !!current;
}

function renderTutorThreads() {
  const select = $('tutor-thread'); select.replaceChildren();
  tutorThreads.forEach(item => {
    const name = item.session_id ? `Sessão de ${localDate(item.session_started_at)}${item.session_status === 'complete' ? ' · concluída' : ''}` : 'Conversa da matéria';
    select.add(new Option(name, item.id));
  });
  if (!tutorThreads.length) select.add(new Option('Nenhuma conversa', ''));
  select.value = tutorThread?.id || '';
}

function renderTutorMaterials() {
  const options = $('tutor-material-options'); options.replaceChildren();
  const available = materials.filter(item => item.subject_id === tutorThread?.subject_id);
  if (!available.length) { const p = document.createElement('p'); p.className = 'hint'; p.textContent = 'Nenhum material nesta matéria.'; options.append(p); return; }
  available.forEach(item => {
    const label = document.createElement('label'), check = document.createElement('input');
    check.type = 'checkbox'; check.value = item.id; check.checked = tutorThread.material_ids.includes(item.id);
    const name = document.createElement('span'); name.textContent = `${item.name} · ${item.status === 'ready' ? 'texto disponível' : 'sem texto extraível'}`;
    label.append(check, name); options.append(label);
    check.onchange = async () => {
      const chosen = Array.from(options.querySelectorAll('input:checked')).map(element => element.value);
      if (chosen.length > 5) { check.checked = false; tutorError('Escolha até cinco materiais.'); return; }
      try { tutorThread = await api('/tutor/threads/' + tutorThread.id, 'PATCH', {material_ids: chosen}); tutorError(''); }
      catch (error) { check.checked = !check.checked; tutorError(error.message); }
    };
  });
}

function renderTutorHistory() {
  const history = $('tutor-history'); history.replaceChildren();
  if (!tutorThread?.messages?.length) { const p = document.createElement('p'); p.className = 'empty'; p.textContent = 'Ainda não há mensagens nesta conversa.'; history.append(p); return; }
  tutorThread.messages.forEach(item => {
    const card = document.createElement('article'), label = document.createElement('strong'), body = document.createElement('p');
    card.className = 'tutor-message ' + item.role;
    const eventNames = {question: 'Pergunta', attempt: 'Tentativa', feedback: 'Correção', lesson_prompt: 'Aula guiada', answer: 'Resposta'};
    label.textContent = `${item.role === 'user' ? 'Você' : 'Tutor'} · ${eventNames[item.kind] || item.kind}`;
    body.textContent = item.body; card.append(label, body);
    if (item.role === 'assistant') {
      const basis = document.createElement('small');
      basis.textContent = item.basis === 'materials' ? 'Trechos dos materiais selecionados' :
        item.basis === 'insufficient' ? 'Material selecionado sem trecho correspondente; confira a resposta' :
        'Sem material selecionado · conhecimento geral ou inferência';
      card.append(basis);
      if (item.sources?.length) {
        const sources = document.createElement('ul'); sources.className = 'tutor-sources';
        item.sources.forEach(source => {
          const li = document.createElement('li'), link = document.createElement(source.material_id && source.chunk_id ? 'a' : 'span');
          link.textContent = `[${source.ordinal}] ${source.material_name} · ${source.locator}`;
          if (link.tagName === 'A') {
            link.href = '#materiais';
            link.onclick = () => { setTimeout(() => openMaterial(source.material_id, source.chunk_id), 0); };
          }
          const excerpt = document.createElement('small'); excerpt.textContent = source.excerpt;
          li.append(link, excerpt); sources.append(li);
        });
        card.append(sources);
      }
    } else if (item.status === 'failed') {
      const retry = document.createElement('button'); retry.type = 'button'; retry.className = 'text-button'; retry.textContent = 'Repetir esta pergunta';
      retry.onclick = () => { $('tutor-draft').value = item.body; tutorRequestId = item.request_id; tutorFailedDraft = item.body; sendTutor(); };
      card.append(retry);
    } else if (item.status === 'pending') {
      const status = document.createElement('small'); status.textContent = 'Aguardando resposta…'; card.append(status);
    }
    history.append(card);
  });
  history.scrollTop = history.scrollHeight;
}

function renderTutorThread() {
  renderTutorThreads();
  $('tutor-mode').value = tutorThread?.mode || 'duvida';
  $('tutor-context').textContent = tutorThread?.session_id
    ? `Conversa ligada à sessão de ${localDate(tutorThread.session_started_at)}${tutorThread.session_status === 'complete' ? ' (histórica; o cronômetro não muda)' : ''}.`
    : 'Conversa da matéria, sem sessão de estudo vinculada.';
  renderTutorMaterials(); renderTutorHistory();
}

async function loadTutorContext(subjectId, preferredThreadId = null) {
  const revision = ++tutorLoadRevision;
  tutorSubjectOptions(subjectId);
  if (!subjectId) { tutorThread = null; tutorThreads = []; memoryItems = []; renderTutorThread(); renderMemory(); return; }
  const found = await api('/tutor/threads?subject_id=' + encodeURIComponent(subjectId));
  if (revision !== tutorLoadRevision) return;
  let desired = current?.subject_id === subjectId
    ? found.find(item => item.session_id === current.id)
    : found.find(item => item.id === preferredThreadId) || found[0];
  let loaded;
  if (!desired) {
    loaded = await api('/tutor/threads', 'POST', {subject_id: subjectId,
      session_id: current?.subject_id === subjectId ? current.id : null});
  } else loaded = await api('/tutor/threads/' + desired.id);
  if (revision !== tutorLoadRevision) return;
  const loadedThreads = await api('/tutor/threads?subject_id=' + encodeURIComponent(subjectId));
  if (revision !== tutorLoadRevision) return;
  tutorThread = loaded;
  tutorThreads = loadedThreads;
  renderTutorThread();
  await loadMemory(subjectId);
}

window.refreshTutorContext = () => {
  const subjectId = current?.subject_id || $('tutor-subject').value || uiState.subject_id || subjects[0]?.id || '';
  const key = subjectId + '|' + (current?.id || '');
  if (key === tutorContextKey && tutorThread) { renderTutorMaterials(); return Promise.resolve(); }
  tutorContextKey = key;
  const preferred = tutorThread?.subject_id === subjectId &&
    (!current || tutorThread.session_id === current.id) ? tutorThread.id : null;
  return loadTutorContext(subjectId, preferred)
    .catch(error => { tutorError(error.message); });
};

async function sendTutor() {
  if (tutorPending) return;
  const draft = $('tutor-draft'), body = draft.value.trim();
  if (!body) { tutorError('Escreva sua pergunta ou tentativa.'); draft.focus(); return; }
  if (!tutorThread) { tutorError('Escolha uma matéria antes de enviar.'); return; }
  if (!tutorRequestId || tutorFailedDraft !== body) tutorRequestId = crypto.randomUUID();
  tutorFailedDraft = body; tutorPending = true; tutorError('');
  $('tutor-send').disabled = $('tutor-retry').disabled = true;
  $('tutor-send').textContent = 'Aguardando resposta…';
  const started = performance.now();
  const phase = $('tutor-config-status').textContent.includes('Motor em execução') ? 'Gerando resposta' : 'Carregando modelo e gerando resposta';
  const elapsed = setInterval(() => { $('tutor-response-status').textContent = `${phase} · ${Math.round((performance.now() - started) / 1000)} s`; }, 500);
  try {
    tutorThread = await api('/tutor/threads/' + tutorThread.id + '/messages', 'POST', {request_id: tutorRequestId, body});
    draft.value = ''; tutorRequestId = null; tutorFailedDraft = ''; $('tutor-retry').hidden = true;
    renderTutorThread();
    $('tutor-response-status').textContent = `Resposta local em ${((performance.now() - started) / 1000).toFixed(1)} s.`;
    loadTutorStatus();
  } catch (error) {
    tutorError(error.message + ' O rascunho foi mantido.'); $('tutor-retry').hidden = false;
    try { tutorThread = await api('/tutor/threads/' + tutorThread.id); renderTutorThread(); } catch { /* mantém o rascunho */ }
  } finally {
    clearInterval(elapsed);
    tutorPending = false; $('tutor-send').disabled = $('tutor-retry').disabled = false;
    $('tutor-send').textContent = 'Enviar ao tutor';
  }
}

$('tutor-form').onsubmit = event => { event.preventDefault(); sendTutor(); };
$('tutor-retry').onclick = sendTutor;
$('tutor-draft').oninput = () => { if ($('tutor-draft').value.trim() !== tutorFailedDraft) { tutorRequestId = null; $('tutor-retry').hidden = true; } };
$('tutor-subject').onchange = () => { tutorContextKey = ''; loadTutorContext($('tutor-subject').value).catch(error => tutorError(error.message)); };
$('tutor-thread').onchange = async () => {
  try { tutorThread = await api('/tutor/threads/' + $('tutor-thread').value); renderTutorThread(); tutorError(''); }
  catch (error) { tutorError(error.message); }
};
$('tutor-mode').onchange = async () => {
  if (!tutorThread) return;
  try { tutorThread = await api('/tutor/threads/' + tutorThread.id, 'PATCH', {mode: $('tutor-mode').value}); renderTutorThread(); }
  catch (error) { tutorError(error.message); }
};

window.tutorStartMaterial = async materialId => {
  const material = materials.find(item => item.id === materialId);
  if (!material) return;
  tutorContextKey = '';
  await loadTutorContext(material.subject_id);
  if (!tutorThread.material_ids.includes(materialId)) {
    tutorThread = await api('/tutor/threads/' + tutorThread.id, 'PATCH',
      {material_ids: [...tutorThread.material_ids, materialId].slice(0, 5)});
  }
  tutorThread = await api('/tutor/threads/' + tutorThread.id, 'PATCH', {mode: 'aula'});
  renderTutorThread();
  $('tutor-draft').value = `Quero uma aula guiada sobre ${material.name}.`;
  $('tutor-draft').focus();
};

$('tutor-config-form').onsubmit = event => {
  event.preventDefault();
  busy($('tutor-config-save'), 'Salvando…', async () => {
    const body = {model: $('tutor-model').value, model_root: $('tutor-model-root').value.trim()};
    renderTutorStatus(await api('/tutor/config', 'PATCH', body));
    $('tutor-config-error').textContent = '';
    message('Escolha do modelo salva.');
  }, text => { $('tutor-config-error').textContent = text; });
};

async function updateInstallProgress() {
  const state = await api('/tutor/install');
  const percentage = state.total ? Math.min(100, Math.floor(state.done * 100 / state.total)) : 0;
  $('tutor-install-progress').hidden = !state.active;
  $('tutor-install-progress').value = percentage;
  $('tutor-install-status').textContent = state.error ? `Instalação falhou: ${state.error}` :
    state.active ? `${state.file}: ${percentage}% · ${Math.round(state.done / 1048576)} de ${Math.round(state.total / 1048576)} MB` :
    state.file ? 'Instalação concluída e verificada.' : '';
  $('tutor-install').disabled = state.active;
  if (state.active) setTimeout(updateInstallProgress, 1000);
  else await loadTutorStatus();
}
$('tutor-install').onclick = async () => {
  try {
    const body = {model: $('tutor-model').value, model_root: $('tutor-model-root').value.trim()};
    renderTutorStatus(await api('/tutor/config', 'PATCH', body));
    await api('/tutor/install', 'POST', {});
    $('tutor-config-error').textContent = '';
    updateInstallProgress();
  } catch (error) { $('tutor-config-error').textContent = error.message; }
};

function resetMemoryForm() {
  memoryEditing = null;
  $('memory-form').reset();
  $('memory-cancel').hidden = true;
  $('memory-save').textContent = 'Registrar revisão';
}
function renderMemory() {
  const list = $('memory-list'); list.replaceChildren();
  if (!memoryItems.length) {
    const empty = document.createElement('li'); empty.textContent = 'Nenhuma revisão registrada nesta matéria.';
    list.append(empty); return;
  }
  memoryItems.forEach(item => {
    const row = document.createElement('li');
    const name = document.createElement('strong'); name.textContent = item.topic;
    const detail = document.createElement('p');
    const due = new Date(item.next_review_at);
    const reason = item.outcome === 'dificil' ? 'tentativa relatada como difícil; intervalo de 1 dia' :
      item.outcome === 'parcial' ? 'tentativa relatada como parcial; intervalo de 3 dias' :
      'tentativa relatada como confortável; intervalo de 7 dias';
    detail.textContent = `${due <= new Date() ? 'Revisão sugerida agora' : 'Revisar em ' + due.toLocaleDateString('pt-BR')} · ${reason}${item.evidence ? ' · ' + item.evidence : ''}`;
    const record = document.createElement('details'), summary = document.createElement('summary'); summary.textContent = 'Ver tentativa e correção';
    const content = document.createElement('p'); content.textContent = `Exercício: ${item.exercise || 'não registrado'}\nTentativa: ${item.attempt || 'não registrada'}\nCorreção: ${item.feedback || 'não registrada'}\nProgresso observado: ${item.progress_observed || 'não registrado'}`;
    record.append(summary, content);
    const edit = document.createElement('button'); edit.type = 'button'; edit.className = 'text-button'; edit.textContent = 'Editar';
    edit.onclick = () => { memoryEditing = item; $('memory-topic').value = item.topic; $('memory-exercise').value = item.exercise; $('memory-attempt').value = item.attempt; $('memory-feedback').value = item.feedback; $('memory-evidence').value = item.evidence; $('memory-outcome').value = item.outcome; $('memory-progress').value = item.progress_observed; $('memory-cancel').hidden = false; $('memory-save').textContent = 'Salvar revisão'; $('memory-topic').focus(); };
    const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'text-button'; remove.textContent = 'Apagar';
    remove.onclick = async () => {
      if (!confirm(`Apagar a revisão de ${item.topic}?`)) return;
      try { await api('/study-memory/' + item.id, 'DELETE', {version: item.version}); await loadMemory(tutorThread.subject_id); }
      catch (error) { $('memory-error').textContent = error.message; }
    };
    row.append(name, detail, record, edit, remove); list.append(row);
  });
}
async function loadMemory(subjectId) {
  memoryItems = await api('/study-memory?subject_id=' + encodeURIComponent(subjectId));
  renderMemory();
}
$('memory-form').onsubmit = async event => {
  event.preventDefault();
  if (!tutorThread) { $('memory-error').textContent = 'Escolha uma matéria.'; return; }
  const body = {subject_id: tutorThread.subject_id, topic: $('memory-topic').value.trim(),
    exercise: $('memory-exercise').value.trim(), attempt: $('memory-attempt').value.trim(),
    feedback: $('memory-feedback').value.trim(), evidence: $('memory-evidence').value.trim(),
    outcome: $('memory-outcome').value, progress_observed: $('memory-progress').value.trim()};
  try {
    await api(memoryEditing ? '/study-memory/' + memoryEditing.id : '/study-memory',
      memoryEditing ? 'PATCH' : 'POST', memoryEditing ? {...body, version: memoryEditing.version} : body);
    resetMemoryForm(); $('memory-error').textContent = '';
    await loadMemory(tutorThread.subject_id);
  } catch (error) { $('memory-error').textContent = error.message; }
};
$('memory-cancel').onclick = resetMemoryForm;
$('memory-from-chat').onclick = () => {
  const messages = tutorThread?.messages || [];
  const lastUser = [...messages].reverse().find(item => item.role === 'user' && item.status === 'complete');
  const lastAssistant = [...messages].reverse().find(item => item.role === 'assistant');
  const priorAssistant = lastUser ? [...messages].reverse().find(item => item.role === 'assistant' && item.created_at < lastUser.created_at) : null;
  if (!lastUser) { $('memory-error').textContent = 'Ainda não há tentativa no chat.'; return; }
  $('memory-exercise').value = (priorAssistant?.body || '').slice(0, 2000);
  $('memory-attempt').value = lastUser.body.slice(0, 2000);
  $('memory-feedback').value = (lastAssistant?.body || '').slice(0, 2000);
  $('memory-error').textContent = 'Revise os campos antes de registrar.';
};
$('memory-export').onclick = () => {
  const file = new Blob([JSON.stringify(memoryItems, null, 2)], {type: 'application/json'});
  const link = document.createElement('a'); link.href = URL.createObjectURL(file);
  link.download = 'ritmo-revisoes.json'; link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 1000);
};

loadTutorStatus();
updateInstallProgress().catch(() => {});
api('/tutor/knowledge').then(data => {
  $('tutor-knowledge-date').textContent = `Catálogo versão ${data.version}, verificado em ${data.checked_at}.`;
  const list = $('tutor-knowledge'); list.replaceChildren();
  [...data.pedagogy, ...data.academic_and_labor_sources].forEach(source => {
    const item = document.createElement('li'), link = document.createElement('a');
    link.href = source.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
    link.textContent = source.name;
    const detail = document.createElement('span'); detail.textContent = ' · ' + source.scope;
    item.append(link, detail); list.append(item);
  });
}).catch(() => { $('tutor-knowledge-date').textContent = 'Catálogo indisponível; consulte o diagnóstico.'; });

async function loadKnowledgeUpdates() {
  const list = $('knowledge-updates'); list.replaceChildren();
  const rows = await api('/tutor/knowledge-updates');
  if (!rows.length) { const empty = document.createElement('li'); empty.textContent = 'Nenhuma atualização manual adicionada.'; list.append(empty); return; }
  rows.forEach(row => {
    const item = document.createElement('li'), link = document.createElement('a');
    link.href = row.source_url; link.target = '_blank'; link.rel = 'noopener noreferrer';
    link.textContent = `v${row.version} · ${row.source_name}`;
    const detail = document.createElement('p');
    detail.textContent = `${row.category === 'academic' ? 'Ensino superior' : 'Trabalho formal'} · ${row.kind} · publicado ${row.published_at} · observado até ${row.observed_until} · licença: ${row.license}. ${row.scope} ${row.summary}`;
    const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'text-button'; remove.textContent = 'Remover versão';
    remove.onclick = async () => {
      if (!confirm(`Remover atualização v${row.version}?`)) return;
      try { await api('/tutor/knowledge-updates/' + row.version, 'DELETE', {}); await loadKnowledgeUpdates(); }
      catch (error) { $('knowledge-update-error').textContent = error.message; }
    };
    item.append(link, detail, remove); list.append(item);
  });
}
$('knowledge-update-form').onsubmit = async event => {
  event.preventDefault();
  const data = {category: $('knowledge-category').value, kind: $('knowledge-kind').value,
    source_name: $('knowledge-name').value.trim(), source_url: $('knowledge-url').value.trim(),
    published_at: $('knowledge-published').value, observed_until: $('knowledge-observed').value,
    license: $('knowledge-license').value.trim(), scope: $('knowledge-scope').value.trim(),
    summary: $('knowledge-summary').value.trim()};
  const preview = `Fonte: ${data.source_name}\nPublicação: ${data.published_at}\nDados até: ${data.observed_until}\nTipo: ${data.kind}\nResumo: ${data.summary}\n\nNenhum download será feito. Adicionar versão?`;
  if (!confirm(preview)) return;
  try {
    await api('/tutor/knowledge-updates', 'POST', data);
    $('knowledge-update-form').reset(); $('knowledge-update-error').textContent = '';
    await loadKnowledgeUpdates();
  } catch (error) { $('knowledge-update-error').textContent = error.message; }
};
loadKnowledgeUpdates().catch(error => { $('knowledge-update-error').textContent = error.message; });
