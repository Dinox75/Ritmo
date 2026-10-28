const $ = id => document.getElementById(id);
const VIEWS = new Set(['inicio', 'estudar', 'plano', 'materiais', 'anotacoes', 'evolucao', 'configuracoes']);
let subjects = [], archivedSubjects = [], sessions = [], notes = [], materials = [], current = null, sensorConfig = null;
let currentMaterial = null, selectedChunk = null, selectedRange = null, cameraOptions = null;
let materialMatches = [], activeMaterialMatch = 0;
let progress = null, dayProgress = null, activeView = null;
let uiState = {view: 'inicio', subject_id: null, revision: 0};
let uiSave = Promise.resolve();
let sessionActionPending = false, refreshRevision = 0;
let experience = null, activeSound = null, audioContext = null, audioNode = null;
let localAudio = null, localAudioUrl = null, audioWanted = false, readerRevision = 0;
let soundRevision = 0;

async function api(path, method = 'GET', data) {
  const response = await fetch('/api' + path, {
    method, headers: {'Content-Type': 'application/json'},
    body: data === undefined ? undefined : JSON.stringify(data)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Erro ao comunicar com o Ritmo');
  return result;
}

function message(text, kind = 'success') {
  const region = $('message');
  region.textContent = text;
  region.dataset.kind = kind;
  if (text) setTimeout(() => { if (region.textContent === text) region.textContent = ''; }, 6500);
}

function fieldError(id, text, controlId) {
  $(id).textContent = text || '';
  if (controlId) {
    if (text) $(controlId).setAttribute('aria-invalid', 'true');
    else $(controlId).removeAttribute('aria-invalid');
  }
}

async function busy(button, label, work, onError) {
  if (button.disabled) return;
  const original = button.textContent;
  button.disabled = true;
  button.textContent = label;
  button.setAttribute('aria-busy', 'true');
  try { return await work(); }
  catch (error) { (onError || (text => message(text, 'error')))(error.message); }
  finally {
    button.disabled = false;
    if (button.textContent === label) button.textContent = original;
    button.removeAttribute('aria-busy');
  }
}

const duration = seconds => {
  const count = Math.max(0, Math.floor(Number(seconds) || 0));
  return [Math.floor(count / 3600), Math.floor(count % 3600 / 60), count % 60]
    .map(value => String(value).padStart(2, '0')).join(':');
};
const localDate = value => new Date(value).toLocaleString('pt-BR');
const hourLabel = minutes => (minutes / 60).toLocaleString('pt-BR', {maximumFractionDigits: 2});
const completedLabel = count => `${count} ${count === 1 ? 'sessão concluída' : 'sessões concluídas'}`;

function queueUiSave() {
  uiState.revision = Math.max(Date.now(), (uiState.revision || 0) + 1);
  const snapshot = {...uiState};
  uiSave = uiSave.catch(() => {}).then(() => api('/ui-state', 'PATCH', snapshot));
  uiSave.catch(error => message('Não foi possível lembrar a tela escolhida: ' + error.message, 'error'));
}

function showView(view, {persist = true, focus = true} = {}) {
  if (!VIEWS.has(view)) view = 'inicio';
  const changed = activeView !== view;
  if (changed && activeView) $('message').textContent = '';
  activeView = view;
  document.querySelectorAll('[data-view]').forEach(section => { section.hidden = section.dataset.view !== view; });
  document.querySelectorAll('[data-view-target]').forEach(link => {
    if (link.dataset.viewTarget === view) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  $('session-ribbon').hidden = !current || view === 'estudar';
  if (location.hash !== '#' + view) history.replaceState(null, '', '#' + view);
  if (persist && changed) { uiState.view = view; queueUiSave(); }
  if (view === 'configuracoes') refreshDiagnostics().catch(error => message(error.message, 'error'));
  if (focus && changed) {
    const heading = $('view-' + view).querySelector('h1');
    heading.setAttribute('tabindex', '-1');
    heading.focus({preventScroll: true});
    window.scrollTo(0, 0);
  }
}

function renderSubjects() {
  const chosen = $('subject-select').value || uiState.subject_id || current?.subject_id || '';
  const noteChosen = $('note-subject').value || current?.subject_id || uiState.subject_id || '';
  const homeChosen = $('home-subject').value || uiState.subject_id || sessions[0]?.subject_id || '';
  const materialChosen = $('material-subject').value || uiState.subject_id || '';
  for (const [select, previous] of [[$('subject-select'), chosen], [$('note-subject'), noteChosen],
                                    [$('home-subject'), homeChosen], [$('material-subject'), materialChosen]]) {
    select.replaceChildren(new Option('Escolha uma matéria', ''));
    subjects.forEach(subject => select.add(new Option(subject.name, subject.id)));
    select.value = subjects.some(subject => subject.id === previous) ? previous : '';
  }
  for (const id of ['note-filter-subject', 'material-filter']) {
    const select = $(id), previous = select.value;
    select.replaceChildren(new Option('Todas as matérias', ''));
    [...subjects, ...archivedSubjects].forEach(subject => select.add(new Option(subject.name, subject.id)));
    select.value = previous && [...subjects, ...archivedSubjects].some(subject => subject.id === previous) ? previous : '';
  }
  const list = $('subjects-list'); list.replaceChildren();
  if (!subjects.length) list.append(emptyItem('Nenhuma matéria ainda. Adicione uma acima para começar.'));
  subjects.forEach(subject => {
    const li = document.createElement('li');
    const name = document.createElement('span'); name.textContent = subject.name;
    const actions = document.createElement('span'); actions.className = 'row-actions';
    const edit = document.createElement('button'); edit.type = 'button'; edit.textContent = 'Renomear';
    const archive = document.createElement('button'); archive.type = 'button'; archive.textContent = 'Arquivar';
    edit.onclick = () => {
      const form = document.createElement('form'); form.className = 'row-edit'; form.noValidate = true;
      const input = document.createElement('input'); input.value = subject.name; input.maxLength = 120;
      input.setAttribute('aria-label', 'Novo nome da matéria ' + subject.name);
      const save = document.createElement('button'); save.className = 'primary'; save.textContent = 'Salvar';
      const cancel = document.createElement('button'); cancel.type = 'button'; cancel.textContent = 'Cancelar';
      const error = document.createElement('p'); error.className = 'field-error'; error.setAttribute('role', 'alert');
      cancel.onclick = () => renderSubjects();
      form.onsubmit = event => {
        event.preventDefault();
        const next = input.value.trim();
        if (!next) { error.textContent = 'Informe o nome da matéria.'; input.focus(); return; }
        if (next === subject.name) { renderSubjects(); return; }
        busy(save, 'Salvando…', async () => {
          await api('/subjects/' + subject.id, 'PATCH', {name: next});
          await refresh(); message('Matéria renomeada.');
        }, text => { error.textContent = text; input.focus(); });
      };
      form.append(input, save, cancel, error); li.replaceChildren(form); input.focus(); input.select();
    };
    archive.onclick = () => {
      if (!confirm(`Arquivar ${subject.name}? Sessões e anotações serão preservadas.`)) return;
      busy(archive, 'Arquivando…', async () => {
        await api('/subjects/' + subject.id, 'PATCH', {archived: true});
        if (uiState.subject_id === subject.id) { uiState.subject_id = null; queueUiSave(); }
        await refresh(); message('Matéria arquivada.');
      });
    };
    actions.append(edit, archive); li.append(name, actions); list.append(li);
  });
  const archived = $('archived-list'); archived.replaceChildren();
  if (!archivedSubjects.length) archived.append(emptyItem('Nenhuma matéria arquivada.'));
  archivedSubjects.forEach(subject => {
    const li = document.createElement('li'), name = document.createElement('span'), restore = document.createElement('button');
    name.textContent = subject.name; restore.type = 'button'; restore.textContent = 'Restaurar';
    restore.onclick = () => busy(restore, 'Restaurando…', async () => {
      await api('/subjects/' + subject.id, 'PATCH', {archived: false});
      await refresh(); message('Matéria restaurada.');
    });
    li.append(name, restore); archived.append(li);
  });
  $('start-btn').disabled = !subjects.length;
  $('material-import').disabled = !subjects.length;
  $('note-session-hint').textContent = current && $('note-subject').value === current.subject_id
    ? 'Será vinculada à sessão em andamento.' : 'Será vinculada à matéria selecionada.';
}

function emptyItem(text) {
  const li = document.createElement('li'); li.className = 'empty'; li.textContent = text; return li;
}

function noteSourceLink(note) {
  if (!note.material_id || !note.chunk_id) return null;
  const link = document.createElement('a');
  link.href = '#materiais'; link.textContent = `Abrir origem · ${note.material_name} · ${note.locator}`;
  link.onclick = () => { setTimeout(() => openMaterial(note.material_id, note.chunk_id), 0); };
  return link;
}

function renderSession() {
  $('start-panel').hidden = !!current;
  $('session-panel').hidden = !current;
  $('quick-note-wrap').hidden = !current;
  $('study-context').hidden = !current;
  document.querySelector('.study-layout').classList.toggle('has-session', !!current);
  if (current) {
    $('session-subject').textContent = current.subject_name;
    $('session-status').textContent = current.status === 'focus' ? 'Em foco' : 'Em pausa';
    $('session-status').classList.toggle('paused', current.status === 'pause');
    $('session-started').textContent = 'Iniciada em ' + localDate(current.started_at);
    $('pause-btn').textContent = current.status === 'focus' ? 'Pausar' : 'Retomar';
    $('ribbon-text').textContent = `${current.subject_name} · ${current.status === 'focus' ? 'em foco' : 'em pausa'}`;
    tick();
  }
  if (!current || current.status !== 'focus') {
    stopSound(); $('focus-reminder').hidden = true;
    $('focus-audio-status').textContent = current ? 'Som pausado junto com a sessão.' : 'Som desligado.';
  }
  else if (audioWanted) startSound().catch(() => {});
  $('focus-play').disabled = !current || current.status !== 'focus' || $('focus-sound').value === 'off';
  $('session-ribbon').hidden = !current || activeView === 'estudar';
  const finished = sessions.find(item => item.status === 'complete');
  $('session-summary').hidden = !!current || !finished;
  if (finished && !current) {
    $('summary-subject').textContent = finished.subject_name;
    $('summary-date').textContent = 'Concluída em ' + localDate(finished.ended_at);
    $('summary-focus').textContent = duration(finished.focus_seconds);
    $('summary-pause').textContent = duration(finished.pause_seconds);
  }
  const noteList = $('session-notes'); noteList.replaceChildren();
  const previousList = $('previous-notes'); previousList.replaceChildren();
  if (current) {
    const linked = notes.filter(note => note.session_id === current.id);
    if (!linked.length) noteList.append(emptyItem('Nenhuma anotação nesta sessão.'));
    linked.forEach(note => { const li = document.createElement('li'); li.textContent = note.body;
      const source = noteSourceLink(note); if (source) li.append(document.createElement('br'), source); noteList.append(li); });
    const earlier = notes.filter(note => note.subject_id === current.subject_id && note.session_id !== current.id).slice(0, 8);
    if (!earlier.length) previousList.append(emptyItem('Nenhuma nota anterior desta matéria.'));
    earlier.forEach(note => { const li = document.createElement('li'); li.textContent = note.body;
      const source = noteSourceLink(note); if (source) li.append(document.createElement('br'), source); previousList.append(li); });
  }
  const materialList = $('study-materials'); materialList.replaceChildren();
  if (current) {
    const linked = materials.filter(item => item.subject_id === current.subject_id);
    if (!linked.length) materialList.append(emptyItem('Nenhum material nesta matéria.'));
    linked.forEach(item => {
      const li = document.createElement('li'), link = document.createElement('a');
      link.href = '#materiais'; link.textContent = item.name;
      link.onclick = () => { setTimeout(() => openMaterial(item.id), 0); };
      li.append(link); materialList.append(li);
    });
  }
  renderStudyReader();
}

function tick() {
  if (!current) return;
  const now = Date.now();
  const sums = {focus: 0, pause: 0};
  current.intervals.forEach(item => {
    sums[item.kind] += Math.max(0, (new Date(item.ended_at || now).getTime() - new Date(item.started_at).getTime()) / 1000);
  });
  const corrected = sums.focus + current.adjustments.reduce((sum, item) => sum + item.delta_seconds, 0);
  $('timer').textContent = duration(corrected);
  $('pause-time').textContent = duration(sums.pause);
  checkFocusReminder(sums.focus);
}

function renderStudyReader() {
  const select = $('study-reader-select');
  const available = materials.filter(item => item.subject_id === (current?.subject_id || uiState.subject_id));
  const selected = available.some(item => item.id === select.value) ? select.value : (available[0]?.id || '');
  select.replaceChildren(new Option('Escolha um material', ''));
  available.forEach(item => select.add(new Option(item.name, item.id)));
  select.value = selected;
  loadStudyReader(selected);
}

async function loadStudyReader(id) {
  const revision = ++readerRevision, container = $('study-reader-content');
  container.replaceChildren();
  if (!id) { container.textContent = 'Adicione um material à matéria para lê-lo durante a sessão.'; return; }
  container.textContent = 'Carregando material…';
  try {
    const material = await api('/materials/' + encodeURIComponent(id));
    if (revision !== readerRevision || $('study-reader-select').value !== id) return;
    container.replaceChildren();
    if (!material.chunks?.length) { container.textContent = 'Sem texto extraível. Abra o material original na Biblioteca.'; return; }
    material.chunks.forEach(chunk => {
      const section = document.createElement('section'), label = document.createElement('small'), body = document.createElement('pre');
      section.className = 'reader-section'; label.textContent = chunk.locator || 'Trecho'; body.textContent = chunk.body;
      section.append(label, body); container.append(section);
    });
  } catch (error) { if (revision === readerRevision) container.textContent = error.message; }
}

function applyExperience(value) {
  const previousSound = experience?.soundscape;
  const syncSessionSound = !experience || $('focus-sound').value === previousSound;
  experience = value;
  const theme = value.theme === 'system'
    ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : value.theme;
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.setProperty('--ui-dim', String((100 - value.brightness) / 100));
  $('theme-quick').textContent = theme === 'dark' ? 'Tema escuro' : 'Tema claro';
  $('experience-theme').value = value.theme;
  $('experience-brightness').value = value.brightness;
  $('brightness-value').textContent = value.brightness + '%';
  $('experience-sound').value = value.soundscape;
  $('experience-volume').value = value.volume;
  $('volume-value').textContent = value.volume + '%';
  $('experience-reminders').checked = value.reminders_enabled;
  $('experience-break').value = value.break_minutes;
  $('experience-excess').value = value.excess_minutes;
  $('experience-completion').checked = value.completion_sound;
  if (syncSessionSound) $('focus-sound').value = value.soundscape;
  $('focus-play').disabled = !current || current.status !== 'focus' || $('focus-sound').value === 'off';
  $('focus-volume').value = value.volume;
  if (localAudio) localAudio.volume = value.volume / 100;
  if (audioNode?.gain) audioNode.gain.gain.value = value.volume / 100 * .18;
}

function stopSound() {
  soundRevision++;
  if (audioNode?.source) { try { audioNode.source.stop(); } catch { /* já encerrado */ } }
  audioNode = null;
  if (localAudio) localAudio.pause();
  $('focus-play').textContent = 'Reproduzir';
}

async function startSound() {
  const choice = $('focus-sound').value;
  const revision = soundRevision;
  if (!audioWanted || !current || current.status !== 'focus' || choice === 'off') return;
  if (choice === 'file') {
    if (!localAudioUrl) { $('focus-audio-status').textContent = 'Escolha um arquivo de áudio deste computador.'; return; }
    localAudio ||= new Audio();
    if (localAudio.src !== localAudioUrl) localAudio.src = localAudioUrl;
    localAudio.loop = true; localAudio.volume = Number($('focus-volume').value) / 100;
    await localAudio.play();
    if (revision !== soundRevision || current?.status !== 'focus' || !audioWanted) { localAudio.pause(); return; }
  } else {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) throw new Error('Áudio indisponível neste navegador.');
    audioContext ||= new AudioContextClass();
    await audioContext.resume();
    if (revision !== soundRevision || current?.status !== 'focus' || !audioWanted || $('focus-sound').value !== choice) return;
    if (!audioNode) {
      const buffer = audioContext.createBuffer(1, audioContext.sampleRate * 2, audioContext.sampleRate);
      const samples = buffer.getChannelData(0);
      let brown = 0;
      for (let i = 0; i < samples.length; i++) {
        const white = Math.random() * 2 - 1;
        brown = (brown + .02 * white) / 1.02;
        samples[i] = choice === 'brown' ? brown * 3.5 : white * .28;
      }
      const source = audioContext.createBufferSource(), filter = audioContext.createBiquadFilter();
      const gain = audioContext.createGain();
      source.buffer = buffer; source.loop = true;
      filter.type = 'lowpass'; filter.frequency.value = choice === 'brown' ? 380 : 2800;
      gain.gain.value = Number($('focus-volume').value) / 100 * .18;
      source.connect(filter).connect(gain).connect(audioContext.destination);
      source.start(); audioNode = {source, gain};
    }
  }
  $('focus-play').textContent = 'Pausar som';
  $('focus-audio-status').textContent = 'Som opcional em reprodução local. Pausa junto com a sessão.';
}

function checkFocusReminder(focusSeconds) {
  if (!experience?.reminders_enabled || current?.status !== 'focus') return;
  const breakLimit = experience.break_minutes * 60;
  const excessLimit = (experience.break_minutes + experience.excess_minutes) * 60;
  const key = current.id + ':';
  const seen = marker => sessionStorage.getItem('ritmo-reminder:' + key + marker);
  const mark = marker => sessionStorage.setItem('ritmo-reminder:' + key + marker, '1');
  if (focusSeconds >= excessLimit && !seen('excess')) {
    mark('break'); mark('excess');
    $('focus-reminder-text').textContent = 'Você passou do tempo de foco planejado. Quer fazer uma pausa?';
    $('focus-reminder').hidden = false;
  } else if (focusSeconds >= breakLimit && !seen('break')) {
    mark('break');
    $('focus-reminder-text').textContent = 'Seu bloco de foco terminou. Você pode fazer uma pausa ou continuar.';
    $('focus-reminder').hidden = false;
  }
}

function completionChime() {
  if (!experience?.completion_sound) return;
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) return;
  audioContext ||= new AudioContextClass();
  audioContext.resume().then(() => {
    for (const [index, frequency] of [440, 660].entries()) {
      const oscillator = audioContext.createOscillator(), gain = audioContext.createGain();
      oscillator.type = 'sine'; oscillator.frequency.value = frequency;
      const at = audioContext.currentTime + index * .16;
      gain.gain.setValueAtTime(.0001, at);
      gain.gain.exponentialRampToValueAtTime(.08, at + .03);
      gain.gain.exponentialRampToValueAtTime(.0001, at + .25);
      oscillator.connect(gain).connect(audioContext.destination);
      oscillator.start(at); oscillator.stop(at + .26);
    }
  }).catch(() => {});
}

function renderProgress(value) {
  $('progress-time').textContent = duration(value.focus_seconds);
  $('progress-pause').textContent = duration(value.pause_seconds);
  $('progress-detail').textContent = `${completedLabel(value.completed_sessions)} · meta de ${hourLabel(value.weekly_goal_minutes)} horas`;
  const percent = Math.min(100, value.focus_seconds / (value.weekly_goal_minutes * 60) * 100);
  $('progress-fill').style.width = percent + '%';
  $('home-progress-fill').style.width = percent + '%';
  $('home-progress-time').textContent = duration(value.focus_seconds);
  $('home-progress-detail').textContent = `de ${hourLabel(value.weekly_goal_minutes)} horas de meta semanal`;
  $('goal-current').textContent = `Meta atual: ${hourLabel(value.weekly_goal_minutes)} horas por semana.`;
  if (document.activeElement !== $('goal-hours')) $('goal-hours').value = hourLabel(value.weekly_goal_minutes);
}

function renderHome() {
  $('today-time').textContent = duration(dayProgress.focus_seconds);
  $('today-detail').textContent = `${completedLabel(dayProgress.completed_sessions)} hoje · ${duration(dayProgress.pause_seconds)} em pausa`;
  if (current) {
    $('home-session-title').textContent = current.status === 'focus' ? 'Sessão em andamento' : 'Sessão em pausa';
    $('home-session-detail').textContent = `${current.subject_name} · iniciada em ${localDate(current.started_at)}`;
    $('home-primary').textContent = 'Voltar à sessão';
    $('home-primary').hidden = false; $('home-create').hidden = true; $('home-idle-actions').hidden = true;
    $('home-recent').textContent = current.status === 'pause' ? 'O foco está parado até você retomar.' : 'O tempo de foco está contando.';
    $('home-next').textContent = 'Sua sessão continua disponível na tela Estudar.';
    $('home-next-link').textContent = 'Voltar à sessão'; $('home-next-link').href = '#estudar';
  } else if (subjects.length) {
    $('home-session-title').textContent = 'Começar uma nova sessão';
    $('home-session-detail').textContent = 'Escolha uma matéria existente. Um novo registro será criado.';
    $('home-primary').textContent = 'Estudar matéria existente';
    $('home-primary').hidden = false; $('home-create').hidden = false; $('home-idle-actions').hidden = false;
    const finished = sessions.find(item => item.status === 'complete');
    $('home-recent').textContent = finished ? `Matéria usada recentemente: ${finished.subject_name}.` : 'Nenhuma sessão anterior.';
    $('home-next').textContent = finished ? `Última sessão: ${finished.subject_name}, ${duration(finished.focus_seconds)} de foco.` : 'Inicie uma sessão na tela Estudar.';
    $('home-next-link').textContent = finished ? 'Ver evolução' : 'Abrir Estudar';
    $('home-next-link').href = finished ? '#evolucao' : '#estudar';
  } else {
    $('home-session-title').textContent = 'Vamos começar?';
    $('home-session-detail').textContent = 'Adicione sua primeira matéria em Meu plano.';
    $('home-primary').hidden = true; $('home-create').hidden = false; $('home-idle-actions').hidden = true;
    $('home-recent').textContent = 'Nenhuma matéria cadastrada.';
    $('home-next').textContent = 'Crie uma matéria para iniciar uma sessão de estudo.';
    $('home-next-link').textContent = 'Abrir Meu plano'; $('home-next-link').href = '#plano';
  }
}

function renderNotes() {
  const filter = $('note-search').value.trim().toLocaleLowerCase('pt-BR');
  const subjectFilter = $('note-filter-subject').value;
  const visible = notes.filter(note => {
    const subject = [...subjects, ...archivedSubjects].find(item => item.id === note.subject_id);
    return (!subjectFilter || note.subject_id === subjectFilter) &&
      (!filter || (note.body + ' ' + (subject?.name || '') + ' ' + (note.material_name || ''))
        .toLocaleLowerCase('pt-BR').includes(filter));
  });
  const list = $('notes-list'); list.replaceChildren();
  if (!visible.length) list.append(emptyItem(notes.length ? 'Nenhuma anotação corresponde à busca.' : 'Nenhuma anotação ainda. Use o formulário ao lado para começar.'));
  visible.forEach(note => {
    const li = document.createElement('li'), body = document.createElement('div'), meta = document.createElement('div');
    const actions = document.createElement('div'), edit = document.createElement('button'), remove = document.createElement('button');
    body.textContent = note.body;
    const subject = [...subjects, ...archivedSubjects].find(item => item.id === note.subject_id);
    const session = sessions.find(item => item.id === note.session_id);
    meta.className = 'note-meta';
    meta.textContent = `${subject?.name || 'Matéria arquivada'} · ${localDate(note.updated_at)}${session ? ' · sessão de ' + localDate(session.started_at) : ''}${note.material_name ? ' · ' + note.material_name + ' · ' + note.locator : ''}`;
    actions.className = 'note-actions'; edit.type = remove.type = 'button'; edit.textContent = 'Editar'; remove.textContent = 'Apagar';
    edit.onclick = () => {
      const form = document.createElement('form'); form.className = 'note-edit'; form.noValidate = true;
      const input = document.createElement('textarea'); input.value = note.body; input.setAttribute('aria-label', 'Editar anotação');
      const row = document.createElement('div'); row.className = 'row-actions';
      const save = document.createElement('button'); save.className = 'primary'; save.textContent = 'Salvar alteração';
      const cancel = document.createElement('button'); cancel.type = 'button'; cancel.textContent = 'Cancelar';
      const error = document.createElement('p'); error.className = 'field-error'; error.setAttribute('role', 'alert');
      cancel.onclick = () => renderNotes();
      form.onsubmit = event => {
        event.preventDefault();
        if (!input.value.trim()) { error.textContent = 'Escreva o texto da anotação.'; input.focus(); return; }
        busy(save, 'Salvando…', async () => {
          await api('/notes/' + note.id, 'PATCH', {body: input.value, version: note.version});
          await refresh(); message('Anotação atualizada.');
        }, text => { error.textContent = text; input.focus(); });
      };
      row.append(save, cancel); form.append(input, error, row); li.replaceChildren(form); input.focus();
    };
    remove.onclick = () => {
      if (!confirm('Apagar esta anotação? Esta ação não pode ser desfeita pela interface.')) return;
      busy(remove, 'Apagando…', async () => {
        await api('/notes/' + note.id, 'DELETE', {version: note.version});
        await refresh(); message('Anotação apagada.');
      });
    };
    actions.append(edit, remove); li.append(body, meta);
    if (note.quote) { const quote = document.createElement('blockquote'); quote.textContent = note.quote; li.append(quote); }
    const source = noteSourceLink(note); if (source) li.append(source);
    li.append(actions); list.append(li);
  });
}

function renderMaterialList() {
  const list = $('materials-list'); list.replaceChildren();
  const filtered = materials.filter(item => !$('material-filter').value || item.subject_id === $('material-filter').value);
  if (!filtered.length) list.append(emptyItem(materials.length ? 'Nenhum material nesta matéria.' : 'Nenhum material importado.'));
  filtered.forEach(item => {
    const li = document.createElement('li'), button = document.createElement('button');
    button.type = 'button'; button.textContent = item.name;
    if (currentMaterial?.id === item.id) button.setAttribute('aria-current', 'true');
    const meta = document.createElement('small'); meta.textContent = `${item.subject_name} · ${item.file_type} · ${item.status === 'ready' ? item.chunk_count + (item.chunk_count === 1 ? ' trecho' : ' trechos') : item.status === 'no_text' ? 'sem texto extraível' : 'erro na extração'}`;
    button.onclick = () => openMaterial(item.id);
    li.append(button, meta); list.append(li);
  });
}

async function openMaterial(id, jumpChunkId = null, citationExcerpt = null) {
  fieldError('reader-error', '');
  try {
    currentMaterial = await api('/materials/' + id);
    selectedChunk = selectedRange = null; $('material-note-form').hidden = true;
    $('reader-title').textContent = currentMaterial.name;
    $('reader-meta').textContent = `${currentMaterial.subject_name} · ${currentMaterial.file_type} · ${Math.ceil(currentMaterial.size_bytes / 1024)} KB · importado em ${localDate(currentMaterial.imported_at)} · origem: ${currentMaterial.source_name}`;
    $('reader-controls').hidden = false;
    $('material-original').href = '/api/materials/' + id + '/original';
    $('material-original').download = currentMaterial.source_name;
    $('material-search').value = '';
    if (currentMaterial.status !== 'ready') fieldError('reader-error', currentMaterial.error || 'Não há texto extraído. O original continua disponível.');
    renderMaterialChunks(); renderMaterialList();
    if (jumpChunkId) {
      const section = $('chunk-' + jumpChunkId);
      const chunk = currentMaterial.chunks.find(item => item.id === jumpChunkId);
      let target = section;
      if (citationExcerpt && chunk && section) {
        const tokens = citationExcerpt.trim().split(/\s+/).filter(Boolean);
        const escaped = tokens.map(token => token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
        const pattern = escaped.length && citationExcerpt.length <= 1000 ? new RegExp(escaped.join('\\s+'), 'gu') : null;
        const matches = pattern ? [...chunk.body.matchAll(pattern)].slice(0, 2) : [];
        if (matches.length === 1) {
          const match = matches[0], start = match.index, end = start + match[0].length;
          const body = section.querySelector('p'), mark = document.createElement('mark');
          mark.className = 'citation-highlight'; mark.textContent = chunk.body.slice(start, end);
          body.replaceChildren(document.createTextNode(chunk.body.slice(0, start)), mark,
            document.createTextNode(chunk.body.slice(end)));
          target = mark;
        } else {
          fieldError('reader-error', 'Não foi possível identificar a frase citada com segurança. Confira o trecho completo abaixo.');
        }
      } else if (citationExcerpt) {
        fieldError('reader-error', 'O trecho citado não está disponível neste material.');
      }
      target?.scrollIntoView({block: 'center'});
    }
  } catch (error) { fieldError('reader-error', error.message); }
}

const foldSearch = text => text.normalize('NFD').replace(/\p{M}/gu, '').toLocaleLowerCase('pt-BR');

function findOccurrences(text, query) {
  const mapped = [], offsets = [];
  for (let index = 0; index < text.length;) {
    const character = String.fromCodePoint(text.codePointAt(index));
    const folded = foldSearch(character);
    mapped.push(folded);
    for (let unit = 0; unit < folded.length; unit++) offsets.push(index);
    index += character.length;
  }
  const normalized = mapped.join(''), needle = foldSearch(query), found = [];
  if (!needle) return found;
  for (let index = normalized.indexOf(needle); index !== -1; index = normalized.indexOf(needle, index + needle.length)) {
    found.push({start: offsets[index], end: offsets[index + needle.length] ?? text.length});
  }
  return found;
}

function navigateMaterialMatch(step = 0, scroll = true) {
  if (!materialMatches.length) return;
  activeMaterialMatch = (activeMaterialMatch + step + materialMatches.length) % materialMatches.length;
  materialMatches.forEach((item, index) => item.element.classList.toggle('current-match', index === activeMaterialMatch));
  $('material-position').textContent = `${activeMaterialMatch + 1} de ${materialMatches.length}`;
  if (scroll) materialMatches[activeMaterialMatch].element.scrollIntoView({block: 'center', behavior: 'smooth'});
}

function sentenceAround(text, start, end) {
  const before = text.slice(0, start), after = text.slice(end);
  let first = Math.max(before.lastIndexOf('.'), before.lastIndexOf('?'), before.lastIndexOf('!'), before.lastIndexOf('\n')) + 1;
  const following = after.search(/[.!?\n]/);
  let last = following < 0 ? text.length : end + following + 1;
  if (last - first > 500) { first = Math.max(first, start - 180); last = Math.min(last, first + 500); }
  while (first < last && /\s/.test(text[first])) first++;
  while (last > first && /\s/.test(text[last - 1])) last--;
  return {start: first, end: last};
}

function beginMaterialAnnotation(chunk, paragraph, preferSelection) {
  selectedRange = null;
  if (preferSelection) {
    const selection = window.getSelection();
    if (selection && selection.rangeCount) {
      const range = selection.getRangeAt(0);
      if (paragraph.contains(range.startContainer) && paragraph.contains(range.endContainer) && !range.collapsed) {
        const prefix = range.cloneRange(); prefix.selectNodeContents(paragraph); prefix.setEnd(range.startContainer, range.startOffset);
        selectedRange = {start: prefix.toString().length, end: prefix.toString().length + range.toString().length};
        if (selectedRange.end - selectedRange.start > 500) { selectedRange = null; fieldError('reader-error', 'Selecione até 500 caracteres.'); return; }
      }
    }
    if (!selectedRange) {
      const occurrence = materialMatches[activeMaterialMatch]?.chunkId === chunk.id ? materialMatches[activeMaterialMatch]
        : materialMatches.find(item => item.chunkId === chunk.id);
      if (occurrence) selectedRange = sentenceAround(chunk.body, occurrence.start, occurrence.end);
      else { fieldError('reader-error', 'Selecione uma frase ou pesquise para anotar a ocorrência.'); return; }
    }
  }
  selectedChunk = chunk;
  $('material-note-title').textContent = selectedRange ? 'Anotar seleção' : 'Anotar trecho';
  const quote = selectedRange ? chunk.body.slice(selectedRange.start, selectedRange.end) : chunk.body.slice(0, 360);
  $('material-quote').textContent = `${chunk.locator}: ${quote}`;
  fieldError('reader-error', ''); $('material-note-form').hidden = false; $('material-note-body').focus();
}

function renderMaterialChunks() {
  const list = $('material-chunks'); list.replaceChildren();
  const query = $('material-search').value.trim();
  materialMatches = []; activeMaterialMatch = 0;
  const chunks = (currentMaterial?.chunks || []).filter(item => !query || findOccurrences(item.body, query).length);
  if (!chunks.length) { const p = document.createElement('p'); p.className = 'empty'; p.textContent = query ? 'Nenhuma ocorrência corresponde à busca.' : 'Nenhum texto extraível. Confira o arquivo original.'; list.append(p); }
  chunks.forEach(chunk => {
    const section = document.createElement('section'), heading = document.createElement('h3');
    const body = document.createElement('p'), selectionButton = document.createElement('button'), chunkButton = document.createElement('button');
    section.className = 'material-chunk'; section.id = 'chunk-' + chunk.id; heading.textContent = chunk.locator;
    const occurrences = query ? findOccurrences(chunk.body, query) : [];
    let offset = 0;
    occurrences.forEach(match => {
      body.append(document.createTextNode(chunk.body.slice(offset, match.start)));
      const mark = document.createElement('mark'); mark.textContent = chunk.body.slice(match.start, match.end);
      body.append(mark); materialMatches.push({...match, element: mark, chunkId: chunk.id}); offset = match.end;
    });
    body.append(document.createTextNode(chunk.body.slice(offset)));
    selectionButton.type = chunkButton.type = 'button'; selectionButton.className = chunkButton.className = 'text-button';
    selectionButton.textContent = 'Anotar seleção ou frase encontrada'; chunkButton.textContent = 'Anotar trecho';
    selectionButton.onclick = () => beginMaterialAnnotation(chunk, body, true);
    chunkButton.onclick = () => beginMaterialAnnotation(chunk, body, false);
    section.append(heading, body, selectionButton, chunkButton); list.append(section);
  });
  $('material-search-count').textContent = query ?
    `${chunks.length} ${chunks.length === 1 ? 'trecho encontrado' : 'trechos encontrados'} · ${materialMatches.length} ${materialMatches.length === 1 ? 'ocorrência' : 'ocorrências'}.` :
    `${chunks.length} ${chunks.length === 1 ? 'trecho extraído' : 'trechos extraídos'}.`;
  $('material-search-nav').hidden = !materialMatches.length;
  $('material-position').textContent = materialMatches.length ? `1 de ${materialMatches.length}` : '';
  if (materialMatches.length) navigateMaterialMatch(0, false);
}

$('material-filter').onchange = renderMaterialList;
$('material-search').oninput = renderMaterialChunks;
$('material-prev').onclick = () => navigateMaterialMatch(-1);
$('material-next').onclick = () => navigateMaterialMatch(1);
$('material-guided').onclick = () => {
  if (!currentMaterial) return;
  busy($('material-guided'), 'Preparando…', async () => {
    const id = currentMaterial.id;
    location.hash = '#estudar';
    await window.tutorStartMaterial(id);
  }, text => fieldError('reader-error', text));
};
$('material-subject').onchange = () => { uiState.subject_id = $('material-subject').value || null; queueUiSave(); };
$('material-form').onsubmit = event => {
  event.preventDefault();
  const file = $('material-file').files[0], subjectId = $('material-subject').value;
  if (!subjectId) { fieldError('material-error', 'Escolha uma matéria.', 'material-subject'); return; }
  if (!file || !/\.(pdf|docx|txt)$/i.test(file.name) || !file.size || file.size > 5_000_000) {
    fieldError('material-error', 'Escolha PDF, DOCX ou TXT de até 5 MB.', 'material-file'); return;
  }
  fieldError('material-error', '', 'material-file');
  busy($('material-import'), 'Importando…', async () => {
    const contentBase64 = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error('Não foi possível ler o arquivo.'));
      reader.onload = () => resolve(String(reader.result).split(',', 2)[1]);
      reader.readAsDataURL(file);
    });
    const item = await api('/materials', 'POST', {subject_id: subjectId,
      name: $('material-name').value.trim(), filename: file.name, content_base64: contentBase64});
    $('material-file').value = ''; $('material-name').value = '';
    await refresh(); await openMaterial(item.id);
    message(item.status === 'ready' ? 'Material importado; texto pronto para leitura.' :
      'Original importado. Confira o estado da extração no leitor.', item.status === 'error' ? 'error' : 'success');
  }, text => fieldError('material-error', text, 'material-file'));
};
$('material-rename').onclick = () => {
  if (!currentMaterial) return;
  const next = prompt('Novo nome do material:', currentMaterial.name);
  if (next === null || next.trim() === currentMaterial.name) return;
  busy($('material-rename'), 'Renomeando…', async () => {
    const id = currentMaterial.id;
    await api('/materials/' + id, 'PATCH', {name: next.trim()});
    await refresh(); await openMaterial(id); message('Material renomeado.');
  }, text => fieldError('reader-error', text));
};
$('material-remove').onclick = () => {
  if (!currentMaterial || !confirm(`Remover ${currentMaterial.name}? O original e os trechos extraídos serão apagados. O texto das anotações será preservado.`)) return;
  busy($('material-remove'), 'Removendo…', async () => {
    await api('/materials/' + currentMaterial.id, 'DELETE', {confirmation: 'REMOVER'});
    currentMaterial = selectedChunk = null; $('reader-title').textContent = 'Escolha um material';
    $('reader-meta').textContent = 'O material foi removido. As anotações foram preservadas.';
    $('reader-controls').hidden = true; $('material-note-form').hidden = true;
    $('material-chunks').replaceChildren(); await refresh(); message('Material removido.');
  }, text => fieldError('reader-error', text));
};
$('material-note-form').onsubmit = event => {
  event.preventDefault();
  if (!currentMaterial || !selectedChunk) return;
  const body = $('material-note-body').value;
  if (!body.trim()) { fieldError('material-note-error', 'Escreva a anotação.', 'material-note-body'); return; }
  fieldError('material-note-error', '', 'material-note-body');
  busy($('material-note-save'), 'Salvando…', async () => {
    await api('/notes', 'POST', {subject_id: currentMaterial.subject_id,
      session_id: current?.subject_id === currentMaterial.subject_id ? current.id : null,
      material_id: currentMaterial.id, chunk_id: selectedChunk.id, body,
      selection_start: selectedRange ? Array.from(selectedChunk.body.slice(0, selectedRange.start)).length : null,
      selection_end: selectedRange ? Array.from(selectedChunk.body.slice(0, selectedRange.end)).length : null});
    $('material-note-body').value = ''; $('material-note-form').hidden = true;
    selectedChunk = selectedRange = null; await refresh(); message('Anotação vinculada ao trecho.');
  }, text => fieldError('material-note-error', text, 'material-note-body'));
};
$('material-note-cancel').onclick = () => { $('material-note-form').hidden = true; selectedChunk = selectedRange = null; };

