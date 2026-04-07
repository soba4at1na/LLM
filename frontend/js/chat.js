// frontend/js/chat.js — Модуль чата с LLM

const API_BASE = '';

// ==================== ОТПРАВКА СООБЩЕНИЯ ====================

async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  const message = input.value.trim();
  
  if (!message) return;

  // Добавляем сообщение пользователя
  addChatMessage('user', message);
  
  // Очищаем поле ввода
  input.value = '';

  // Показываем индикатор загрузки
  showLoading('LLM думает...');

  try {
    const token = localStorage.getItem('llm_auth_token');

    const res = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ message })
    });

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Ошибка ${res.status}: ${errorText.substring(0, 100)}`);
    }

    const data = await res.json();
    
    // Добавляем ответ модели
    addChatMessage('assistant', data.response || data.content || "Нет ответа от модели");

  } catch (err) {
    console.error('Chat error:', err);
    addChatMessage('assistant', 'Ошибка связи с моделью. Попробуйте позже.');
  } finally {
    hideLoading();
    // Прокручиваем чат вниз
    scrollChatToBottom();
  }
}

// ==================== ДОБАВЛЕНИЕ СООБЩЕНИЯ В ЧАТ ====================

function addChatMessage(role, text) {
  const chatContainer = document.getElementById('chat-messages');
  if (!chatContainer) return;

  const messageDiv = document.createElement('div');
  messageDiv.className = `chat-message ${role}`;
  
  // Можно добавить аватарки позже
  messageDiv.innerHTML = `
    <div class="message-content">
      ${text}
    </div>
  `;

  chatContainer.appendChild(messageDiv);
  scrollChatToBottom();
}

function scrollChatToBottom() {
  const chatContainer = document.getElementById('chat-messages');
  if (chatContainer) {
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }
}

// ==================== ОБРАБОТКА ВВОДА ====================

function setupChatInput() {
  const input = document.getElementById('chat-input');
  if (!input) return;

  // Отправка по Enter (без Shift)
  input.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });

  console.log('✅ Чат-инпут настроен');
}

// Экспорт функций
window.sendChatMessage = sendChatMessage;
window.setupChatInput = setupChatInput;

console.log('✅ chat.js загружен');