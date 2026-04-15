// frontend/js/admin.js - админ панель, аудит, пользователи, документы

let adminDocFilter = 'all';
let adminUsersSort = 'last_login';
let adminOnlyBlocked = false;
let knowledgeActiveOnly = false;
const knowledgeStore = { sources: [], glossary: [], rules: [] };
let knowledgeEditState = null;

async function apiGet(path) {
  const token = localStorage.getItem('llm_auth_token');
  const res = await fetch(path, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Ошибка ${res.status}: ${body}`);
  }
  return res.json();
}

async function apiPatch(path, payload) {
  const token = localStorage.getItem('llm_auth_token');
  const res = await fetch(path, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Ошибка ${res.status}: ${body}`);
  }
  return res.json();
}

async function apiPost(path, payload = null) {
  const token = localStorage.getItem('llm_auth_token');
  const options = {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  };
  if (payload !== null) options.body = JSON.stringify(payload);
  const res = await fetch(path, options);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Ошибка ${res.status}: ${body}`);
  }
  return res.json();
}

async function apiPostAsCurrentUser(path, payload = null) {
  return apiPost(path, payload);
}

async function apiDelete(path) {
  const token = localStorage.getItem('llm_auth_token');
  const res = await fetch(path, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Ошибка ${res.status}: ${body}`);
  }
}

function escapeHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function safeDecodeURIComponent(value) {
  try {
    return decodeURIComponent(String(value ?? ''));
  } catch (_) {
    return String(value ?? '');
  }
}

function setInlineError(id, message = '') {
  const el = document.getElementById(id);
  if (!el) return;
  if (!message) {
    el.textContent = '';
    el.classList.add('hidden');
    return;
  }
  el.textContent = message;
  el.classList.remove('hidden');
}

function clearKnowledgeFormErrors() {
  setInlineError('knowledge-source-error', '');
  setInlineError('knowledge-term-error', '');
  setInlineError('knowledge-rule-error', '');
}

function setActiveFilter(buttonIds, activeId) {
  buttonIds.forEach(id => {
    const btn = document.getElementById(id);
    if (!btn) return;
    if (id === activeId) btn.classList.add('active-filter');
    else btn.classList.remove('active-filter');
  });
}

async function loadAdminOverview() {
  try {
    const overview = await apiGet('/api/admin/overview');
    const history = await apiGet('/api/analysis/history?limit=20');

    const usersEl = document.getElementById('admin-users-count');
    const docsEl = document.getElementById('admin-documents-count');
    const analysesEl = document.getElementById('admin-analyses-count');
    const logsEl = document.getElementById('admin-logs-count');
    const activeUsersEl = document.getElementById('admin-active-users-24h');
    const uploads24hEl = document.getElementById('admin-uploads-24h');
    const analyses24hEl = document.getElementById('admin-analyses-24h');
    const splitEl = document.getElementById('admin-doc-purpose-split');

    if (usersEl) usersEl.textContent = overview.users_count;
    if (docsEl) docsEl.textContent = overview.documents_count;
    if (analysesEl) analysesEl.textContent = overview.analysis_runs_count;
    if (logsEl) logsEl.textContent = overview.audit_logs_count;
    if (activeUsersEl) activeUsersEl.textContent = overview.active_users_24h;
    if (uploads24hEl) uploads24hEl.textContent = overview.uploads_24h;
    if (analyses24hEl) analyses24hEl.textContent = overview.analyses_24h;
    if (splitEl) splitEl.textContent = `${overview.check_documents_count}/${overview.training_documents_count}`;

    const listEl = document.getElementById('admin-history-list');
    if (!listEl) return;
    if (!history.length) {
      listEl.innerHTML = '<p class="summary-text">Пока нет проверок.</p>';
      return;
    }

    listEl.innerHTML = history.map(item => `
      <div class="admin-list-item">
        <div><strong>${escapeHtml(item.filename || 'Без имени')}</strong></div>
        <div>Пользователь: ${escapeHtml(item.user_email || '—')}</div>
        <div>Оценка: ${item.overall_score}/100</div>
        <div>Режим: ${escapeHtml(item.model_mode || item.run_mode || 'unknown')}</div>
        <div>Время: ${escapeHtml(item.created_at || '')}</div>
      </div>
    `).join('');
  } catch (err) {
    const listEl = document.getElementById('admin-history-list');
    if (listEl) listEl.innerHTML = `<p class="summary-text">Ошибка: ${escapeHtml(err.message)}</p>`;
  }
}