function renderSessions() {
  const list = $('sessions-list'); list.replaceChildren();
  const completed = sessions.filter(item => item.status === 'complete');
  if (!completed.length) list.append(emptyItem('Nenhuma sessão concluída ainda. Ao concluir uma, ela aparecerá aqui.'));
  completed.forEach(item => {
    const li = document.createElement('li'), info = document.createElement('div'), title = document.createElement('strong');
    const date = document.createElement('small'), totals = document.createElement('div'), adjust = document.createElement('button');
    info.className = 'session-info'; totals.className = 'time-pair';
    title.textContent = item.subject_name;
    date.textContent = `${localDate(item.started_at)} → ${localDate(item.ended_at)}`;
    totals.innerHTML = `<span>Foco <strong>${duration(item.focus_seconds)}</strong></span><span>Pausa ${duration(item.pause_seconds)}</span>`;
    adjust.type = 'button'; adjust.textContent = 'Corrigir tempo de foco'; adjust.className = 'text-button';
    adjust.onclick = () => {
      const form = document.createElement('form'); form.className = 'adjust-form'; form.noValidate = true;
      const delta = document.createElement('input'); delta.inputMode = 'decimal'; delta.placeholder = 'Ex.: -2 ou 1,5';
      const reason = document.createElement('input'); reason.maxLength = 300; reason.placeholder = 'Motivo da correção';
      const deltaLabel = document.createElement('label'); deltaLabel.textContent = 'Ajuste em minutos'; deltaLabel.append(delta);
      const reasonLabel = document.createElement('label'); reasonLabel.textContent = 'Motivo'; reasonLabel.append(reason);
      const save = document.createElement('button'); save.className = 'secondary'; save.textContent = 'Registrar ajuste';
      const error = document.createElement('p'); error.className = 'field-error'; error.setAttribute('role', 'alert');
      form.onsubmit = event => {
        event.preventDefault();
        const minutes = Number(delta.value.trim().replace(',', '.'));
        if (!Number.isFinite(minutes) || !minutes || !Number.isInteger(minutes * 60)) { error.textContent = 'Informe minutos válidos, diferentes de zero.'; delta.focus(); return; }
        if (!reason.value.trim()) { error.textContent = 'Informe o motivo da correção.'; reason.focus(); return; }
        busy(save, 'Registrando…', async () => {
          await api('/sessions/' + item.id + '/adjustments', 'POST', {delta_seconds: minutes * 60, reason: reason.value.trim()});
          await refresh(); message('Correção registrada no histórico.');
        }, text => { error.textContent = text; });
      };
      form.append(deltaLabel, reasonLabel, save, error); adjust.replaceWith(form); delta.focus();
    };
    info.append(title, date, adjust);
    if (item.adjustments.length) {
      const history = document.createElement('ul'); history.className = 'adjustments';
      item.adjustments.forEach(entry => {
        const row = document.createElement('li');
        row.textContent = `${localDate(entry.created_at)} · ${entry.delta_seconds > 0 ? '+' : ''}${(entry.delta_seconds / 60).toLocaleString('pt-BR')} min · ${entry.reason}`;
        history.append(row);
      });
      info.append(history);
    }
    li.append(info, totals); list.append(li);
  });
}

