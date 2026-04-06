// frontend/js/app.js — SPA с реальными API вызовами

const API_BASE = ''; // Пустая строка = относительные пути (nginx проксирует)

// Хранилище "страниц" как HTML-шаблонов
const pages = {
  login: `
    <div class="auth-container">
      <div class="auth-card">
        <h1>🔐 Вход в систему</h1>
        <div id="login-error" class="alert error"></div>
        <form id="login-form">
          <div class="form-group">
            <label>Email или username</label>
            <input type="text" id="login-username" required placeholder="user@example.com">
          </div>
          <div class="form-group">
            <label>Пароль</label>
            <input type="password" id="login-password" required>
          </div>
          <button type="submit" id="login-btn" class="btn-primary">Войти</button>
        </form>
        <p class="toggle">Нет аккаунта? <a href="#" onclick="showPage('register')">Зарегистрироваться</a></p>
      </div>
    </div>
  `,

  register: `
    <div class="auth-container">
      <div class="auth-card">
        <h1>📝 Регистрация</h1>
        <div id="register-error" class="alert error"></div>
        <div id="register-success" class="alert success"></div>
        <form id="register-form">
          <div class="form-group">
            <label>Email</label>
            <input type="email" id="reg-email" required>
          </div>
          <div class="form-group">
            <label>Username</label>
            <input type="text" id="reg-username" required minlength="3">
          </div>
          <div class="form-group">
            <label>Пароль (мин. 8 символов)</label>
            <input type="password" id="reg-password" required minlength="8">
          </div>
          <button type="submit" id="register-btn" class="btn-primary">Зарегистрироваться</button>
        </form>
        <p class="toggle">Уже есть аккаунт? <a href="#" onclick="showPage('login')">Войти</a></p>
      </div>
    </div>
  `,

  dashboard: `
    <div class="dashboard-wrapper">
      <aside class="sidebar">
        <div class="logo"><h2>🤖 LLM Checker</h2></div>
        <nav class="menu">
          <a href="#" onclick="navTo('dashboard')" class="menu-item active">🏠 Главная</a>
          <a href="#" onclick="navTo('training')" class="menu-item">📚 Дообучение</a>
          <a href="#" onclick="navTo('check')" class="menu-item">🔍 Проверка</a>
          <a href="#" onclick="navTo('chat')" class="menu-item">💬 Чат</a>
        </nav>
      </aside>
      <div class="main-wrapper">
        <header class="topbar">
          <div class="topbar-left"><h1 id="page-title">👋 Главная</h1></div>
          <div class="topbar-right">
            <div class="user-info-display">
              <span id="top-email" class="user-email-display">Загрузка...</span>
              <span id="top-id" class="user-id-display">ID: —</span>
            </div>
            <button onclick="doLogout()" class="btn-danger">Выйти</button>
          </div>
        </header>
        <div class="content">
          <div id="view-dashboard" class="view active">
            <div class="welcome-card">
              <h2>Добро пожаловать!</h2>
              <div class="info-grid">
                <div class="info-item"><label>Username</label><span id="user-username">—</span></div>
                <div class="info-item"><label>Email</label><span id="user-email">—</span></div>
                <div class="info-item"><label>ID</label><span id="user-id">—</span></div>
                <div class="info-item"><label>Статус</label><span class="badge success">Активен</span></div>
              </div>
            </div>
            <div class="placeholder"><h3>🚀 Скоро новые функции</h3><p>Система в разработке.</p></div>
          </div>
          <div id="view-training" class="view hidden"><div class="placeholder"><h3>📚 Дообучение</h3><p>Скоро...</p></div></div>
          
<!-- Проверка -->
<div id="view-check" class="view hidden">
  <div class="check-container">
    <div class="check-header">
      <h2>🔍 Проверка документа</h2>
      <p class="check-description">Загрузите файл для анализа</p>
    </div>
    
    <!-- Только файл -->
    <div class="file-upload-area" onclick="document.getElementById('file-input').click()">
      <div class="file-upload-icon">📄</div>
      <div class="file-upload-text">Нажмите для выбора файла</div>
      <div class="file-upload-hint">PDF, DOCX, TXT</div>
      <input type="file" id="file-input" accept=".txt,.pdf,.docx" style="display:none" onchange="handleFileSelect(this)">
    </div>
    
    <div id="file-selected" class="file-selected hidden">
      <span class="file-name" id="file-name"></span>
      <button class="btn-small" onclick="clearFile()">✕</button>
    </div>
    
<!-- Кнопка анализа -->
<div class="check-actions">
  <button id="analyze-btn" class="btn-primary btn-large">
    <span class="btn-text">🚀 Начать анализ</span>
    <span class="spinner hidden"></span>
  </button>
</div>
    
    <!-- Результаты -->
    <div id="analysis-results" class="results-container hidden">
      <div class="results-header">
        <h3>📊 Результаты анализа</h3>
        <button class="btn-small" onclick="clearResults()">Очистить</button>
      </div>
      
      <div class="score-card">
        <div class="score-circle" id="quality-score">
          <span class="score-value">--</span>
          <span class="score-label">Качество</span>
        </div>
        <div class="score-details">
          <div class="score-item"><span class="label">Читаемость:</span><span class="value" id="readability-score">--</span></div>
          <div class="score-item"><span class="label">Грамотность:</span><span class="value" id="grammar-score">--</span></div>
          <div class="score-item"><span class="label">Структура:</span><span class="value" id="structure-score">--</span></div>
        </div>
      </div>
      
      <div class="results-section">
        <h4>⚠️ Найденные проблемы</h4>
        <ul id="issues-list" class="issues-list"></ul>
      </div>
      
      <div class="results-section">
        <h4>💡 Рекомендации</h4>
        <ul id="recommendations-list" class="recommendations-list"></ul>
      </div>
      
      <div class="results-section">
        <h4>📝 Краткое резюме</h4>
        <p id="summary-text" class="summary-text"></p>
      </div>
    </div>
    
    <div id="analysis-error" class="alert error hidden"></div>
  </div>
</div>
          
          <div id="view-chat" class="view hidden"><div class="placeholder"><h3>💬 Чат</h3><p>Скоро...</p></div></div>
        </div>
      </div>
    </div>
  `
};

