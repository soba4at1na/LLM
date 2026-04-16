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
      <aside class="sidebar" id="sidebar">
        <div class="logo"><h2>🤖 <span class="logo-text">LLM Checker</span></h2></div>
        <nav class="menu">
          <a href="#" id="menu-dashboard" onclick="navTo('dashboard')" class="menu-item active"><span class="menu-icon">🏠</span><span class="menu-label">Главная</span></a>
          <a href="#" id="menu-training" onclick="navTo('training')" class="menu-item"><span class="menu-icon">📚</span><span class="menu-label">Дообучение</span></a>
          <a href="#" id="menu-check" onclick="navTo('check')" class="menu-item"><span class="menu-icon">🔍</span><span class="menu-label">Проверка</span></a>
          <a href="#" id="menu-chat" onclick="toggleChatMenu(event)" class="menu-item"><span class="menu-icon">💬</span><span class="menu-label">Чат</span></a>
          <div id="chat-submenu" class="chat-submenu hidden">
            <div id="chat-list" class="chat-list"></div>
            <div class="chat-submenu-foot">
              <button class="btn-small" onclick="createNewChat()">+ Новый чат</button>
            </div>
          </div>
          <a href="#" id="admin-menu-overview" onclick="navTo('admin-overview')" class="menu-item hidden"><span class="menu-icon">🛡️</span><span class="menu-label">Админка</span></a>
          <a href="#" id="admin-menu-documents" onclick="navTo('admin-documents')" class="menu-item hidden"><span class="menu-icon">🗂️</span><span class="menu-label">Документы</span></a>
          <a href="#" id="admin-menu-users" onclick="navTo('admin-users')" class="menu-item hidden"><span class="menu-icon">👥</span><span class="menu-label">Пользователи</span></a>
          <a href="#" id="admin-menu-knowledge" onclick="navTo('admin-knowledge')" class="menu-item hidden"><span class="menu-icon">🧠</span><span class="menu-label">База знаний</span></a>
          <a href="#" id="admin-menu-audit" onclick="navTo('admin-audit')" class="menu-item hidden"><span class="menu-icon">📜</span><span class="menu-label">Аудит</span></a>
        </nav>
        <div class="sidebar-footer">
          <button class="btn-small sidebar-toggle" onclick="toggleSidebarCollapse()">⫶</button>
        </div>
      </aside>
      <div class="main-wrapper">
        <header class="topbar">
          <div class="topbar-left">
            <button class="btn-small mobile-sidebar-btn" onclick="toggleMobileSidebar()">☰</button>
            <h1 id="page-title">👋 Главная</h1>
          </div>
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
                <div class="info-item"><label>Роль</label><span id="user-role" class="badge">Пользователь</span></div>
              </div>
            </div>
          </div>

          <!-- Дообучение -->
          <div id="view-training" class="view hidden">
            <div class="results-section">
              <h4>📚 Документы для дообучения</h4>
              <div class="form-stack" style="margin-bottom:12px;">
                <select id="training-confidentiality">
                  <option value="confidential" selected>Конфиденциальность: commercial/confidential</option>
                  <option value="public">Конфиденциальность: public</option>
                </select>
              </div>
              <div id="training-upload-area" class="file-upload-area" onclick="document.getElementById('training-file-input').click()">
                <div class="file-upload-icon">📘</div>
                <div class="file-upload-text">Загрузить документ в базу дообучения</div>
                <div class="file-upload-hint">TXT, PDF, DOCX до 10MB</div>
                <input type="file" id="training-file-input" accept=".txt,.pdf,.docx" style="display:none" onchange="uploadTrainingDocument(this)">
              </div>
              <div class="check-actions">
                <button class="btn-small" onclick="loadTrainingDocuments()">Обновить список</button>
              </div>
              <div id="training-documents-list" class="admin-list"></div>
            </div>
          </div>

          <!-- Проверка -->
          <div id="view-check" class="view hidden">
            <div class="results-section">
              <h4>🔍 Документы для проверки</h4>
              <div class="form-stack" style="margin-bottom:12px;">
                <select id="check-confidentiality">
                  <option value="confidential" selected>Конфиденциальность: commercial/confidential</option>
                  <option value="public">Конфиденциальность: public</option>
                </select>
              </div>
              <div id="check-upload-area" class="file-upload-area" onclick="document.getElementById('file-input').click()">
                <div class="file-upload-icon">📄</div>
                <div class="file-upload-text">Нажмите для выбора файла</div>
                <div class="file-upload-hint">TXT, PDF, DOCX до 10MB</div>
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
            </div>
              
            <div id="analysis-results" class="results-container hidden">
                <div class="results-header">
                  <h3>📊 Результаты анализа</h3>
                  <div class="results-header-actions">
                    <button class="btn-small" onclick="exportCurrentAnalysis('json')">Экспорт JSON</button>
                    <button class="btn-small" onclick="exportCurrentAnalysis('pdf')">Экспорт PDF</button>
                    <button class="btn-small" onclick="clearResults()">Очистить</button>
                  </div>
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
                  <p id="analysis-meta" class="summary-text"></p>
                </div>

                <div class="results-section">
                  <div class="results-section-head">
                    <h4>📄 Просмотр документа</h4>
                    <div class="results-header-actions">
                      <button class="btn-small" onclick="applyAllFixes()">Применить все</button>
                      <button class="btn-small" onclick="undoAllFixes()">Отменить все</button>
                    </div>
                  </div>
                  <div id="analyzed-document-viewer" class="doc-viewer"></div>
                </div>
            </div>
              
            <div id="analysis-error" class="alert error hidden"></div>
          </div>

          <!-- Чат -->
          <!-- Чат -->
          <div id="view-chat" class="view hidden">
            <div class="chat-container">
              <div class="chat-messages" id="chat-messages"></div>
            </div>
          </div>

          <div id="view-admin-overview" class="view hidden">
            <div class="welcome-card">
              <h2>🛡️ Админ-статистика</h2>
              <div class="info-grid">
                <div class="info-item"><label>Пользователей</label><span id="admin-users-count">—</span></div>
                <div class="info-item"><label>Документов</label><span id="admin-documents-count">—</span></div>
                <div class="info-item"><label>Проверок</label><span id="admin-analyses-count">—</span></div>
                <div class="info-item"><label>Событий аудита</label><span id="admin-logs-count">—</span></div>
                <div class="info-item"><label>Активных за 24ч</label><span id="admin-active-users-24h">—</span></div>
                <div class="info-item"><label>Загрузок за 24ч</label><span id="admin-uploads-24h">—</span></div>
                <div class="info-item"><label>Проверок за 24ч</label><span id="admin-analyses-24h">—</span></div>
                <div class="info-item"><label>Документы check/training</label><span id="admin-doc-purpose-split">—</span></div>
              </div>
              <div class="check-actions">
                <button class="btn-small" onclick="loadAdminOverview()">Обновить статистику</button>
              </div>
            </div>

            <div class="results-section">
              <h4>Последние проверки (все пользователи)</h4>
              <div id="admin-history-list" class="admin-list"></div>
            </div>
          </div>

          <div id="view-admin-audit" class="view hidden">
            <div class="results-section">
              <h4>📜 Аудит-логи</h4>
              <div class="check-actions">
                <button class="btn-small" onclick="loadAdminAuditLogs()">Обновить логи</button>
              </div>
              <div id="admin-audit-list" class="admin-list"></div>
            </div>
          </div>

          <div id="view-admin-documents" class="view hidden">
            <div class="results-section">
              <h4>🗂️ Загруженные документы (админ)</h4>
              <div class="check-actions">
                <button id="admin-doc-filter-all" class="btn-small active-filter" onclick="loadAdminDocuments('all')">Все</button>
                <button id="admin-doc-filter-check" class="btn-small" onclick="loadAdminDocuments('check')">Для проверки</button>
                <button id="admin-doc-filter-training" class="btn-small" onclick="loadAdminDocuments('training')">Для дообучения</button>
              </div>
              <div id="admin-documents-list" class="admin-list"></div>
            </div>
          </div>

          <div id="view-admin-users" class="view hidden">
            <div class="results-section">
              <h4>👥 Краткая сводка по пользователям</h4>
              <div class="check-actions">
                <button id="admin-users-sort-last-login" class="btn-small active-filter" onclick="loadAdminUsersSummary('last_login')">По последнему входу</button>
                <button id="admin-users-sort-account-age" class="btn-small" onclick="loadAdminUsersSummary('account_age')">По возрасту аккаунта</button>
                <button id="admin-users-only-blocked" class="btn-small" onclick="toggleBlockedUsersFilter()">Только заблокированные: нет</button>
              </div>
              <div id="admin-users-list" class="admin-list"></div>
            </div>
          </div>

          <div id="view-admin-knowledge" class="view hidden knowledge-view">
            <div class="results-section">
              <h4>🧠 База знаний</h4>
              <div class="check-actions">
                <button class="btn-small" onclick="loadAdminKnowledge()">Обновить</button>
                <button class="btn-small" onclick="seedAdminKnowledgeDefaults()">Заполнить базовыми правилами</button>
                <button id="knowledge-filter-active-btn" class="btn-small" onclick="toggleKnowledgeActiveFilter()">Только активные: нет</button>
              </div>
              <div class="info-grid">
                <div class="info-item"><label>Источники</label><span id="knowledge-sources-count">—</span></div>
                <div class="info-item"><label>Термины</label><span id="knowledge-glossary-count">—</span></div>
                <div class="info-item"><label>Правила</label><span id="knowledge-rules-count">—</span></div>
                <div class="info-item"><label>Активные правила</label><span id="knowledge-active-rules-count">—</span></div>
              </div>
              <div class="results-section">
                <h4>Проверка правил на тексте</h4>
                <div class="form-stack">
                  <textarea id="knowledge-test-text" rows="4" placeholder="Введите тестовый текст, например: ip это интернет. ИБ!!"></textarea>
                  <button class="btn-small" onclick="runKnowledgeSmokeTest()">Проверить срабатывания</button>
                </div>
                <div id="knowledge-test-result" class="summary-text">—</div>
              </div>
            </div>

            <div class="admin-grid knowledge-grid">
              <div class="results-section">
                <h4>Источники (активные)</h4>
                <div id="knowledge-sources-list" class="admin-list knowledge-list-scroll"></div>
              </div>

              <div class="results-section">
                <h4>Термины глоссария</h4>
                <div class="knowledge-toolbar">
                  <input id="knowledge-glossary-search" type="text" placeholder="Поиск по термину/определению/источнику">
                  <select id="knowledge-glossary-source-filter">
                    <option value="all">Все источники</option>
                  </select>
                </div>
                <div id="knowledge-glossary-filter-stats" class="summary-text">Показаны все записи</div>
                <form id="knowledge-glossary-form" class="form-stack">
                  <input id="knowledge-term" type="text" placeholder="Термин" required>
                  <textarea id="knowledge-term-definition" rows="2" placeholder="Каноничное определение" required></textarea>
                  <input id="knowledge-term-forbidden" type="text" placeholder="Запрещенные варианты через ;">
                  <select id="knowledge-term-source-id">
                    <option value="">Источник: не выбран</option>
                  </select>
                  <select id="knowledge-term-severity">
                    <option value="low">low</option>
                    <option value="medium" selected>medium</option>
                    <option value="high">high</option>
                    <option value="critical">critical</option>
                  </select>
                  <button class="btn-small" type="submit">Добавить термин</button>
                  <div id="knowledge-term-error" class="form-error hidden"></div>
                </form>
                <div id="knowledge-glossary-list" class="admin-list knowledge-list-scroll"></div>
              </div>

              <div class="results-section">
                <h4>Правила</h4>
                <p class="summary-text">Regex-правила встроены в систему и недоступны для редактирования из UI.</p>
                <div id="knowledge-rules-list" class="admin-list knowledge-list-scroll"></div>
              </div>
            </div>
            <div class="results-section">
              <h4>Черновик Импорта</h4>
              <div class="knowledge-toolbar">
                <select id="knowledge-candidates-source-filter">
                  <option value="all">Все источники</option>
                </select>
                <div class="inline-actions">
                  <button class="btn-small" onclick="approveAllPendingCandidates()">Принять Все Pending</button>
                  <button class="btn-small btn-danger" onclick="rejectAllPendingCandidates()">Отклонить Все Pending</button>
                </div>
              </div>
              <div id="knowledge-candidates-list" class="admin-list knowledge-list-scroll"></div>
            </div>
            <div class="results-section">
              <h4>Снимки Policy</h4>
              <div class="inline-actions">
                <button class="btn-small" onclick="createKnowledgeSnapshot()">Создать снимок</button>
                <button class="btn-small" onclick="loadKnowledgeSnapshots()">Обновить список</button>
              </div>
              <div id="knowledge-snapshots-list" class="admin-list"></div>
            </div>
            <div class="results-section">
              <h4>Лента изменений базы знаний</h4>
              <div id="knowledge-audit-list" class="admin-list"></div>
            </div>
          </div>
        </div>
        <div id="chat-dock" class="chat-dock hidden">
          <button id="chat-scroll-down-btn" class="chat-scroll-down-btn hidden" onclick="scrollChatToBottom()">↓</button>
          <div class="chat-input-area">
            <textarea id="chat-input"
                      class="chat-input"
                      placeholder="Напишите сообщение... (Enter для отправки)"
                      rows="1"></textarea>
            <button onclick="sendChatMessage()" class="chat-send-btn">➤</button>
          </div>
        </div>

        <div id="knowledge-edit-modal" class="modal-overlay hidden">
          <div class="modal-card">
            <div class="modal-header">
              <h3 id="knowledge-edit-title">Редактирование</h3>
              <button class="btn-small" onclick="closeKnowledgeEditModal()">✕</button>
            </div>
            <form id="knowledge-edit-form" class="form-stack">
              <div id="knowledge-edit-fields"></div>
              <div class="inline-actions">
                <button type="submit" class="btn-small">Сохранить</button>
                <button type="button" class="btn-small btn-danger" onclick="closeKnowledgeEditModal()">Отмена</button>
              </div>
            </form>
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