function renderConfig(config) {
  sensorConfig = config;
  const camera = $('camera-index'), previous = document.activeElement === camera ? camera.value : String(config.presence_detector.camera_index);
  camera.replaceChildren();
  (cameraOptions?.indices || [0, 1, 2, 3, 4, 5]).forEach(index => camera.add(new Option(`Câmera ${index}`, String(index))));
  camera.value = previous;
  renderCameraOptions();
  const values = {
    'window-enabled': config.window_tracker.enabled, 'title-enabled': config.window_tracker.capture_titles,
    'idle-enabled': config.idle_tracker.enabled, 'presence-enabled': config.presence_detector.enabled,
    'multitask-enabled': config.multitask_analyzer.enabled,
    'window-interval': config.window_tracker.interval_seconds, 'idle-interval': config.idle_tracker.interval_seconds,
    'idle-threshold': config.idle_tracker.threshold_seconds, 'presence-interval': config.presence_detector.interval_seconds,
    'observation-seconds': config.multitask_analyzer.observation_seconds, 'alert-switches': config.multitask_analyzer.alert_switches
  };
  Object.entries(values).forEach(([id, value]) => {
    if ($(id).type === 'checkbox') $(id).checked = value; else $(id).value = value;
  });
}

function renderCameraOptions() {
  const named = cameraOptions?.devices || [];
  Array.from($('camera-index').options).forEach(option => {
    const index = Number(option.value);
    option.textContent = cameraOptions?.indexed && named[index] ? `Câmera ${index} · ${named[index]}` : `Câmera ${index}`;
  });
  $('camera-devices').textContent = named.length ? `${cameraOptions?.indexed ? 'DirectShow identificou' : 'O Windows identificou'}: ${named.join(', ')}. Confirme a imagem pelo teste.` :
    'O Windows não identificou câmera conectada nesta consulta. Você ainda pode testar um índice.';
  if (cameraOptions?.indexed && sensorConfig?.presence_detector.camera_index >= named.length)
    $('camera-status').textContent = 'A câmera escolhida não aparece mais. Selecione outra, teste a imagem e salve.';
}