async function loadAdminAuditLogs() {
  try {
    const logs = await apiGet('/api/admin/audit-logs?limit=120');
    const listEl = document.getElementById('admin-audit-list');
    if (!listEl) return;
    if (!logs.length) {
      listEl.innerHTML = '<p class="summary-text">Аудит-логи пока пусты.</p>';
      return;
    }
    listEl.innerHTML = logs.map(item => `
      <div class="admin-list-item">
        <div><strong>${escapeHtml(item.action)}</strong></div>
        <div>Пользователь: ${escapeHtml(item.user_email || item.user_id || 'system')}</div>
        <div>Ресурс: ${escapeHtml(item.resource_type || '—')} ${escapeHtml(item.resource_id || '')}</div>
        <div>IP: ${escapeHtml(item.ip_address || '—')}</div>
        <div>Время: ${escapeHtml(item.created_at || '')}</div>
      </div>
    `).join('');
  } catch (err) {
    const listEl = document.getElementById('admin-audit-list');
    if (listEl) listEl.innerHTML = `<p class="summary-text">Ошибка: ${escapeHtml(err.message)}</p>`;
  }
}

async function loadAdminDocuments(purpose = 'all') {
  adminDocFilter = purpose;
  setActiveFilter(
    ['admin-doc-filter-all', 'admin-doc-filter-check', 'admin-doc-filter-training'],
    purpose === 'all' ? 'admin-doc-filter-all' : purpose === 'check' ? 'admin-doc-filter-check' : 'admin-doc-filter-training'
  );

  try {
    const qs = purpose === 'all' ? '' : `?purpose=${encodeURIComponent(purpose)}`;
    const docs = await apiGet(`/api/documents${qs}`);
    const listEl = document.getElementById('admin-documents-list');
    if (!listEl) return;
    if (!docs.length) {
      listEl.innerHTML = '<p class="summary-text">Документы не найдены.</p>';
      return;
    }
    listEl.innerHTML = docs.map(item => `
      <div class="admin-list-item">
        <div><strong>${escapeHtml(item.filename || 'Без имени')}</strong></div>
        <div>Пользователь: ${escapeHtml(item.owner_email || '—')}</div>
        <div>Назначение: ${escapeHtml(item.purpose || 'check')}</div>
        <div>Конфиденциальность: ${escapeHtml(item.confidentiality_level || 'confidential')}</div>
        <div>Тип: ${escapeHtml(item.source_type || '—')}</div>
        <div>Слов: ${Number(item.word_count || 0)} | Размер: ${Number(item.file_size || 0)} байт</div>
        <div>Время: ${escapeHtml(item.created_at || '')}</div>
        <div class="inline-actions">
          <button class="btn-small" onclick="previewDocumentContent(${item.id}, 'admin-document-preview')">Просмотр</button>
          <button class="btn-small btn-danger" onclick="adminDeleteDocument(${item.id}, '${encodeURIComponent(String(item.filename || ''))}')">Удалить</button>
        </div>
      </div>
    `).join('') + '<div id="admin-document-preview" class="doc-viewer"></div>';
  } catch (err) {
    const listEl = document.getElementById('admin-documents-list');
    if (listEl) listEl.innerHTML = `<p class="summary-text">Ошибка: ${escapeHtml(err.message)}</p>`;
  }
}

async function adminDeleteDocument(documentId, encodedFilename = '') {
  const filename = safeDecodeURIComponent(encodedFilename);
  const namePart = filename ? ` "${filename}"` : '';
  if (!confirm(`Удалить документ${namePart} (ID ${documentId})?`)) return;
  try {
    await apiDelete(`/api/documents/${documentId}`);
    await loadAdminDocuments(adminDocFilter);
  } catch (err) {
    alert(err.message || 'Ошибка удаления документа');
  }
}

function toggleBlockedUsersFilter() {
  adminOnlyBlocked = !adminOnlyBlocked;
  const btn = document.getElementById('admin-users-only-blocked');
  if (btn) btn.textContent = `Только заблокированные: ${adminOnlyBlocked ? 'да' : 'нет'}`;
  loadAdminUsersSummary(adminUsersSort);
}

async function setUserActive(encodedUserId, isActive) {
  const userId = safeDecodeURIComponent(encodedUserId);
  try {
    const result = await apiPatch(`/api/admin/users/${encodeURIComponent(userId)}/status`, { is_active: isActive });
    if (!result.ok) throw new Error(result.message || 'Не удалось обновить статус');
    await loadAdminUsersSummary(adminUsersSort);
  } catch (err) {
    alert(err.message || 'Ошибка обновления статуса');
  }
}

