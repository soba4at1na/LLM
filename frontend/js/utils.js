// frontend/js/utils.js

function showLoading(text = 'Загрузка...') {
  let overlay = document.getElementById('loading-overlay');
  if (overlay) return;

  overlay = document.createElement('div');
  overlay.id = 'loading-overlay';
  overlay.style.cssText = `
    position: fixed; inset: 0; background: rgba(0,0,0,0.85);
    display: flex; align-items: center; justify-content: center;
    color: white; z-index: 9999; font-size: 1.1rem;
  `;
  overlay.innerHTML = `
    <div style="text-align:center;">
      <div style="width:40px;height:40px;border:4px solid #ffffff30;border-top-color:#6366f1;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 15px;"></div>
      <div>${text}</div>
    </div>
  `;
  document.body.appendChild(overlay);
}

function hideLoading() {
  const overlay = document.getElementById('loading-overlay');
  if (overlay) overlay.remove();
}

function showError(message) {
  const el = document.getElementById('analysis-error');
  if (el) {
    el.textContent = message;
    el.classList.remove('hidden');
    setTimeout(() => el.classList.add('hidden'), 8000);
  } else {
    alert(message);
  }
}

function hideError() {
  const el = document.getElementById('analysis-error');
  if (el) el.classList.add('hidden');
}

// Анимация спиннера (если ещё нет в style.css)
const style = document.createElement('style');
style.textContent = `
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`;
document.head.appendChild(style);

console.log('✅ utils.js загружен');