function collectConfig() {
  const checked = id => $(id).checked, number = id => Number($(id).value);
  return {
    ...sensorConfig,
    window_tracker: {enabled: checked('window-enabled'), capture_titles: checked('title-enabled'), interval_seconds: number('window-interval')},
    idle_tracker: {enabled: checked('idle-enabled'), interval_seconds: number('idle-interval'), threshold_seconds: number('idle-threshold')},
    presence_detector: {enabled: checked('presence-enabled'), interval_seconds: number('presence-interval'),
      camera_index: number('camera-index')},
    multitask_analyzer: {enabled: checked('multitask-enabled'), observation_seconds: number('observation-seconds'), alert_switches: number('alert-switches')}
  };
}

const statusNames = {running: 'Ativo', disabled: 'Desligado', stopped: 'Encerrado', failed: 'Falhou',
  unavailable: 'Indisponível', waiting: 'Iniciando', stopping_timeout: 'Demorou para encerrar'};

async function refreshDiagnostics(updateConfig = false) {
  const configPromise = (updateConfig || !sensorConfig) ? api('/config') : Promise.resolve(null);
  const diagnosticPromise = api('/diagnostics');
  const cameraPromise = !cameraOptions ? api('/cameras') : Promise.resolve(null);
  const config = await configPromise;
  if (config) renderConfig(config);
  const [diagnostic, available] = await Promise.all([diagnosticPromise, cameraPromise]);
  if (available) { cameraOptions = available; renderCameraOptions(); }
  const health = $('health-list'); health.replaceChildren();
  if (!diagnostic.sensors.length) health.append(emptyItem('Sensores ainda não iniciados.'));
  diagnostic.sensors.forEach(sensor => {
    const li = document.createElement('li'), label = document.createElement('span'), status = document.createElement('small');
    label.textContent = sensor.sensor.replaceAll('_', ' ');
    status.textContent = (statusNames[sensor.status] || sensor.status) + (sensor.detail ? ' · ' + sensor.detail : '');
    status.className = sensor.status === 'running' ? 'healthy' : ['failed','unavailable','stopping_timeout'].includes(sensor.status) ? 'warning' : '';
    li.append(label, status); health.append(li);
  });
  const events = $('event-list'); events.replaceChildren();
  diagnostic.events.forEach(item => {
    const li = document.createElement('li'); li.textContent = `${localDate(item.at)} · ${item.sensor} · ${item.state}`; events.append(li);
  });
  if (!diagnostic.events.length) events.append(emptyItem('Nenhum evento ainda.'));
  $('log-view').textContent = diagnostic.log.length ? diagnostic.log.join('\n') : 'Nenhum erro registrado.';
}

