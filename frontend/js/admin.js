// frontend/js/admin.js - админ панель, аудит, пользователи, документы

let adminDocFilter = 'all';
let adminUsersSort = 'last_login';
let adminOnlyBlocked = false;

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
        <div>Тип: ${escapeHtml(item.source_type || '—')}</div>
        <div>Слов: ${Number(item.word_count || 0)} | Размер: ${Number(item.file_size || 0)} байт</div>
        <div>Время: ${escapeHtml(item.created_at || '')}</div>
        <div class="inline-actions">
          <button class="btn-small" onclick="previewDocumentContent(${item.id}, 'admin-document-preview')">Просмотр</button>
          <button class="btn-small btn-danger" onclick="adminDeleteDocument(${item.id}, '${escapeHtml(item.filename || '')}')">Удалить</button>
        </div>
      </div>
    `).join('') + '<div id="admin-document-preview" class="doc-viewer"></div>';
  } catch (err) {
    const listEl = document.getElementById('admin-documents-list');
    if (listEl) listEl.innerHTML = `<p class="summary-text">Ошибка: ${escapeHtml(err.message)}</p>`;
  }
}

async function adminDeleteDocument(documentId, filename = '') {
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

async function setUserActive(userId, isActive) {
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
            ? `<button class="btn-small btn-danger" onclick="setUserActive('${escapeHtml(item.user_id)}', false)">Заблокировать</button>`
            : `<button class="btn-small" onclick="setUserActive('${escapeHtml(item.user_id)}', true)">Разблокировать</button>`}
        </div>
      </div>
    `).join('');
  } catch (err) {
    const listEl = document.getElementById('admin-users-list');
    if (listEl) listEl.innerHTML = `<p class="summary-text">Ошибка: ${escapeHtml(err.message)}</p>`;
  }
}

window.loadAdminOverview = loadAdminOverview;
window.loadAdminAuditLogs = loadAdminAuditLogs;
window.loadAdminDocuments = loadAdminDocuments;
window.toggleBlockedUsersFilter = toggleBlockedUsersFilter;
window.loadAdminUsersSummary = loadAdminUsersSummary;
window.setUserActive = setUserActive;
window.adminDeleteDocument = adminDeleteDocument;
