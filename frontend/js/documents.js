// frontend/js/documents.js - пользовательские документы (дообучение)

const trainingPreviewState = new Map();

async function apiGetWithAuth(path) {
  const token = localStorage.getItem('llm_auth_token');
  const res = await fetch(path, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) {
    throw new Error(`Ошибка ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

async function apiDeleteWithAuth(path) {
  const token = localStorage.getItem('llm_auth_token');
  const res = await fetch(path, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) {
    throw new Error(`Ошибка ${res.status}: ${await res.text()}`);
  }
}

function escapeHtmlSafe(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

async function uploadTrainingDocument(input) {
  const file = input?.files?.[0];
  if (!file) return;
  showLoading('Загружаем документ для дообучения...');
  try {
    const token = localStorage.getItem('llm_auth_token');
    const confidentiality = (document.getElementById('training-confidentiality')?.value || 'confidential').trim();
    const form = new FormData();
    form.append('file', file);
    form.append('purpose', 'training');
    form.append('confidentiality_level', confidentiality);

    const res = await fetch('/api/documents/upload', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: form
    });
    if (!res.ok) throw new Error(`Ошибка ${res.status}: ${await res.text()}`);

    await loadTrainingDocuments();
  } catch (e) {
    showError(e.message || 'Ошибка загрузки документа');
  } finally {
    input.value = '';
    hideLoading();
  }
}

async function loadTrainingDocuments() {
  const listEl = document.getElementById('training-documents-list');
  if (!listEl) return;
  try {
    const docs = await apiGetWithAuth('/api/documents?purpose=training&limit=200');
    if (!docs.length) {
      listEl.innerHTML = '<p class="summary-text">Документы для дообучения пока не загружены.</p>';
      return;
    }

    listEl.innerHTML = docs.map(d => {
      const isOpen = trainingPreviewState.get(d.id) === true;
      return `
        <div class="admin-list-item">
          <div><strong>${escapeHtmlSafe(d.filename)}</strong></div>
          <div>Слов: ${d.word_count} | Размер: ${d.file_size} байт</div>
          <div>Конфиденциальность: ${escapeHtmlSafe(d.confidentiality_level || 'confidential')}</div>
          <div>Создан: ${escapeHtmlSafe(d.created_at || '')}</div>
          <div class="inline-actions">
            <button id="training-preview-btn-${d.id}" class="btn-small" onclick="toggleTrainingPreview(${d.id})">
              ${isOpen ? 'Свернуть' : 'Просмотр'}
            </button>
            <button class="btn-small btn-danger" onclick="deleteTrainingDocument(${d.id})">Удалить</button>
          </div>
          <div id="training-preview-${d.id}" class="doc-viewer ${isOpen ? '' : 'hidden'}"></div>
        </div>
      `;
    }).join('');

    for (const doc of docs) {
      if (trainingPreviewState.get(doc.id) === true) {
        await renderTrainingPreview(doc.id);
      }
    }
  } catch (e) {
    listEl.innerHTML = `<p class="summary-text">Ошибка: ${escapeHtmlSafe(e.message)}</p>`;
  }
}

async function toggleTrainingPreview(id) {
  const currentlyOpen = trainingPreviewState.get(id) === true;
  trainingPreviewState.set(id, !currentlyOpen);
  const btn = document.getElementById(`training-preview-btn-${id}`);
  const panel = document.getElementById(`training-preview-${id}`);
  if (btn) btn.textContent = currentlyOpen ? 'Просмотр' : 'Свернуть';
  if (panel) panel.classList.toggle('hidden', currentlyOpen);

  if (!currentlyOpen) {
    await renderTrainingPreview(id);
  }
}

async function renderTrainingPreview(id) {
  const panel = document.getElementById(`training-preview-${id}`);
  if (!panel) return;
  panel.innerHTML = 'Загрузка текста...';
  try {
    const data = await apiGetWithAuth(`/api/documents/${id}/content`);
    panel.innerHTML = `
      <div class="doc-meta"><strong>${escapeHtmlSafe(data.filename)}</strong> | purpose: ${escapeHtmlSafe(data.purpose)} | confidentiality: ${escapeHtmlSafe(data.confidentiality_level || 'confidential')}</div>
      <pre>${escapeHtmlSafe(data.extracted_text || '')}</pre>
    `;
  } catch (e) {
    panel.innerHTML = `<p class="summary-text">Ошибка: ${escapeHtmlSafe(e.message)}</p>`;
  }
}

async function deleteTrainingDocument(id) {
  if (!confirm(`Удалить документ #${id}?`)) return;
  try {
    await apiDeleteWithAuth(`/api/documents/${id}`);
    trainingPreviewState.delete(id);
    await loadTrainingDocuments();
  } catch (e) {
    showError(e.message || 'Ошибка удаления документа');
  }
}

async function previewDocumentContent(documentId, targetId = 'analyzed-document-viewer') {
  const target = document.getElementById(targetId);
  if (!target) return;
  target.innerHTML = 'Загрузка текста...';
  try {
    const data = await apiGetWithAuth(`/api/documents/${documentId}/content`);
    target.innerHTML = `
      <div class="doc-meta">
        <strong>${escapeHtmlSafe(data.filename)}</strong>
        <span> | purpose: ${escapeHtmlSafe(data.purpose)}</span>
        <span> | confidentiality: ${escapeHtmlSafe(data.confidentiality_level || 'confidential')}</span>
      </div>
      <pre>${escapeHtmlSafe(data.extracted_text || '')}</pre>
    `;
  } catch (e) {
    target.innerHTML = `<p class="summary-text">Ошибка: ${escapeHtmlSafe(e.message)}</p>`;
  }
}

window.uploadTrainingDocument = uploadTrainingDocument;
window.loadTrainingDocuments = loadTrainingDocuments;
window.toggleTrainingPreview = toggleTrainingPreview;
window.deleteTrainingDocument = deleteTrainingDocument;
window.previewDocumentContent = previewDocumentContent;