// === Инициализация ===
document.addEventListener('DOMContentLoaded', () => {
  const token = localStorage.getItem('llm_auth_token');
  showPage(token ? 'dashboard' : 'login');
});

// === Навигация ===
function showPage(pageName) {
  const app = document.getElementById('app');
  if (!app) return;
  
  app.innerHTML = pages[pageName] || pages.login;
  
  if (pageName === 'login') {
    document.getElementById('login-form')?.addEventListener('submit', handleLogin);
  }
  if (pageName === 'register') {
    document.getElementById('register-form')?.addEventListener('submit', handleRegister);
  }
 if (pageName === 'dashboard') {
  loadUserInfo();
  setTimeout(attachAnalyzeButton, 150);   // чуть больше задержка
}
}

// Переключение вкладок внутри дашборда
function navTo(viewName) {
  document.querySelectorAll('.menu-item').forEach(el => el.classList.remove('active'));
  event.currentTarget.classList.add('active');
  
  const titles = {
    dashboard: '👋 Главная',
    training: '📚 Дообучение',
    check: '🔍 Проверка',
    chat: '💬 Чат'
  };
  document.getElementById('page-title').textContent = titles[viewName] || 'LLM Checker';
  
  document.querySelectorAll('.view').forEach(el => el.classList.add('hidden'));
  document.getElementById(`view-${viewName}`)?.classList.remove('hidden');
}

