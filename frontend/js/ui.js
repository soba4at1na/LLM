// frontend/js/ui.js — Управление интерфейсом и SPA навигацией

function showPage(pageName) {
  const app = document.getElementById('app');
  if (!app) return;

  app.innerHTML = pages[pageName] || pages.login;

  // Привязка форм логина и регистрации
  if (pageName === 'login') {
    const form = document.getElementById('login-form');
    if (form) form.addEventListener('submit', handleLogin);
  }

  if (pageName === 'register') {
    const form = document.getElementById('register-form');
    if (form) form.addEventListener('submit', handleRegister);
  }

  // Дашборд
  if (pageName === 'dashboard') {
    loadUserInfo();
    setTimeout(attachAnalyzeButton, 100);
  }

  // Чат
  if (pageName === 'chat') {
    setTimeout(setupChat, 100);
  }

  console.log(`📄 Показана страница: ${pageName}`);
}

// Навигация по вкладкам
function navTo(viewName) {
  document.querySelectorAll('.menu-item').forEach(el => el.classList.remove('active'));

  const activeItem = document.querySelector(`.menu-item[onclick*="navTo('${viewName}')"]`);
  if (activeItem) activeItem.classList.add('active');

  const titles = {
    dashboard: '👋 Главная',
    training: '📚 Дообучение',
    check: '🔍 Проверка',
    chat: '💬 Чат'
  };
  const titleEl = document.getElementById('page-title');
  if (titleEl) titleEl.textContent = titles[viewName] || 'LLM Checker';

  document.querySelectorAll('.view').forEach(el => el.classList.add('hidden'));
  const viewEl = document.getElementById(`view-${viewName}`);
  if (viewEl) viewEl.classList.remove('hidden');

  console.log(`🧭 Переключение на вкладку: ${viewName}`);
}

// Привязка кнопки анализа
function attachAnalyzeButton() {
  let btn = document.getElementById('analyze-btn');
  if (!btn) return;

  const newBtn = btn.cloneNode(true);
  btn.parentNode.replaceChild(newBtn, btn);

  newBtn.addEventListener('click', () => {
    console.log('🖱️ Клик по кнопке "Начать анализ"');
    startAnalysis();
  });

  console.log('✅ Кнопка "Начать анализ" успешно привязана');
}

// Инициализация приложения
function initApp() {
  const token = localStorage.getItem('llm_auth_token');
  showPage(token ? 'dashboard' : 'login');
}

// Экспорт
window.showPage = showPage;
window.navTo = navTo;
window.attachAnalyzeButton = attachAnalyzeButton;
window.initApp = initApp;

console.log('✅ ui.js загружен');