async function refresh() {
  const revision = ++refreshRevision;
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const dayPath = `/progress/day?since=${encodeURIComponent(today.toISOString())}&until=${encodeURIComponent(now.toISOString())}`;
  const [active, all, recent, allNotes, allMaterials, week, day] = await Promise.all([
    api('/subjects'), api('/subjects?archived=1'), api('/sessions'), api('/notes'),
    api('/materials'), api('/progress'), api(dayPath)
  ]);
  if (revision !== refreshRevision) return;
  subjects = active; archivedSubjects = all.filter(item => item.archived);
  sessions = recent; notes = allNotes; materials = allMaterials; progress = week; dayProgress = day;
  current = sessions.find(item => item.status !== 'complete') || null;
  renderSubjects(); renderSession(); renderProgress(progress); renderHome(); renderNotes(); renderSessions(); renderMaterialList();
  window.refreshTutorContext?.();
}

$('home-primary').onclick = () => {
  if (current) { location.hash = '#estudar'; return; }
  const subjectId = $('home-subject').value;
  if (!subjectId) { fieldError('home-error', 'Escolha uma matéria.'); return; }
  busy($('home-primary'), 'Iniciando…', async () => {
    await api('/sessions', 'POST', {subject_id: subjectId});
    await refresh(); location.hash = '#estudar'; message('Nova sessão iniciada.');
  }, text => fieldError('home-error', text));
};
$('home-create').onclick = () => { location.hash = '#plano'; setTimeout(() => $('subject-name').focus(), 0); };
$('home-subject').onchange = () => { uiState.subject_id = $('home-subject').value || null; queueUiSave(); fieldError('home-error', ''); };
$('subject-select').onchange = () => {
  fieldError('start-error', '', 'subject-select');
  uiState.subject_id = $('subject-select').value || null; queueUiSave();
};
$('note-subject').onchange = () => {
  fieldError('note-error', '', 'note-subject');
  $('note-session-hint').textContent = current && $('note-subject').value === current.subject_id
    ? 'Será vinculada à sessão em andamento.' : 'Será vinculada à matéria selecionada.';
};
$('note-search').oninput = renderNotes;
$('note-filter-subject').onchange = renderNotes;

