/**
 * MB Farm — Farm Page Logic
 */

let currentFarmData = null;
let inventoryData = null;
let refreshTimer = null;
let staminaTimer = null;
let countdownTimer = null;
let lastStaminaValue = null;
let lastStaminaFetchTime = null;

// ── Init ───────────────────────────────────────────────────

async function initFarm() {
  await Promise.all([loadFarm(), loadInventory()]);
  renderAll();
  startAutoRefresh();
  startStaminaEstimate();
}

function stopAutoRefresh() {
  if (refreshTimer) clearInterval(refreshTimer);
  if (staminaTimer) clearInterval(staminaTimer);
  if (countdownTimer) clearInterval(countdownTimer);
}

function startAutoRefresh() {
  refreshTimer = setInterval(() => {
    loadFarm().then(() => {
      renderPlots();
      renderHeader();
    });
  }, 15000); // Every 15 seconds
}

function startStaminaEstimate() {
  lastStaminaFetchTime = Date.now();
  staminaTimer = setInterval(async () => {
    if (!currentFarmData) return;
    const serverStamina = currentFarmData.user.stamina;
    if (lastStaminaValue === serverStamina) {
      // Regenerate locally
      const elapsed = (Date.now() - lastStaminaFetchTime) / 1000;
      const gained = Math.floor(elapsed / 60);
      if (gained > 0) {
        currentFarmData.user.stamina = Math.min(100, serverStamina + gained);
        lastStaminaValue = currentFarmData.user.stamina;
        lastStaminaFetchTime = Date.now();
        renderHeader();
      }
    } else {
      lastStaminaValue = serverStamina;
      lastStaminaFetchTime = Date.now();
      renderHeader();
    }
  }, 5000);
}

// ── Data Loading ───────────────────────────────────────────

async function loadFarm() {
  currentFarmData = await apiFarmInfo();
}

async function loadInventory() {
  inventoryData = await apiGetInventory();
}

// ── Rendering ──────────────────────────────────────────────

function renderAll() {
  renderHeader();
  renderPlots();
  renderInventory();
  renderShop();
}

function renderHeader() {
  if (!currentFarmData) return;
  const user = currentFarmData.user;
  document.getElementById('header-username').textContent = user.username;
  document.getElementById('header-coins').textContent = `💰 ${user.coins}`;
  document.getElementById('header-level').textContent = `⭐ Lv.${user.level}`;
  document.getElementById('header-xp-bar').style.width = `${((user.xp || 0) / xpForNextLevel(user.level) * 100).toFixed(0)}%`;
  document.getElementById('header-stamina-bar').style.width = `${user.stamina}%`;
  document.getElementById('header-stamina-text').textContent = `${user.stamina}/100`;
}

function renderPlots() {
  if (!currentFarmData) return;
  const grid = document.getElementById('plot-grid');
  grid.innerHTML = '';

  currentFarmData.plots.forEach(plot => {
    grid.appendChild(createPlotCard(plot));
  });
}

function createPlotCard(plot) {
  const card = document.createElement('div');
  card.className = 'plot-card';
  card.dataset.plotIndex = plot.index;

  if (!plot.crop) {
    // Empty plot
    card.classList.add('empty');
    card.title = '点击播种';
    card.onclick = () => openPlantModal(plot.index);
    return card;
  }

  const crop = plot.crop;
  const config = CROP_CONFIG[crop.seed_type] || { emoji: '❓', name: crop.seed_name };
  const remaining = calcRemainingTime(crop.plant_time, crop.seed_type);

  card.classList.add(crop.is_mature ? 'mature' : 'growing');

  let html = `
    <div class="plot-emoji">${config.emoji}</div>
    <div class="plot-name">${config.name}</div>
  `;

  if (crop.is_mature) {
    html += `<div class="plot-actions">
      <button class="harvest-btn" onclick="doHarvest(${plot.index})">收获</button>
    </div>`;
  } else {
    html += `
      <div class="growth-bar-container">
        <div class="growth-bar-bg">
          <div class="growth-bar-fill ${crop.growth_stage}"></div>
        </div>
        <div class="growth-text">${stageName(crop.growth_stage)} · ${formatTime(remaining)}</div>
      </div>
      <div class="plot-actions">
        <button class="water-btn" onclick="doWater(${plot.index})" ${crop.watered_times >= 99 ? 'disabled' : ''}>
          💧 浇水${crop.watered_times > 0 ? ` (${crop.watered_times})` : ''}
        </button>
      </div>
    `;
  }

  card.innerHTML = html;
  return card;
}