// === Авторизация ===
async function handleLogin(e) {
  e.preventDefault();
  
  const username = document.getElementById('login-username')?.value.trim();
  const password = document.getElementById('login-password')?.value;
  const errorEl = document.getElementById('login-error');
  const btn = document.getElementById('login-btn');
  
  if (!username || !password) return;
  
  errorEl.style.display = 'none';
  btn.disabled = true;
  btn.textContent = 'Вход...';
  
  console.log('🔐 Sending login...', { username });
  
  try {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData
    });
    
    console.log('📡 Status:', res.status);
    const data = await res.json();
    
    if (!res.ok) throw new Error(data.detail || 'Ошибка входа');
    
    localStorage.setItem('llm_auth_token', data.access_token);
    console.log('✅ Token:', data.access_token.substring(0, 40) + '...');
    
    showPage('dashboard');
    
  } catch (err) {
    console.error('❌ Login error:', err);
    if (errorEl) {
      errorEl.textContent = err.message;
      errorEl.style.display = 'block';
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Войти';
    }
  }
}

async function handleRegister(e) {
  e.preventDefault();
  
  const payload = {
    email: document.getElementById('reg-email')?.value.trim().toLowerCase(),
    username: document.getElementById('reg-username')?.value.trim(),
    password: document.getElementById('reg-password')?.value
  };
  
  const errorEl = document.getElementById('register-error');
  const successEl = document.getElementById('register-success');
  const btn = document.getElementById('register-btn');
  
  errorEl.style.display = 'none';
  successEl.style.display = 'none';
  btn.disabled = true;
  btn.textContent = 'Регистрация...';
  
  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    const data = await res.json();
    
    if (!res.ok) throw new Error(data.detail || 'Ошибка регистрации');
    
    successEl.textContent = '✅ Успешно! Теперь войдите.';
    successEl.style.display = 'block';
    
    setTimeout(() => showPage('login'), 1500);
    
  } catch (err) {
    console.error('❌ Register error:', err);
    if (errorEl) {
      errorEl.textContent = err.message;
      errorEl.style.display = 'block';
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Зарегистрироваться';
    }
  }
}

// === Профиль ===
async function loadUserInfo() {
  const token = localStorage.getItem('llm_auth_token');
  if (!token) {
    showPage('login');
    return;
  }
  
  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (!res.ok) {
      if (res.status === 401) {
        localStorage.removeItem('llm_auth_token');
        showPage('login');
      }
      throw new Error('Не удалось загрузить данные');
    }
    
    const user = await res.json();
    console.log('✅ User loaded:', user);
    
    const topEmail = document.getElementById('top-email');
    const topId = document.getElementById('top-id');
    if (topEmail) topEmail.textContent = user.email;
    if (topId && user.id) topId.textContent = 'ID: ' + user.id.substring(0, 8) + '...';
    
    ['username', 'email', 'id'].forEach(field => {
      const el = document.getElementById(`user-${field}`);
      if (el && user[field]) {
        el.textContent = field === 'id' ? user[field] : user[field];
      }
    });
    
  } catch (err) {
    console.error('❌ Profile error:', err);
  }
}

function doLogout() {
  console.log('🚪 Logout');
  localStorage.removeItem('llm_auth_token');
  showPage('login');
}

// === Check Page Functions ===

function switchSource(source) {
  document.querySelectorAll('.source-tab').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.source-panel').forEach(el => el.classList.remove('active'));
  
  document.querySelector(`[data-source="${source}"]`)?.classList.add('active');
  document.getElementById(`source-${source}`)?.classList.add('active');
}

// Счётчик символов
document.addEventListener('input', (e) => {
  if (e.target.id === 'document-text') {
    const count = e.target.value.length;
    document.getElementById('char-count').textContent = count;
  }
});

// Выбор файла
function handleFileSelect(input) {
  const file = input.files[0];
  if (file) {
    document.getElementById('file-name').textContent = file.name;
    document.getElementById('file-selected').classList.remove('hidden');
    document.querySelector('.file-upload-area').classList.add('hidden');
  }
}

function clearFile() {
  document.getElementById('file-input').value = '';
  document.getElementById('file-selected').classList.add('hidden');
  document.querySelector('.file-upload-area').classList.remove('hidden');
}

// Начало анализа (для текста)
// ==================== АНАЛИЗ (с отладкой) ====================