$('subject-form').onsubmit = event => {
  event.preventDefault();
  const input = $('subject-name'), name = input.value.trim();
  if (!name) { fieldError('subject-error', 'Informe o nome da matéria.', 'subject-name'); input.focus(); return; }
  fieldError('subject-error', '', 'subject-name');
  busy($('subject-submit'), 'Adicionando…', async () => {
    const created = await api('/subjects', 'POST', {name});
    input.value = ''; uiState.subject_id = created.id; queueUiSave();
    await refresh(); $('subject-created').hidden = false; message('Matéria adicionada.');
  }, text => fieldError('subject-error', text, 'subject-name'));
};

$('goal-form').onsubmit = event => {
  event.preventDefault();
  const raw = $('goal-hours').value.trim().replace(',', '.');
  const minutes = Number(raw) * 60;
  if (!Number.isInteger(minutes) || minutes < 1 || minutes > 10080) {
    fieldError('goal-error', 'Informe entre 1 minuto e 168 horas, usando vírgula ou ponto.', 'goal-hours'); return;
  }
  fieldError('goal-error', '', 'goal-hours');
  busy($('goal-submit'), 'Salvando…', async () => {
    await api('/preferences', 'PATCH', {weekly_goal_minutes: minutes});
    await refresh(); message('Meta atualizada.');
  }, text => fieldError('goal-error', text, 'goal-hours'));
};

