// frontend/js/analysis.js — Анализ документов (файл + текст)

// API_BASE уже объявлен в app.js — не объявляем заново

// ==================== ОБРАБОТКА ВЫБОРА ФАЙЛА ====================

function handleFileSelect(input) {
  const file = input.files[0];
  if (!file) return;

  document.getElementById('file-name').textContent = file.name;
  document.getElementById('file-selected').classList.remove('hidden');
  document.querySelector('.file-upload-area').classList.add('hidden');

  console.log(`📁 Выбран файл: ${file.name}`);
}

function clearFile() {
  document.getElementById('file-input').value = '';
  document.getElementById('file-selected').classList.add('hidden');
  document.querySelector('.file-upload-area').classList.remove('hidden');
}

// ==================== ЗАПУСК АНАЛИЗА ====================

async function startAnalysis() {
  console.log('=== startAnalysis ВЫЗВАНА ===');

  const fileInput = document.getElementById('file-input');
  const textInput = document.getElementById('document-text');

  // Анализ файла
  if (fileInput && fileInput.files && fileInput.files.length > 0) {
    const file = fileInput.files[0];
    console.log('✅ Найден файл:', file.name);

    showLoading(`Анализируем файл: ${file.name}...`);

    try {
      let text = '';
      const lowerName = file.name.toLowerCase();

      if (lowerName.endsWith('.txt')) {
        text = await file.text();
      } else if (lowerName.endsWith('.docx') || lowerName.endsWith('.pdf')) {
        text = `[Документ: ${file.name}]\n\n(Полный парсинг DOCX/PDF будет добавлен позже.)`;
      } else {
        showError('Поддерживаются только .txt, .docx и .pdf файлы');
        hideLoading();
        return;
      }

      if (text.length < 20) {
        showError(`Файл слишком короткий (${text.length} символов)`);
        hideLoading();
        return;
      }

      console.log('📄 Прочитано символов:', text.length);

      const token = localStorage.getItem('llm_auth_token');

      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ text })
      });

      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`Ошибка ${res.status}`);
      }

      const data = await res.json();
      showResults(data);

    } catch (err) {
      console.error('❌ Ошибка анализа файла:', err);
      showError(err.message || 'Не удалось проанализировать файл');
    } finally {
      hideLoading();
    }
    return;
  }

  // Анализ текста
  if (textInput) {
    const text = textInput.value.trim();
    if (text.length < 30) {
      showError('Введите минимум 30 символов');
      return;
    }

    const btn = document.getElementById('analyze-btn');
    const btnText = btn?.querySelector('.btn-text');
    const spinner = btn?.querySelector('.spinner');

    if (btnText) btnText.textContent = 'Анализ...';
    if (spinner) spinner.classList.remove('hidden');
    if (btn) btn.disabled = true;

    hideError();
    document.getElementById('analysis-results')?.classList.add('hidden');

    try {
      const token = localStorage.getItem('llm_auth_token');
      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ text })
      });

      const data = await res.json();
      showResults(data);
    } catch (err) {
      showError(err.message || 'Ошибка анализа');
    } finally {
      if (btnText) btnText.textContent = '🚀 Начать анализ';
      if (spinner) spinner.classList.add('hidden');
      if (btn) btn.disabled = false;
    }
  } else {
    showError('Выберите файл или введите текст');
  }
}

// ==================== ОТОБРАЖЕНИЕ РЕЗУЛЬТАТОВ ====================

function showResults(data) {
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
    issuesList.innerHTML = (data.issues || []).map(i => `<li>${i}</li>`).join('') || '<li>Явных проблем не найдено ✅</li>';
  }

  const recList = document.getElementById('recommendations-list');
  if (recList) {
    recList.innerHTML = (data.recommendations || []).map(r => `<li>${r}</li>`).join('') || '<li>Рекомендаций нет</li>';
  }

  const summaryEl = document.getElementById('summary-text');
  if (summaryEl) summaryEl.textContent = data.summary || 'Анализ завершён';

  resultsEl.classList.remove('hidden');
}

function setScore(id, value) {
  const el = document.getElementById(id);
  if (el && value !== undefined) el.textContent = `${Math.round(value)}/100`;
}

function clearResults() {
  document.getElementById('analysis-results')?.classList.add('hidden');
  const textInput = document.getElementById('document-text');
  if (textInput) textInput.value = '';
  document.getElementById('char-count').textContent = '0';
  clearFile();
  hideError();
}

// Экспорт
window.handleFileSelect = handleFileSelect;
window.startAnalysis = startAnalysis;
window.showResults = showResults;
window.clearResults = clearResults;
window.clearFile = clearFile;

console.log('✅ analysis.js загружен');