/**
 * MB Farm — Crop Configuration (mirrors backend constants)
 */

const CROP_CONFIG = {
  wheat:      { emoji: '🌾', name: '小麦',      growTime: 30 * 60,   unlockLevel: 1, buyPrice: 10,  sellPrice: 18  },
  carrot:     { emoji: '🥕', name: '胡萝卜',    growTime: 2 * 3600,  unlockLevel: 2, buyPrice: 30,  sellPrice: 55  },
  tomato:     { emoji: '🍅', name: '番茄',      growTime: 6 * 3600,  unlockLevel: 3, buyPrice: 80,  sellPrice: 150 },
  strawberry: { emoji: '🍓', name: '草莓',      growTime: 12 * 3600, unlockLevel: 5, buyPrice: 200, sellPrice: 400 },
  sunflower:  { emoji: '🌻', name: '向日葵',    growTime: 24 * 3600, unlockLevel: 8, buyPrice: 500, sellPrice: 1000 },
};

const SEED_TYPES = Object.keys(CROP_CONFIG);

/**
 * Format seconds to human-readable time string.
 */
function formatTime(seconds) {
  seconds = Math.max(0, Math.round(seconds));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}时${m}分`;
  if (m > 0) return `${m}分${s > 0 ? s + '秒' : ''}`;
  return `${s}秒`;
}

/**
 * Format duration in a compact way.
 */
function formatDuration(seconds) {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分`;
  return `${Math.floor(seconds / 3600)}时`;
}

/**
 * Get growth stage display name.
 */
function stageName(stage) {
  const map = {
    seedling: '幼苗',
    growing: '生长中',
    almost_mature: '即将成熟',
    mature: '成熟',
  };
  return map[stage] || stage;
}

/**
 * Check if a crop type is unlocked by the given level.
 */
function isCropUnlocked(seedType, userLevel) {
  const config = CROP_CONFIG[seedType];
  return config && userLevel >= config.unlockLevel;
}

/**
 * Calculate remaining time for a crop.
 * Returns seconds remaining, or 0 if mature.
 */
function calcRemainingTime(plantTime, seedType) {
  const config = CROP_CONFIG[seedType];
  if (!config) return 0;
  const plantDate = new Date(plantTime);
  const matureDate = new Date(plantDate.getTime() + config.growTime * 1000);
  const now = Date.now();
  return Math.max(0, Math.floor((matureDate.getTime() - now) / 1000));
}