$('start-form').onsubmit = event => {
  event.preventDefault();
  const subjectId = $('subject-select').value;
  if (!subjectId) { fieldError('start-error', 'Escolha uma matéria para iniciar.', 'subject-select'); $('subject-select').focus(); return; }
  fieldError('start-error', '', 'subject-select');
  busy($('start-btn'), 'Iniciando…', async () => {
    await api('/sessions', 'POST', {subject_id: subjectId});
    await refresh(); message('Sessão iniciada.');
  }, text => fieldError('start-error', text, 'subject-select'));
};

async function changeSession(action) {
  if (!current || sessionActionPending) return;
  sessionActionPending = true;
  const sessionId = current.id;
  const pause = $('pause-btn'), finish = $('finish-btn');
  const button = action === 'finish' ? finish : pause;
  pause.disabled = finish.disabled = true;
  button.textContent = {pause: 'Pausando…', resume: 'Retomando…', finish: 'Concluindo…'}[action];
  fieldError('session-error', '');
  try {
    await api('/sessions/' + sessionId + '/' + action, 'POST', {});
    if (action === 'finish') { audioWanted = false; stopSound(); completionChime(); }
    await refresh();
    message({pause: 'Sessão pausada.', resume: 'Sessão retomada.',
      finish: 'Sessão concluída. Confira o resumo abaixo.'}[action]);
  } catch (error) {
    fieldError('session-error', error.message);
    try { await refresh(); } catch { /* mantém o erro da transição visível */ }
  } finally {
    sessionActionPending = false;
    pause.disabled = finish.disabled = false;
    pause.textContent = current?.status === 'pause' ? 'Retomar' : 'Pausar';
    finish.textContent = 'Concluir sessão';
  }
}
$('pause-btn').onclick = () => changeSession(current?.status === 'pause' ? 'resume' : 'pause');
$('finish-btn').onclick = () => changeSession('finish');
$('focus-reminder-pause').onclick = () => changeSession('pause');
$('focus-reminder-dismiss').onclick = () => { $('focus-reminder').hidden = true; };
$('study-reader-select').onchange = () => loadStudyReader($('study-reader-select').value);

$('theme-quick').onclick = async () => {
  if (!experience) return;
  const previous = experience;
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  applyExperience({...previous, theme});
  try { applyExperience(await api('/experience', 'PATCH', {theme})); }
  catch (error) { applyExperience(previous); message(error.message, 'error'); }
};
$('experience-brightness').oninput = () => {
  document.documentElement.style.setProperty('--ui-dim', String((100 - Number($('experience-brightness').value)) / 100));
  $('brightness-value').textContent = $('experience-brightness').value + '%';
};
$('experience-volume').oninput = () => { $('volume-value').textContent = $('experience-volume').value + '%'; };
$('experience-form').onsubmit = event => {
  event.preventDefault();
  const values = {
    theme: $('experience-theme').value, brightness: Number($('experience-brightness').value),
    soundscape: $('experience-sound').value, volume: Number($('experience-volume').value),
    reminders_enabled: $('experience-reminders').checked,
    break_minutes: Number($('experience-break').value),
    excess_minutes: Number($('experience-excess').value),
    completion_sound: $('experience-completion').checked
  };
  busy($('experience-form').querySelector('button[type="submit"]'), 'Salvando…', async () => {
    applyExperience(await api('/experience', 'PATCH', values));
    fieldError('experience-error', ''); message('Ambiente de estudo salvo.');
  }, text => fieldError('experience-error', text));
};
$('focus-sound').onchange = () => {
  stopSound(); audioWanted = false;
  if ($('focus-sound').value === 'file' && !localAudioUrl) $('focus-file').click();
  $('focus-play').disabled = !current || current.status !== 'focus' || $('focus-sound').value === 'off';
  $('focus-audio-status').textContent = $('focus-sound').value === 'off' ? 'Som desligado.' :
    'Pronto para reproduzir. O som só começa quando você clicar no player.';
};
$('focus-file').onchange = () => {
  const file = $('focus-file').files[0];
  if (!file) { $('focus-sound').value = 'off'; $('focus-play').disabled = true; return; }
  if (!file.type.startsWith('audio/') || file.size > 50_000_000) {
    $('focus-audio-status').textContent = 'Escolha um áudio de até 50 MB.';
    $('focus-sound').value = 'off'; $('focus-play').disabled = true; return;
  }
  if (localAudioUrl) URL.revokeObjectURL(localAudioUrl);
  localAudioUrl = URL.createObjectURL(file);
  $('focus-audio-status').textContent = file.name + ' pronto. O arquivo fica no seu computador e não é importado.';
};
$('focus-play').onclick = async () => {
  if (audioNode || (localAudio && !localAudio.paused)) {
    audioWanted = false; stopSound(); $('focus-audio-status').textContent = 'Som pausado.'; return;
  }
  audioWanted = true;
  try { await startSound(); }
  catch (error) { audioWanted = false; stopSound(); $('focus-audio-status').textContent = error.message; }
};
$('focus-volume').oninput = () => {
  const volume = Number($('focus-volume').value);
  if (localAudio) localAudio.volume = volume / 100;
  if (audioNode?.gain) audioNode.gain.gain.value = volume / 100 * .18;
};
$('focus-volume').onchange = async () => {
  try { applyExperience(await api('/experience', 'PATCH', {volume: Number($('focus-volume').value)})); }
  catch (error) { message(error.message, 'error'); }
};
matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', () => {
  if (experience?.theme === 'system') applyExperience(experience);
});

