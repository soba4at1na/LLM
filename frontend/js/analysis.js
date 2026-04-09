// frontend/js/analysis.js — проверка и интерактивные правки во фронте

let currentCheckDocumentId = null;
let analyzedOriginalText = '';
let analyzedCurrentText = '';
let analyzedIssueDetails = [];
let issueAppliedState = [];

function handleFileSelect(input) {
  const file = input.files[0];
  if (!file) return;
  document.getElementById('file-name').textContent = file.name;
  document.getElementById('file-selected').classList.remove('hidden');
  document.querySelector('.file-upload-area').classList.add('hidden');
}

function clearFile() {
  const input = document.getElementById('file-input');
  if (input) input.value = '';
  document.getElementById('file-selected')?.classList.add('hidden');
  document.querySelector('.file-upload-area')?.classList.remove('hidden');
  currentCheckDocumentId = null;
}

async function startAnalysis() {
  const token = localStorage.getItem('llm_auth_token');
  const fileInput = document.getElementById('file-input');
  const textInput = document.getElementById('document-text');
  if (!token) return showError('Требуется авторизация');

  hideError();
  document.getElementById('analysis-results')?.classList.add('hidden');

  try {
    if (fileInput?.files?.length) {
      showLoading('Загрузка и анализ документа...');
      const file = fileInput.files[0];
      const form = new FormData();
      form.append('file', file);
      form.append('purpose', 'check');

      const uploadRes = await fetch('/api/documents/upload', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form
      });
      if (!uploadRes.ok) throw new Error(`Ошибка загрузки ${uploadRes.status}: ${await uploadRes.text()}`);
      const uploaded = await uploadRes.json();
      currentCheckDocumentId = uploaded.id;

      const analyzeRes = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ document_id: currentCheckDocumentId })
      });
      if (!analyzeRes.ok) throw new Error(`Ошибка анализа ${analyzeRes.status}: ${await analyzeRes.text()}`);
      const data = await analyzeRes.json();
      await showResults(data);
      return;
    }

    if (textInput) {
      const text = textInput.value.trim();
      if (text.length < 30) return showError('Введите минимум 30 символов');
      showLoading('Анализируем текст...');
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ text, filename: 'inline_text.txt' })
      });
      if (!res.ok) throw new Error(`Ошибка анализа ${res.status}: ${await res.text()}`);
      const data = await res.json();
      currentCheckDocumentId = data.document_id;
      await showResults(data);
      return;
    }
  } catch (err) {
    showError(err.message || 'Ошибка анализа');
  } finally {
    hideLoading();
  }
}

async function showResults(data) {
  const resultsEl = document.getElementById('analysis-results');
  if (!resultsEl) return;

  const scoreEl = document.getElementById('quality-score');
  if (scoreEl && data.overall_score !== undefined) {
    const score = Math.round(data.overall_score);
    scoreEl.querySelector('.score-value').textContent = score;
    scoreEl.style.background = `conic-gradient(var(--primary) ${score * 3.6}deg, var(--border) ${score * 3.6}deg)`;
  }
  setScore('readability-score', data.readability_score);
  setScore('grammar-score', data.grammar_score);
  setScore('structure-score', data.structure_score);

  const issuesList = document.getElementById('issues-list');
  if (issuesList) {
    issuesList.innerHTML = (data.issues || []).map(i => `<li>${escapeHtml(i)}</li>`).join('') || '<li>Явных проблем не найдено ✅</li>';
  }
  const recList = document.getElementById('recommendations-list');
  if (recList) {
    recList.innerHTML = (data.recommendations || []).map(r => `<li>${escapeHtml(r)}</li>`).join('') || '<li>Рекомендаций нет</li>';
  }
  const summaryEl = document.getElementById('summary-text');
  if (summaryEl) summaryEl.textContent = data.summary || 'Анализ завершён';

  resultsEl.classList.remove('hidden');

  analyzedIssueDetails = Array.isArray(data.issue_details) ? data.issue_details : [];
  issueAppliedState = analyzedIssueDetails.map(() => false);
  if (data.document_id) {
    await loadAnalyzedDocument(data.document_id);
    renderAnalyzedDocument();
  }
}

async function loadAnalyzedDocument(documentId) {
  const token = localStorage.getItem('llm_auth_token');
  const res = await fetch(`/api/documents/${documentId}/content`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error(`Ошибка ${res.status}: ${await res.text()}`);
  const doc = await res.json();
  analyzedOriginalText = doc.extracted_text || '';
  analyzedCurrentText = analyzedOriginalText;
}

function renderAnalyzedDocument() {
  const viewer = document.getElementById('analyzed-document-viewer');
  if (!viewer) return;
  const html = buildHighlightedHtml(analyzedCurrentText, analyzedIssueDetails, issueAppliedState);
  viewer.innerHTML = `
    <div class="doc-meta"><strong>Документ</strong> | слов: ${countWords(analyzedCurrentText)}</div>
    <div class="doc-rendered">${html}</div>
  `;
}

function buildHighlightedHtml(text, details, appliedState) {
  if (!text) return '<em>Пустой текст</em>';
  let html = escapeHtml(text);
  details.forEach((detail, i) => {
    const fragment = String(detail.fragment || '').trim();
    if (!fragment) return;
    const safe = escapeHtml(fragment);
    const suggestion = escapeHtml(detail.suggestion || 'Нет рекомендации');
    const reason = escapeHtml(detail.reason || '');
    const btnText = appliedState[i] ? 'Откатить' : 'Применить';
    const replacement = `
      <span class="issue-mark">
        ${safe}
        <span class="issue-popover">
          <div class="issue-popover-text">${suggestion}</div>
          ${reason ? `<div class="issue-popover-reason">${reason}</div>` : ''}
          <button class="btn-small" onclick="toggleIssueFix(${i})">${btnText}</button>
        </span>
      </span>
    `;
    html = html.replace(safe, replacement);
  });
  return `<div class="doc-highlighted">${html}</div>`;
}

function toggleIssueFix(index) {
  const detail = analyzedIssueDetails[index];
  if (!detail) return;
  const fragment = String(detail.fragment || '');
  const suggestion = String(detail.suggestion || '');
  if (!fragment || !suggestion) return;

  if (!issueAppliedState[index]) {
    analyzedCurrentText = analyzedCurrentText.replace(fragment, suggestion);
    issueAppliedState[index] = true;
  } else {
    analyzedCurrentText = analyzedCurrentText.replace(suggestion, fragment);
    issueAppliedState[index] = false;
  }
  renderAnalyzedDocument();
}

function setScore(id, value) {
  const el = document.getElementById(id);
  if (el && value !== undefined) el.textContent = `${Math.round(value)}/100`;
}

function countWords(text) {
  return String(text || '').trim().split(/\s+/).filter(Boolean).length;
}

function clearResults() {
  document.getElementById('analysis-results')?.classList.add('hidden');
  document.getElementById('analyzed-document-viewer').innerHTML = '';
  analyzedOriginalText = '';
  analyzedCurrentText = '';
  analyzedIssueDetails = [];
  issueAppliedState = [];
  clearFile();
  hideError();
}

function escapeHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

window.handleFileSelect = handleFileSelect;
window.startAnalysis = startAnalysis;
window.showResults = showResults;
window.clearResults = clearResults;
window.clearFile = clearFile;
window.toggleIssueFix = toggleIssueFix;