async function startAnalysis() {
  console.log('=== startAnalysis ВЫЗВАНА ===');

  const fileInput = document.getElementById('file-input');
  const textInput = document.getElementById('document-text');

  if (fileInput && fileInput.files && fileInput.files.length > 0) {
    const file = fileInput.files[0];
    console.log('✅ Будем анализировать файл:', file.name);

    // Показываем оверлей и НЕ прячем его до конца запроса
    showLoading(`Анализируем файл: ${file.name}... (это может занять несколько минут)`);

    try {
      let text = '';

      if (file.type === 'text/plain' || file.name.toLowerCase().endsWith('.txt')) {
        text = await file.text();
        console.log('📄 Прочитано символов:', text.length);
      } else {
        showError('Пока поддерживаются только .txt файлы.');
        hideLoading();
        return;
      }

      if (text.length < 10) {   // снизили порог для тестов
        showError(`Файл слишком короткий (${text.length} символов)`);
        hideLoading();
        return;
      }

      console.log('📤 Отправляем запрос на сервер...');
      const token = localStorage.getItem('llm_auth_token');

      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ text })
      });

      console.log('📡 Статус ответа:', res.status);

      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`Ошибка ${res.status}: ${errorText.substring(0, 150)}`);
      }

      const data = await res.json();
      console.log('✅ Результат получен');
      showResults(data);

    } catch (err) {
      console.error('❌ Ошибка анализа:', err);
      showError(err.message || 'Не удалось получить результат');
    } finally {
      hideLoading();        // прячем только в конце
    }
    return;
  }

  // Анализ текста (оставляем как было)
  if (textInput) {
    const text = textInput.value.trim();
    if (text.length < 10) {
      showError('Введите текст (минимум 10 символов)');
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
      console.error('Analysis error:', err);
      showError(err.message);
    } finally {
      if (btnText) btnText.textContent = '🚀 Начать анализ';
      if (spinner) spinner.classList.add('hidden');
      if (btn) btn.disabled = false;
    }
  }
}

function showResults(data) {
  const resultsEl = document.getElementById('analysis-results');
  if (!resultsEl) return;
  
  const scoreEl = document.getElementById('quality-score');
  if (scoreEl && data.overall_score) {
    const score = data.overall_score;
    scoreEl.querySelector('.score-value').textContent = score;
    scoreEl.style.background = `conic-gradient(var(--primary) ${score * 3.6}deg, var(--border) ${score * 3.6}deg)`;
  }
  
  setScore('readability-score', data.readability_score);
  setScore('grammar-score', data.grammar_score);
  setScore('structure-score', data.structure_score);
  
  const issuesList = document.getElementById('issues-list');
  if (issuesList) {
    issuesList.innerHTML = (data.issues || []).map(i => `<li>${i}</li>`).join('') || '<li>Проблем не найдено ✅</li>';
  }
  
  const recList = document.getElementById('recommendations-list');
  if (recList) {
    recList.innerHTML = (data.recommendations || []).map(r => `<li>${r}</li>`).join('') || '<li>Нет рекомендаций</li>';
  }
  
  const summaryEl = document.getElementById('summary-text');
  if (summaryEl) {
    summaryEl.textContent = data.summary || 'Анализ завершён';
  }
  
  resultsEl.classList.remove('hidden');
}

function setScore(id, value) {
  const el = document.getElementById(id);
  if (el && value !== undefined) {
    el.textContent = value + '/100';
  }
}

function clearResults() {
  document.getElementById('analysis-results')?.classList.add('hidden');
  document.getElementById('document-text').value = '';
  document.getElementById('char-count').textContent = '0';
  clearFile();
  hideError();
}

function showError(message) {
  const el = document.getElementById('analysis-error');
  if (el) {
    el.textContent = message;
    el.classList.remove('hidden');
  }
}

function hideError() {
  const el = document.getElementById('analysis-error');
  if (el) {
    el.classList.add('hidden');
    el.textContent = '';
  }
}

// ==================== НОВОЕ: Обработка файла ====================
// ==================== ОБРАБОТКА ФАЙЛА ====================
// ==================== ОБРАБОТКА ФАЙЛА ====================
// ==================== ОБРАБОТКА ФАЙЛА ====================

