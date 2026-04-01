// Проверка авторизации при загрузке
document.addEventListener('DOMContentLoaded', async () => {
  const token = localStorage.getItem('llm_auth_token');
  
  if (!token) {
    window.location.href = '/login.html';
    return;
  }

  try {
    // Получаем данные пользователя
    const res = await fetch('/auth/me', {
      headers: { 
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });

    if (!res.ok) {
      if (res.status === 401) {
        // Токен истёк
        localStorage.removeItem('llm_auth_token');
        window.location.href = '/login.html';
      }
      throw new Error('Не удалось загрузить данные');
    }

    const user = await res.json();

    // Отображаем данные в topbar (справа сверху)
    document.getElementById('top-email').textContent = user.email;
    document.getElementById('top-id').textContent = 'ID: ' + user.id.substring(0, 8) + '...';

    // Отображаем данные в карточке
    document.getElementById('user-username').textContent = user.username;
    document.getElementById('user-email').textContent = user.email;
    document.getElementById('user-id').textContent = user.id;

  } catch (err) {
    console.error('Dashboard error:', err);
    localStorage.removeItem('llm_auth_token');
    window.location.href = '/login.html';
  }
});

function logout() {
  localStorage.removeItem('llm_auth_token');
  window.location.href = '/login.html';
}