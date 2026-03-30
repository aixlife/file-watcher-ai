// ═══ State ═══
let currentRules = [];
let generatedRule = null;

// ═══ Init ═══
document.addEventListener('DOMContentLoaded', async () => {
  const status = await api('/api/status');
  if (!status.setup_complete) {
    showScreen('setup-screen');
    checkEnvironment();
  } else {
    showScreen('main-screen');
    loadDashboard();
  }
});

// ═══ Helpers ═══
async function api(url, opts = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  return res.json();
}

function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.style.display = 'none');
  document.getElementById(id).style.display = 'block';
}

function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.toggle('active', c.id === `tab-${name}`));
  if (name === 'activity') loadLogs();
}

function closeModal(id) {
  document.getElementById(id).style.display = 'none';
}

// ═══ Setup Wizard ═══
async function checkEnvironment() {
  const env = await api('/api/environment');
  const checks = document.getElementById('env-checks');

  const items = [
    { ok: true, label: `OS: ${env.os} ${env.os_version}` },
    { ok: true, label: `Python: ${env.python_version}` },
    { ok: env.venv_exists, label: '가상환경 (.venv)', warn: '설치 필요' },
    { ok: env.dependencies_ok, label: '의존성 패키지', warn: '설치 필요' },
    { ok: env.gemini_api_key, label: 'Gemini API Key', warn: '미설정 (AI 규칙 생성 시 필요)', optional: true },
  ];

  checks.innerHTML = items.map(i => {
    const icon = i.ok ? '&#10003;' : (i.optional ? '!' : '&#10007;');
    const cls = i.ok ? 'ok' : (i.optional ? 'warn' : 'err');
    return `<div class="env-item">
      <span class="env-icon ${cls}">${icon}</span>
      <span>${i.label}${!i.ok ? ` <span style="color:var(--text-muted)">— ${i.warn}</span>` : ''}</span>
    </div>`;
  }).join('');

  if (!env.dependencies_ok) {
    document.getElementById('install-deps-area').style.display = 'block';
  }
}

async function installDeps() {
  const btn = document.getElementById('btn-install-deps');
  const status = document.getElementById('install-status');
  btn.disabled = true;
  status.innerHTML = '<span class="spinner"></span> 설치 중...';

  const result = await api('/api/setup/install-deps', { method: 'POST' });
  if (result.status === 'ok') {
    status.textContent = '설치 완료!';
    status.style.color = 'var(--green)';
    setTimeout(() => checkEnvironment(), 500);
  } else {
    status.textContent = `오류: ${result.message}`;
    status.style.color = 'var(--red)';
    btn.disabled = false;
  }
}

function goStep(n) {
  document.querySelectorAll('.setup-step').forEach(s => s.style.display = 'none');
  document.getElementById(`setup-step${n}`).style.display = 'block';
  if (n === 2) loadFolders('~');
}

async function loadFolders(path) {
  const result = await api(`/api/folders?path=${encodeURIComponent(path)}`);
  document.getElementById('current-path').textContent = result.current;
  document.getElementById('watch-dir-input').value = result.current;

  const list = document.getElementById('folder-list');
  if (!result.folders.length) {
    list.innerHTML = '<div class="folder-item" style="color:var(--text-muted)">하위 폴더 없음</div>';
    return;
  }
  list.innerHTML = result.folders.map(f =>
    `<div class="folder-item" onclick="selectFolder('${f.path}')">&#128193; ${f.name}</div>`
  ).join('');
}

function selectFolder(path) {
  document.getElementById('watch-dir-input').value = path;
  loadFolders(path);
}

function navigateFolder(path) {
  if (path === 'parent') {
    const current = document.getElementById('current-path').textContent;
    const parent = current.split('/').slice(0, -1).join('/') || '/';
    loadFolders(parent);
  } else {
    loadFolders(path);
  }
}

async function completeSetup() {
  const watchDir = document.getElementById('watch-dir-input').value.trim();
  if (!watchDir) return;

  await api('/api/setup', { method: 'POST', body: { watch_directory: watchDir } });
  showScreen('main-screen');
  loadDashboard();
}

// ═══ Dashboard ═══
async function loadDashboard() {
  await Promise.all([loadStatus(), loadRules()]);
}

async function loadStatus() {
  const status = await api('/api/status');
  const badge = document.getElementById('watcher-status');
  const btn = document.getElementById('btn-toggle-watcher');

  if (status.watcher_running) {
    badge.textContent = `실행 중 (PID: ${status.watcher_pid})`;
    badge.className = 'status-badge on';
    btn.textContent = '중지';
  } else {
    badge.textContent = '중지됨';
    badge.className = 'status-badge off';
    btn.textContent = '시작';
  }
}

