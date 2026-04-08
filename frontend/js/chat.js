// frontend/js/chat.js — Чат с LLM

// ==================== ОТПРАВКА СООБЩЕНИЯ ====================

async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  const messageText = input ? input.value.trim() : '';

  if (!messageText) return;

  addChatMessage('user', messageText);
  input.value = '';

  showLoading('Модель думает...');

  try {
    const token = localStorage.getItem('llm_auth_token');

    const res = await fetch('/api/chat', {   // используем относительный путь
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ message: messageText })
    });

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Ошибка ${res.status}: ${errorText}`);
    }

    const data = await res.json();
    addChatMessage('assistant', data.response || "Нет ответа от модели");

  } catch (err) {
    console.error('Chat error:', err);
    addChatMessage('assistant', '❌ Ошибка связи с моделью. Попробуйте позже.');
  } finally {
    hideLoading();
    scrollChatToBottom();
  }
}

// ==================== ДОБАВЛЕНИЕ СООБЩЕНИЯ ====================

function addChatMessage(role, text) {
  const container = document.getElementById('chat-messages');
  if (!container) return;

  const messageDiv = document.createElement('div');
  messageDiv.className = `chat-message ${role}`;
  messageDiv.innerHTML = `<div class="message-content">${text}</div>`;

  container.appendChild(messageDiv);
  scrollChatToBottom();
}

function scrollChatToBottom() {
  const container = document.getElementById('chat-messages');
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}

// ==================== ИНИЦИАЛИЗАЦИЯ ====================

function setupChat() {
  const input = document.getElementById('chat-input');
  if (!input) return;

  // Убираем старые обработчики и добавляем новый
  const newInput = input.cloneNode(true);
  input.parentNode.replaceChild(newInput, input);

  newInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });

  console.log('✅ Чат успешно инициализирован');
}

// Экспорт функций
window.sendChatMessage = sendChatMessage;
window.setupChat = setupChat;

console.log('✅ chat.js загружен');