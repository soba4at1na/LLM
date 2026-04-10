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
    setTimeout(applySavedSidebarState, 0);
    setTimeout(startModelStatusMonitor, 100);
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

  const menuByView = {
    dashboard: 'menu-dashboard',
    training: 'menu-training',
    check: 'menu-check',
    chat: 'menu-chat',
    'admin-overview': 'admin-menu-overview',
    'admin-documents': 'admin-menu-documents',
    'admin-users': 'admin-menu-users',
    'admin-audit': 'admin-menu-audit',
  };
  const activeItem = document.getElementById(menuByView[viewName] || '');
  if (activeItem) activeItem.classList.add('active');

  const titles = {
    dashboard: '👋 Главная',
    training: '📚 Дообучение',
    check: '🔍 Проверка',
    chat: '💬 Чат',
    'admin-overview': '🛡️ Админка',
    'admin-documents': '🗂️ Документы',
    'admin-users': '👥 Пользователи',
    'admin-audit': '📜 Аудит'
  };
  const titleEl = document.getElementById('page-title');
  if (titleEl) titleEl.textContent = titles[viewName] || 'LLM Checker';

  document.querySelectorAll('.view').forEach(el => el.classList.add('hidden'));
  const viewEl = document.getElementById(`view-${viewName}`);
  if (viewEl) viewEl.classList.remove('hidden');
  localStorage.setItem('llm_last_view', viewName);

  const sidebar = document.getElementById('sidebar');
  const chatDock = document.getElementById('chat-dock');
  const content = document.querySelector('.content');
  const chatSubmenu = document.getElementById('chat-submenu');
  if (sidebar && sidebar.classList.contains('open')) {
    sidebar.classList.remove('open');
  }
  if (chatDock) {
    const isChat = viewName === 'chat';
    chatDock.classList.toggle('hidden', !isChat);
    if (isChat) syncChatDockPosition();
  }
  if (content) {
    content.classList.toggle('chat-mode', viewName === 'chat');
  }
  if (chatSubmenu && viewName !== 'chat') {
    chatSubmenu.classList.add('hidden');
    if (typeof window.setChatsExpanded === 'function') window.setChatsExpanded(false);
  }

  if (viewName === 'admin-overview' && typeof loadAdminOverview === 'function') {
    loadAdminOverview();
  }

  if (viewName === 'admin-audit' && typeof loadAdminAuditLogs === 'function') {
    loadAdminAuditLogs();
  }

  if (viewName === 'admin-documents' && typeof loadAdminDocuments === 'function') {
    loadAdminDocuments('all');
  }

  if (viewName === 'admin-users' && typeof loadAdminUsersSummary === 'function') {
    loadAdminUsersSummary();
  }

  if (viewName === 'training' && typeof loadTrainingDocuments === 'function') {
    loadTrainingDocuments();
  }

  if (viewName === 'check' && typeof loadLatestAnalysisForUser === 'function') {
    loadLatestAnalysisForUser();
  }

  if (viewName === 'chat' && typeof setupChat === 'function') {
    setupChat();
  }

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

function toggleSidebarCollapse() {
  const sidebar = document.getElementById('sidebar');
  const main = document.querySelector('.main-wrapper');
  if (!sidebar || !main) return;
  const isCollapsed = sidebar.classList.toggle('collapsed');
  main.classList.toggle('sidebar-collapsed', isCollapsed);
  localStorage.setItem('llm_sidebar_collapsed', isCollapsed ? '1' : '0');
  syncSidebarToggleButton();
  syncChatDockPosition();
  syncChatSubmenuState();
}

function toggleMobileSidebar() {
  const sidebar = document.getElementById('sidebar');
  if (!sidebar) return;
  sidebar.classList.toggle('open');
}

function applySavedSidebarState() {
  const sidebar = document.getElementById('sidebar');
  const main = document.querySelector('.main-wrapper');
  if (!sidebar || !main) return;
  const collapsed = localStorage.getItem('llm_sidebar_collapsed') === '1';
  sidebar.classList.toggle('collapsed', collapsed);
  main.classList.toggle('sidebar-collapsed', collapsed);
  syncSidebarToggleButton();
  syncChatDockPosition();
  syncChatSubmenuState();
}

function syncSidebarToggleButton() {
  const sidebar = document.getElementById('sidebar');
  const btn = document.querySelector('.sidebar-toggle');
  if (!sidebar || !btn) return;
  const collapsed = sidebar.classList.contains('collapsed');
  btn.textContent = collapsed ? '»' : '«';
  btn.title = collapsed ? 'Развернуть панель' : 'Свернуть панель';
}

function syncChatDockPosition() {
  const sidebar = document.getElementById('sidebar');
  const dock = document.getElementById('chat-dock');
  if (!dock || !sidebar) return;
  dock.classList.toggle('sidebar-collapsed', sidebar.classList.contains('collapsed'));
}

function syncChatSubmenuState() {
  const sidebar = document.getElementById('sidebar');
  const submenu = document.getElementById('chat-submenu');
  if (!sidebar || !submenu) return;
  if (sidebar.classList.contains('collapsed')) {
    submenu.classList.add('hidden');
    if (typeof window.setChatsExpanded === 'function') window.setChatsExpanded(false);
  }
}

let modelStatusTimer = null;

async function checkModelStatusAndPaintLogo() {
  const logo = document.querySelector('.logo');
  if (!logo) return;
  try {
    const res = await fetch('/health');
    if (!res.ok) throw new Error('health endpoint unavailable');
    const data = await res.json();
    const loaded = Boolean(data && data.llm_loaded);
    logo.classList.toggle('model-loading', !loaded);
  } catch (_) {
    logo.classList.add('model-loading');
  }
}

function startModelStatusMonitor() {
  if (modelStatusTimer) {
    clearInterval(modelStatusTimer);
    modelStatusTimer = null;
  }
  checkModelStatusAndPaintLogo();
  modelStatusTimer = setInterval(checkModelStatusAndPaintLogo, 5000);
}

// Экспорт
window.showPage = showPage;
window.navTo = navTo;
window.attachAnalyzeButton = attachAnalyzeButton;
window.initApp = initApp;
window.toggleSidebarCollapse = toggleSidebarCollapse;
window.toggleMobileSidebar = toggleMobileSidebar;
window.startModelStatusMonitor = startModelStatusMonitor;
window.syncChatDockPosition = syncChatDockPosition;
window.syncChatSubmenuState = syncChatSubmenuState;

console.log('✅ ui.js загружен');