async function toggleWatcher() {
  const badge = document.getElementById('watcher-status');
  const isRunning = badge.classList.contains('on');

  if (isRunning) {
    await api('/api/watcher/stop', { method: 'POST' });
  } else {
    await api('/api/watcher/start', { method: 'POST' });
  }
  await loadStatus();
}

// ═══ Rules ═══
async function loadRules() {
  const data = await api('/api/rules');
  currentRules = data.rules || [];
  document.getElementById('rules-count').textContent = currentRules.length;
  renderRules();
}

function renderRules() {
  const list = document.getElementById('rules-list');
  if (!currentRules.length) {
    list.innerHTML = `<div class="empty-state">
      <p>등록된 규칙이 없습니다</p>
      <p>규칙을 추가하거나 AI로 자동 생성하세요</p>
    </div>`;
    return;
  }

  list.innerHTML = currentRules.map((r, i) => {
    const enabled = r.enabled !== false;
    const trigger = r.trigger || {};
    const tags = [];
    if (trigger.filename_contains) tags.push(`키워드: *${trigger.filename_contains}*`);
    if (trigger.filename_starts_with) tags.push(`시작: ${trigger.filename_starts_with}*`);
    if (trigger.extensions) tags.push(trigger.extensions.join(', '));
    tags.push(`<span class="rule-tag action">${r.action || 'none'}</span>`);

    if (r.action === 'split_by_size' && r.options?.size_rules) {
      const sr = r.options.size_rules.map(s => `${s.min_kb}KB→${s.parts}분할`).join(', ');
      tags.push(sr);
    }
    if (r.action === 'move_to_folder' && r.options?.destination) {
      tags.push(`→ ${r.options.destination}`);
    }

    return `<div class="rule-card ${enabled ? '' : 'disabled'}">
      <div class="rule-top">
        <span class="rule-name">${r.name || 'unnamed'}</span>
        <div class="rule-actions">
          <button class="btn btn-ghost btn-sm" onclick="toggleRule(${i})">${enabled ? 'OFF' : 'ON'}</button>
          <button class="btn btn-ghost btn-sm" onclick="showAIEdit(${i})">AI 수정</button>
          <button class="btn btn-danger btn-sm" onclick="deleteRule(${i})">삭제</button>
        </div>
      </div>
      <div class="rule-desc">${r.description || ''}</div>
      <div class="rule-meta">${tags.map(t => t.startsWith('<') ? t : `<span class="rule-tag">${t}</span>`).join('')}</div>
    </div>`;
  }).join('');
}

async function toggleRule(index) {
  await api(`/api/rules/${index}/toggle`, { method: 'PATCH' });
  await loadRules();
}

async function deleteRule(index) {
  if (!confirm(`규칙 "${currentRules[index]?.name}"을 삭제하시겠습니까?`)) return;
  await api(`/api/rules/${index}`, { method: 'DELETE' });
  await loadRules();
}

// ═══ AI Edit ═══
let aiEditIndex = -1;
let aiEditedRule = null;

function showAIEdit(index) {
  aiEditIndex = index;
  aiEditedRule = null;
  const rule = currentRules[index];
  document.getElementById('ai-edit-current-json').textContent = JSON.stringify(rule, null, 2);
  document.getElementById('ai-edit-instruction').value = '';
  document.getElementById('ai-edit-result').style.display = 'none';
  document.getElementById('btn-ai-edit').style.display = '';
  document.getElementById('btn-ai-edit-apply').style.display = 'none';
  document.getElementById('modal-ai-edit').style.display = 'flex';
}

async function executeAIEdit() {
  const instruction = document.getElementById('ai-edit-instruction').value.trim();
  if (!instruction) return;

  const btn = document.getElementById('btn-ai-edit');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> AI 수정 중...';

  try {
    const result = await api(`/api/rules/${aiEditIndex}/ai-edit`, {
      method: 'POST',
      body: { instruction },
    });

    if (result.rule) {
      aiEditedRule = result.rule;
      document.getElementById('ai-edit-result-json').textContent = JSON.stringify(result.rule, null, 2);
      document.getElementById('ai-edit-result').style.display = 'block';
      document.getElementById('btn-ai-edit-apply').style.display = '';
    }
  } catch (e) {
    alert('AI 수정 실패: ' + (e.message || '알 수 없는 오류'));
  } finally {
    btn.disabled = false;
    btn.textContent = 'AI 수정';
  }
}