// ── Plant Modal ────────────────────────────────────────────

function openPlantModal(plotIndex) {
  if (!inventoryData) return;
  const overlay = document.getElementById('plant-modal-overlay');
  const list = document.getElementById('plant-seed-list');
  list.innerHTML = '';

  // Show seeds that are in inventory or can be bought
  SEED_TYPES.forEach(seedType => {
    const config = CROP_CONFIG[seedType];
    const count = (inventoryData[seedType] || 0);
    const canBuy = count === 0;
    const unlocked = isCropUnlocked(seedType, currentFarmData ? currentFarmData.user.level : 1);

    if (!unlocked) return;

    const item = document.createElement('div');
    item.className = 'seed-item';

    if (!canBuy) {
      item.innerHTML = `
        <div class="seed-info">
          <span class="seed-emoji">${config.emoji}</span>
          <span class="seed-name">${config.name}</span>
        </div>
        <div style="display:flex;align-items:center;gap:10px;">
          <span class="seed-count">×${count}</span>
          <button class="btn btn-primary btn-sm" onclick="doPlant(${plotIndex}, '${seedType}')" ${count <= 0 ? 'disabled' : ''}>
            种植
          </button>
        </div>
      `;
      list.appendChild(item);
    }
  });

  // If no seeds, show shop link
  if (list.children.length === 0) {
    list.innerHTML = '<p style="text-align:center;color:var(--color-text-light);padding:20px;">暂无可用种子，去商店购买吧！</p>';
  }

  overlay.dataset.plotIndex = plotIndex;
  overlay.classList.add('open');
}

function closePlantModal() {
  document.getElementById('plant-modal-overlay').classList.remove('open');
}

// ── Actions ────────────────────────────────────────────────