async function loadAdminUsersSummary(sortBy = 'last_login') {
  adminUsersSort = sortBy;
  setActiveFilter(
    ['admin-users-sort-last-login', 'admin-users-sort-account-age'],
    sortBy === 'last_login' ? 'admin-users-sort-last-login' : 'admin-users-sort-account-age'
  );

  try {
    const query = new URLSearchParams({
      limit: '200',
      sort_by: sortBy,
      sort_order: 'desc',
      only_blocked: adminOnlyBlocked ? 'true' : 'false'
    });
    const users = await apiGet(`/api/admin/users-summary?${query.toString()}`);
    const listEl = document.getElementById('admin-users-list');
    if (!listEl) return;
    if (!users.length) {
      listEl.innerHTML = '<p class="summary-text">Пользователи не найдены.</p>';
      return;
    }

    listEl.innerHTML = users.map(item => `
      <div class="admin-list-item">
        <div><strong>${escapeHtml(item.email)}</strong> (${escapeHtml(item.username)})</div>
        <div>Статус: ${item.is_active ? 'активен' : 'заблокирован'} | Роль: ${item.is_admin ? 'admin' : 'user'}</div>
        <div>Документов: ${item.documents_count} (check: ${item.check_documents_count}, training: ${item.training_documents_count})</div>
        <div>Проверок: ${item.analyses_count}</div>
        <div>Регистрация: ${escapeHtml(item.created_at || '—')}</div>
        <div>Последний вход: ${escapeHtml(item.last_login_at || '—')}</div>
        <div>Последняя активность: ${escapeHtml(item.last_activity_at || '—')}</div>
        <div class="inline-actions">
          ${item.is_active
            ? `<button class="btn-small btn-danger" onclick="setUserActive('${encodeURIComponent(String(item.user_id || ''))}', false)">Заблокировать</button>`
            : `<button class="btn-small" onclick="setUserActive('${encodeURIComponent(String(item.user_id || ''))}', true)">Разблокировать</button>`}
        </div>
      </div>
    `).join('');
  } catch (err) {
    const listEl = document.getElementById('admin-users-list');
    if (listEl) listEl.innerHTML = `<p class="summary-text">Ошибка: ${escapeHtml(err.message)}</p>`;
  }
}

function splitBySemicolon(value) {
  return String(value || '')
    .split(';')
    .map(x => x.trim())
    .filter(Boolean);
}

function renderSourceSelect(selectEl, sources, selectedValue = '') {
  if (!selectEl) return;
  const selected = String(selectedValue || '');
  const options = [`<option value="">Источник: не выбран</option>`];
  (sources || []).forEach((source) => {
    const sid = String(source.id);
    const label = `${escapeHtml(source.title || 'Без названия')} (${escapeHtml(source.reference_code || 'без кода')})`;
    options.push(`<option value="${sid}" ${sid === selected ? 'selected' : ''}>${label}</option>`);
  });
  selectEl.innerHTML = options.join('');
}

async function seedAdminKnowledgeDefaults() {
  try {
    const result = await apiPost('/api/admin/knowledge/seed-defaults');
    alert(`Добавлено: источники ${result.sources_created}, термины ${result.glossary_created}, правила ${result.rules_created}`);
    await loadAdminKnowledge();
  } catch (err) {
    alert(err.message || 'Ошибка сидирования базы знаний');
  }
}

