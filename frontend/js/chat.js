// frontend/js/chat.js — Мульти-чаты с историей в БД

let activeChatId = null;
let chatsExpanded = false;
let chatGlobalEventsBound = false;
const CHAT_INPUT_MAX_HEIGHT = 220;
let chatsCache = [];
let chatInitPromise = null;
let historyLoadToken = 0;
let isChatSending = false;
let pendingChatPollTimer = null;

const CHAT_ACTIVE_KEY = 'llm_active_chat_id';
const CHAT_PENDING_KEY = 'llm_pending_chat_v1';

function getContentScrollContainer() {
  return document.querySelector('.content');
}

function escapeHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function saveActiveChatId(chatId) {
  try {
    if (!chatId) {
      localStorage.removeItem(CHAT_ACTIVE_KEY);
      return;
    }
    localStorage.setItem(CHAT_ACTIVE_KEY, String(chatId));
  } catch (_) {}
}

function loadSavedActiveChatId() {
  try {
    const raw = localStorage.getItem(CHAT_ACTIVE_KEY);
    if (!raw) return null;
    const parsed = Number(raw);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  } catch (_) {
    return null;
  }
}

function savePendingChatState(payload) {
  try {
    localStorage.setItem(CHAT_PENDING_KEY, JSON.stringify(payload || {}));
  } catch (_) {}
}

function getPendingChatState() {
  try {
    const raw = localStorage.getItem(CHAT_PENDING_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || !parsed.chat_id || !parsed.sent_at) return null;
    return parsed;
  } catch (_) {
    return null;
  }
}

function clearPendingChatState() {
  try {
    localStorage.removeItem(CHAT_PENDING_KEY);
  } catch (_) {}
  if (pendingChatPollTimer) {
    clearTimeout(pendingChatPollTimer);
    pendingChatPollTimer = null;
  }
}

function setChatSendingState(isSending) {
  isChatSending = Boolean(isSending);
  const input = document.getElementById('chat-input');
  const sendBtn = document.querySelector('#chat-dock .chat-send-btn');
  if (input) input.disabled = isChatSending;
  if (sendBtn) sendBtn.disabled = isChatSending;
}

function scrollChatToBottom(smooth = true) {
  const scroller = getContentScrollContainer();
  if (!scroller) return;
  scroller.scrollTo({
    top: scroller.scrollHeight,
    behavior: smooth ? 'smooth' : 'auto'
  });
  updateScrollDownButton();
}

function updateScrollDownButton() {
  const scroller = getContentScrollContainer();
  const btn = document.getElementById('chat-scroll-down-btn');
  if (!scroller || !btn) return;
  const distance = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight;
  btn.classList.toggle('hidden', distance < 120);
}

function addChatMessage(role, text, { animate = true } = {}) {
  const container = document.getElementById('chat-messages');
  if (!container) return;

  const messageDiv = document.createElement('div');
  messageDiv.className = `chat-message ${role}${animate ? ' entering' : ''}`;
  messageDiv.innerHTML = `<div class="message-content">${escapeHtml(text).replace(/\n/g, '<br>')}</div>`;
  container.appendChild(messageDiv);
}

