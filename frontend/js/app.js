/**
 * LLM Document Quality Checker — Frontend Application
 * Чистый JavaScript, без зависимостей
 */

// 🎯 Конфигурация
const CONFIG = {
  API_BASE: '', // Пустая строка = относительные пути (nginx проксирует /auth → backend:8000)
  TOKEN_KEY: 'llm_auth_token',
  USER_KEY: 'llm_user_data'
};

// 📦 Состояние приложения
const state = {
  token: null,
  user: null,
  loading: false
};

// 🔧 DOM Elements (кэшируем)
const elements = {};

// 🚀 Инициализация
document.addEventListener('DOMContentLoaded', () => {
  cacheElements();
  bindEvents();
  initAuth();
});

// 📦 Кэширование элементов
function cacheElements() {
  // Forms
  elements.loginForm = document.getElementById('login-form');
  elements.registerForm = document.getElementById('register-form');
  elements.dashboard = document.getElementById('dashboard');
  
  // Login
  elements.login = document.getElementById('login');
  elements.loginUsername = document.getElementById('login-username');
  elements.loginPassword = document.getElementById('login-password');
  elements.loginBtn = document.getElementById('login-btn');
  elements.loginError = document.getElementById('login-error');
  
  // Register
  elements.register = document.getElementById('register');
  elements.regEmail = document.getElementById('reg-email');
  elements.regUsername = document.getElementById('reg-username');
  elements.regPassword = document.getElementById('reg-password');
  elements.regBtn = document.getElementById('register-btn');
  elements.regError = document.getElementById('register-error');
  elements.regSuccess = document.getElementById('register-success');
  
  // Dashboard
  elements.userUsername = document.getElementById('user-username');
  elements.userEmail = document.getElementById('user-email');
  elements.logoutBtn = document.getElementById('logout-btn');
}

// 🔗 Привязка событий
function bindEvents() {
  // Формы
  elements.login?.addEventListener('submit', handleLogin);
  elements.register?.addEventListener('submit', handleRegister);
  elements.logoutBtn?.addEventListener('click', handleLogout);
  
  // Переключение форм
  document.querySelectorAll('[data-show]').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const target = e.currentTarget.dataset.show;
      showView(target);
    });
  });
}

// 🔐 Инициализация авторизации
async function initAuth() {
  // Проверяем сохранённый токен
  const savedToken = localStorage.getItem(CONFIG.TOKEN_KEY);
  const savedUser = localStorage.getItem(CONFIG.USER_KEY);
  
  if (savedToken && savedUser) {
    state.token = savedToken;
    state.user = JSON.parse(savedUser);
    
    // Проверяем валидность токена
    try {
      await fetchMe();
      showDashboard(state.user);
      return;
    } catch (error) {
      console.warn('Token expired, clearing auth:', error);
      clearAuth();
    }
  }
  
  showView('login');
}

// 🔄 Переключение видов
function showView(view) {
  // Скрываем все
  [elements.loginForm, elements.registerForm, elements.dashboard].forEach(el => {
    if (el) el.classList.add('hidden');
  });
  
  // Показываем нужный + очищаем формы
  clearForms();
  
  switch (view) {
    case 'login':
      elements.loginForm?.classList.remove('hidden');
      elements.loginUsername?.focus();
      break;
    case 'register':
      elements.registerForm?.classList.remove('hidden');
      elements.regEmail?.focus();
      break;
    case 'dashboard':
      elements.dashboard?.classList.remove('hidden');
      break;
  }
}

// 🧹 Очистка форм
function clearForms() {
  // Сброс значений
  document.querySelectorAll('form').forEach(form => form.reset());
  
  // Скрытие сообщений
  document.querySelectorAll('.alert').forEach(alert => {
    alert.style.display = 'none';
    alert.textContent = '';
  });
  
  // Сброс кнопок
  document.querySelectorAll('button').forEach(btn => {
    btn.disabled = false;
    btn.classList.remove('loading');
  });
}

