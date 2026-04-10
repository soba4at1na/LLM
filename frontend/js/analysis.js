// frontend/js/analysis.js — проверка и интерактивные правки во фронте

let currentCheckDocumentId = null;
let analyzedOriginalText = '';
let analyzedCurrentText = '';
let analyzedIssueDetails = [];
let issueAppliedState = [];
let currentAnalysisId = null;

function handleFileSelect(input) {
  const file = input.files[0];
  if (!file) return;
  document.getElementById('file-name').textContent = file.name;
  document.getElementById('file-selected').classList.remove('hidden');
  document.getElementById('check-upload-area')?.classList.add('hidden');
}

function clearFile() {
  const input = document.getElementById('file-input');
  if (input) input.value = '';
  document.getElementById('file-selected')?.classList.add('hidden');
  document.getElementById('check-upload-area')?.classList.remove('hidden');
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
  const metaEl = document.getElementById('analysis-meta');
  if (metaEl) {
    const parts = [];
    if (data.processing_ms !== undefined && data.processing_ms !== null) {
      parts.push(`Время анализа: ${(Number(data.processing_ms) / 1000).toFixed(2)} сек`);
    }
    if (data.model_mode) {
      parts.push(`Режим: ${escapeHtml(String(data.model_mode))}`);
    }
    if (data.analyzed_at) {
      parts.push(`Выполнено: ${escapeHtml(data.analyzed_at)}`);
    }
    metaEl.textContent = parts.join(' | ');
  }

  resultsEl.classList.remove('hidden');

  currentAnalysisId = data.analysis_id || null;
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
    <div class="doc-meta"><strong>Документ</strong> | слов: ${countWords(analyzedCurrentText)}${currentAnalysisId ? ` | анализ #${currentAnalysisId}` : ''}</div>
    <div class="doc-rendered">${html}</div>
  `;
}

function buildHighlightedHtml(text, details, appliedState) {
  if (!text) return '<em>Пустой текст</em>';
  let html = escapeHtml(text);
  let anyHighlightApplied = false;
  details.forEach((detail, i) => {
    const fragment = String(detail.fragment || '').trim();
    if (!fragment) return;
    const suggestionRaw = String(detail.suggestion || '');
    const markerText = appliedState[i] ? suggestionRaw : fragment;
    if (!markerText.trim()) return;
    const safeMarker = escapeHtml(markerText);
    const suggestion = escapeHtml(detail.suggestion || 'Нет рекомендации');
    const reason = escapeHtml(detail.reason || '');
    const confidence = String(detail.confidence || 'medium').toLowerCase();
    const confidenceBadge = confidence === 'low'
      ? '<div class="issue-popover-confidence low">Низкая уверенность</div>'
      : '';
    const btnText = appliedState[i] ? 'Откатить' : 'Применить';
    const replacement = `
      <span class="issue-mark" id="issue-mark-${i}" onclick="toggleIssuePopover(${i}, event)">
        ${safeMarker}
        <span class="issue-popover">
          ${confidenceBadge}
          <div class="issue-popover-text">${suggestion}</div>
          ${reason ? `<div class="issue-popover-reason">${reason}</div>` : ''}
          <button class="btn-small" onclick="toggleIssueFix(${i}, event)">${btnText}</button>
        </span>
      </span>
    `;
    const nextHtml = html.replace(safeMarker, replacement);
    if (nextHtml !== html) {
      anyHighlightApplied = true;
      html = nextHtml;
    }
  });
  if (!anyHighlightApplied) {
    return `<div class="doc-highlighted">${html}</div><p class="summary-text">Точные фрагменты не найдены, показываю исходный текст без подсветки.</p>`;
  }
  return `<div class="doc-highlighted">${html}</div>`;
}

function toggleIssueFix(index, event) {
  if (event && typeof event.stopPropagation === 'function') {
    event.stopPropagation();
  }
  const detail = analyzedIssueDetails[index];
  if (!detail) return;
  const fragment = String(detail.fragment || '');
  const suggestion = String(detail.suggestion || '');
  if (!fragment || !suggestion) return;

  if (!issueAppliedState[index]) {
    const result = replaceFirstOccurrence(analyzedCurrentText, fragment, suggestion);
    if (!result.replaced) return;
    analyzedCurrentText = result.text;
    issueAppliedState[index] = true;
  } else {
    const result = replaceFirstOccurrence(analyzedCurrentText, suggestion, fragment);
    if (!result.replaced) return;
    analyzedCurrentText = result.text;
    issueAppliedState[index] = false;
  }
  renderAnalyzedDocument();
  const el = document.getElementById(`issue-mark-${index}`);
  if (el) el.classList.add('open');
}

function replaceFirstOccurrence(source, search, replacement) {
  const start = String(source).indexOf(String(search));
  if (start < 0) return { text: source, replaced: false };
  const before = source.slice(0, start);
  const after = source.slice(start + String(search).length);
  return { text: `${before}${replacement}${after}`, replaced: true };
}

function closeIssuePopovers() {
  document.querySelectorAll('.issue-mark.open').forEach(el => el.classList.remove('open'));
}

function toggleIssuePopover(index, event) {
  if (event && typeof event.stopPropagation === 'function') {
    event.stopPropagation();
  }
  const el = document.getElementById(`issue-mark-${index}`);
  if (!el) return;
  const willOpen = !el.classList.contains('open');
  closeIssuePopovers();
  if (willOpen) el.classList.add('open');
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
  const viewer = document.getElementById('analyzed-document-viewer');
  if (viewer) viewer.innerHTML = '';
  const meta = document.getElementById('analysis-meta');
  if (meta) meta.textContent = '';
  analyzedOriginalText = '';
  analyzedCurrentText = '';
  analyzedIssueDetails = [];
  issueAppliedState = [];
  currentAnalysisId = null;
  clearFile();
  hideError();
}

async function loadLatestAnalysisForUser() {
  const token = localStorage.getItem('llm_auth_token');
  if (!token) return;

  try {
    const res = await fetch('/api/analysis/history?limit=1', {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) return;
    const history = await res.json();
    if (!Array.isArray(history) || history.length === 0) return;

    const latest = history[0];
    await showResults({
      analysis_id: latest.analysis_id,
      document_id: latest.document_id,
      overall_score: latest.overall_score,
      readability_score: latest.readability_score,
      grammar_score: latest.grammar_score,
      structure_score: latest.structure_score,
      issues: latest.issues || [],
      recommendations: latest.recommendations || [],
      issue_details: latest.issue_details || [],
      summary: latest.summary || 'Анализ завершён',
      model_mode: latest.run_mode || latest.model_mode || 'unknown',
      processing_ms: latest.processing_ms,
      analyzed_at: latest.created_at
    });
  } catch (err) {
    console.warn('Не удалось загрузить последнюю проверку:', err);
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

window.handleFileSelect = handleFileSelect;
window.startAnalysis = startAnalysis;
window.showResults = showResults;
window.clearResults = clearResults;
window.clearFile = clearFile;
window.toggleIssueFix = toggleIssueFix;
window.toggleIssuePopover = toggleIssuePopover;
window.loadLatestAnalysisForUser = loadLatestAnalysisForUser;

if (!window.__issuePopoverGlobalClickBound) {
  document.addEventListener('click', () => closeIssuePopovers());
  window.__issuePopoverGlobalClickBound = true;
}