async function loadAdminKnowledge() {
  try {
    clearKnowledgeFormErrors();
    const activeQuery = knowledgeActiveOnly ? '&active_only=true' : '';
    const [overview, sources, glossary, rules, audit] = await Promise.all([
      apiGet('/api/admin/knowledge/overview'),
      apiGet(`/api/admin/knowledge/sources?limit=200${activeQuery}`),
      apiGet(`/api/admin/knowledge/glossary?limit=200${activeQuery}`),
      apiGet(`/api/admin/knowledge/rules?limit=200${activeQuery}`),
      apiGet('/api/admin/audit-logs?limit=120')
    ]);

    const filterBtn = document.getElementById('knowledge-filter-active-btn');
    if (filterBtn) filterBtn.textContent = `Только активные: ${knowledgeActiveOnly ? 'да' : 'нет'}`;

    const sourcesCountEl = document.getElementById('knowledge-sources-count');
    const glossaryCountEl = document.getElementById('knowledge-glossary-count');
    const rulesCountEl = document.getElementById('knowledge-rules-count');
    const activeRulesCountEl = document.getElementById('knowledge-active-rules-count');
    if (sourcesCountEl) sourcesCountEl.textContent = String(overview.sources_count ?? 0);
    if (glossaryCountEl) glossaryCountEl.textContent = String(overview.glossary_terms_count ?? 0);
    if (rulesCountEl) rulesCountEl.textContent = String(overview.rule_patterns_count ?? 0);
    if (activeRulesCountEl) activeRulesCountEl.textContent = String(overview.active_rule_patterns_count ?? 0);

    const sourcesListEl = document.getElementById('knowledge-sources-list');
    if (sourcesListEl) {
      sourcesListEl.innerHTML = (sources || []).map(item => `
        <div class="admin-list-item ${item.is_active ? '' : 'item-inactive'}">
          <div class="knowledge-row">
            <div>
              <div><strong>${escapeHtml(item.title)}</strong></div>
              <div class="knowledge-sub">ID ${item.id} | ${escapeHtml(item.reference_code || 'без кода')}</div>
            </div>
            <div class="knowledge-meta">
              <span class="knowledge-pill">${item.is_active ? 'active' : 'inactive'}</span>
            </div>
          </div>
          <div class="knowledge-sub">Раздел: ${escapeHtml(item.section || '—')}</div>
          <div class="inline-actions">
            <button class="btn-small" onclick="editKnowledgeSource(${item.id})">Изменить</button>
            ${item.is_active
              ? `<button class="btn-small btn-danger" onclick="setKnowledgeSourceActive(${item.id}, false)">Выкл</button>`
              : `<button class="btn-small" onclick="setKnowledgeSourceActive(${item.id}, true)">Вкл</button>`}
          </div>
        </div>
      `).join('') || '<p class="summary-text">Источники пока пусты.</p>';
    }

    const glossaryListEl = document.getElementById('knowledge-glossary-list');
    if (glossaryListEl) {
      glossaryListEl.innerHTML = (glossary || []).map(item => `
        <div class="admin-list-item ${item.is_active ? '' : 'item-inactive'}">
          <div class="knowledge-row">
            <div>
              <div><strong>${escapeHtml(item.term)}</strong></div>
              <div class="knowledge-sub">ID ${item.id}</div>
            </div>
            <div class="knowledge-meta">
              <span class="knowledge-pill">${escapeHtml(item.severity_default)}</span>
              <span class="knowledge-pill">${item.is_active ? 'active' : 'inactive'}</span>
            </div>
          </div>
          <div class="knowledge-sub">${escapeHtml(item.canonical_definition)}</div>
          <div class="knowledge-sub">Запрещено: ${escapeHtml((item.forbidden_variants || []).join(', ') || '—')}</div>
          <div class="knowledge-sub">Источник: ${escapeHtml(item.source_ref_title || '—')}</div>
          <div class="inline-actions">
            <button class="btn-small" onclick="editKnowledgeTerm(${item.id})">Изменить</button>
            ${item.is_active
              ? `<button class="btn-small btn-danger" onclick="setKnowledgeTermActive(${item.id}, false)">Выкл</button>`
              : `<button class="btn-small" onclick="setKnowledgeTermActive(${item.id}, true)">Вкл</button>`}
          </div>
        </div>
      `).join('') || '<p class="summary-text">Термины пока пусты.</p>';
    }

    const rulesListEl = document.getElementById('knowledge-rules-list');
    if (rulesListEl) {
      rulesListEl.innerHTML = (rules || []).map(item => `
        <div class="admin-list-item ${item.is_active ? '' : 'item-inactive'}">
          <div class="knowledge-row">
            <div>
              <div><strong>${escapeHtml(item.name)}</strong></div>
              <div class="knowledge-sub">ID ${item.id}</div>
            </div>
            <div class="knowledge-meta">
              <span class="knowledge-pill">${escapeHtml(item.rule_type)}</span>
              <span class="knowledge-pill">${escapeHtml(item.severity)}</span>
              <span class="knowledge-pill">${item.is_active ? 'active' : 'inactive'}</span>
            </div>
          </div>
          <div class="knowledge-sub"><code>${escapeHtml(item.pattern)}</code></div>
          <div class="knowledge-sub">${escapeHtml(item.description || 'Без описания')}</div>
          <div class="knowledge-sub">Источник: ${escapeHtml(item.source_ref_title || '—')}</div>
          <div class="inline-actions">
            <button class="btn-small" onclick="editKnowledgeRule(${item.id})">Изменить</button>
            ${item.is_active
              ? `<button class="btn-small btn-danger" onclick="setKnowledgeRuleActive(${item.id}, false)">Выкл</button>`
              : `<button class="btn-small" onclick="setKnowledgeRuleActive(${item.id}, true)">Вкл</button>`}
          </div>
        </div>
      `).join('') || '<p class="summary-text">Правила пока пусты.</p>';
    }

    knowledgeStore.sources = Array.isArray(sources) ? sources : [];
    knowledgeStore.glossary = Array.isArray(glossary) ? glossary : [];
    knowledgeStore.rules = Array.isArray(rules) ? rules : [];
    renderSourceSelect(document.getElementById('knowledge-term-source-id'), knowledgeStore.sources);
    renderSourceSelect(document.getElementById('knowledge-rule-source-id'), knowledgeStore.sources);

    bindKnowledgeForms();
    setupKnowledgeTestInputAutoResize();
    await loadKnowledgeSnapshots();

    const auditListEl = document.getElementById('knowledge-audit-list');
    if (auditListEl) {
      const knowledgeLogs = (Array.isArray(audit) ? audit : []).filter((x) => String(x.action || '').startsWith('knowledge_'));
      auditListEl.innerHTML = knowledgeLogs.length
        ? knowledgeLogs.slice(0, 30).map(item => `
            <div class="admin-list-item">
              <div><strong>${escapeHtml(item.action)}</strong></div>
              <div>Кто: ${escapeHtml(item.user_email || item.user_id || 'system')}</div>
              <div>Объект: ${escapeHtml(item.resource_type || '—')} ${escapeHtml(item.resource_id || '')}</div>
              <div>Время: ${escapeHtml(item.created_at || '')}</div>
            </div>
          `).join('')
        : '<p class="summary-text">Изменений пока нет.</p>';
    }
  } catch (err) {
    const wrapIds = ['knowledge-sources-list', 'knowledge-glossary-list', 'knowledge-rules-list'];
    wrapIds.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = `<p class="summary-text">Ошибка: ${escapeHtml(err.message)}</p>`;
    });
  }
}

