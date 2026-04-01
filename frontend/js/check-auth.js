// Проверка авторизации на всех страницах
function checkAuth() {
  const token = localStorage.getItem('llm_auth_token');
  
  if (!token) {
    console.log('❌ No token, redirecting to login');
    window.location.href = '/login.html';
    return null;
  }
  
  console.log('✅ Token found:', token.substring(0, 30) + '...');
  return token;
}

// Загрузка данных пользователя
async function loadUserInfo() {
  const token = checkAuth();
  if (!token) return;

  try {
    const res = await fetch('/auth/me', {
      headers: { 
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });

    if (!res.ok) {
      console.error('❌ Failed to load user info:', res.status);
      if (res.status === 401) {
        localStorage.removeItem('llm_auth_token');
        window.location.href = '/login.html';
      }
      throw new Error('Failed to load user data');
    }

    const user = await res.json();
    console.log('✅ User loaded:', user);

    // Обновляем email во всех местах где есть элемент
    const emailEls = document.querySelectorAll('#top-email, .user-email-display');
    emailEls.forEach(el => {
      if (el) el.textContent = user.email;
    });

    // Обновляем ID если есть
    const idEl = document.getElementById('top-id');
    if (idEl && user.id) {
      idEl.textContent = 'ID: ' + user.id.substring(0, 8) + '...';
    }

    return user;

  } catch (err) {
    console.error('Load user error:', err);
    localStorage.removeItem('llm_auth_token');
    window.location.href = '/login.html';
  }
}

function logout() {
  console.log('🚪 Logging out...');
  localStorage.removeItem('llm_auth_token');
  window.location.href = '/login.html';
}