/**
 * MB Farm — Toast Notification System
 */

const toastContainer = document.getElementById('toast-container');

let toastId = 0;

/**
 * Show a toast notification.
 * @param {string} message - Toast text
 * @param {string} type - 'success' | 'error' | 'info' | 'warning'
 * @param {number} duration - Auto-dismiss in ms (default 3000)
 */
function showToast(message, type = 'info', duration = 3000) {
  const id = ++toastId;
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  el.dataset.toastId = id;
  toastContainer.appendChild(el);

  setTimeout(() => {
    el.classList.add('fade-out');
    setTimeout(() => el.remove(), 300);
  }, duration);
}