function setupKnowledgeTestInputAutoResize() {
  const input = document.getElementById('knowledge-test-text');
  if (!input) return;
  if (!input.dataset.autosizeBound) {
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = `${Math.max(92, input.scrollHeight)}px`;
    });
    input.dataset.autosizeBound = '1';
  }
  input.style.height = 'auto';
  input.style.height = `${Math.max(92, input.scrollHeight)}px`;
}

function bindKnowledgeForms() {
  const sourceForm = document.getElementById('knowledge-source-form');
  if (sourceForm) {
    sourceForm.onsubmit = async (e) => {
      e.preventDefault();
      clearKnowledgeFormErrors();
      const title = document.getElementById('knowledge-source-title')?.value.trim();
      const referenceCode = (document.getElementById('knowledge-source-code')?.value || '').trim().toUpperCase();
      const section = document.getElementById('knowledge-source-section')?.value.trim();
      if (!title) {
        setInlineError('knowledge-source-error', 'Введите название источника.');
        return;
      }
      if (referenceCode && !/^[A-Z0-9][A-Z0-9._-]{1,63}$/.test(referenceCode)) {
        setInlineError('knowledge-source-error', 'Некорректный код источника.');
        return;
      }
      try {
        await apiPost('/api/admin/knowledge/sources', {
          title,
          reference_code: referenceCode || null,
          section: section || null
        });
        sourceForm.reset();
        await loadAdminKnowledge();
      } catch (err) {
        setInlineError('knowledge-source-error', err.message || 'Ошибка добавления источника');
      }
    };
  }

  const glossaryForm = document.getElementById('knowledge-glossary-form');
  if (glossaryForm) {
    glossaryForm.onsubmit = async (e) => {
      e.preventDefault();
      clearKnowledgeFormErrors();
      const term = document.getElementById('knowledge-term')?.value.trim();
      const definition = document.getElementById('knowledge-term-definition')?.value.trim();
      const forbiddenRaw = document.getElementById('knowledge-term-forbidden')?.value;
      const severity = document.getElementById('knowledge-term-severity')?.value || 'medium';
      const sourceRefIdRaw = document.getElementById('knowledge-term-source-id')?.value || '';
      if (!term || !definition) {
        setInlineError('knowledge-term-error', 'Термин и определение обязательны.');
        return;
      }
      try {
        await apiPost('/api/admin/knowledge/glossary', {
          term,
          canonical_definition: definition,
          forbidden_variants: splitBySemicolon(forbiddenRaw),
          severity_default: severity,
          source_ref_id: sourceRefIdRaw ? Number(sourceRefIdRaw) : null
        });
        glossaryForm.reset();
        renderSourceSelect(document.getElementById('knowledge-term-source-id'), knowledgeStore.sources);
        await loadAdminKnowledge();
      } catch (err) {
        setInlineError('knowledge-term-error', err.message || 'Ошибка добавления термина');
      }
    };
  }

  const ruleForm = document.getElementById('knowledge-rule-form');
  if (ruleForm) {
    ruleForm.onsubmit = async (e) => {
      e.preventDefault();
      clearKnowledgeFormErrors();
      const name = document.getElementById('knowledge-rule-name')?.value.trim();
      const pattern = document.getElementById('knowledge-rule-pattern')?.value;
      const description = document.getElementById('knowledge-rule-description')?.value.trim();
      const suggestion = document.getElementById('knowledge-rule-suggestion')?.value.trim();
      const severity = document.getElementById('knowledge-rule-severity')?.value || 'medium';
      const sourceRefIdRaw = document.getElementById('knowledge-rule-source-id')?.value || '';
      if (!name || !pattern) {
        setInlineError('knowledge-rule-error', 'Название и pattern обязательны.');
        return;
      }
      try {
        await apiPost('/api/admin/knowledge/rules', {
          name,
          rule_type: 'regex',
          pattern,
          description: description || null,
          suggestion_template: suggestion || null,
          severity,
          source_ref_id: sourceRefIdRaw ? Number(sourceRefIdRaw) : null
        });
        ruleForm.reset();
        renderSourceSelect(document.getElementById('knowledge-rule-source-id'), knowledgeStore.sources);
        await loadAdminKnowledge();
      } catch (err) {
        setInlineError('knowledge-rule-error', err.message || 'Ошибка добавления правила');
      }
    };
  }
}