async function handleFileSelect(input) {
  const file = input.files[0];
  if (!file) return;

  document.getElementById('file-name').textContent = file.name;
  document.getElementById('file-selected').classList.remove('hidden');
  document.querySelector('.file-upload-area').classList.add('hidden');
}

function clearFile() {
  document.getElementById('file-input').value = '';
  document.getElementById('file-selected').classList.add('hidden');
  document.querySelector('.file-upload-area').classList.remove('hidden');
}

// ==================== LOADING ====================

function showLoading(text = 'Загрузка...') {
  let overlay = document.getElementById('loading-overlay');
  if (overlay) return;

  overlay = document.createElement('div');
  overlay.id = 'loading-overlay';
  overlay.style.cssText = `
    position: fixed; inset: 0; background: rgba(0,0,0,0.85);
    display: flex; align-items: center; justify-content: center;
    color: white; z-index: 9999; font-size: 1.1rem;
  `;
  overlay.innerHTML = `
    <div style="text-align:center;">
      <div style="width:40px;height:40px;border:4px solid #ffffff30;border-top-color:#6366f1;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 15px;"></div>
      <div>${text}</div>
    </div>
  `;
  document.body.appendChild(overlay);
}

function hideLoading() {
  const overlay = document.getElementById('loading-overlay');
  if (overlay) overlay.remove();
}

// ==================== АНАЛИЗ ====================

async function startAnalysis() {
  console.log('=== startAnalysis ВЫЗВАНА ===');

  const fileInput = document.getElementById('file-input');
  console.log('fileInput:', fileInput ? 'найден' : 'НЕ НАЙДЕН');
  console.log('files.length:', fileInput ? fileInput.files.length : 0);

  // Если есть выбранный файл
  if (fileInput && fileInput.files && fileInput.files.length > 0) {
    const file = fileInput.files[0];
    console.log('✅ Будем анализировать файл:', file.name);

    showLoading(`Анализируем файл: ${file.name}...`);

    try {
      let text = '';

      if (file.type === 'text/plain' || file.name.toLowerCase().endsWith('.txt')) {
        text = await file.text();
        console.log('📄 Прочитано символов:', text.length);
      } else {
        showError('Поддерживаются только .txt файлы');
        hideLoading();
        return;
      }

      if (text.length < 50) {
        showError('Файл слишком короткий');
        hideLoading();
        return;
      }

      console.log('📤 Отправляем запрос на сервер...');
      const token = localStorage.getItem('llm_auth_token');
      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ text })
      });

      console.log('📡 Статус ответа:', res.status);

      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`Ошибка ${res.status}`);
      }

      const data = await res.json();
      console.log('✅ Результат получен');
      showResults(data);

    } catch (err) {
      console.error('❌ Ошибка:', err);
      showError(err.message);
    } finally {
      hideLoading();
    }
    return;
  }

  console.log('⚠️ Ни файл, ни текст не обнаружены');
  showError('Выберите файл или введите текст');
}

// ==================== ПРИВЯЗКА КНОПКИ АНАЛИЗА ====================

// ==================== ПРИВЯЗКА КНОПКИ АНАЛИЗА ====================

function attachAnalyzeButton() {
  const analyzeBtn = document.getElementById('analyze-btn');
  if (!analyzeBtn) {
    console.log('⚠️ Кнопка analyze-btn не найдена');
    return;
  }

  // Удаляем все старые обработчики
  const newBtn = analyzeBtn.cloneNode(true);
  analyzeBtn.parentNode.replaceChild(newBtn, analyzeBtn);

  // Добавляем новый обработчик
  newBtn.addEventListener('click', () => {
    console.log('🖱️ Клик по кнопке "Начать анализ" зафиксирован');
    startAnalysis();
  });

  console.log('✅ Кнопка "Начать анализ" успешно перепривязана');
}

// ==================== Запуск ====================

document.addEventListener('DOMContentLoaded', () => {
  const token = localStorage.getItem('llm_auth_token');
  showPage(token ? 'dashboard' : 'login');
});