async function apiWithAuth(path, options = {}) {
  const token = localStorage.getItem('llm_auth_token');
  const headers = { ...(options.headers || {}), Authorization: `Bearer ${token}` };
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(path, {
    ...options,
    headers
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Ошибка ${res.status}: ${text}`);
  }
  return res.json();
}

function renderChatsList(chats) {
  const list = document.getElementById('chat-list');
  if (!list) return;
  if (!Array.isArray(chats) || chats.length === 0) {
    list.innerHTML = '<div class="chat-list-empty">Нет чатов</div>';
    return;
  }
  list.innerHTML = chats.map((chat) => `
    <div class="chat-list-item ${chat.id === activeChatId ? 'active' : ''}">
      <button class="chat-list-open" onclick="openChat(${chat.id})" title="${escapeHtml(chat.title)}">
        ${escapeHtml(chat.title)}
      </button>
      <button class="chat-dots-btn" onclick="toggleChatContextMenu(${chat.id}, event)">⋯</button>
      <div id="chat-menu-${chat.id}" class="chat-context-menu hidden">
        <button onclick="renameChat(${chat.id})">Переименовать</button>
        <button class="danger" onclick="deleteChat(${chat.id})">Удалить</button>
      </div>
    </div>
  `).join('');
}

function updateChatTopbarTitle() {
  const titleEl = document.getElementById('page-title');
  if (!titleEl) return;
  const active = chatsCache.find((c) => c.id === activeChatId);
  const chatTitle = active?.title ? active.title : 'Чат';
  titleEl.textContent = `💬 ${chatTitle}`;
}

async function loadChats({ selectLatest = false } = {}) {
  const chats = await apiWithAuth('/api/chats');
  chatsCache = Array.isArray(chats) ? chats : [];
  if (!activeChatId) {
    const saved = loadSavedActiveChatId();
    if (saved) activeChatId = saved;
  }
  if (activeChatId && !chats.some((c) => Number(c.id) === Number(activeChatId))) {
    activeChatId = null;
  }
  if (!activeChatId && chats.length) activeChatId = chats[0].id;
  if (selectLatest && chats.length) activeChatId = chats[0].id;
  saveActiveChatId(activeChatId);
  renderChatsList(chats);
  updateChatTopbarTitle();
  return chats;
}

async function loadChatHistory(chatId) {
  const container = document.getElementById('chat-messages');
  if (!container || !chatId) return;
  const token = ++historyLoadToken;
  container.innerHTML = '';
  const items = await apiWithAuth(`/api/chat/history?chat_id=${chatId}&limit=300`);
  if (token !== historyLoadToken) return;
  if (!items.length) {
    addChatMessage('assistant', 'Новый чат создан. Напишите сообщение.');
    scrollChatToBottom(false);
    return;
  }
  items.forEach((item) => {
    const isAssistant = item.role !== 'user';
    const suffix = isAssistant && item.context_used ? '\n\n(Использован контекст из ваших документов)' : '';
    addChatMessage(isAssistant ? 'assistant' : 'user', (item.content || '') + suffix, { animate: false });
  });
  scrollChatToBottom(false);
}

async function openChat(chatId) {
  activeChatId = chatId;
  saveActiveChatId(activeChatId);
  const chats = await loadChats();
  const exists = chats.some((x) => x.id === chatId);
  if (!exists && chats.length) activeChatId = chats[0].id;
  saveActiveChatId(activeChatId);
  await loadChatHistory(activeChatId);
  navTo('chat');
  updateChatTopbarTitle();
  maybeResumePendingChatResponse();
}

async function createNewChat() {
  const created = await apiWithAuth('/api/chats', {
    method: 'POST',
    body: JSON.stringify({ title: 'Новый чат' })
  });
  activeChatId = created.id;
  saveActiveChatId(activeChatId);
  await loadChats();
  await loadChatHistory(activeChatId);
  navTo('chat');
  updateChatTopbarTitle();
  maybeResumePendingChatResponse();
}

async function renameChat(chatId) {
  const title = prompt('Новое имя чата:');
  if (!title || !title.trim()) return;
  await apiWithAuth(`/api/chats/${chatId}`, {
    method: 'PATCH',
    body: JSON.stringify({ title: title.trim().slice(0, 120) })
  });
  await loadChats();
  updateChatTopbarTitle();
}

async function deleteChat(chatId) {
  if (!confirm('Удалить этот чат?')) return;
  await apiWithAuth(`/api/chats/${chatId}`, { method: 'DELETE' });
  if (activeChatId === chatId) activeChatId = null;
  saveActiveChatId(activeChatId);
  const chats = await loadChats({ selectLatest: true });
  if (chats.length) await loadChatHistory(chats[0].id);
  else {
    const container = document.getElementById('chat-messages');
    if (container) container.innerHTML = '';
  }
  updateChatTopbarTitle();
  maybeResumePendingChatResponse();
}

function toggleChatContextMenu(chatId, event) {
  event?.stopPropagation();
  document.querySelectorAll('.chat-context-menu').forEach((el) => el.classList.add('hidden'));
  const menu = document.getElementById(`chat-menu-${chatId}`);
  if (!menu) return;
  menu.classList.toggle('hidden');
}

function toggleChatMenu(event) {
  event?.preventDefault();
  const sidebar = document.getElementById('sidebar');
  const submenu = document.getElementById('chat-submenu');
  if (!submenu) return;
  if (sidebar && sidebar.classList.contains('collapsed')) {
    chatsExpanded = false;
    submenu.classList.add('hidden');
    navTo('chat');
    return;
  }
  chatsExpanded = !chatsExpanded;
  submenu.classList.toggle('hidden', !chatsExpanded);
  navTo('chat');
  updateChatTopbarTitle();
}

function setChatsExpanded(value) {
  chatsExpanded = Boolean(value);
}

function autoResizeChatInput(inputEl) {
  if (!inputEl) return;
  inputEl.style.height = 'auto';
  const nextHeight = Math.min(inputEl.scrollHeight, CHAT_INPUT_MAX_HEIGHT);
  inputEl.style.height = `${Math.max(50, nextHeight)}px`;
  inputEl.style.overflowY = inputEl.scrollHeight > CHAT_INPUT_MAX_HEIGHT ? 'auto' : 'hidden';
}

async function sendChatMessage() {
  if (isChatSending) return;
  const input = document.getElementById('chat-input');
  const messageText = input ? input.value.trim() : '';
  if (!messageText) return;

  if (!activeChatId) {
    const created = await apiWithAuth('/api/chats', {
      method: 'POST',
      body: JSON.stringify({ title: messageText.slice(0, 60) || 'Новый чат' })
    });
    activeChatId = created.id;
    saveActiveChatId(activeChatId);
    await loadChats();
    updateChatTopbarTitle();
  }

  addChatMessage('user', messageText);
  input.value = '';
  autoResizeChatInput(input);
  scrollChatToBottom();
  showLoading('Модель думает...');
  setChatSendingState(true);
  savePendingChatState({
    chat_id: activeChatId,
    sent_at: new Date().toISOString()
  });

  try {
    const data = await apiWithAuth('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message: messageText, chat_id: activeChatId })
    });

    if (data.chat_id && data.chat_id !== activeChatId) {
      activeChatId = data.chat_id;
      saveActiveChatId(activeChatId);
    }
    const suffix = data.context_used ? '\n\n(Использован контекст из ваших документов)' : '';
    addChatMessage('assistant', (data.response || 'Нет ответа от модели') + suffix);
    scrollChatToBottom();
    await loadChats();
    updateChatTopbarTitle();
    clearPendingChatState();
  } catch (err) {
    console.error('Chat error:', err);
    addChatMessage('assistant', 'Ошибка связи с моделью. Попробуйте позже.');
    scrollChatToBottom();
    maybeResumePendingChatResponse();
  } finally {
    setChatSendingState(false);
    hideLoading();
  }
}

async function initializeChats() {
  const chats = await loadChats();
  if (!chats.length) {
    const created = await apiWithAuth('/api/chats', {
      method: 'POST',
      body: JSON.stringify({ title: 'Новый чат' })
    });
    activeChatId = created.id;
    saveActiveChatId(activeChatId);
    await loadChats();
  }
  if (!activeChatId) {
    const refreshed = await loadChats({ selectLatest: true });
    if (refreshed.length) activeChatId = refreshed[0].id;
  }
  saveActiveChatId(activeChatId);
  if (activeChatId) await loadChatHistory(activeChatId);
  updateChatTopbarTitle();
}

function maybeResumePendingChatResponse() {
  if (pendingChatPollTimer) return;
  const pending = getPendingChatState();
  if (!pending) return;
  if (!activeChatId || Number(pending.chat_id) !== Number(activeChatId)) return;

  const sentAtMs = Date.parse(String(pending.sent_at || ''));
  if (!Number.isFinite(sentAtMs)) {
    clearPendingChatState();
    return;
  }

  const timeoutMs = 8 * 60 * 1000;
  const startedMs = Date.now();
  setChatSendingState(true);

  const tick = async () => {
    try {
      const items = await apiWithAuth(`/api/chat/history?chat_id=${activeChatId}&limit=80`);
      const hasAssistantAfterPending = (Array.isArray(items) ? items : []).some((item) => {
        if (String(item?.role) === 'user') return false;
        const createdMs = Date.parse(String(item?.created_at || ''));
        return Number.isFinite(createdMs) && createdMs >= sentAtMs - 1500;
      });

      if (hasAssistantAfterPending) {
        await loadChatHistory(activeChatId);
        clearPendingChatState();
        setChatSendingState(false);
        return;
      }

      if (Date.now() - startedMs >= timeoutMs) {
        clearPendingChatState();
        setChatSendingState(false);
        return;
      }
      pendingChatPollTimer = setTimeout(tick, 2500);
    } catch (_) {
      if (Date.now() - startedMs >= timeoutMs) {
        clearPendingChatState();
        setChatSendingState(false);
        return;
      }
      pendingChatPollTimer = setTimeout(tick, 3500);
    }
  };

  pendingChatPollTimer = setTimeout(tick, 1200);
}

async function ensureChatsInitialized() {
  if (!chatInitPromise) {
    chatInitPromise = initializeChats().finally(() => {
      chatInitPromise = null;
    });
  }
  return chatInitPromise;
}

function setupChat() {
  const input = document.getElementById('chat-input');
  if (!input) return;
  const newInput = input.cloneNode(true);
  input.parentNode.replaceChild(newInput, input);
  newInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });
  newInput.addEventListener('input', () => autoResizeChatInput(newInput));
  autoResizeChatInput(newInput);

  const scroller = getContentScrollContainer();
  if (scroller) {
    scroller.removeEventListener('scroll', updateScrollDownButton);
    scroller.addEventListener('scroll', updateScrollDownButton);
  }
  ensureChatsInitialized()
    .then(() => {
      updateScrollDownButton();
      maybeResumePendingChatResponse();
    })
    .catch((e) => console.warn(e));

  if (!chatGlobalEventsBound) {
    document.addEventListener('click', () => {
      document.querySelectorAll('.chat-context-menu').forEach((el) => el.classList.add('hidden'));
    });
    chatGlobalEventsBound = true;
  }
}

window.setupChat = setupChat;
window.sendChatMessage = sendChatMessage;
window.toggleChatMenu = toggleChatMenu;
window.setChatsExpanded = setChatsExpanded;
window.createNewChat = createNewChat;
window.openChat = openChat;
window.renameChat = renameChat;
window.deleteChat = deleteChat;
window.toggleChatContextMenu = toggleChatContextMenu;
window.scrollChatToBottom = scrollChatToBottom;
