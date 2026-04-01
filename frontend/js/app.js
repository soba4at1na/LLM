// frontend/js/app.js — SPA с реальными API вызовами

const API_BASE = 'http://localhost:8000'; // Пустая строка = относительные пути (nginx проксирует)

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
<div id="view-check" class="view hidden">
  <div class="check-container">
    <div class="check-header">
      <h2>🔍 Проверка качества документа</h2>
      <p class="check-description">Вставьте текст документа или загрузите файл для анализа</p>
    </div>
    
    <!-- Выбор источника -->
    <div class="source-tabs">
      <button class="source-tab active" data-source="text" onclick="switchSource('text')">📝 Текст</button>
      <button class="source-tab" data-source="file" onclick="switchSource('file')">📁 Файл</button>
    </div>
    
    <!-- Ввод текста -->
    <div id="source-text" class="source-panel active">
      <textarea id="document-text" placeholder="Вставьте текст документа сюда...&#10;&#10;Минимум 50 символов для анализа." rows="12"></textarea>
      <div class="char-count"><span id="char-count">0</span> символов</div>
    </div>
    
    <!-- Загрузка файла -->
    <div id="source-file" class="source-panel hidden">
      <div class="file-upload-area" onclick="document.getElementById('file-input').click()">
        <div class="file-upload-icon">📄</div>
        <div class="file-upload-text">Нажмите для выбора файла</div>
        <div class="file-upload-hint">PDF, DOCX, TXT (макс. 10 МБ)</div>
        <input type="file" id="file-input" accept=".txt,.pdf,.docx" style="display:none" onchange="handleFileSelect(this)">
      </div>
      <div id="file-selected" class="file-selected hidden">
        <span class="file-name" id="file-name"></span>
        <button class="btn-small" onclick="clearFile()">✕</button>
      </div>
    </div>
    
    <!-- Кнопка анализа -->
    <div class="check-actions">
      <button id="analyze-btn" class="btn-primary btn-large" onclick="startAnalysis()">
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
    
    <!-- Ошибка -->
    <div id="analysis-error" class="alert error hidden"></div>
  </div>
</div>          <div id="view-chat" class="view hidden"><div class="placeholder"><h3>💬 Чат</h3><p>Скоро...</p></div></div>
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
  
  // Привязываем обработчики после отрисовки
  if (pageName === 'login') {
    document.getElementById('login-form')?.addEventListener('submit', handleLogin);
  }
  if (pageName === 'register') {
    document.getElementById('register-form')?.addEventListener('submit', handleRegister);
  }
  if (pageName === 'dashboard') {
    loadUserInfo();
  }
}

// Переключение вкладок внутри дашборда
function navTo(viewName) {
  // Обновляем активную вкладку в меню
  document.querySelectorAll('.menu-item').forEach(el => el.classList.remove('active'));
  event.currentTarget.classList.add('active');
  
  // Обновляем заголовок
  const titles = {
    dashboard: '👋 Главная',
    training: '📚 Дообучение',
    check: '🔍 Проверка',
    chat: '💬 Чат'
  };
  document.getElementById('page-title').textContent = titles[viewName] || 'LLM Checker';
  
  // Показываем нужный view
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
    
    // ✅ Сохраняем РЕАЛЬНЫЙ токен
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
    
    // Topbar
    const topEmail = document.getElementById('top-email');
    const topId = document.getElementById('top-id');
    if (topEmail) topEmail.textContent = user.email;
    if (topId && user.id) topId.textContent = 'ID: ' + user.id.substring(0, 8) + '...';
    
    // Card
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

// Начало анализа
async function startAnalysis() {
  const textInput = document.getElementById('document-text');
  const fileInput = document.getElementById('file-input');
  const activeSource = document.querySelector('.source-tab.active')?.dataset.source;
  
  let text = '';
  
  if (activeSource === 'text') {
    text = textInput?.value.trim();
    if (text.length < 50) {
      showError('Введите минимум 50 символов для анализа');
      return;
    }
  } else {
    const file = fileInput?.files[0];
    if (!file) {
      showError('Выберите файл для анализа');
      return;
    }
    // Для простоты читаем только TXT файлы
    if (file.type === 'text/plain') {
      text = await file.text();
    } else {
      showError('Пока поддерживаются только TXT файлы. Вставьте текст вручную для других форматов.');
      return;
    }
  }
  
  const btn = document.getElementById('analyze-btn');
  const btnText = btn?.querySelector('.btn-text');
  const spinner = btn?.querySelector('.spinner');
  
  // Показываем загрузку
  if (btnText) btnText.textContent = 'Анализ...';
  if (spinner) spinner.classList.remove('hidden');
  if (btn) btn.disabled = true;
  
  hideError();
  document.getElementById('analysis-results')?.classList.add('hidden');
  
  try {
const token = localStorage.getItem('llm_auth_token');

const res = await fetch('/api/analyze', {
  method: 'POST',
  headers: { 
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`  // ← ДОБАВИЛИ ТОКЕН!
  },
  body: JSON.stringify({ text })
});
    
    const data = await res.json();
    
    if (!res.ok) throw new Error(data.detail || 'Ошибка анализа');
    
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

function showResults(data) {
  const resultsEl = document.getElementById('analysis-results');
  if (!resultsEl) return;
  
  // Общий score
  const scoreEl = document.getElementById('quality-score');
  if (scoreEl && data.overall_score) {
    const score = data.overall_score;
    scoreEl.querySelector('.score-value').textContent = score;
    scoreEl.style.background = `conic-gradient(var(--primary) ${score * 3.6}deg, var(--border) ${score * 3.6}deg)`;
  }
  
  // Детальные scores
  setScore('readability-score', data.readability_score);
  setScore('grammar-score', data.grammar_score);
  setScore('structure-score', data.structure_score);
  
  // Проблемы
  const issuesList = document.getElementById('issues-list');
  if (issuesList) {
    issuesList.innerHTML = (data.issues || []).map(i => `<li>${i}</li>`).join('') || '<li>Проблем не найдено ✅</li>';
  }
  
  // Рекомендации
  const recList = document.getElementById('recommendations-list');
  if (recList) {
    recList.innerHTML = (data.recommendations || []).map(r => `<li>${r}</li>`).join('') || '<li>Нет рекомендаций</li>';
  }
  
  // Резюме
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