async function deactivateKnowledgeSource(id) {
  if (!confirm(`Деактивировать источник #${id}?`)) return;
  try {
    await apiDelete(`/api/admin/knowledge/sources/${id}`);
    await loadAdminKnowledge();
  } catch (err) {
    alert(err.message || 'Ошибка деактивации источника');
  }
}

async function deactivateKnowledgeTerm(id) {
  if (!confirm(`Деактивировать термин #${id}?`)) return;
  try {
    await apiDelete(`/api/admin/knowledge/glossary/${id}`);
    await loadAdminKnowledge();
  } catch (err) {
    alert(err.message || 'Ошибка деактивации термина');
  }
}

async function deactivateKnowledgeRule(id) {
  if (!confirm(`Деактивировать правило #${id}?`)) return;
  try {
    await apiDelete(`/api/admin/knowledge/rules/${id}`);
    await loadAdminKnowledge();
  } catch (err) {
    alert(err.message || 'Ошибка деактивации правила');
  }
}

async function setKnowledgeSourceActive(id, isActive) {
  try {
    await apiPatch(`/api/admin/knowledge/sources/${id}`, { is_active: isActive });
    await loadAdminKnowledge();
  } catch (err) {
    alert(err.message || 'Ошибка изменения статуса источника');
  }
}

async function setKnowledgeTermActive(id, isActive) {
  try {
    await apiPatch(`/api/admin/knowledge/glossary/${id}`, { is_active: isActive });
    await loadAdminKnowledge();
  } catch (err) {
    alert(err.message || 'Ошибка изменения статуса термина');
  }
}

async function setKnowledgeRuleActive(id, isActive) {
  try {
    await apiPatch(`/api/admin/knowledge/rules/${id}`, { is_active: isActive });
    await loadAdminKnowledge();
  } catch (err) {
    alert(err.message || 'Ошибка изменения статуса правила');
  }
}

function toggleKnowledgeActiveFilter() {
  knowledgeActiveOnly = !knowledgeActiveOnly;
  loadAdminKnowledge();
}

async function createKnowledgeSnapshot() {
  try {
    const label = prompt('Название снимка (необязательно):', '') || null;
    await apiPost('/api/admin/knowledge/snapshots', { label });
    await loadKnowledgeSnapshots();
  } catch (err) {
    alert(err.message || 'Ошибка создания снимка policy');
  }
}