async function applyAIEdit() {
  if (!aiEditedRule || aiEditIndex < 0) return;
  await api(`/api/rules/${aiEditIndex}`, { method: 'PUT', body: aiEditedRule });
  closeModal('modal-ai-edit');
  await loadRules();
}

// ═══ AI Generate ═══
function showAIGenerate() {
  document.getElementById('ai-description').value = '';
  document.getElementById('ai-result').style.display = 'none';
  document.getElementById('btn-ai-generate').style.display = '';
  document.getElementById('btn-ai-apply').style.display = 'none';
  generatedRule = null;
  document.getElementById('modal-ai').style.display = 'flex';
}

async function generateAIRule() {
  const desc = document.getElementById('ai-description').value.trim();
  if (!desc) return;

  const btn = document.getElementById('btn-ai-generate');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> 생성 중...';

  try {
    const result = await api('/api/rules/generate', { method: 'POST', body: { description: desc } });

    if (result.rule) {
      generatedRule = result.rule;
      document.getElementById('ai-result-json').textContent = JSON.stringify(result.rule, null, 2);
      document.getElementById('ai-result').style.display = 'block';
      document.getElementById('btn-ai-apply').style.display = '';
    }
  } catch (e) {
    alert('AI 생성 실패: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = '생성';
  }
}

async function applyAIRule() {
  if (!generatedRule) return;
  await api('/api/rules', { method: 'POST', body: generatedRule });
  closeModal('modal-ai');
  await loadRules();
}

// ═══ Settings ═══
async function showSettings() {
  const [settings, config] = await Promise.all([
    api('/api/settings'),
    api('/api/config'),
  ]);
  document.getElementById('setting-watch-dir').value = settings.watch_directory || '~/Downloads';
  document.getElementById('setting-originals').value = settings.originals_directory || '_originals';
  document.getElementById('setting-processed').value = settings.processed_directory || '_processed';
  document.getElementById('setting-stability').value = settings.stability_seconds || 3;
  document.getElementById('setting-cooldown').value = settings.cooldown_seconds || 10;

  // API Key 상태 표시
  const apiKeyInput = document.getElementById('setting-api-key');
  const apiKeyStatus = document.getElementById('setting-api-key-status');
  apiKeyInput.value = '';
  if (config.gemini_api_key_masked) {
    apiKeyInput.placeholder = `저장됨: ${config.gemini_api_key_masked}`;
    apiKeyStatus.textContent = '저장됨';
    apiKeyStatus.style.color = 'var(--green)';
  } else {
    apiKeyInput.placeholder = 'AI 규칙 생성/수정에 필요';
    apiKeyStatus.textContent = '미설정';
    apiKeyStatus.style.color = 'var(--yellow)';
  }

  document.getElementById('modal-settings').style.display = 'flex';
}

async function saveSettings() {
  const settings = {
    watch_directory: document.getElementById('setting-watch-dir').value.trim(),
    originals_directory: document.getElementById('setting-originals').value.trim(),
    processed_directory: document.getElementById('setting-processed').value.trim(),
    stability_seconds: parseInt(document.getElementById('setting-stability').value),
    cooldown_seconds: parseInt(document.getElementById('setting-cooldown').value),
  };
  await api('/api/settings', { method: 'PUT', body: settings });

  // API Key가 입력되었으면 config에 저장
  const apiKeyValue = document.getElementById('setting-api-key').value.trim();
  if (apiKeyValue) {
    await api('/api/config', { method: 'PUT', body: { gemini_api_key: apiKeyValue } });
  }

  closeModal('modal-settings');
}

// ═══ Activity Logs ═══
async function loadLogs() {
  const data = await api('/api/logs');

  const actList = document.getElementById('activity-list');
  if (data.activity?.length) {
    actList.innerHTML = data.activity.map(a => `
      <div class="activity-item">
        <span class="activity-time">${a.time}</span>
        <span class="activity-type ${a.type}">${a.type}</span>
        <span class="activity-msg">${a.message} ${a.detail ? `<span class="activity-detail">${a.detail}</span>` : ''}</span>
      </div>
    `).join('');
  } else {
    actList.innerHTML = '<div class="empty-state"><p>활동 기록 없음</p></div>';
  }

  const logArea = document.getElementById('watcher-logs');
  if (data.watcher_logs?.length) {
    logArea.textContent = data.watcher_logs.map(l => l.message).join('\n');
    logArea.scrollTop = logArea.scrollHeight;
  } else {
    logArea.textContent = 'Watcher 로그 없음';
  }
}
