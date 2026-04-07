// frontend/js/ui.js — Управление интерфейсом и SPA навигацией

// === Основная функция показа страницы ===
function showPage(pageName) {
  const app = document.getElementById('app');
  if (!app) return;

  app.innerHTML = pages[pageName] || pages.login;

  // Привязываем обработчики в зависимости от страницы
  if (pageName === 'login') {
    const form = document.getElementById('login-form');
    if (form) form.addEventListener('submit', handleLogin);
  }

  if (pageName === 'register') {
    const form = document.getElementById('register-form');
    if (form) form.addEventListener('submit', handleRegister);
  }

  if (pageName === 'dashboard') {
    loadUserInfo();
    setTimeout(attachAnalyzeButton, 100);
  }

  console.log(`📄 Показана страница: ${pageName}`);
}

// === Навигация по вкладкам в дашборде ===
function navTo(viewName) {
  // Убираем активный класс у всех пунктов меню
  document.querySelectorAll('.menu-item').forEach(el => el.classList.remove('active'));
  
  // Добавляем активный класс текущему пункту
  const activeItem = document.querySelector(`.menu-item[onclick*="navTo('${viewName}')"]`);
  if (activeItem) activeItem.classList.add('active');

  // Меняем заголовок в топбаре
  const titles = {
    dashboard: '👋 Главная',
    training: '📚 Дообучение',
    check: '🔍 Проверка',
    chat: '💬 Чат'
  };
  const titleEl = document.getElementById('page-title');
  if (titleEl) titleEl.textContent = titles[viewName] || 'LLM Checker';

  // Прячем все view и показываем нужный
  document.querySelectorAll('.view').forEach(el => el.classList.add('hidden'));
  const viewEl = document.getElementById(`view-${viewName}`);
  if (viewEl) viewEl.classList.remove('hidden');

  console.log(`🧭 Переключение на вкладку: ${viewName}`);
}

// === Привязка кнопки "Начать анализ" ===
function attachAnalyzeButton() {
  const analyzeBtn = document.getElementById('analyze-btn');
  if (!analyzeBtn) {
    console.log('⚠️ Кнопка analyze-btn не найдена');
    return;
  }

  // Клонируем кнопку, чтобы удалить старые обработчики
  const newBtn = analyzeBtn.cloneNode(true);
  analyzeBtn.parentNode.replaceChild(newBtn, analyzeBtn);

  // Добавляем новый обработчик
  newBtn.addEventListener('click', () => {
    console.log('🖱️ Клик по кнопке "Начать анализ"');
    startAnalysis();
  });

  console.log('✅ Кнопка "Начать анализ" успешно привязана');
}

// === Инициализация всего приложения ===
function initApp() {
  const token = localStorage.getItem('llm_auth_token');
  showPage(token ? 'dashboard' : 'login');
}

// Экспортируем функции для использования в других модулях
window.showPage = showPage;
window.navTo = navTo;
window.attachAnalyzeButton = attachAnalyzeButton;
window.initApp = initApp;

  if (pageName === 'chat') {
    setTimeout(setupChatInput, 100);
  }

console.log('✅ ui.js загружен');