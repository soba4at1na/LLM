// LLM Checker - Frontend App

const CONFIG = {
  API_BASE: '',
  TOKEN_KEY: 'llm_auth_token',
  USER_KEY: 'llm_user_data'
};

const state = { token: null, user: null, loading: false };
const elements = {};

document.addEventListener('DOMContentLoaded', () => {
  cacheElements();
  bindEvents();
  initAuth();
});

function cacheElements() {
  elements.loginForm = document.getElementById('login-form');
  elements.registerForm = document.getElementById('register-form');
  elements.dashboard = document.getElementById('dashboard');
  elements.login = document.getElementById('login');
  elements.loginUsername = document.getElementById('login-username');
  elements.loginPassword = document.getElementById('login-password');
  elements.loginBtn = document.getElementById('login-btn');
  elements.loginError = document.getElementById('login-error');
  elements.register = document.getElementById('register');
  elements.regEmail = document.getElementById('reg-email');
  elements.regUsername = document.getElementById('reg-username');
  elements.regPassword = document.getElementById('reg-password');
  elements.regBtn = document.getElementById('register-btn');
  elements.regError = document.getElementById('register-error');
  elements.regSuccess = document.getElementById('register-success');
  elements.userUsername = document.getElementById('user-username');
  elements.userEmail = document.getElementById('user-email');
  elements.userId = document.getElementById('user-id');
  elements.logoutBtn = document.getElementById('logout-btn');
}

function bindEvents() {
  elements.login?.addEventListener('submit', handleLogin);
  elements.register?.addEventListener('submit', handleRegister);
  elements.logoutBtn?.addEventListener('click', handleLogout);
  document.querySelectorAll('[data-show]').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      showView(e.currentTarget.dataset.show);
    });
  });
}

async function initAuth() {
  const savedToken = localStorage.getItem(CONFIG.TOKEN_KEY);
  const savedUser = localStorage.getItem(CONFIG.USER_KEY);
  if (savedToken && savedUser) {
    state.token = savedToken;
    state.user = JSON.parse(savedUser);
    try {
      await fetchMe();
      showDashboard(state.user);
      return;
    } catch (error) {
      console.warn('Token expired');
      clearAuth();
    }
  }
  showView('login');
}

function showView(view) {
  [elements.loginForm, elements.registerForm, elements.dashboard].forEach(el => {
    if (el) el.classList.add('hidden');
  });
  clearForms();
  if (view === 'login') {
    elements.loginForm?.classList.remove('hidden');
    elements.loginUsername?.focus();
  } else if (view === 'register') {
    elements.registerForm?.classList.remove('hidden');
    elements.regEmail?.focus();
  } else if (view === 'dashboard') {
    elements.dashboard?.classList.remove('hidden');
  }
}

function clearForms() {
  document.querySelectorAll('form').forEach(f => f.reset());
  document.querySelectorAll('.alert').forEach(el => {
    el.style.display = 'none';
    el.textContent = '';
  });
  document.querySelectorAll('button').forEach(btn => {
    btn.disabled = false;
    btn.classList.remove('loading');
  });
}

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
    const response = await fetch(CONFIG.API_BASE + '/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Login failed');
    state.token = data.access_token;
    localStorage.setItem(CONFIG.TOKEN_KEY, state.token);
    const user = await fetchMe();
    state.user = user;
    localStorage.setItem(CONFIG.USER_KEY, JSON.stringify(user));
    showDashboard(user);
  } catch (error) {
    showError(elements.loginError, error.message);
  } finally {
    setLoading(false, elements.loginBtn);
  }
}

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
  if (payload.password.length < 8) {
    showError(elements.regError, 'Password must be at least 8 characters');
    setLoading(false, elements.regBtn);
    return;
  }
  try {
    const response = await fetch(CONFIG.API_BASE + '/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Registration failed');
    showSuccess(elements.regSuccess, 'Success! Please login.');
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

async function fetchMe() {
  const response = await fetch(CONFIG.API_BASE + '/auth/me', {
    headers: {
      'Authorization': 'Bearer ' + state.token,
      'Content-Type': 'application/json'
    }
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to fetch user');
  }
  return await response.json();
}

function showDashboard(user) {
  if (elements.userUsername) elements.userUsername.textContent = user.username || '—';
  if (elements.userEmail) elements.userEmail.textContent = user.email || '—';
  if (elements.userId) {
    if (user.id) {
      const shortId = user.id.length > 10 ? user.id.substring(0, 8) + '...' : user.id;
      elements.userId.textContent = shortId;
    } else {
      elements.userId.textContent = '—';
    }
  }
  showView('dashboard');
}

function handleLogout() {
  clearAuth();
  showView('login');
}

function clearAuth() {
  state.token = null;
  state.user = null;
  localStorage.removeItem(CONFIG.TOKEN_KEY);
  localStorage.removeItem(CONFIG.USER_KEY);
}

function setLoading(loading, button) {
  state.loading = loading;
  if (button) {
    button.disabled = loading;
    button.classList.toggle('loading', loading);
  }
  document.querySelectorAll('button[type="submit"]').forEach(btn => {
    if (btn !== button) btn.disabled = loading;
  });
}

function showError(element, message) {
  if (!element) return;
  element.textContent = 'Error: ' + message;
  element.style.display = 'block';
  setTimeout(() => { if (element.textContent.includes(message)) hideAlert(element); }, 5000);
}

function showSuccess(element, message) {
  if (!element) return;
  element.textContent = message;
  element.style.display = 'block';
}

function hideAlert(element) {
  if (element) {
    element.style.display = 'none';
    element.textContent = '';
  }
}

// Dev tools
if (location.hostname === 'localhost') {
  window.app = { state, CONFIG, fetchMe, clearAuth, showDashboard };
}