function saveNote(form) {
  const quick = form.id === 'quick-note-form';
  const body = $(quick ? 'quick-note-body' : 'note-body');
  const errorId = quick ? 'quick-note-error' : 'note-error';
  const button = $(quick ? 'quick-note-save' : 'note-submit');
  const subjectId = quick ? current?.subject_id : $('note-subject').value;
  const sessionId = quick ? current?.id : current?.subject_id === subjectId ? current.id : null;
  if (!subjectId) { fieldError(errorId, 'Escolha uma matéria.', quick ? 'quick-note-body' : 'note-subject'); return; }
  if (!body.value.trim()) { fieldError(errorId, 'Escreva o texto da anotação.', body.id); body.focus(); return; }
  fieldError(errorId, '', body.id);
  busy(button, 'Salvando…', async () => {
    await api('/notes', 'POST', {subject_id: subjectId, session_id: sessionId, body: body.value});
    body.value = '';
    await refresh(); message('Anotação salva.');
  }, text => { fieldError(errorId, text, body.id); body.focus(); });
}
$('note-form').onsubmit = event => { event.preventDefault(); saveNote(event.currentTarget); };
$('quick-note-form').onsubmit = event => { event.preventDefault(); saveNote(event.currentTarget); };

$('sensor-form').onsubmit = event => {
  event.preventDefault(); fieldError('sensor-error', '');
  const config = collectConfig();
  busy($('save-sensors'), 'Salvando…', async () => {
    const saved = await api('/config', 'PATCH', config);
    renderConfig(saved); await refreshDiagnostics(); message('Sensores atualizados.');
  }, text => fieldError('sensor-error', text));
};
$('camera-test').onclick = () => busy($('camera-test'), 'Testando…', async () => {
  $('camera-preview').hidden = true; $('camera-image').removeAttribute('src');
  const result = await api('/cameras/test', 'POST', {index: Number($('camera-index').value)});
  $('camera-status').textContent = result.detail;
  if (result.status === 'ready') {
    $('camera-image').src = result.image; $('camera-preview').hidden = false;
  }
}, text => { $('camera-status').textContent = 'Falha ao testar a câmera: ' + text; });
$('camera-close').onclick = () => {
  $('camera-preview').hidden = true; $('camera-image').removeAttribute('src');
  $('camera-status').textContent = 'Teste fechado. A câmera foi liberada.';
};
$('camera-index').onchange = () => {
  $('camera-preview').hidden = true; $('camera-image').removeAttribute('src');
  $('camera-status').textContent = 'Teste este índice antes de salvar, para confirmar a imagem.';
};
$('refresh-diagnostics').onclick = () => busy($('refresh-diagnostics'), 'Atualizando…',
  async () => { await refreshDiagnostics(); message('Diagnóstico atualizado.'); });

$('import-btn').onclick = () => {
  const file = $('legacy-file').files[0];
  if (!file) { fieldError('import-error', 'Escolha um arquivo CSV.', 'legacy-file'); return; }
  if (!file.name.toLowerCase().endsWith('.csv') || file.size > 5_000_000) {
    fieldError('import-error', 'Escolha um CSV de até 5 MB.', 'legacy-file'); return;
  }
  if (!confirm(`Importar eventos de ${file.name}? O arquivo original será preservado.`)) return;
  fieldError('import-error', '', 'legacy-file');
  busy($('import-btn'), 'Importando…', async () => {
    const bytes = await file.arrayBuffer();
    let content, encoding = 'UTF-8';
    try { content = new TextDecoder('utf-8', {fatal: true}).decode(bytes); }
    catch { content = new TextDecoder('windows-1252', {fatal: true}).decode(bytes); encoding = 'Windows-1252'; }
    const result = await api('/import-legacy', 'POST', {name: file.name, content});
    $('import-report').textContent = `${result.rows_accepted} linhas aceitas; ${result.rows_rejected.length} rejeitadas · leitura ${encoding}.` +
      (result.rows_rejected.length ? '\n' + result.rows_rejected.slice(0, 10).map(item => `Linha ${item.line}: ${item.reason}`).join('\n') : '');
    await refreshDiagnostics(); message('Importação concluída. Confira o relatório.');
  }, text => fieldError('import-error', text, 'legacy-file'));
};

$('backup-btn').onclick = () => busy($('backup-btn'), 'Criando backup…', async () => {
  const result = await api('/backup', 'POST', {});
  $('backup-report').textContent = `Backup criado: ${result.name} (${Math.ceil(result.bytes / 1024)} KB).`;
  message('Backup criado.');
}, text => { $('backup-report').textContent = 'Falha ao criar backup: ' + text; });

$('open-backups-folder').onclick = () => busy($('open-backups-folder'), 'Abrindo…',
  async () => { await api('/app/open-backups-folder', 'POST', {}); });
$('open-data-folder').onclick = () => busy($('open-data-folder'), 'Abrindo…',
  async () => { await api('/app/open-data-folder', 'POST', {}); });
$('erase-data').onclick = () => {
  if (!confirm('Apagar permanentemente matérias, sessões, notas, eventos e configurações deste aplicativo?')) return;
  const confirmation = prompt('Digite APAGAR para confirmar. Uma cópia antiga no checkout WorkWatch, se existir, será preservada.');
  if (confirmation === null) return;
  fieldError('erase-error', '');
  busy($('erase-data'), 'Encerrando…', async () => {
    await api('/app/erase', 'POST', {confirmation});
    message('Encerrando e apagando os dados do aplicativo…');
  }, text => fieldError('erase-error', text));
};
$('quit-btn').onclick = () => busy($('quit-btn'), 'Saindo…', async () => {
  await uiSave.catch(() => {});
  await api('/app/quit', 'POST', {});
  message('Encerrando o Ritmo…');
});

window.addEventListener('hashchange', () => showView(location.hash.slice(1)));
window.addEventListener('pagehide', () => {
  stopSound();
  if (localAudioUrl) URL.revokeObjectURL(localAudioUrl);
  audioContext?.close().catch(() => {});
  fetch('/api/ui-state', {method: 'PATCH', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(uiState), keepalive: true}).catch(() => {});
});
setInterval(tick, 1000);
setInterval(() => { if (activeView === 'configuracoes') refreshDiagnostics().catch(() => {}); }, 15000);

async function boot() {
  $('app-loading').textContent = 'Carregando seus dados…';
  try {
    uiState = await api('/ui-state');
    await refresh();
    renderConfig(await api('/config'));
    applyExperience(await api('/experience'));
    $('app-loading').hidden = true;
    showView(VIEWS.has(location.hash.slice(1)) ? location.hash.slice(1) : uiState.view,
      {persist: VIEWS.has(location.hash.slice(1)) && location.hash.slice(1) !== uiState.view, focus: false});
  } catch (error) {
    $('app-loading').textContent = 'Não foi possível carregar o Ritmo: ' + error.message + ' ';
    const retry = document.createElement('button'); retry.className = 'secondary'; retry.textContent = 'Tentar novamente'; retry.onclick = boot;
    $('app-loading').append(retry);
  }
}
boot();
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
