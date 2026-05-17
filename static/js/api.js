/**
 * MB Farm — API Client Module
 * All API calls use fetch with credentials: 'same-origin' (cookie auth).
 */

const API_BASE = '/api';

// ── Generic fetch wrapper ──────────────────────────────────

async function apiFetch(path, opts = {}) {
  const url = `${API_BASE}${path}`;
  const defaults = {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
  };
  const config = {
    ...defaults,
    ...opts,
    headers: { ...defaults.headers, ...(opts.headers || {}) },
  };
  const res = await fetch(url, config);
  if (!res.ok) {
    let msg = `请求失败 (${res.status})`;
    try {
      const data = await res.json();
      msg = data.error?.message || msg;
    } catch {}
    throw new Error(msg);
  }
  return res.json();
}

// ── Auth ───────────────────────────────────────────────────

async function apiRegister(username, password) {
  return apiFetch('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

async function apiLogin(username, password) {
  return apiFetch('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

async function apiLogout() {
  return apiFetch('/auth/logout', { method: 'POST' });
}

async function apiGetMe() {
  return apiFetch('/auth/me');
}

// ── Farm ───────────────────────────────────────────────────

async function apiFarmInfo() {
  return apiFetch('/farm/info');
}

async function apiPlant(plotIndex, seedType) {
  return apiFetch('/farm/plant', {
    method: 'POST',
    body: JSON.stringify({ plot_index: plotIndex, seed_type: seedType }),
  });
}

async function apiWater(plotIndex) {
  return apiFetch('/farm/water', {
    method: 'POST',
    body: JSON.stringify({ plot_index: plotIndex }),
  });
}

async function apiHarvest(plotIndex) {
  return apiFetch('/farm/harvest', {
    method: 'POST',
    body: JSON.stringify({ plot_index: plotIndex }),
  });
}

async function apiUnlockPlot() {
  return apiFetch('/farm/unlock', { method: 'POST' });
}

async function apiGetInventory() {
  return apiFetch('/farm/inventory');
}

// ── Shop ───────────────────────────────────────────────────

async function apiGetShop() {
  return apiFetch('/shop/seeds');
}

async function apiBuySeed(seedType, quantity) {
  return apiFetch('/shop/buy', {
    method: 'POST',
    body: JSON.stringify({ seed_type: seedType, quantity }),
  });
}

// ── Social ─────────────────────────────────────────────────

async function apiGetFriends() {
  return apiFetch('/social/friends');
}

async function apiAddFriend(username) {
  return apiFetch('/social/friend/request', {
    method: 'POST',
    body: JSON.stringify({ friend_username: username }),
  });
}

async function apiRespondFriend(friendshipId, accept) {
  return apiFetch('/social/friend/respond', {
    method: 'POST',
    body: JSON.stringify({ friendship_id: friendshipId, accept }),
  });
}

async function apiGetPendingRequests() {
  return apiFetch('/social/requests/pending');
}

async function apiRemoveFriend(targetUserId) {
  return apiFetch('/social/friend/remove', {
    method: 'POST',
    body: JSON.stringify({ target_user_id: targetUserId }),
  });
}

// ── Steal ──────────────────────────────────────────────────

async function apiSteal(targetUserId) {
  return apiFetch(`/steal/${targetUserId}`, { method: 'POST' });
}

async function apiGetMySteals() {
  return apiFetch('/steal/my');
}

async function apiGetBeingStolen() {
  return apiFetch('/steal/me');
}

// ── Health ─────────────────────────────────────────────────

async function apiHealth() {
  return fetch('/health').then(r => r.json());
}