// 🔐 Обработчик входа
async function handleLogin(e) {
  e.preventDefault();
  if (state.loading) return;
  
  setLoading(true, elements.loginBtn);
  hideAlert(elements.loginError);
  
  const username = elements.loginUsername.value.trim();
  const password = elements.loginPassword.value;
  
  try {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    
    const response = await fetch(`${CONFIG.API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.detail || 'Ошибка входа');
    }
    
    // Сохраняем токен
    state.token = data.access_token;
    localStorage.setItem(CONFIG.TOKEN_KEY, state.token);
    
    // Получаем данные пользователя
    const user = await fetchMe();
    state.user = user;
    localStorage.setItem(CONFIG.USER_KEY, JSON.stringify(user));
    
    // Переход в дашборд
    showDashboard(user);
    
  } catch (error) {
    showError(elements.loginError, error.message);
  } finally {
    setLoading(false, elements.loginBtn);
  }
}

// 📝 Обработчик регистрации
async function handleRegister(e) {
  e.preventDefault();
  if (state.loading) return;
  
  setLoading(true, elements.regBtn);
  hideAlert(elements.regError);
  hideAlert(elements.regSuccess);
  
  const payload = {
    email: elements.regEmail.value.trim().toLowerCase(),
    username: elements.regUsername.value.trim(),
    password: elements.regPassword.value
  };
  
  // Простая валидация на клиенте
  if (payload.password.length < 8) {
    showError(elements.regError, 'Пароль должен содержать минимум 8 символов');
    setLoading(false, elements.regBtn);
    return;
  }
  
  try {
    const response = await fetch(`${CONFIG.API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.detail || 'Ошибка регистрации');
    }
    
    // Успех
    showSuccess(elements.regSuccess, '✅ Регистрация успешна! Теперь войдите.');
    
    // Авто-переход на вход через 1.5с
    setTimeout(() => {
      elements.loginUsername.value = payload.email;
      showView('login');
      elements.loginPassword.focus();
    }, 1500);
    
  } catch (error) {
    showError(elements.regError, error.message);
  } finally {
    setLoading(false, elements.regBtn);
  }
}

// 👤 Получение данных пользователя
async function fetchMe() {
  const response = await fetch(`${CONFIG.API_BASE}/auth/me`, {
    headers: {
      'Authorization': `Bearer ${state.token}`,
      'Content-Type': 'application/json'
    }
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Не удалось получить данные пользователя');
  }
  
  return await response.json();
}

// 🖥️ Показать дашборд
function showDashboard(user) {
  if (elements.userUsername) elements.userUsername.textContent = user.username;
  if (elements.userEmail) elements.userEmail.textContent = user.email;
  showView('dashboard');
}

// 🚪 Обработчик выхода
function handleLogout() {
  clearAuth();
  showView('login');
}

// 🧹 Очистка авторизации
function clearAuth() {
  state.token = null;
  state.user = null;
  localStorage.removeItem(CONFIG.TOKEN_KEY);
  localStorage.removeItem(CONFIG.USER_KEY);
}

// 🎛️ Управление состоянием загрузки
function setLoading(loading, button) {
  state.loading = loading;
  
  if (button) {
    button.disabled = loading;
    button.classList.toggle('loading', loading);
  }
  
  // Блокируем все кнопки при загрузке
  if (loading) {
    document.querySelectorAll('button[type="submit"]').forEach(btn => {
      if (btn !== button) btn.disabled = true;
    });
  } else {
    document.querySelectorAll('button[type="submit"]').forEach(btn => {
      btn.disabled = false;
    });
  }
}

// ❌ Показать ошибку
function showError(element, message) {
  if (!element) return;
  element.textContent = `❌ ${message}`;
  element.style.display = 'block';
  
  // Автоскрытие через 5с
  setTimeout(() => {
    if (element.textContent.includes(message)) {
      hideAlert(element);
    }
  }, 5000);
}

// ✅ Показать успех
function showSuccess(element, message) {
  if (!element) return;
  element.textContent = message;
  element.style.display = 'block';
}

// 🙈 Скрыть алерт
function hideAlert(element) {
  if (element) {
    element.style.display = 'none';
    element.textContent = '';
  }
}

// 🌐 Глобальный обработчик ошибок сети
window.addEventListener('online', () => {
  console.log('🌐 Сеть восстановлена');
});

window.addEventListener('offline', () => {
  console.warn('🔌 Нет соединения с интернетом');
  // Можно показать уведомление пользователю
});

// 🔧 Утилиты для отладки (только в dev)
if (import.meta?.env?.DEV || window.location.hostname === 'localhost') {
  window.app = { state, CONFIG, fetchMe, clearAuth };
  console.log('🔧 Dev tools available: window.app');
}