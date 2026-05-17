/**
 * MB Farm — Main App Bootstrap
 * Handles auth checks, redirects, and page initialization.
 */

document.addEventListener('DOMContentLoaded', async () => {
  const page = document.body.dataset.page;

  // Hide loading overlay
  document.getElementById('loading-overlay')?.classList.add('hidden');

  // Pages that require auth
  const authPages = ['farm', 'friend-farm', 'shop', 'profile'];

  if (authPages.includes(page)) {
    try {
      const user = await apiGetMe();
      if (!user) throw new Error('未登录');
      // Auth successful, continue
    } catch {
      // Redirect to login
      window.location.href = '/login';
      return;
    }
  }

  // Initialize page-specific logic
  switch (page) {
    case 'farm':
      initFarm();
      break;
    case 'friend-farm':
      initSocial();
      break;
    case 'login':
      initLogin();
      break;
    case 'register':
      initRegister();
      break;
  }
});

// ── Auth Pages ─────────────────────────────────────────────

function initLogin() {
  const form = document.getElementById('login-form');
  const errorEl = document.getElementById('login-error');

  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorEl.classList.remove('show');

    const username = form.username.value.trim();
    const password = form.password.value;

    if (!username || !password) {
      errorEl.textContent = '请输入用户名和密码';
      errorEl.classList.add('show');
      return;
    }

    try {
      const btn = form.querySelector('button[type="submit"]');
      btn.disabled = true;
      btn.textContent = '登录中...';

      await apiLogin(username, password);
      showToast('登录成功！', 'success');
      setTimeout(() => {
        window.location.href = '/farm';
      }, 300);
    } catch (e) {
      errorEl.textContent = e.message;
      errorEl.classList.add('show');
    } finally {
      btn.disabled = false;
      btn.textContent = '登录';
    }
  });
}

function initRegister() {
  const form = document.getElementById('register-form');
  const errorEl = document.getElementById('register-error');

  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorEl.classList.remove('show');

    const username = form.username.value.trim();
    const password = form.password.value;
    const confirm = form.confirm.value;

    if (!username || !password || !confirm) {
      errorEl.textContent = '请填写所有字段';
      errorEl.classList.add('show');
      return;
    }
    if (password !== confirm) {
      errorEl.textContent = '两次输入的密码不一致';
      errorEl.classList.add('show');
      return;
    }
    if (username.length < 2 || username.length > 32) {
      errorEl.textContent = '用户名长度需在 2-32 个字符之间';
      errorEl.classList.add('show');
      return;
    }
    if (password.length < 6 || password.length > 128) {
      errorEl.textContent = '密码长度需在 6-128 个字符之间';
      errorEl.classList.add('show');
      return;
    }

    try {
      const btn = form.querySelector('button[type="submit"]');
      btn.disabled = true;
      btn.textContent = '注册中...';

      await apiRegister(username, password);
      // Auto-login after registration
      await apiLogin(username, password);
      showToast('注册成功！自动登录中...', 'success');
      setTimeout(() => {
        window.location.href = '/farm';
      }, 500);
    } catch (e) {
      errorEl.textContent = e.message;
      errorEl.classList.add('show');
    } finally {
      btn.disabled = false;
      btn.textContent = '注册';
    }
  });
}

// ── Logout ─────────────────────────────────────────────────

async function doLogout() {
  try {
    await apiLogout();
    showToast('已退出登录', 'info');
    setTimeout(() => {
      window.location.href = '/login';
    }, 300);
  } catch (e) {
    showToast('登出失败', 'error');
  }
}