async function doPlant(plotIndex, seedType) {
  try {
    closePlantModal();
    const btn = document.querySelector(`.plot-card[data-plot-index="${plotIndex}"]`)?.querySelector('button, .plot-card');
    if (btn) btn.style.pointerEvents = 'none';
    await apiPlant(plotIndex, seedType);
    showToast(`成功种植 ${CROP_CONFIG[seedType].name}！`, 'success');
    await Promise.all([loadFarm(), loadInventory()]);
    renderAll();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function doWater(plotIndex) {
  try {
    await apiWater(plotIndex);
    showToast('浇水成功！', 'success');
    await loadFarm();
    renderPlots();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function doHarvest(plotIndex) {
  try {
    await apiHarvest(plotIndex);
    showToast('收获成功！', 'success');
    await loadFarm();
    renderPlots();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function doUnlock() {
  try {
    await apiUnlockPlot();
    showToast('地块解锁成功！', 'success');
    await loadFarm();
    renderPlots();
    renderUnlockSection();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ── Inventory ──────────────────────────────────────────────

function renderInventory() {
  const container = document.getElementById('inventory-panel');
  container.innerHTML = '<h2>🌱 我的种子</h2><div class="seed-list" id="seed-list"></div>';

  if (!inventoryData) return;

  const list = document.getElementById('seed-list');
  const userLevel = currentFarmData ? currentFarmData.user.level : 1;

  SEED_TYPES.forEach(seedType => {
    const config = CROP_CONFIG[seedType];
    const count = inventoryData[seedType] || 0;
    const unlocked = isCropUnlocked(seedType, userLevel);

    const item = document.createElement('div');
    item.className = `seed-item ${!unlocked ? 'locked' : ''}`;

    if (unlocked) {
      item.innerHTML = `
        <div class="seed-info">
          <span class="seed-emoji">${config.emoji}</span>
          <div>
            <div class="seed-name">${config.name}</div>
            <div class="seed-meta">成熟 ${formatDuration(config.growTime)} · 售价 ¥${config.sellPrice}</div>
          </div>
        </div>
        <span class="seed-count">×${count}</span>
      `;
    } else {
      item.innerHTML = `
        <div class="seed-info">
          <span class="seed-emoji">🔒</span>
          <div>
            <div class="seed-name">${config.name}</div>
            <div class="seed-meta">等级 ${config.unlockLevel} 解锁</div>
          </div>
        </div>
      `;
    }
    list.appendChild(item);
  });
}

// ── Shop ───────────────────────────────────────────────────

let shopData = null;

async function loadShop() {
  shopData = await apiGetShop();
  renderShop();
}

function renderShop() {
  const container = document.getElementById('shop-panel');
  container.innerHTML = '<h2>🏪 种子商店</h2><div class="shop-grid" id="shop-grid"></div>';
  if (!shopData) return;

  const grid = document.getElementById('shop-grid');
  const userLevel = shopData.user_coins !== undefined ? currentFarmData?.user.level : 1;

  shopData.seeds.forEach(item => {
    const config = CROP_CONFIG[item.seed_type] || {};
    const unlocked = isCropUnlocked(item.seed_type, currentFarmData?.user.level || 1);

    const div = document.createElement('div');
    div.className = `shop-item ${!unlocked ? 'locked' : ''}`;

    if (unlocked) {
      div.innerHTML = `
        <div class="shop-emoji">${config.emoji || '🌱'}</div>
        <div class="shop-name">${item.name}</div>
        <div class="shop-price">¥${item.buy_price}</div>
        <div class="shop-meta">售价 ¥${item.sell_price} · 成熟 ${formatDuration(item.grow_time)}</div>
        <div class="shop-meta">经验 +${config.xp_reward || 0}</div>
        <button class="btn btn-primary btn-sm btn-full" onclick="doBuySeed('${item.seed_type}')" ${shopData.user_coins < item.buy_price ? 'disabled' : ''}>
          购买
        </button>
      `;
    } else {
      div.innerHTML = `
        <div class="shop-emoji">🔒</div>
        <div class="shop-name">${item.name}</div>
        <div class="shop-locked">需要等级 ${item.unlock_level}</div>
      `;
    }
    grid.appendChild(div);
  });
}

async function doBuySeed(seedType) {
  try {
    await apiBuySeed(seedType, 1);
    showToast(`购买 ${CROP_CONFIG[seedType].name} 种子成功！`, 'success');
    await Promise.all([loadFarm(), loadShop(), loadInventory()]);
    renderAll();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ── Unlock Section ─────────────────────────────────────────

function renderUnlockSection() {
  if (!currentFarmData) return;
  const section = document.getElementById('unlock-section');
  const plots = currentFarmData.plots;
  const totalPlots = plots.length;
  const maxPlots = currentFarmData.max_plots;

  if (totalPlots >= maxPlots) {
    section.innerHTML = `
      <div class="unlock-section">
        <p>🎉 已达到最大地块数！</p>
        <p class="plots-count">${totalPlots} / ${maxPlots}</p>
      </div>`;
    return;
  }

  section.innerHTML = `
    <div class="unlock-section">
      <p>🔓 解锁新地块</p>
      <p class="plots-count">${totalPlots} / ${maxPlots} 已解锁</p>
      <button class="btn btn-accent" onclick="doUnlock()" ${currentFarmData.user.coins < 200 ? 'disabled' : ''}>
        解锁 (¥200)
      </button>
    </div>`;
}

// ── Tab Switching ──────────────────────────────────────────

function switchTab(tabName) {
  // Update tab buttons
  document.querySelectorAll('.farm-tab').forEach(t => t.classList.remove('active'));
  document.querySelector(`.farm-tab[data-tab="${tabName}"]`)?.classList.add('active');

  // Show/hide panels
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));

  const panels = {
    farm: null,      // farm grid is always visible
    inventory: 'inventory-panel',
    shop: 'shop-panel',
  };

  if (panels[tabName]) {
    document.getElementById(panels[tabName])?.classList.add('active');
  }
}

// ── Cleanup on page exit ───────────────────────────────────

window.addEventListener('beforeunload', stopAutoRefresh);
