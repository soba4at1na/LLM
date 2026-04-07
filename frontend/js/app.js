// frontend/js/app.js — Главный файл SPA (инициализация и подключение модулей)

// Подключаем все модули
// (они уже загружены через window, но мы вызываем их здесь)

//const API_BASE = '';

// Хранилище страниц (HTML-шаблоны)
const pages = {
  login: `
    <div class="auth-container">
      <div class="auth-card">
        <h1>🔐 Вход в систему</h1>
        <div id="login-error" class="alert error"></div>
        <form id="login-form">
          <div class="form-group">
            <label>Email или username</label>
            <input type="text" id="login-username" required placeholder="egor.gulih@gmail.com">
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
          <!-- Главная -->
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
          </div>

          <!-- Дообучение -->
          <div id="view-training" class="view hidden">
            <div class="placeholder"><h3>📚 Дообучение</h3><p>Скоро...</p></div>
          </div>

          <!-- Проверка -->
          <div id="view-check" class="view hidden">
            <div class="check-container">
              <div class="check-header">
                <h2>🔍 Проверка документа</h2>
                <p class="check-description">Загрузите файл для анализа</p>
              </div>
              
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
              
              <div class="check-actions">
                <button id="analyze-btn" class="btn-primary btn-large">
                  <span class="btn-text">🚀 Начать анализ</span>
                  <span class="spinner hidden"></span>
                </button>
              </div>
              
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

          <!-- Чат -->
          <!-- Чат -->
          <div id="view-chat" class="view hidden">
            <div class="chat-container">
              <div class="chat-messages" id="chat-messages"></div>
              
              <div class="chat-input-area">
                <textarea id="chat-input" 
                          class="chat-input" 
                          placeholder="Напишите сообщение... (Enter для отправки)"
                          rows="1"></textarea>
                <button onclick="sendChatMessage()" class="chat-send-btn">➤</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `
};

// === Запуск приложения ===
document.addEventListener('DOMContentLoaded', () => {
  console.log('🚀 Приложение запущено');
  const token = localStorage.getItem('llm_auth_token');
  showPage(token ? 'dashboard' : 'login');
});

// Экспортируем страницы для других модулей
window.pages = pages;

console.log('✅ app.js загружен — SPA инициализирован');