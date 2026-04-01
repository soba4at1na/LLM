document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('register-form');
  const errorEl = document.getElementById('register-error');
  const successEl = document.getElementById('register-success');
  const btn = document.getElementById('register-btn');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const payload = {
      email: document.getElementById('reg-email').value.trim().toLowerCase(),
      username: document.getElementById('reg-username').value.trim(),
      password: document.getElementById('reg-password').value
    };
    
    errorEl.style.display = 'none';
    successEl.style.display = 'none';
    btn.disabled = true;
    btn.textContent = 'Регистрация...';

    try {
      const res = await fetch('/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Ошибка регистрации');
      }

      // Успех
      successEl.textContent = '✅ Регистрация успешна! Перенаправление...';
      successEl.style.display = 'block';
      
      setTimeout(() => {
        window.location.href = '/login.html';
      }, 1500);

    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.style.display = 'block';
    } finally {
      btn.disabled = false;
      btn.textContent = 'Зарегистрироваться';
    }
  });
});