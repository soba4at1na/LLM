// frontend/js/analysis.js — проверка и интерактивные правки во фронте

let currentCheckDocumentId = null;
let analyzedOriginalText = '';
let analyzedCurrentText = '';
let analyzedIssueDetails = [];
let issueAppliedState = [];
let currentAnalysisId = null;
let isAnalyzeInProgress = false;
let pendingAnalysisPollTimer = null;

const PENDING_ANALYSIS_KEY = 'llm_pending_analysis_v1';

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
  if (isAnalyzeInProgress) return;
  const token = localStorage.getItem('llm_auth_token');
  const fileInput = document.getElementById('file-input');
  const textInput = document.getElementById('document-text');
  if (!token) return showError('Требуется авторизация');

  hideError();
  document.getElementById('analysis-results')?.classList.add('hidden');
  setAnalyzeBusy(true);
  isAnalyzeInProgress = true;

  try {
    if (fileInput?.files?.length) {
      showLoading('Загрузка и анализ документа...');
      const file = fileInput.files[0];
      const confidentiality = (document.getElementById('check-confidentiality')?.value || 'confidential').trim();
      const form = new FormData();
      form.append('file', file);
      form.append('purpose', 'check');
      form.append('confidentiality_level', confidentiality);

      const uploadRes = await fetch('/api/documents/upload', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form
      });
      if (!uploadRes.ok) throw new Error(`Ошибка загрузки ${uploadRes.status}: ${await uploadRes.text()}`);
      const uploaded = await uploadRes.json();
      currentCheckDocumentId = uploaded.id;
      savePendingAnalysisState({
        started_at: new Date().toISOString(),
        document_id: currentCheckDocumentId,
        filename: String(file?.name || ''),
        mode: 'file'
      });

      const analyzeRes = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ document_id: currentCheckDocumentId })
      });
      if (!analyzeRes.ok) throw new Error(await extractApiErrorMessage(analyzeRes, `Ошибка анализа ${analyzeRes.status}`));
      const data = await analyzeRes.json();
      await showResults(data);
      return;
    }

    if (textInput) {
      const text = textInput.value.trim();
      if (text.length < 30) return showError('Введите минимум 30 символов');
      showLoading('Анализируем текст...');
      savePendingAnalysisState({
        started_at: new Date().toISOString(),
        document_id: null,
        filename: 'inline_text.txt',
        mode: 'inline'
      });
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ text, filename: 'inline_text.txt' })
      });
      if (!res.ok) throw new Error(await extractApiErrorMessage(res, `Ошибка анализа ${res.status}`));
      const data = await res.json();
      currentCheckDocumentId = data.document_id;
      await showResults(data);
      return;
    }

    showError('Выберите файл или введите текст для анализа');
  } catch (err) {
    clearPendingAnalysisState();
    showError(err.message || 'Ошибка анализа');
  } finally {
    isAnalyzeInProgress = false;
    setAnalyzeBusy(false);
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
    const replacementRaw = String(detail.replacement || '').trim();
    const markerText = appliedState[i] ? String(detail._appliedReplacement || suggestionRaw) : fragment;
    if (!markerText.trim()) return;
    const safeMarker = escapeHtml(markerText);
    const suggestion = escapeHtml(detail.suggestion || 'Нет рекомендации');
    const reason = escapeHtml(detail.reason || '');
    const confidence = String(detail.confidence || 'medium').toLowerCase();
    const confidenceBadge = confidence === 'low'
      ? '<div class="issue-popover-confidence low">Низкая уверенность</div>'
      : '';
    const canApply = Boolean(replacementRaw) && replacementRaw !== fragment;
    const btnText = appliedState[i] ? 'Откатить' : (canApply ? 'Применить' : 'Нет автозамены');
    const btnDisabledAttr = canApply || appliedState[i] ? '' : 'disabled';
    const replacement = `<span class="issue-mark" id="issue-mark-${i}" onclick="toggleIssuePopover(${i}, event)">${safeMarker}<span class="issue-popover">${confidenceBadge}<div class="issue-popover-text">${suggestion}</div>${reason ? `<div class="issue-popover-reason">${reason}</div>` : ''}<button class="btn-small" ${btnDisabledAttr} onclick="toggleIssueFix(${i}, event)">${btnText}</button></span></span>`;
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
  const replacement = String(detail.replacement || '').trim();
  if (!fragment) return;

  if (!issueAppliedState[index]) {
    if (!replacement || replacement === fragment) return;
    const replacementWithCase = applyReplacementCase(fragment, replacement);
    const result = replaceFirstOccurrence(analyzedCurrentText, fragment, replacementWithCase);
    if (!result.replaced) return;
    analyzedCurrentText = result.text;
    detail._appliedReplacement = replacementWithCase;
    issueAppliedState[index] = true;
  } else {
    const appliedReplacement = String(detail._appliedReplacement || replacement);
    const result = replaceFirstOccurrence(analyzedCurrentText, appliedReplacement, fragment);
    if (!result.replaced) return;
    analyzedCurrentText = result.text;
    detail._appliedReplacement = '';
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

function applyReplacementCase(sourceFragment, replacement) {
  const src = String(sourceFragment || '');
  const dst = String(replacement || '');
  if (!src || !dst) return dst;

  const lettersOnly = src.replace(/[^A-Za-zА-Яа-яЁё]/g, '');
  if (lettersOnly && lettersOnly === lettersOnly.toUpperCase()) {
    return dst.toUpperCase();
  }

  const firstLetterIdx = src.search(/[A-Za-zА-Яа-яЁё]/);
  if (firstLetterIdx >= 0) {
    const firstLetter = src[firstLetterIdx];
    const isCapitalized = firstLetter === firstLetter.toUpperCase();
    if (isCapitalized) {
      const dstFirstLetterIdx = dst.search(/[A-Za-zА-Яа-яЁё]/);
      if (dstFirstLetterIdx >= 0) {
        return (
          dst.slice(0, dstFirstLetterIdx) +
          dst[dstFirstLetterIdx].toUpperCase() +
          dst.slice(dstFirstLetterIdx + 1)
        );
      }
    }
  }

  return dst;
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
  clearPendingAnalysisState();
  clearFile();
  hideError();
}

function applyAllFixes() {
  if (!Array.isArray(analyzedIssueDetails) || analyzedIssueDetails.length === 0) return;
  let changed = 0;
  for (let i = 0; i < analyzedIssueDetails.length; i += 1) {
    if (issueAppliedState[i]) continue;
    const detail = analyzedIssueDetails[i];
    if (!detail) continue;
    const fragment = String(detail.fragment || '');
    const replacement = String(detail.replacement || '').trim();
    if (!fragment || !replacement || replacement === fragment) continue;
    const replacementWithCase = applyReplacementCase(fragment, replacement);
    const result = replaceFirstOccurrence(analyzedCurrentText, fragment, replacementWithCase);
    if (!result.replaced) continue;
    analyzedCurrentText = result.text;
    detail._appliedReplacement = replacementWithCase;
    issueAppliedState[i] = true;
    changed += 1;
  }
  if (!changed) return showError('Нет доступных автозамен для применения');
  closeIssuePopovers();
  renderAnalyzedDocument();
}

function undoAllFixes() {
  if (!Array.isArray(analyzedIssueDetails) || analyzedIssueDetails.length === 0) return;
  let changed = 0;
  for (let i = analyzedIssueDetails.length - 1; i >= 0; i -= 1) {
    if (!issueAppliedState[i]) continue;
    const detail = analyzedIssueDetails[i];
    if (!detail) continue;
    const fragment = String(detail.fragment || '');
    const appliedReplacement = String(detail._appliedReplacement || detail.replacement || '').trim();
    if (!fragment || !appliedReplacement) continue;
    const result = replaceFirstOccurrence(analyzedCurrentText, appliedReplacement, fragment);
    if (!result.replaced) continue;
    analyzedCurrentText = result.text;
    detail._appliedReplacement = '';
    issueAppliedState[i] = false;
    changed += 1;
  }
  if (!changed) return showError('Нет применённых автозамен для отката');
  closeIssuePopovers();
  renderAnalyzedDocument();
}

function setAnalyzeBusy(isBusy) {
  const btn = document.getElementById('analyze-btn');
  if (!btn) return;
  btn.disabled = !!isBusy;
  btn.classList.toggle('is-busy', !!isBusy);
  const textEl = btn.querySelector('.btn-text');
  const spinner = btn.querySelector('.spinner');
  if (textEl) textEl.textContent = isBusy ? 'Выполняется анализ...' : '🚀 Начать анализ';
  if (spinner) spinner.classList.toggle('hidden', !isBusy);
}

async function extractApiErrorMessage(response, fallback) {
  try {
    const text = await response.text();
    if (!text) return fallback;
    try {
      const parsed = JSON.parse(text);
      if (parsed && typeof parsed.detail === 'string') return parsed.detail;
      return fallback;
    } catch (_) {
      return text.slice(0, 300);
    }
  } catch (_) {
    return fallback;
  }
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
    clearPendingAnalysisState();
  } catch (err) {
    console.warn('Не удалось загрузить последнюю проверку:', err);
  }

  maybeResumePendingAnalysis();
}

function savePendingAnalysisState(payload) {
  try {
    localStorage.setItem(PENDING_ANALYSIS_KEY, JSON.stringify(payload || {}));
  } catch (_) {}
}

function getPendingAnalysisState() {
  try {
    const raw = localStorage.getItem(PENDING_ANALYSIS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || !parsed.started_at) return null;
    return parsed;
  } catch (_) {
    return null;
  }
}

function clearPendingAnalysisState() {
  try {
    localStorage.removeItem(PENDING_ANALYSIS_KEY);
  } catch (_) {}
  if (pendingAnalysisPollTimer) {
    clearTimeout(pendingAnalysisPollTimer);
    pendingAnalysisPollTimer = null;
  }
}

function maybeResumePendingAnalysis() {
  const pending = getPendingAnalysisState();
  if (!pending || pendingAnalysisPollTimer) return;

  const pendingStartedMs = Date.parse(String(pending.started_at || ''));
  if (!Number.isFinite(pendingStartedMs)) {
    clearPendingAnalysisState();
    return;
  }

  showLoading('Проверка продолжается... Подождите, результат скоро появится.');
  const startedAt = Date.now();
  const timeoutMs = 12 * 60 * 1000;

  const tick = async () => {
    try {
      const token = localStorage.getItem('llm_auth_token');
      if (!token) {
        clearPendingAnalysisState();
        hideLoading();
        return;
      }

      const res = await fetch('/api/analysis/history?limit=5', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) throw new Error('history unavailable');
      const history = await res.json();
      const items = Array.isArray(history) ? history : [];

      const candidate = items.find((item) => {
        const createdMs = Date.parse(String(item?.created_at || ''));
        if (!Number.isFinite(createdMs)) return false;
        if (createdMs + 1500 < pendingStartedMs) return false;
        const expectedDocId = pending.document_id;
        if (expectedDocId !== null && expectedDocId !== undefined) {
          return Number(item?.document_id) === Number(expectedDocId);
        }
        return true;
      });

      if (candidate) {
        await showResults({
          analysis_id: candidate.analysis_id,
          document_id: candidate.document_id,
          overall_score: candidate.overall_score,
          readability_score: candidate.readability_score,
          grammar_score: candidate.grammar_score,
          structure_score: candidate.structure_score,
          issues: candidate.issues || [],
          recommendations: candidate.recommendations || [],
          issue_details: candidate.issue_details || [],
          summary: candidate.summary || 'Анализ завершён',
          model_mode: candidate.run_mode || candidate.model_mode || 'unknown',
          processing_ms: candidate.processing_ms,
          analyzed_at: candidate.created_at
        });
        clearPendingAnalysisState();
        hideLoading();
        return;
      }

      if (Date.now() - startedAt > timeoutMs) {
        clearPendingAnalysisState();
        hideLoading();
        showError('Не дождались завершения анализа. Можно запустить проверку заново.');
        return;
      }

      pendingAnalysisPollTimer = setTimeout(tick, 3500);
    } catch (_) {
      pendingAnalysisPollTimer = setTimeout(tick, 4500);
    }
  };

  pendingAnalysisPollTimer = setTimeout(tick, 800);
}

async function exportCurrentAnalysis(format) {
  const token = localStorage.getItem('llm_auth_token');
  if (!token) return showError('Требуется авторизация');
  if (!currentAnalysisId) return showError('Сначала выполните анализ документа');
  const normalizedFormat = String(format || '').toLowerCase();
  if (!['json', 'pdf'].includes(normalizedFormat)) return showError('Неизвестный формат экспорта');

  try {
    showLoading(`Готовим отчет (${normalizedFormat.toUpperCase()})...`);
    const res = await fetch(`/api/analysis/${currentAnalysisId}/export?format=${encodeURIComponent(normalizedFormat)}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) throw new Error(`Ошибка экспорта ${res.status}: ${await res.text()}`);

    const blob = await res.blob();
    const defaultName = `analysis_${currentAnalysisId}.${normalizedFormat}`;
    const filename = getFilenameFromDisposition(res.headers.get('Content-Disposition')) || defaultName;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    showError(err.message || 'Не удалось экспортировать отчет');
  } finally {
    hideLoading();
  }
}

function getFilenameFromDisposition(disposition) {
  if (!disposition) return null;
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match && utf8Match[1]) {
    try {
      return decodeURIComponent(utf8Match[1].trim());
    } catch (_) {}
  }
  const plainMatch = disposition.match(/filename=\"?([^\";]+)\"?/i);
  if (plainMatch && plainMatch[1]) return plainMatch[1].trim();
  return null;
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
window.exportCurrentAnalysis = exportCurrentAnalysis;
window.applyAllFixes = applyAllFixes;
window.undoAllFixes = undoAllFixes;

if (!window.__issuePopoverGlobalClickBound) {
  document.addEventListener('click', () => closeIssuePopovers());
  window.__issuePopoverGlobalClickBound = true;
}
