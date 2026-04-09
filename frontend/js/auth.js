// frontend/js/auth.js — Всё, что связано с авторизацией

const API_BASE = '';

// === Основные функции авторизации ===

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

  try {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData
    });

    const data = await res.json();

    if (!res.ok) throw new Error(data.detail || 'Неверный логин или пароль');

    localStorage.setItem('llm_auth_token', data.access_token);
    console.log('✅ Token saved');

    showPage('dashboard');   // Переход на дашборд

  } catch (err) {
    console.error('❌ Login error:', err);
    if (errorEl) {
      errorEl.textContent = err.message;
      errorEl.style.display = 'block';
    }
  } finally {
    btn.disabled = false;
    btn.textContent = 'Войти';
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

    successEl.textContent = '✅ Регистрация прошла успешно! Перенаправляем...';
    successEl.style.display = 'block';

    setTimeout(() => showPage('login'), 1500);

  } catch (err) {
    console.error('❌ Register error:', err);
    errorEl.textContent = err.message;
    errorEl.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Зарегистрироваться';
  }
}

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
      throw new Error('Не удалось загрузить данные пользователя');
    }

    const user = await res.json();
    console.log('✅ User loaded:', user);
    window.currentUser = user;
    applyRoleBasedMenu(user);
    if (user.is_admin) {
      const adminView = document.getElementById('view-admin-overview');
      if (adminView) {
        navTo('admin-overview');
      }
    }

    // Обновляем данные в топбаре
    const topEmail = document.getElementById('top-email');
    const topId = document.getElementById('top-id');
    if (topEmail) topEmail.textContent = user.email || user.username;
    if (topId && user.id) topId.textContent = 'ID: ' + user.id.substring(0, 8) + '...';

    // Обновляем данные в карточке на главной
    document.getElementById('user-username').textContent = user.username || '—';
    document.getElementById('user-email').textContent = user.email || '—';
    document.getElementById('user-id').textContent = user.id ? user.id.substring(0, 8) + '...' : '—';

    const roleEl = document.getElementById('user-role');
    if (roleEl) {
      roleEl.textContent = user.is_admin ? 'Администратор' : 'Пользователь';
      roleEl.className = `badge ${user.is_admin ? 'success' : ''}`;
    }

    const adminOverview = document.getElementById('admin-menu-overview');
    const adminDocuments = document.getElementById('admin-menu-documents');
    const adminUsers = document.getElementById('admin-menu-users');
    const adminAudit = document.getElementById('admin-menu-audit');
    if (adminOverview && !user.is_admin) adminOverview.classList.add('hidden');
    if (adminDocuments && !user.is_admin) adminDocuments.classList.add('hidden');
    if (adminUsers && !user.is_admin) adminUsers.classList.add('hidden');
    if (adminAudit && !user.is_admin) adminAudit.classList.add('hidden');

  } catch (err) {
    console.error('❌ Load user error:', err);
  }
}

function doLogout() {
  console.log('🚪 Logout');
  localStorage.removeItem('llm_auth_token');
  window.currentUser = null;
  showPage('login');
}

function applyRoleBasedMenu(user) {
  const userMenus = ['menu-training', 'menu-check', 'menu-chat'];
  const adminMenus = ['admin-menu-overview', 'admin-menu-documents', 'admin-menu-users', 'admin-menu-audit'];

  userMenus.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    if (user.is_admin) el.classList.add('hidden');
    else el.classList.remove('hidden');
  });

  adminMenus.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    if (user.is_admin) el.classList.remove('hidden');
    else el.classList.add('hidden');
  });
}

// Экспортируем функции (для использования в других модулях)
window.handleLogin = handleLogin;
window.handleRegister = handleRegister;
window.loadUserInfo = loadUserInfo;
window.doLogout = doLogout;
window.applyRoleBasedMenu = applyRoleBasedMenu;

console.log('✅ auth.js загружен');
