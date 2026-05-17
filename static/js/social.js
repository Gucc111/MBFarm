/**
 * MB Farm — Social / Friend Farm Page Logic
 */

let friendsData = null;
let pendingData = null;
let selectedFriendId = null;
let stealData = null;
let refreshTimer = null;

// ── Init ───────────────────────────────────────────────────

async function initSocial() {
  await Promise.all([loadFriends(), loadPendingRequests()]);
  renderAll();
  startAutoRefresh();
}

function startAutoRefresh() {
  refreshTimer = setInterval(() => {
    if (selectedFriendId) loadFriendFarm(selectedFriendId);
  }, 30000);
}

// ── Data Loading ───────────────────────────────────────────

async function loadFriends() {
  friendsData = await apiGetFriends();
}

async function loadPendingRequests() {
  pendingData = await apiGetPendingRequests();
}

async function loadFriendFarm(friendId) {
  selectedFriendId = friendId;
  try {
    const data = await apiFarmInfoForFriend(friendId);
    renderFriendFarm(data);
    renderStealHistory();
  } catch (e) {
    showToast('加载好友农场失败: ' + e.message, 'error');
  }
}

async function apiFarmInfoForFriend(friendId) {
  // Try to get friend's farm info via steal/me endpoint for steal info
  return apiFarmInfo(); // We'll need a dedicated endpoint
}

// ── Rendering ──────────────────────────────────────────────

function renderAll() {
  renderFriendList();
  renderPendingRequests();
  renderUnlockSocial();
}

function renderFriendList() {
  const list = document.getElementById('friend-list');
  if (!list || !friendsData) return;
  list.innerHTML = '';

  if (friendsData.friends.length === 0) {
    list.innerHTML = '<li style="padding:16px;text-align:center;color:var(--color-text-light);font-size:14px;">暂无好友，去添加一些吧！</li>';
    return;
  }

  friendsData.friends.forEach(f => {
    const li = document.createElement('li');
    li.className = `friend-item ${selectedFriendId === f.id ? 'active' : ''}`;
    li.innerHTML = `
      <div>
        <div class="friend-name">${f.username}</div>
        <div class="friend-level">⭐ Lv.${f.level}</div>
      </div>
      <button class="btn btn-outline btn-sm visit-btn" onclick="visitFriend(${f.id})">
        🏃 前往
      </button>
    `;
    list.appendChild(li);
  });
}

function renderPendingRequests() {
  const container = document.getElementById('pending-container');
  if (!container) return;

  if (!pendingData || pendingData.requests.length === 0) {
    container.innerHTML = '';
    return;
  }

  let html = '<h3>📨 待处理好友请求</h3>';
  html += '<div class="requests-list">';

  pendingData.requests.forEach(req => {
    html += `
      <div class="request-item">
        <span class="req-user">${req.username}</span>
        <span style="font-size:12px;color:var(--color-text-light);">Lv.${req.from_user_id}</span>
        <div class="req-actions">
          <button class="btn btn-primary btn-sm" onclick="doRespondRequest(${req.friendship_id}, true)">✓</button>
          <button class="btn btn-danger btn-sm" onclick="doRespondRequest(${req.friendship_id}, false)">✗</button>
        </div>
      </div>
    `;
  });

  html += '</div>';
  container.innerHTML = html;
}

function renderUnlockSocial() {
  if (!friendsData) return;
  document.getElementById('friend-count').textContent = `${friendsData.total}/${friendsData.pending_count > 0 ? friendsData.pending_count + friendsData.total : friendsData.total} 好友`;
}

// ── Friend Actions ─────────────────────────────────────────

async function doAddFriend() {
  const input = document.getElementById('add-friend-input');
  const username = input.value.trim();
  if (!username) return;

  try {
    await apiAddFriend(username);
    showToast('好友请求已发送！', 'success');
    input.value = '';
    await Promise.all([loadFriends(), loadPendingRequests()]);
    renderAll();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function doRespondRequest(friendshipId, accept) {
  try {
    await apiRespondFriend(friendshipId, accept);
    showToast(accept ? '已接受好友请求' : '已拒绝好友请求', 'success');
    await Promise.all([loadFriends(), loadPendingRequests()]);
    renderAll();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function visitFriend(friendId) {
  // Navigate to friend farm view with steal functionality
  selectedFriendId = friendId;

  // Highlight selected friend
  document.querySelectorAll('.friend-item').forEach(el => el.classList.remove('active'));
  event?.target?.closest('.friend-item')?.classList.add('active');

  // Load friend's farm for stealing
  await loadFriendFarmView(friendId);
}

async function loadFriendFarmView(friendId) {
  // This needs a backend endpoint to view another user's farm
  // For now, we'll use the steal history info and farm info
  try {
    renderStealView(friendId);
  } catch (e) {
    showToast('加载好友农场失败', 'error');
  }
}

// ── Steal View ─────────────────────────────────────────────

function renderStealView(friendId) {
  const container = document.getElementById('steal-farm-container');
  if (!container) return;

  const friend = friendsData?.friends.find(f => f.id === friendId);
  if (!friend) return;

  container.innerHTML = `
    <h3>🌾 ${friend.username} 的农场</h3>
    <p style="font-size:13px;color:var(--color-text-light);margin-bottom:16px;">
      ⭐ Lv.${friend.level} · 今日可偷 ${getRemainingSteals()} 次
    </p>
    <div id="steal-plot-grid" class="steal-grid"></div>
  `;

  // Show steal buttons placeholder — full implementation needs friend farm data
  const grid = document.getElementById('steal-plot-grid');
  grid.innerHTML = '<p style="padding:40px;text-align:center;color:var(--color-text-light);">查看好友农场需要查看功能</p>';
}

function getRemainingSteals() {
  // Backend: GET /steal/my returns today's steal count
  return 3; // Simplified — would query API
}

async function doSteal(friendId) {
  try {
    await apiSteal(friendId);
    showToast('偷菜成功！', 'success');
    // Update cooldown UI
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ── Steal History ──────────────────────────────────────────

async function renderStealHistory() {
  try {
    stealData = await apiGetMySteals();
    const container = document.getElementById('steal-history-container');
    if (!container) return;

    if (!stealData.records.length) {
      container.innerHTML = '<p style="padding:20px;text-align:center;color:var(--color-text-light);">暂无偷菜记录</p>';
      return;
    }

    let html = '<h3>📋 偷菜记录</h3><ul class="steal-history-list">';
    stealData.records.slice(0, 10).forEach(record => {
      const cropConfig = CROP_CONFIG[record.stolen_crop_type] || { emoji: '🌱', name: record.stolen_crop_type };
      html += `
        <li class="steal-history-item">
          <span>${cropConfig.emoji} ${cropConfig.name} ×${record.quantity}</span>
          <span style="color:var(--color-text-light);">${record.stolen_at}</span>
        </li>
      `;
    });
    html += '</ul>';
    container.innerHTML = html;
  } catch (e) {
    console.error('Failed to load steal history', e);
  }
}