async function loadKnowledgeSnapshots() {
  const listEl = document.getElementById('knowledge-snapshots-list');
  if (!listEl) return;
  try {
    const snapshots = await apiGet('/api/admin/knowledge/snapshots?limit=30');
    if (!Array.isArray(snapshots) || snapshots.length === 0) {
      listEl.innerHTML = '<p class="summary-text">Снимков пока нет.</p>';
      return;
    }
    listEl.innerHTML = snapshots.map(item => `
      <div class="admin-list-item">
        <div><strong>${escapeHtml(item.label || `snapshot #${item.id}`)}</strong></div>
        <div>Создал: ${escapeHtml(item.created_by_email || item.created_by || '—')}</div>
        <div>hash: ${escapeHtml((item.policy_hash || '').slice(0, 16))}...</div>
        <div>Время: ${escapeHtml(item.created_at || '')}</div>
        <div class="inline-actions">
          <button class="btn-small btn-danger" onclick="restoreKnowledgeSnapshot(${item.id})">Восстановить</button>
        </div>
      </div>
    `).join('');
  } catch (err) {
    listEl.innerHTML = `<p class="summary-text">Ошибка: ${escapeHtml(err.message)}</p>`;
  }
}

async function restoreKnowledgeSnapshot(snapshotId) {
  if (!confirm(`Восстановить policy из снимка #${snapshotId}? Текущие правила будут заменены.`)) return;
  try {
    await apiPost(`/api/admin/knowledge/snapshots/${snapshotId}/restore`, {});
    await loadAdminKnowledge();
  } catch (err) {
    alert(err.message || 'Ошибка восстановления снимка');
  }
}

function closeKnowledgeEditModal() {
  const modal = document.getElementById('knowledge-edit-modal');
  const form = document.getElementById('knowledge-edit-form');
  const fieldsWrap = document.getElementById('knowledge-edit-fields');
  if (form) form.onsubmit = null;
  if (fieldsWrap) fieldsWrap.innerHTML = '';
  if (modal) modal.classList.add('hidden');
  knowledgeEditState = null;
}

function openKnowledgeEditModal(config) {
  const modal = document.getElementById('knowledge-edit-modal');
  const title = document.getElementById('knowledge-edit-title');
  const form = document.getElementById('knowledge-edit-form');
  const fieldsWrap = document.getElementById('knowledge-edit-fields');
  if (!modal || !title || !form || !fieldsWrap) return;

  title.textContent = config.title || 'Редактирование';
  fieldsWrap.innerHTML = '';
  const fields = [];
  (config.fields || []).forEach((conf) => {
    const type = conf.type || 'text';
    let element;
    if (type === 'select') {
      element = document.createElement('select');
      (conf.options || []).forEach((optionValue) => {
        const option = document.createElement('option');
        option.value = String(optionValue);
        if (typeof conf.optionLabels === 'function') {
          option.textContent = String(conf.optionLabels(String(optionValue)));
        } else {
          option.textContent = String(optionValue);
        }
        if (String(conf.value || '') === String(optionValue)) option.selected = true;
        element.appendChild(option);
      });
    } else {
      element = document.createElement('input');
      element.type = 'text';
      element.value = conf.value || '';
    }
    element.className = 'knowledge-edit-control';
    element.placeholder = conf.placeholder || '';
    element.dataset.key = conf.key || '';
    fieldsWrap.appendChild(element);
    fields.push(element);
  });

  knowledgeEditState = config;
  form.onsubmit = async (e) => {
    e.preventDefault();
    if (!knowledgeEditState) return;
    const payload = {};
    fields.forEach(field => {
      if (field.classList.contains('hidden')) return;
      const key = field.dataset.key;
      if (!key) return;
      payload[key] = field.value;
    });
    try {
      await knowledgeEditState.onSubmit(payload);
      closeKnowledgeEditModal();
      await loadAdminKnowledge();
    } catch (err) {
      alert(err.message || 'Ошибка сохранения');
    }
  };

  modal.classList.remove('hidden');
}

async function editKnowledgeSource(id) {
  const item = knowledgeStore.sources.find(x => Number(x.id) === Number(id));
  if (!item) return;
  openKnowledgeEditModal({
    title: `Источник #${id}`,
    fields: [
      { key: 'title', placeholder: 'Название источника', value: item.title || '' },
      { key: 'reference_code', placeholder: 'Код источника', value: item.reference_code || '' },
      { key: 'section', placeholder: 'Раздел', value: item.section || '' }
    ],
    onSubmit: async (raw) => apiPatch(`/api/admin/knowledge/sources/${id}`, {
      title: String(raw.title || '').trim(),
      reference_code: String(raw.reference_code || '').trim().toUpperCase() || null,
      section: String(raw.section || '').trim() || null
    })
  });
}

async function editKnowledgeTerm(id) {
  const item = knowledgeStore.glossary.find(x => Number(x.id) === Number(id));
  if (!item) return;
  openKnowledgeEditModal({
    title: `Термин #${id}`,
    fields: [
      { key: 'term', placeholder: 'Термин', value: item.term || '' },
      { key: 'canonical_definition', placeholder: 'Каноничное определение', value: item.canonical_definition || '' },
      { key: 'forbidden_variants', placeholder: 'Запрещенные варианты через ;', value: (item.forbidden_variants || []).join('; ') },
      {
        key: 'source_ref_id',
        type: 'select',
        value: item.source_ref_id ? String(item.source_ref_id) : '',
        options: [''].concat(knowledgeStore.sources.map(s => String(s.id))),
        allowCustom: false,
        optionLabels: (value) => {
          if (!value) return 'Источник: не выбран';
          const source = knowledgeStore.sources.find(s => String(s.id) === String(value));
          return source ? `${source.title} (${source.reference_code || 'без кода'})` : value;
        }
      },
      { key: 'severity_default', type: 'select', value: item.severity_default || 'medium', options: ['low', 'medium', 'high', 'critical'] }
    ],
    onSubmit: async (raw) => apiPatch(`/api/admin/knowledge/glossary/${id}`, {
      term: String(raw.term || '').trim(),
      canonical_definition: String(raw.canonical_definition || '').trim(),
      forbidden_variants: splitBySemicolon(raw.forbidden_variants || ''),
      source_ref_id: String(raw.source_ref_id || '').trim() ? Number(raw.source_ref_id) : null,
      severity_default: String(raw.severity_default || 'medium').trim()
    })
  });
}

async function editKnowledgeRule(id) {
  const item = knowledgeStore.rules.find(x => Number(x.id) === Number(id));
  if (!item) return;
  openKnowledgeEditModal({
    title: `Правило #${id}`,
    fields: [
      { key: 'name', placeholder: 'Название правила', value: item.name || '' },
      { key: 'pattern', placeholder: 'Regex pattern', value: item.pattern || '' },
      { key: 'description', placeholder: 'Описание', value: item.description || '' },
      { key: 'suggestion_template', placeholder: 'Подсказка исправления', value: item.suggestion_template || '' },
      {
        key: 'source_ref_id',
        type: 'select',
        value: item.source_ref_id ? String(item.source_ref_id) : '',
        options: [''].concat(knowledgeStore.sources.map(s => String(s.id))),
        allowCustom: false,
        optionLabels: (value) => {
          if (!value) return 'Источник: не выбран';
          const source = knowledgeStore.sources.find(s => String(s.id) === String(value));
          return source ? `${source.title} (${source.reference_code || 'без кода'})` : value;
        }
      },
      { key: 'severity', type: 'select', value: item.severity || 'medium', options: ['low', 'medium', 'high', 'critical'] }
    ],
    onSubmit: async (raw) => apiPatch(`/api/admin/knowledge/rules/${id}`, {
      name: String(raw.name || '').trim(),
      pattern: String(raw.pattern || ''),
      description: String(raw.description || '').trim() || null,
      suggestion_template: String(raw.suggestion_template || '').trim() || null,
      source_ref_id: String(raw.source_ref_id || '').trim() ? Number(raw.source_ref_id) : null,
      severity: String(raw.severity || 'medium').trim()
    })
  });
}

async function runKnowledgeSmokeTest() {
  const textEl = document.getElementById('knowledge-test-text');
  const resultEl = document.getElementById('knowledge-test-result');
  if (!textEl || !resultEl) return;
  const text = textEl.value.trim();
  if (!text) {
    resultEl.textContent = 'Введите текст для проверки.';
    return;
  }
  resultEl.textContent = 'Проверяю...';
  try {
    const result = await apiPostAsCurrentUser('/api/analyze', {
      text,
      filename: 'knowledge_smoke_test.txt'
    });
    const issuesCount = Array.isArray(result.issues) ? result.issues.length : 0;
    const details = Array.isArray(result.issue_details) ? result.issue_details : [];
    const originMap = {};
    details.forEach(item => {
      const origin = String(item?.rule_origin || 'llm').trim();
      originMap[origin] = (originMap[origin] || 0) + 1;
    });
    const topOrigins = Object.entries(originMap)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([k, v]) => `${k}:${v}`)
      .join(', ');
    resultEl.textContent = `rule_findings: ${result.rule_findings || 0}, issues: ${issuesCount}, policy_hash: ${result.policy_hash || '—'}, mode: ${result.model_mode || 'unknown'}, origins: ${topOrigins || '—'}`;
  } catch (err) {
    resultEl.textContent = `Ошибка: ${err.message || 'Не удалось выполнить тест'}`;
  }
}

window.loadAdminOverview = loadAdminOverview;
window.loadAdminAuditLogs = loadAdminAuditLogs;
window.loadAdminDocuments = loadAdminDocuments;
window.toggleBlockedUsersFilter = toggleBlockedUsersFilter;
window.loadAdminUsersSummary = loadAdminUsersSummary;
window.setUserActive = setUserActive;
window.adminDeleteDocument = adminDeleteDocument;
window.loadAdminKnowledge = loadAdminKnowledge;
window.seedAdminKnowledgeDefaults = seedAdminKnowledgeDefaults;
window.deactivateKnowledgeSource = deactivateKnowledgeSource;
window.deactivateKnowledgeTerm = deactivateKnowledgeTerm;
window.deactivateKnowledgeRule = deactivateKnowledgeRule;
window.setKnowledgeSourceActive = setKnowledgeSourceActive;
window.setKnowledgeTermActive = setKnowledgeTermActive;
window.setKnowledgeRuleActive = setKnowledgeRuleActive;
window.toggleKnowledgeActiveFilter = toggleKnowledgeActiveFilter;
window.runKnowledgeSmokeTest = runKnowledgeSmokeTest;
window.editKnowledgeSource = editKnowledgeSource;
window.editKnowledgeTerm = editKnowledgeTerm;
window.editKnowledgeRule = editKnowledgeRule;
window.closeKnowledgeEditModal = closeKnowledgeEditModal;
window.createKnowledgeSnapshot = createKnowledgeSnapshot;
window.loadKnowledgeSnapshots = loadKnowledgeSnapshots;
window.restoreKnowledgeSnapshot = restoreKnowledgeSnapshot;
