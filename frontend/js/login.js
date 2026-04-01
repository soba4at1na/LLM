document.addEventListener('DOMContentLoaded', () => {
  // Если уже есть токен — редирект на дашборд
  const token = localStorage.getItem('llm_auth_token');
  if (token) {
    window.location.href = '/dashboard.html';
  }

  const form = document.getElementById('login-form');
  const errorEl = document.getElementById('login-error');
  const btn = document.getElementById('login-btn');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    
    errorEl.style.display = 'none';
    btn.disabled = true;
    btn.textContent = 'Вход...';

    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const res = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Неверный логин или пароль');
      }

      // ✅ Сохраняем РЕАЛЬНЫЙ токен
      localStorage.setItem('llm_auth_token', data.access_token);
      console.log('✅ Token saved:', data.access_token.substring(0, 40) + '...');
      
      // ✅ Переход на дашборд
      window.location.href = '/dashboard.html';

    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.style.display = 'block';
      console.error('❌ Login error:', err);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Войти';
    }
  });
});