/**
 * Parts Extractor v8.4.6 - main.js
 * Single source of truth for all UI logic, filtering, scraping, exports.
 */

'use strict';

// ── $ helper ──────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

// ── DOM refs ──────────────────────────────────────────────────────────────────
const runBtn = $('runBtn');
const urlsTA = $('urls');
const urlCountBadge = $('urlCountBadge');
const statusDot = $('statusDot');
const statusText = $('statusText');
const advancedToggle = $('advancedToggle');
const advancedControls = $('advancedControls');
const filterArrow = $('filterArrow');
const filterCount = $('filterCount');
const resetAllBtn = $('resetAllBtn');

const percentInput = $('percent');
const absOffInput = $('absOff');
const addPercentInput = $('addPercent');
const priceMin = $('priceMin');
const priceMax = $('priceMax');
const dropPct = $('dropPct');
const kwInclude = $('kwInclude');
const kwExclude = $('kwExclude');
const includeHidden = $('include');
const excludeHidden = $('exclude');
const includeChipsCt = $('includeChips');
const excludeChipsCt = $('excludeChips');
const sortBy = $('sortBy');
const hideDupes = $('hideDupes');
const showInStockOnly = $('showInStockOnly');
const showOutOfStockOnly = $('showOutOfStockOnly');
const groupModel = $('groupModel');
const enrichDetails = $('enrichDetails');
const useBrowserApi = $('useBrowserApi');



const alertBox = $('alert');
const confirmModal = $('confirmModal');
const confirmModalDialog = $('confirmModalDialog');
const confirmModalTitle = $('confirmModalTitle');
const confirmModalMessage = $('confirmModalMessage');
const confirmConfirmBtn = $('confirmConfirmBtn');
const confirmCancelBtn = $('confirmCancelBtn');
const comparisonPanel = $('comparisonPanel');
const comparisonContent = $('comparisonContent');
const exportActions = $('exportActions');
const watchlistBar = $('watchlistBar');
const uploadZone = $('uploadZone');
const csvUpload = $('csvUpload');
const uploadText = $('uploadText');
const clearFileBtn = $('clearFileBtn');

const countBadge = $('countBadge');
const searchInput = $('search');
const csvBtn = $('csvBtn');
const xlsxBtn = $('xlsxBtn');
const copyBtn = $('copyBtn');
const exportWatchlistBtn = $('exportWatchlistBtn');
const viewWatchlistBtn = $('viewWatchlistBtn');
const clearResultsBtn = $('clearResultsBtn');

const showWatchlistOnly = $('showWatchlistOnly');
const heroWatchCount = $('heroWatchCount');
const clearWatchlistBtn = $('clearWatchlistBtn');

const resultsEmpty = $('resultsEmpty');
const resultsHeader = $('resultsHeader');
const resultsTableWrap = $('resultsTableWrap');
const resultsFooter = $('resultsFooter');
const prevPageBtn = $('prevPage');
const nextPageBtn = $('nextPage');
const pageInfo = $('pageInfo');
const pageSizeSelect = $('pageSize');
const tbody = document.querySelector('#resultsTable tbody');
const modelChipWrap = $('modelChipWrap');

const darkMode = $('darkMode');
const loadingOverlay = $('loading');
const loaderText = $('loaderText');
const loaderSub = $('loaderSub');
const loaderBar = $('loaderBar');
const loaderPct = $('loaderPct');
const loaderTimer = $('loaderTimer');
const imageHoverPreview = $('imageHoverPreview');
const imageHoverPreviewImg = $('imageHoverPreviewImg');

const currentDateValue = $('currentDateValue');
const currentTimeValue = $('currentTimeValue');

// ── State ─────────────────────────────────────────────────────────────────────
let rawItems = [];
let rows = [];
let lastExportRows = [];
let latestComparison = null;
let latestComparisonExportRows = [];
let currentPage = 1;
let pageSize = 25;
let currentModels = [];
let watch = new Set();
let watchlistItems = [];
let watchPendingUrls = new Set();
let watchlistLoaded = false;
let viewingWatchlist = false;
let compareMap = new Map();
let activePreviewSrc = '';
let confirmResolver = null;
let confirmReturnFocus = null;
let confirmTrapCleanup = null;
// keyword chip state
let incKeywords = [];
let excKeywords = [];

// ── Constants ─────────────────────────────────────────────────────────────────
const STORAGE_RESULTS = 'msx_results_v2';
const STORAGE_PAGESIZE = 'msx_page_size_v1';
const STORAGE_MODELS = 'msx_last_models_v1';

const MODEL_SKIP = new Set([
  'replacement-parts', 'parts', 'apple', 'samsung', 'huawei', 'xiaomi', 'oneplus', 'google',
  'lg', 'sony', 'nokia', 'motorola', 'oppo', 'vivo', 'ipad', 'iphone', 'watch', 'macbook', 'mac',
  'tablet', 'iphone-parts', 'ipad-parts', 'watch-parts', 'tablet-parts', 'phone-parts',
  'category', 'products', 'product', 'collections', 'accessories', 'accessory', 'shop', 'all', 'index'
]);

const LOAD_MSGS = [
  ['Connecting to store...', 'Establishing secure connection'],
  ['Analyzing page structure...', 'Understanding the website layout'],
  ['Extracting product data...', 'Finding products and prices'],
  ['Processing images...', 'Collecting product images'],
  ['Calculating discounts...', 'Computing price differences'],
  ['Organizing results...', 'Sorting and filtering data'],
  ['Almost there...', 'Finalizing extraction'],
];
const SCRAPE_REQUEST_TIMEOUT_MS = 5 * 60 * 1000;

// ── Inline notification bar ───────────────────────────────────────────────────
const _NOTIF_CLS = {
  success: 'alert-success', error: 'alert-danger', danger: 'alert-danger',
  warn: 'alert-warning', warning: 'alert-warning', info: 'alert-info'
};
const _NOTIF_ICONS = { success: 'OK', error: 'ERR', danger: 'ERR', warn: 'WARN', warning: 'WARN', info: 'INFO' };

function showToast(type, msg, duration = 6000) {
  if (!alertBox) return;
  alertBox.className = `alert-banner ${_NOTIF_CLS[type] || 'alert-info'}`;
  alertBox.innerHTML =
    `<span style="font-weight:800;margin-right:.45rem">${_NOTIF_ICONS[type] || 'ℹ'}</span>${escapeHtml(msg)}` +
    `<button onclick="this.parentElement.classList.add('d-none')" style="margin-left:auto;background:none;border:none;cursor:pointer;color:inherit;font-size:1rem;opacity:.7;padding:0 .2rem" title="Close">x</button>`;
  alertBox.style.display = 'flex';
  alertBox.style.alignItems = 'center';
  alertBox.style.gap = '.5rem';
  alertBox.classList.remove('d-none');
  clearTimeout(alertBox._clearTimer);
  alertBox._clearTimer = setTimeout(() => alertBox.classList.add('d-none'), duration);
}

function showAlert(type, msg) { showToast(type, msg); }
function clearAlert() { if (alertBox) { alertBox.classList.add('d-none'); } }
function hideComparison() {
  latestComparison = null;
  latestComparisonExportRows = [];
  if (comparisonPanel) comparisonPanel.classList.add('d-none');
  if (comparisonContent) comparisonContent.innerHTML = '';
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function resolveConfirmDialog(result) {
  if (!confirmModal) return;
  const resolver = confirmResolver;
  const returnFocus = confirmReturnFocus;
  if (typeof confirmTrapCleanup === 'function') confirmTrapCleanup();
  confirmTrapCleanup = null;
  confirmResolver = null;
  confirmReturnFocus = null;
  confirmModal.classList.add('d-none');
  confirmModal.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('modal-open');
  if (confirmConfirmBtn) {
    confirmConfirmBtn.classList.remove('btn-danger');
    confirmConfirmBtn.classList.add('btn-export');
    confirmConfirmBtn.disabled = false;
  }
  if (confirmCancelBtn) confirmCancelBtn.disabled = false;
  if (returnFocus?.isConnected && typeof returnFocus.focus === 'function' && !returnFocus.disabled) {
    returnFocus.focus();
  }
  if (typeof resolver === 'function') resolver(Boolean(result));
}

function getConfirmDialogFocusableElements() {
  if (!confirmModal) return [];
  return Array.from(confirmModal.querySelectorAll(
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
  ));
}

function isConfirmDialogOpen() {
  return Boolean(confirmResolver && confirmModal && !confirmModal.classList.contains('d-none'));
}

function focusConfirmDialogTarget(preferred = null) {
  const fallback = getConfirmDialogFocusableElements()[0] || confirmModalDialog || confirmModal;
  const target = preferred && typeof preferred.focus === 'function' ? preferred : fallback;
  if (target && typeof target.focus === 'function') target.focus();
}

function bindConfirmDialog() {
  if (!confirmModal || confirmModal.dataset.bound === '1') return;
  confirmModal.dataset.bound = '1';

  confirmModal.addEventListener('click', event => {
    if (event.target === confirmModal) resolveConfirmDialog(false);
  });

  if (confirmCancelBtn) {
    confirmCancelBtn.addEventListener('click', () => resolveConfirmDialog(false));
  }

  if (confirmConfirmBtn) {
    confirmConfirmBtn.addEventListener('click', () => resolveConfirmDialog(true));
  }

  document.addEventListener('keydown', event => {
    if (!isConfirmDialogOpen()) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      resolveConfirmDialog(false);
      return;
    }

    if (event.key === 'Tab') {
      const focusable = getConfirmDialogFocusableElements();
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !confirmModal.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || !confirmModal.contains(active))) {
        event.preventDefault();
        first.focus();
      }
    }
  });

  document.addEventListener('focusin', event => {
    if (!isConfirmDialogOpen() || !confirmModal) return;
    const nextTarget = event.target;
    if (nextTarget instanceof Node && confirmModal.contains(nextTarget)) return;
    focusConfirmDialogTarget(confirmCancelBtn);
  });
}

function showConfirmDialog({
  title = 'Please confirm',
  message = 'Are you sure you want to continue?',
  confirmLabel = 'Continue',
  cancelLabel = 'Cancel',
  danger = false,
} = {}) {
  if (!confirmModal || !confirmModalTitle || !confirmModalMessage || !confirmConfirmBtn || !confirmCancelBtn) {
    return Promise.resolve(window.confirm(message));
  }

  bindConfirmDialog();

  if (confirmResolver) resolveConfirmDialog(false);
  confirmReturnFocus = document.activeElement !== document.body ? document.activeElement : null;

  confirmModalTitle.textContent = title;
  confirmModalMessage.textContent = message;
  confirmConfirmBtn.textContent = confirmLabel;
  confirmCancelBtn.textContent = cancelLabel;
  confirmConfirmBtn.classList.toggle('btn-danger', danger);
  confirmConfirmBtn.classList.toggle('btn-export', !danger);
  confirmModal.classList.remove('d-none');
  confirmModal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('modal-open');
  confirmTrapCleanup = () => {
    if (document.activeElement instanceof HTMLElement && confirmModal?.contains(document.activeElement)) {
      document.activeElement.blur();
    }
  };

  return new Promise(resolve => {
    confirmResolver = resolve;
    requestAnimationFrame(() => {
      focusConfirmDialogTarget(danger ? confirmConfirmBtn : confirmCancelBtn);
    });
  });
}

const escapeHtml = str => String(str || '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

function normalizeSignedZero(value) {
  return Object.is(value, -0) ? 0 : value;
}

function detectCurrencySymbol(...values) {
  for (const value of values) {
    const text = String(value || '').trim();
    if (!text) continue;
    if (text.startsWith('CA$')) return 'CA$';
    const match = text.match(/^[^\d\s-+]+/);
    if (match) return match[0];
  }
  return '$';
}

function formatSignedPercent(value) {
  if (value == null || Number.isNaN(value)) return '';
  const normalized = normalizeSignedZero(value);
  const sign = normalized > 0 ? '+' : '';
  return `${sign}${normalized.toFixed(1)}%`;
}

function formatSignedMoney(value, currencySymbol = '$') {
  if (value == null || Number.isNaN(value)) return '';
  const normalized = normalizeSignedZero(value);
  const sign = normalized > 0 ? '+' : normalized < 0 ? '-' : '';
  return `${sign}${currencySymbol}${Math.abs(normalized).toFixed(2)}`;
}

function buildImageProxyUrl(imageUrl) {
  const raw = String(imageUrl || '').trim();
  if (!raw) return '';
  if (raw.startsWith('/api/image-proxy?')) return raw;
  const params = new URLSearchParams({ url: raw });
  return `/api/image-proxy?${params.toString()}`;
}

function collapseSpacedAcronyms(text) {
  return text.replace(/\b(?:[a-z]\s+){1,7}[a-z]\b/g, match => match.replace(/\s+/g, ''));
}

const norm = s => collapseSpacedAcronyms(
  (s || '')
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
).replace(/\b(for|with|without|frame|lcd|assembly|screen|display|series|model|global|original|grade|version|and|the|a|an)\b/g, '')
  .replace(/\s+/g, ' ').trim();

function parseKeywordTerms(...values) {
  const seen = new Set();
  const terms = [];
  values.forEach(value => {
    String(value || '')
      .split(/[,\n]/)
      .map(part => norm(part))
      .filter(Boolean)
      .forEach(term => {
        if (seen.has(term)) return;
        seen.add(term);
        terms.push(term);
      });
  });
  return terms;
}

function hasActiveNarrowingFilters() {
  return Boolean(
    (searchInput?.value || '').trim() ||
    parseKeywordTerms(includeHidden?.value, kwInclude?.value).length ||
    parseKeywordTerms(excludeHidden?.value, kwExclude?.value).length ||
    priceMin?.value !== '' ||
    priceMax?.value !== '' ||
    showInStockOnly?.checked ||
    showOutOfStockOnly?.checked ||
    hideDupes?.checked ||
    showWatchlistOnly?.checked
  );
}

function modelKey(title) {
  let t = norm(title);
  const m = t.match(/\b([a-z]{1,3}-?\d{1,4}[a-z]?)\b|\b(galaxy|iphone|ipad|a\d{2}|a0?\d{1,2}|xs?max|pro|max|mini|se|plus)\b/g);
  return m ? m.join(' ') : t;
}

function parseMoney(v) {
  if (!v) return null;
  const m = String(v).match(/([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})|[0-9]+(?:\.[0-9]{2})?)/);
  return m ? parseFloat(m[1].replace(/,/g, '')) : null;
}

function roundMoney(value) {
  if (!Number.isFinite(value)) return null;
  return Math.round((value + 1e-9) * 100) / 100;
}

function getRealtimePricingRules() {
  return {
    percentOff: Math.max(0, parseFloat(percentInput?.value || '0') || 0),
    absoluteOff: Math.max(0, parseFloat(absOffInput?.value || '0') || 0),
    addPercent: Math.max(0, parseFloat(addPercentInput?.value || '0') || 0),
  };
}

function applyRealtimePricing(basePrice, rules = getRealtimePricingRules()) {
  if (!Number.isFinite(basePrice)) return null;
  let price = Number(basePrice);
  if (rules.addPercent > 0) price *= (1 + rules.addPercent / 100);
  if (rules.percentOff > 0) price *= (1 - rules.percentOff / 100);
  if (rules.absoluteOff > 0) price -= rules.absoluteOff;
  return roundMoney(price);
}

function formatMoneyValue(value, currencySymbol = '$') {
  if (!Number.isFinite(value)) return '';
  return `${currencySymbol}${Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatSource(site) {
  if (!site) return { label: '', title: '' };
  let label = String(site).trim();
  try { label = new URL(/^https?:\/\//.test(label) ? label : 'https://' + label).hostname; } catch (_) { }
  label = label.replace(/^www\./i, '').split('/')[0].trim();
  return { label: label || site, title: site };
}

function getStockTone(stockText) {
  const text = String(stockText || '').trim().toLowerCase();
  if (!text) return '';
  if (text.includes('out of stock') || text.includes('out-of-stock') || text.includes('outofstock')) return 'out';
  if (text.includes('in stock') || /\b\d+\s+in stock\b/.test(text)) return 'in';
  if (text.includes('backorder') || text.includes('back order')) return 'backorder';
  if (text.includes('preorder') || text.includes('pre-order')) return 'preorder';
  return 'neutral';
}

function normaliseModelWord(w) {
  const l = w.toLowerCase();
  if (/^\d+$/.test(l) || /^[a-z]?\d+[a-z]?$/i.test(w)) return w.toUpperCase();
  if (['se', 'tv', 'lte', '5g', 'usb'].includes(l)) return l.toUpperCase();
  if (l === 'iphone') return 'iPhone';
  if (l === 'ipad') return 'iPad';
  return l.charAt(0).toUpperCase() + l.slice(1);
}

function deriveModelName(url) {
  try {
    const segs = new URL(url).pathname.split('/').filter(Boolean).map(s => decodeURIComponent(s));
    let cand = '';
    for (let i = segs.length - 1; i >= 0; i--) {
      if (!MODEL_SKIP.has(segs[i].toLowerCase())) { cand = segs[i]; break; }
    }
    if (!cand && segs.length) cand = segs[segs.length - 1];
    if (!cand) return '';
    const pretty = decodeURIComponent(cand)
      .replace(/[-_]+/g, ' ').replace(/\.(htm|html)$/i, '').trim();
    return pretty.split(' ').filter(Boolean).map(normaliseModelWord).join(' ')
      .replace(/\b5g\b/gi, '5G').replace(/\bUsb\b/g, 'USB').replace(/\bWi\s?fi\b/gi, 'Wi‑Fi');
  } catch { return ''; }
}

function hostToSource(url) {
  try {
    const host = new URL(url).hostname.toLowerCase().replace(/^www\./, '');
    if (host === 'mobilesentrix.ca' || host.endsWith('.mobilesentrix.ca')) return 'MS-CA';
    if (host === 'mobilesentrix.com' || host.endsWith('.mobilesentrix.com')) return 'MS-US';
    if (host === 'xcellparts.com' || host.endsWith('.xcellparts.com')) return 'XCellParts';
    if (host === 'txparts.com' || host.endsWith('.txparts.com')) return 'TXParts';
    if (host === 'parts4cells.com' || host.endsWith('.parts4cells.com')) return 'Parts4Cells';
    if (host === 'phonelcdparts.com' || host.endsWith('.phonelcdparts.com')) return 'PhoneLCDParts';
    if (host === 'gadgetfix.com' || host.endsWith('.gadgetfix.com')) return 'GadgetFix';
  } catch { }
  return 'Store';
}

function deriveModelNames(urlList) {
  const seen = new Set(), models = [];
  for (const url of (urlList || [])) {
    const name = deriveModelName(url.trim());
    if (!name) continue;
    const source = hostToSource(url);
    const key = `${name}__${source}`;
    if (seen.has(key)) continue;
    seen.add(key);
    models.push({ name, source });
  }
  return models;
}

// ── Watchlist / Price memory ──────────────────────────────────────────────────
async function fetchJson(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
  const res = await fetch(url, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Server ${res.status}`);
  return data;
}

function ensureItemShape(item) {
  const safe = (item && typeof item === 'object') ? { ...item } : {};
  safe.url = String(safe.url || '').trim();
  safe.site = String(safe.site || '').trim();
  safe.title = String(safe.title || '').trim();
  safe.price_text = String(safe.price_text || '').trim();
  safe.original_formatted = String(safe.original_formatted || '').trim();
  safe.discounted_formatted = String(safe.discounted_formatted || '').trim();
  safe.stock_status = String(safe.stock_status || '').trim();
  safe.description = String(safe.description || '').trim();
  safe.sku = String(safe.sku || '').trim();
  safe.source = String(safe.source || '').trim();
  safe.image_url = String(safe.image_url || '').trim();
  safe.extra = (safe.extra && typeof safe.extra === 'object' && !Array.isArray(safe.extra)) ? safe.extra : {};
  return safe;
}

function watchlistTimestampValue(item) {
  const raw = String(item?.updated_at || item?.created_at || '').trim();
  if (!raw) return 0;
  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? parsed : 0;
}

function sortWatchlistCache() {
  const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
  watchlistItems.sort((a, b) => {
    const tsDelta = watchlistTimestampValue(b) - watchlistTimestampValue(a);
    if (tsDelta !== 0) return tsDelta;
    return collator.compare(a.title || a.url || '', b.title || b.url || '');
  });
}

function setWatchlistCache(items) {
  watchlistItems = Array.isArray(items) ? items.map(ensureItemShape) : [];
  sortWatchlistCache();
  watch = new Set(
    watchlistItems
      .map(item => String(item.url || '').trim())
      .filter(Boolean)
  );
  watchlistLoaded = true;
  updateWatchUI();
}

function upsertWatchlistCacheItem(item) {
  const safe = ensureItemShape(item);
  if (!safe.url) return;
  const index = watchlistItems.findIndex(entry => entry.url === safe.url);
  if (index >= 0) watchlistItems.splice(index, 1, { ...watchlistItems[index], ...safe });
  else watchlistItems.unshift(safe);
  sortWatchlistCache();
  watch.add(safe.url);
  watchlistLoaded = true;
  updateWatchUI();
}

function removeWatchlistCacheItem(url) {
  const normalized = String(url || '').trim();
  if (!normalized) return;
  watchlistItems = watchlistItems.filter(item => item.url !== normalized);
  watch.delete(normalized);
  updateWatchUI();
}

function buildWatchlistPayload(item) {
  const safe = ensureItemShape(item);
  return {
    url: safe.url,
    site: safe.site,
    title: safe.title,
    price_value: safe.price_value,
    price_currency: safe.price_currency,
    price_text: safe.price_text,
    discounted_value: safe.discounted_value,
    discounted_formatted: safe.discounted_formatted,
    original_formatted: safe.original_formatted,
    sku: safe.sku,
    stock_status: safe.stock_status || safe.extra?.stock_status || '',
    description: safe.description || safe.extra?.description || '',
    extra: safe.extra || {},
    source: safe.source,
    image_url: safe.image_url,
  };
}

function formatSavedAt(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  const parsed = Date.parse(raw);
  if (!Number.isFinite(parsed)) return raw;
  return new Date(parsed).toLocaleString();
}

async function loadWatchlistFromServer({ silent = false, rerender = true } = {}) {
  try {
    const data = await fetchJson('/api/watchlist');
    setWatchlistCache(data.items || []);
    if (rerender) render();
    return watchlistItems;
  } catch (err) {
    watchlistLoaded = true;
    updateWatchUI();
    if (rerender) render();
    if (!silent) showToast('error', `Could not load watchlist: ${err.message}`);
    return [];
  }
}

function setDisplayedResults(items, { models = null, persist = false, viewing = false } = {}) {
  rawItems = Array.isArray(items) ? items.map(ensureItemShape) : [];
  rows = [];
  currentPage = 1;
  viewingWatchlist = viewing;
  currentModels = Array.isArray(models)
    ? models
    : deriveModelNames(rawItems.map(item => item.url).filter(Boolean));
  renderModelChips(currentModels);
  if (persist) saveResults(rawItems, currentModels);
}

async function toggleWatchlistForRow(row) {
  const url = String(row?.url || '').trim();
  if (!url || watchPendingUrls.has(url)) return;

  watchPendingUrls.add(url);
  render();
  try {
    if (watch.has(url)) {
      await fetchJson(`/api/watchlist?url=${encodeURIComponent(url)}`, { method: 'DELETE' });
      removeWatchlistCacheItem(url);
      showToast('info', 'Removed from watchlist.');
    } else {
      const payload = buildWatchlistPayload(row.raw_item || row);
      const data = await fetchJson('/api/watchlist', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      upsertWatchlistCacheItem(data.item || payload);
      showToast('success', 'Saved to watchlist.');
    }
  } catch (err) {
    showToast('error', `Watchlist update failed: ${err.message}`);
  } finally {
    watchPendingUrls.delete(url);
    render();
  }
}

async function clearWatchlistFromServer() {
  if (!watch.size) return;
  const confirmed = await showConfirmDialog({
    title: 'Clear Watchlist?',
    message: 'This will remove every saved watchlist item from the shared database. You can save them again later, but this action cannot be undone.',
    confirmLabel: 'Clear Watchlist',
    cancelLabel: 'Keep Saved Items',
    danger: true,
  });
  if (!confirmed) return;
  try {
    await fetchJson('/api/watchlist/clear', {
      method: 'POST',
      headers: { 'X-Confirm-Destructive': 'permanently-delete' },
      body: JSON.stringify({}),
    });
    setWatchlistCache([]);
    if (showWatchlistOnly) showWatchlistOnly.checked = false;
    updateFilterBadge();
    if (viewingWatchlist) {
      setDisplayedResults([], { models: [], viewing: false });
      hideComparison();
      clearAlert();
    }
    render();
    showToast('info', 'Watchlist cleared.');
  } catch (err) {
    showToast('error', `Could not clear watchlist: ${err.message}`);
  }
}

async function viewWatchlistResults() {
  if (!watchlistLoaded) await loadWatchlistFromServer({ silent: false, rerender: false });
  if (!watchlistItems.length) {
    render();
    showToast('info', 'Watchlist is empty.');
    return;
  }

  hideComparison();
  clearAlert();
  setDisplayedResults(watchlistItems, { viewing: true });
  render();
  showToast('info', `Loaded ${watchlistItems.length} saved item${watchlistItems.length === 1 ? '' : 's'}.`);
}

// ── Results persistence ───────────────────────────────────────────────────────
function saveResults(items, models = []) {
  try { localStorage.setItem(STORAGE_RESULTS, JSON.stringify({ items, models, ts: Date.now() })); } catch { }
}
function loadResults() {
  try {
    const d = JSON.parse(localStorage.getItem(STORAGE_RESULTS) || 'null');
    if (!d || Date.now() - d.ts > 86_400_000) { localStorage.removeItem(STORAGE_RESULTS); return null; }
    return d;
  } catch { return null; }
}
function clearResults() { try { localStorage.removeItem(STORAGE_RESULTS); } catch { } }

// ── Compare map lookup ────────────────────────────────────────────────────────
function lookupCmp(title, site, url) {
  const tl = (title || '').trim().toLowerCase();
  const nk = norm(title);
  const mk = modelKey(title);
  const sk = String(site || '').trim().toLowerCase();
  const uk = String(url || '').trim().toLowerCase();
  const g = k => k ? compareMap.get(k) : undefined;
  return g(`url:${uk}`) ?? g(`site:${sk}:${tl}`) ?? g(`title:${tl}`)
    ?? g(`site-model:${sk}:${mk}`) ?? g(`norm:${nk}`) ?? g(`model:${mk}`);
}

// ── Clock ─────────────────────────────────────────────────────────────────────
function startClock() {
  if (!currentDateValue && !currentTimeValue) return;
  const tz = 'Asia/Karachi';
  const df = new Intl.DateTimeFormat('en-PK', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric', timeZone: tz });
  const tf = new Intl.DateTimeFormat('en-PK', { hour: 'numeric', minute: '2-digit', hour12: true, timeZone: tz });
  const tick = () => {
    const now = new Date();
    if (currentDateValue) currentDateValue.textContent = df.format(now);
    if (currentTimeValue) currentTimeValue.textContent = tf.format(now);
    const ms = 60000 - (now.getSeconds() * 1000 + now.getMilliseconds());
    setTimeout(tick, Math.max(500, ms));
  };
  tick();
}

// ── Loading overlay ───────────────────────────────────────────────────────────
let _loadInterval = null, _loadStart = null, _loadMsgIdx = 0;

function setLoading(on, urls = '') {
  if (runBtn) runBtn.disabled = on;
  if (!loadingOverlay) return;

  if (on) {
    _loadStart = Date.now();
    _loadMsgIdx = 0;
    clearInterval(_loadInterval);

    // Show overlay
    loadingOverlay.classList.remove('d-none');

    const phase1 = $('loaderPhase1');
    const phase2 = $('loaderPhase2');
    const phase3 = $('loaderPhase3');
    if (phase1) phase1.className = 'badge bg-primary';
    if (phase2) phase2.className = 'badge bg-secondary';
    if (phase3) phase3.className = 'badge bg-secondary';

    _loadInterval = setInterval(() => {
      const elapsedSeconds = (Date.now() - _loadStart) / 1000;
      if (loaderTimer) loaderTimer.textContent = `${elapsedSeconds.toFixed(1)}s`;

      if (elapsedSeconds >= 45 && useBrowserApi?.checked) {
        if (loaderText) loaderText.textContent = 'Waiting for browser verification...';
        if (loaderSub) loaderSub.textContent = 'Headless Botasaurus is completing the page verification';
        const pct = Math.min(92, 70 + Math.floor(Math.min(elapsedSeconds - 45, 110) / 5));
        if (loaderBar) loaderBar.style.width = `${pct}%`;
        if (loaderPct) loaderPct.textContent = `${pct}%`;
        return;
      }

      // Cycle messages
      _loadMsgIdx = (_loadMsgIdx + 1) % LOAD_MSGS.length;
      const [txt, sub] = LOAD_MSGS[_loadMsgIdx];
      if (loaderText) loaderText.textContent = txt;
      if (loaderSub) loaderSub.textContent = sub;

      // Fake progress up to 92%
      const pct = Math.min(92, Math.floor((_loadMsgIdx / LOAD_MSGS.length) * 100) + Math.floor(Math.random() * 8));
      if (loaderBar) loaderBar.style.width = `${pct}%`;
      if (loaderPct) loaderPct.textContent = `${pct}%`;

      if (phase1 && phase2 && phase3) {
        if (pct < 45) {
          phase1.className = 'badge bg-primary';
          phase2.className = 'badge bg-secondary';
          phase3.className = 'badge bg-secondary';
        } else if (pct < 85) {
          phase1.className = 'badge bg-success';
          phase2.className = 'badge bg-primary';
          phase3.className = 'badge bg-secondary';
        } else {
          phase1.className = 'badge bg-success';
          phase2.className = 'badge bg-success';
          phase3.className = 'badge bg-primary';
        }
      }
    }, 1800);

  } else {
    clearInterval(_loadInterval);
    // Complete animation
    const phase1 = $('loaderPhase1');
    const phase2 = $('loaderPhase2');
    const phase3 = $('loaderPhase3');
    if (phase1) phase1.className = 'badge bg-success';
    if (phase2) phase2.className = 'badge bg-success';
    if (phase3) phase3.className = 'badge bg-success';

    if (loaderBar) loaderBar.style.width = '100%';
    if (loaderPct) loaderPct.textContent = '100%';
    if (loaderText) loaderText.textContent = 'Complete!';
    if (statusDot) statusDot.className = 'status-dot';
    if (statusText) statusText.textContent = rawItems.length ? `${rawItems.length} items` : 'Ready';

    setTimeout(() => {
      if (loadingOverlay) loadingOverlay.classList.add('d-none');
    }, 600);
  }
}

// ── URL counter ───────────────────────────────────────────────────────────────
function updateUrlCounter() {
  if (!urlsTA) return;
  const count = urlsTA.value.split('\n').map(s => s.trim()).filter(s => s.startsWith('http')).length;
  if (urlCountBadge) urlCountBadge.textContent = `${count} URL${count === 1 ? '' : 's'}`;
  if (statusText && (!loadingOverlay || loadingOverlay.classList.contains('d-none'))) {
    statusText.textContent = count ? `${count} URL${count === 1 ? '' : 's'} ready` : 'Ready';
  }
}


// ── Advanced filter toggle ────────────────────────────────────────────────────
let filtersOpen = false;

function syncFiltersDisclosure() {
  if (advancedControls) {
    advancedControls.hidden = !filtersOpen;
    advancedControls.setAttribute('aria-hidden', String(!filtersOpen));
  }
  if (advancedToggle) {
    advancedToggle.classList.toggle('open', filtersOpen);
    advancedToggle.setAttribute('aria-expanded', String(filtersOpen));
    advancedToggle.setAttribute('aria-controls', 'advancedControls');
  }
  if (filterArrow) filterArrow.textContent = filtersOpen ? 'v' : '>';
}

function toggleFilters() {
  filtersOpen = !filtersOpen;
  syncFiltersDisclosure();
}

function updateFilterBadge() {
  let n = 0;
  if ((searchInput?.value || '').trim()) n++;
  if (parseFloat(percentInput?.value || 0) > 0) n++;
  if (parseFloat(absOffInput?.value || 0) > 0) n++;
  if (parseFloat(addPercentInput?.value || 0) > 0) n++;
  if (parseFloat(priceMin?.value || 0) > 0) n++;
  if (parseFloat(priceMax?.value || 0) > 0) n++;
  if (parseKeywordTerms(includeHidden?.value, kwInclude?.value).length) n++;
  if (parseKeywordTerms(excludeHidden?.value, kwExclude?.value).length) n++;
  if (sortBy?.value && sortBy.value !== 'none') n++;
  if (showInStockOnly?.checked) n++;
  if (showOutOfStockOnly?.checked) n++;
  if (hideDupes?.checked) n++;
  if (groupModel?.checked) n++;
  if (showWatchlistOnly?.checked) n++;
  if (filterCount) filterCount.textContent = `${n} active`;
  if (filterCount) filterCount.style.opacity = n ? '1' : '0.5';
}

// ── Keyword chips ─────────────────────────────────────────────────────────────
function makeChip(text, arr, container, hidden) {
  const chip = document.createElement('span');
  chip.className = 'kw-chip';
  chip.innerHTML = `${escapeHtml(text)} <span style="cursor:pointer;margin-left:.2rem;">x</span>`;
  chip.querySelector('span').addEventListener('click', () => {
    const i = arr.indexOf(text);
    if (i > -1) arr.splice(i, 1);
    if (hidden) hidden.value = arr.join(',');
    chip.remove();
    updateFilterBadge();
    refilter();
  });
  container.appendChild(chip);
}

function addKeyword(input, arr, container, hidden) {
  const val = (input.value || '').trim();
  if (!val || arr.includes(val)) { input.value = ''; return; }
  arr.push(val);
  if (hidden) hidden.value = arr.join(',');
  makeChip(val, arr, container, hidden);
  input.value = '';
  updateFilterBadge();
  refilter();
}

// ── Reset all filters ─────────────────────────────────────────────────────────
function resetFilters() {
  if (searchInput) searchInput.value = '';
  if (percentInput) percentInput.value = '0';
  if (absOffInput) absOffInput.value = '0';
  if (addPercentInput) addPercentInput.value = '0';
  if (priceMin) priceMin.value = '';
  if (priceMax) priceMax.value = '';
  if (kwInclude) kwInclude.value = '';
  if (kwExclude) kwExclude.value = '';
  if (dropPct) dropPct.value = '10';
  if (sortBy) sortBy.value = 'none';
  if (hideDupes) hideDupes.checked = false;
  if (showInStockOnly) showInStockOnly.checked = false;
  if (showOutOfStockOnly) showOutOfStockOnly.checked = false;
  if (groupModel) groupModel.checked = false;
  if (enrichDetails) enrichDetails.checked = true;
  if (showWatchlistOnly) showWatchlistOnly.checked = false;
  incKeywords.length = 0; excKeywords.length = 0;
  if (includeHidden) includeHidden.value = '';
  if (excludeHidden) excludeHidden.value = '';
  if (includeChipsCt) includeChipsCt.innerHTML = '';
  if (excludeChipsCt) excludeChipsCt.innerHTML = '';
  updateFilterBadge();
  refilter();
  showToast('info', 'Filters reset.');
}

// ── Model chips renderer ──────────────────────────────────────────────────────
function renderModelChips(models) {
  if (!modelChipWrap) return;
  modelChipWrap.innerHTML = '';
  if (!models?.length) { modelChipWrap.hidden = true; return; }
  const MAX = 4;
  models.slice(0, MAX).forEach(m => {
    const el = document.createElement('span');
    el.className = 'context-chip';
    el.innerHTML = `<span>${escapeHtml(m.name)}</span><span class="context-chip__badge">${escapeHtml(m.source)}</span>`;
    modelChipWrap.appendChild(el);
  });
  if (models.length > MAX) {
    const el = document.createElement('span');
    el.className = 'context-chip context-chip--more';
    el.textContent = `+${models.length - MAX} more`;
    el.title = models.slice(MAX).map(m => `${m.name} (${m.source})`).join(', ');
    modelChipWrap.appendChild(el);
  }
  modelChipWrap.hidden = false;
  try { localStorage.setItem(STORAGE_MODELS, JSON.stringify(models.slice(0, 8))); } catch { }
}

// ── Render (filter + sort + paginate + display) ───────────────────────────────
function buildDisplayRow(item, pricingRules = getRealtimePricingRules()) {
  const safeItem = ensureItemShape(item);
  const origStr = safeItem.original_formatted || safeItem.price_text || '';
  const fallbackFinalStr = safeItem.discounted_formatted || origStr;
  const origNum = parseMoney(safeItem.price_value ?? safeItem.original ?? origStr);
  const fallbackFinalNum = parseMoney(safeItem.discounted_value ?? safeItem.discounted ?? fallbackFinalStr);
  const currencySymbol = detectCurrencySymbol(origStr, fallbackFinalStr);
  const liveFinalNum = applyRealtimePricing(origNum, pricingRules);
  const finNum = liveFinalNum ?? fallbackFinalNum;
  const finalStr = finNum != null ? formatMoneyValue(finNum, currencySymbol) : fallbackFinalStr;
  const pctDelta = (origNum > 0 && finNum != null) ? +((finNum - origNum) / origNum * 100).toFixed(2) : null;
  const amountDelta = (origNum != null && finNum != null) ? +(finNum - origNum).toFixed(2) : null;
  const watchKey = safeItem.url || '';

  return {
    raw_item: safeItem,
    url: safeItem.url,
    site: safeItem.site,
    image_url: safeItem.image_url,
    title: safeItem.title,
    model: modelKey(safeItem.title || ''),
    stock_status: safeItem.stock_status || safeItem.extra?.stock_status || '',
    stock_tone: getStockTone(safeItem.stock_status || safeItem.extra?.stock_status || ''),
    sku: safeItem.sku || safeItem.extra?.sku || '',
    description: safeItem.description || safeItem.extra?.description || '',
    original: origStr,
    final: finalStr,
    original_num: origNum,
    final_num: finNum,
    percent_delta: pctDelta,
    amount_delta: amountDelta,
    currency_symbol: currencySymbol,
    watchlisted: watch.has(watchKey),
    watchPending: watchPendingUrls.has(watchKey),
  };
}

function buildResultExportRows(displayRows) {
  const exportRows = displayRows.map(r => ({ title: r.title, price: r.original, url: r.url }));
  exportRows._hasAdjustedPrice = false;
  return exportRows;
}

function buildWatchlistExportRows() {
  const displayRows = watchlistItems.map(item => buildDisplayRow(item, getRealtimePricingRules()));
  const exportRows = displayRows.map(r => {
    return {
      title: r.title,
      price: r.original,
      stock_status: r.stock_status,
      site: formatSource(r.site).label,
      saved_at: formatSavedAt(r.raw_item.updated_at || r.raw_item.created_at),
      url: r.url,
    };
  });
  exportRows._headers = ['title', 'price', 'stock_status', 'site', 'saved_at', 'url'];
  exportRows._hasAdjustedPrice = false;
  return exportRows;
}

function render() {
  if (!tbody) return;
  tbody.innerHTML = '';

  // Build include/exclude from hidden inputs
  const inc = parseKeywordTerms(includeHidden?.value, kwInclude?.value);
  const exc = parseKeywordTerms(excludeHidden?.value, kwExclude?.value);
  const minP = priceMin?.value !== '' ? parseFloat(priceMin.value) : null;
  const maxP = priceMax?.value !== '' ? parseFloat(priceMax.value) : null;
  const searchQ = norm(searchInput?.value || '');
  const pricingRules = getRealtimePricingRules();
  const filterInStock = Boolean(showInStockOnly?.checked);
  const filterOutOfStock = Boolean(showOutOfStockOnly?.checked);

  // Map raw → display
  rows = rawItems.map(it => buildDisplayRow(it, pricingRules));

  // Search
  if (searchQ) {
    rows = rows.filter(r => norm(r.title + ' ' + r.url).includes(searchQ));
  }

  // Keyword filters
  if (inc.length || exc.length) {
    rows = rows.filter(r => {
      const t = norm(r.title + ' ' + r.url);
      if (inc.length && !inc.every(k => t.includes(k))) return false;
      if (exc.length && exc.some(k => t.includes(k))) return false;
      return true;
    });
  }

  // Price filter
  if (minP != null || maxP != null) {
    rows = rows.filter(r => {
      const p = r.final_num;
      if (minP != null && (p == null || p < minP)) return false;
      if (maxP != null && (p == null || p > maxP)) return false;
      return true;
    });
  }

  if (filterInStock || filterOutOfStock) {
    rows = rows.filter(r => {
      const tone = r.stock_tone || getStockTone(r.stock_status);
      return (filterInStock && tone === 'in') || (filterOutOfStock && tone === 'out');
    });
  }

  // Hide dupes
  if (hideDupes?.checked) {
    const seen = new Set();
    rows = rows.filter(r => {
      const k = r.model || r.title.toLowerCase();
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  }

  // Sort
  const coll = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
  const sv = sortBy?.value || 'none';
  if (sv !== 'none') {
    rows.sort((a, b) => {
      switch (sv) {
        case 'final_asc': return (a.final_num ?? Infinity) - (b.final_num ?? Infinity);
        case 'final_desc': return (b.final_num ?? -Infinity) - (a.final_num ?? -Infinity);
        case 'orig_asc': return (a.original_num ?? Infinity) - (b.original_num ?? Infinity);
        case 'orig_desc': return (b.original_num ?? -Infinity) - (a.original_num ?? -Infinity);
        case 'disc_desc': return Math.abs(b.percent_delta || 0) - Math.abs(a.percent_delta || 0);
        case 'title_asc': return coll.compare(a.title, b.title);
        case 'title_desc': return coll.compare(b.title, a.title);
        default: return 0;
      }
    });
  }

  // Group by model
  if (groupModel?.checked) {
    rows.sort((a, b) => {
      const x = coll.compare(a.model, b.model);
      return x !== 0 ? x : coll.compare(a.title, b.title);
    });
  }

  // Watchlist only
  if (showWatchlistOnly?.checked) {
    rows = rows.filter(r => r.watchlisted);
  }

  // Pagination
  const total = rows.length;
  const hasLoadedResults = rawItems.length > 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (currentPage > totalPages) currentPage = totalPages;
  const start = (currentPage - 1) * pageSize;
  const pageRows = rows.slice(start, start + pageSize);

  // Render rows
  const frag = document.createDocumentFragment();
  pageRows.forEach((r, idx) => {
    const tr = document.createElement('tr');
    const pctTxt = formatSignedPercent(r.percent_delta);
    const absOffTxt = formatSignedMoney(r.amount_delta, r.currency_symbol);
    const { label: srcLabel, title: srcTitle } = formatSource(r.site);
    const safe_url = escapeHtml(r.url);
    const safe_title = escapeHtml(r.title);
    const imageSrc = buildImageProxyUrl(r.image_url);
    const safeImageSrc = escapeHtml(imageSrc);
    const stockText = String(r.stock_status || '').trim();
    const stockTone = r.stock_tone || getStockTone(stockText);
    const stockMarkup = stockText
      ? `<div class="stock-meta stock-meta--${stockTone || 'neutral'}"><span class="stock-meta__label">Stock:</span><span class="stock-meta__value">${escapeHtml(stockText)}</span></div>`
      : '';
    const watchActionLabel = r.watchPending
      ? `Updating watchlist for ${r.title}`
      : `${r.watchlisted ? 'Remove' : 'Save'} ${r.title} ${r.watchlisted ? 'from' : 'to'} watchlist`;

    tr.innerHTML = `
      <td>${start + idx + 1}</td>
      <td><button type="button" class="star" data-url="${safe_url}" aria-label="${escapeHtml(watchActionLabel)}" aria-pressed="${r.watchlisted ? 'true' : 'false'}"${r.watchPending ? ' disabled' : ''}>${r.watchPending ? '...' : (r.watchlisted ? 'Saved' : 'Save')}</button></td>
      <td>${imageSrc ? `<img src="${safeImageSrc}" class="table-img" alt="${safe_title}" data-preview-src="${safeImageSrc}" loading="lazy" onerror="this.style.display='none'">` : ''}</td>
      <td class="col-title">
        <div class="item-title-cell">
          <div class="item-title-main">${safe_title}</div>
          ${stockMarkup}
        </div>
      </td>
      <td>${escapeHtml(r.original)}</td>
      <td>${pctTxt}</td>
      <td>${absOffTxt}</td>
      <td><strong>${escapeHtml(r.final)}</strong></td>
      <td><a class="url-link" href="${safe_url}" target="_blank" rel="noopener noreferrer" title="${safe_url}">Open</a></td>
      <td>${srcLabel ? `<span class="source-chip" title="${escapeHtml(srcTitle)}">${escapeHtml(srcLabel)}</span>` : ''}</td>
    `;

    // Watchlist toggle
    const star = tr.querySelector('.star');
    if (star) {
      star.addEventListener('click', () => {
        if (r.watchPending) return;
        toggleWatchlistForRow(r);
      });
    }

    frag.appendChild(tr);
  });
  tbody.appendChild(frag);

  // Update UI state
  const has = total > 0;
  const showingWatchlistOnly = Boolean(showWatchlistOnly?.checked);
  if (resultsHeader) resultsHeader.hidden = !has;
  if (resultsTableWrap) resultsTableWrap.hidden = !has;
  const resultsTable = resultsTableWrap?.querySelector('table');
  if (resultsTable) resultsTable.hidden = !has;
  if (resultsEmpty) resultsEmpty.classList.toggle('d-none', has);
  const emptyTitle = resultsEmpty?.querySelector('h3');
  const emptyText = resultsEmpty?.querySelector('p');
  if (emptyTitle && emptyText) {
    if (hasLoadedResults && showingWatchlistOnly) {
      emptyTitle.textContent = 'No saved items';
      emptyText.textContent = viewingWatchlist
        ? 'This watchlist view is empty after the current filters. Adjust filters or clear the watchlist-only toggle.'
        : 'Save some items in the current results, click View Watchlist, or turn off the watchlist-only filter.';
    } else if (hasLoadedResults) {
      emptyTitle.textContent = 'No matching results';
      emptyText.textContent = 'Try adjusting your filters or search terms.';
    } else if (watch.size) {
      emptyTitle.textContent = 'Saved items available';
      emptyText.innerHTML = 'Click <strong>View Watchlist</strong> to reopen your saved items, or fetch a new category URL.';
    } else {
      emptyTitle.textContent = 'No results yet';
      emptyText.innerHTML = 'Paste a category URL above and click <strong>Fetch Data</strong>';
    }
  }
  if (resultsFooter) resultsFooter.classList.toggle('d-none', !has);
  if (prevPageBtn) prevPageBtn.disabled = currentPage <= 1;
  if (nextPageBtn) nextPageBtn.disabled = currentPage >= totalPages;
  if (pageInfo) pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
  if (countBadge) countBadge.textContent = `${total.toLocaleString()} item${total === 1 ? '' : 's'}`;
  if (exportActions) exportActions.style.display = has ? 'flex' : 'none';
  if (watchlistBar) watchlistBar.style.display = (hasLoadedResults || watch.size > 0) ? 'flex' : 'none';
  if (csvBtn) csvBtn.disabled = !has;
  if (xlsxBtn) xlsxBtn.disabled = !has;
  if (copyBtn) copyBtn.disabled = !has;

  // Watch count
  updateWatchUI();

  // Export cache — only Title, Price, (Adjusted Price if any row changed), URL
  lastExportRows = buildResultExportRows(rows);
}

function refilter() { currentPage = 1; render(); }

// ── Watch UI update ───────────────────────────────────────────────────────────
function updateWatchUI() {
  const wSz = watch.size;
  if (heroWatchCount) heroWatchCount.textContent = wSz;
  if (exportWatchlistBtn) exportWatchlistBtn.disabled = wSz === 0;
  if (viewWatchlistBtn) viewWatchlistBtn.disabled = wSz === 0;
  if (clearWatchlistBtn) clearWatchlistBtn.disabled = wSz === 0;
}

function formatComparisonTimestamp(timestamp) {
  if (!timestamp) return 'previous run';
  try {
    return new Date(Number(timestamp)).toLocaleString();
  } catch {
    return 'previous run';
  }
}

function compactComparisonText(value, maxLength = 280) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return `${text.slice(0, Math.max(0, maxLength - 3))}...`;
}

function formatComparisonPrice(snapshot) {
  if (!snapshot) return '';
  if (snapshot.price_formatted) return snapshot.price_formatted;
  if (typeof snapshot.effective_price === 'number' && Number.isFinite(snapshot.effective_price)) {
    return String(snapshot.effective_price);
  }
  return '';
}

function buildComparisonExportRows(comparison) {
  if (!comparison || !comparison.has_previous_run) return [];

  const base = {
    previous_session_id: comparison.previous_history_id || '',
    previous_timestamp: comparison.previous_timestamp || '',
  };
  const rowsOut = [];

  for (const entry of comparison.changed || []) {
    const before = entry.before || {};
    const after = entry.after || {};
    const fields = Object.keys(entry.changes || {});
    const beforePrice = typeof before.effective_price === 'number' ? before.effective_price : null;
    const afterPrice = typeof after.effective_price === 'number' ? after.effective_price : null;
    const priceChangePct = (beforePrice && afterPrice)
      ? (((afterPrice - beforePrice) / beforePrice) * 100).toFixed(2)
      : '';

    rowsOut.push({
      ...base,
      change_type: 'changed',
      changed_fields: fields.join(', '),
      title: after.title || before.title || '',
      site: after.site || before.site || '',
      previous_title: before.title || '',
      current_title: after.title || '',
      previous_sku: before.sku || '',
      current_sku: after.sku || '',
      previous_stock: before.stock_status || '',
      current_stock: after.stock_status || '',
      previous_price: formatComparisonPrice(before),
      current_price: formatComparisonPrice(after),
      price_change_pct: priceChangePct,
      previous_url: before.url || '',
      current_url: after.url || '',
      previous_description: compactComparisonText(before.description),
      current_description: compactComparisonText(after.description),
    });
  }

  for (const item of comparison.removed || []) {
    rowsOut.push({
      ...base,
      change_type: 'removed',
      changed_fields: 'removed',
      title: item.title || '',
      site: item.site || '',
      previous_title: item.title || '',
      current_title: '',
      previous_sku: item.sku || '',
      current_sku: '',
      previous_stock: item.stock_status || '',
      current_stock: '',
      previous_price: formatComparisonPrice(item),
      current_price: '',
      price_change_pct: '',
      previous_url: item.url || '',
      current_url: '',
      previous_description: compactComparisonText(item.description),
      current_description: '',
    });
  }

  for (const item of comparison.added || []) {
    rowsOut.push({
      ...base,
      change_type: 'new',
      changed_fields: 'new',
      title: item.title || '',
      site: item.site || '',
      previous_title: '',
      current_title: item.title || '',
      previous_sku: '',
      current_sku: item.sku || '',
      previous_stock: '',
      current_stock: item.stock_status || '',
      previous_price: '',
      current_price: formatComparisonPrice(item),
      price_change_pct: '',
      previous_url: '',
      current_url: item.url || '',
      previous_description: '',
      current_description: compactComparisonText(item.description),
    });
  }

  return rowsOut;
}

function toGenericCSV(rowsArr) {
  if (!rowsArr.length) return '';
  const header = Object.keys(rowsArr[0]);
  const lines = [header.join(',')];
  for (const row of rowsArr) {
    lines.push(header.map(key => `"${String(row[key] ?? '').replace(/"/g, '""')}"`).join(','));
  }
  return lines.join('\n');
}

async function exportComparisonXlsx() {
  if (!latestComparisonExportRows.length) return;

  const btn = $('comparisonXlsxBtn');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '...';
  }

  try {
    const res = await fetch('/api/export/xlsx', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rows: latestComparisonExportRows }),
    });
    if (!res.ok) throw new Error(`Server ${res.status}`);
    const blob = await res.blob();
    const ts = new Date().toISOString().slice(0, 10);
    downloadBlob(blob, `comparison_${ts}.xlsx`);
    showToast('success', `Exported ${latestComparisonExportRows.length} comparison rows as XLSX.`);
  } catch (err) {
    console.error('[comparison xlsx]', err);
    showToast('error', `Comparison XLSX export failed: ${err.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Comparison XLSX';
    }
  }
}

function wireComparisonExportActions() {
  const csvBtn = $('comparisonCsvBtn');
  if (csvBtn) {
    csvBtn.addEventListener('click', () => {
      if (!latestComparisonExportRows.length) return;
      const ts = new Date().toISOString().slice(0, 10);
      downloadBlob(
        new Blob([toGenericCSV(latestComparisonExportRows)], { type: 'text/csv;charset=utf-8;' }),
        `comparison_${ts}.csv`
      );
      showToast('success', `Exported ${latestComparisonExportRows.length} comparison rows as CSV.`);
    });
  }

  const xlsxBtn = $('comparisonXlsxBtn');
  if (xlsxBtn) {
    xlsxBtn.addEventListener('click', exportComparisonXlsx);
  }
}

function renderComparison(comparison) {
  if (!comparisonPanel || !comparisonContent) return;
  if (!comparison) {
    hideComparison();
    return;
  }

  latestComparison = comparison;
  latestComparisonExportRows = buildComparisonExportRows(comparison);
  const summary = comparison.summary || {};
  const hasPrevious = Boolean(comparison.has_previous_run);
  const totalChanges = (summary.added || 0) + (summary.removed || 0) + (summary.changed || 0);

  const renderSnapshotMeta = snapshot => {
    const parts = [];
    if (snapshot.site) parts.push(`Site: ${escapeHtml(snapshot.site)}`);
    if (snapshot.sku) parts.push(`SKU: ${escapeHtml(snapshot.sku)}`);
    if (snapshot.stock_status) parts.push(`Stock: ${escapeHtml(snapshot.stock_status)}`);
    if (snapshot.price_formatted) parts.push(`Price: ${escapeHtml(snapshot.price_formatted)}`);
    return parts.length ? `<div class="comparison-item__meta">${parts.join(' | ')}</div>` : '';
  };

  const renderChangeLine = (field, change) => {
    if (field === 'price') {
      const before = escapeHtml(change.before_formatted || String(change.before ?? ''));
      const after = escapeHtml(change.after_formatted || String(change.after ?? ''));
      return `<div class="comparison-item__change"><strong>Price</strong>: ${before} -> ${after}</div>`;
    }
    const label = field === 'stock_status' ? 'Stock' : field.charAt(0).toUpperCase() + field.slice(1);
    return `<div class="comparison-item__change"><strong>${escapeHtml(label)}</strong>: ${escapeHtml(change.before || '--')} -> ${escapeHtml(change.after || '--')}</div>`;
  };

  const renderChanged = (comparison.changed || []).map(entry => {
    const before = entry.before || {};
    const after = entry.after || {};
    const changeLines = Object.entries(entry.changes || {})
      .map(([field, change]) => renderChangeLine(field, change))
      .join('');
    return `
      <div class="comparison-item">
        <div class="comparison-item__title">${escapeHtml(after.title || before.title || after.url || before.url || 'Changed item')}</div>
        ${renderSnapshotMeta(after)}
        ${changeLines}
      </div>
    `;
  }).join('');

  const renderSimpleList = list => list.map(item => `
      <div class="comparison-item">
        <div class="comparison-item__title">${escapeHtml(item.title || item.url || 'Item')}</div>
        ${renderSnapshotMeta(item)}
      </div>
    `).join('');

  if (!hasPrevious) {
    comparisonContent.innerHTML = `
      <div>
        <div style="font-size:1.05rem;font-weight:800;">Run Comparison</div>
        <div class="comparison-item__meta" style="margin-top:.35rem;">No previous run found for this exact target URL set. This run is now your baseline.</div>
      </div>
    `;
    comparisonPanel.classList.remove('d-none');
    return;
  }

  comparisonContent.innerHTML = `
    <div style="display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;flex-wrap:wrap;">
      <div>
        <div style="font-size:1.05rem;font-weight:800;">Run Comparison</div>
        <div class="comparison-item__meta" style="margin-top:.35rem;">
          Compared against session ${escapeHtml(String(comparison.previous_history_id || ''))} from ${escapeHtml(formatComparisonTimestamp(comparison.previous_timestamp))}
        </div>
        ${latestComparisonExportRows.length ? `
          <div class="comparison-actions">
            <button id="comparisonCsvBtn" class="btn-export">Comparison CSV</button>
            <button id="comparisonXlsxBtn" class="btn-export">Comparison XLSX</button>
          </div>
        ` : ''}
      </div>
      <div class="comparison-item__meta">${totalChanges ? `${totalChanges} change${totalChanges === 1 ? '' : 's'} detected` : 'No differences detected'}</div>
    </div>
    <div class="comparison-summary">
      <div class="comparison-stat"><div class="comparison-stat__label">Previous Items</div><div class="comparison-stat__value">${summary.previous_items || 0}</div></div>
      <div class="comparison-stat"><div class="comparison-stat__label">Current Items</div><div class="comparison-stat__value">${summary.current_items || 0}</div></div>
      <div class="comparison-stat"><div class="comparison-stat__label">Added</div><div class="comparison-stat__value">${summary.added || 0}</div></div>
      <div class="comparison-stat"><div class="comparison-stat__label">Removed</div><div class="comparison-stat__value">${summary.removed || 0}</div></div>
      <div class="comparison-stat"><div class="comparison-stat__label">Changed</div><div class="comparison-stat__value">${summary.changed || 0}</div></div>
      <div class="comparison-stat"><div class="comparison-stat__label">Price Changes</div><div class="comparison-stat__value">${summary.price_changes || 0}</div></div>
      <div class="comparison-stat"><div class="comparison-stat__label">Stock Changes</div><div class="comparison-stat__value">${summary.stock_changes || 0}</div></div>
      <div class="comparison-stat"><div class="comparison-stat__label">Title Changes</div><div class="comparison-stat__value">${summary.title_changes || 0}</div></div>
      <div class="comparison-stat"><div class="comparison-stat__label">SKU Changes</div><div class="comparison-stat__value">${summary.sku_changes || 0}</div></div>
      <div class="comparison-stat"><div class="comparison-stat__label">Description Changes</div><div class="comparison-stat__value">${summary.description_changes || 0}</div></div>
    </div>
    <div class="comparison-groups">
      ${comparison.changed?.length ? `<div class="comparison-group"><div class="comparison-group__title">Changed Items (${comparison.changed.length})</div><div class="comparison-list">${renderChanged}</div></div>` : ''}
      ${comparison.removed?.length ? `<div class="comparison-group"><div class="comparison-group__title">Removed Items (${comparison.removed.length})</div><div class="comparison-list">${renderSimpleList(comparison.removed)}</div></div>` : ''}
      ${comparison.added?.length ? `<div class="comparison-group"><div class="comparison-group__title">New Items (${comparison.added.length})</div><div class="comparison-list">${renderSimpleList(comparison.added)}</div></div>` : ''}
    </div>
  `;
  comparisonPanel.classList.remove('d-none');
  wireComparisonExportActions();
}

// ── Export helpers ────────────────────────────────────────────────────────────
function toCSV(rowsArr) {
  const customHeaders = Array.isArray(rowsArr?._headers) ? rowsArr._headers : null;
  const header = customHeaders || ['title', 'price', 'url'];
  const lines = [header.join(',')];
  for (const r of rowsArr) {
    const cells = header.map(h => `"${String(r[h] ?? '').replace(/"/g, '""')}"`);
    lines.push(cells.join(','));
  }
  return lines.join('\n');
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function hideImageHoverPreview() {
  activePreviewSrc = '';
  if (!imageHoverPreview || !imageHoverPreviewImg) return;
  imageHoverPreview.classList.add('d-none');
  imageHoverPreview.setAttribute('aria-hidden', 'true');
  imageHoverPreviewImg.removeAttribute('src');
}

function positionImageHoverPreview(event) {
  if (!imageHoverPreview || imageHoverPreview.classList.contains('d-none')) return;
  const pad = 18;
  const rect = imageHoverPreview.getBoundingClientRect();
  let left = event.clientX + pad;
  let top = event.clientY + pad;

  if (left + rect.width > window.innerWidth - 12) left = event.clientX - rect.width - pad;
  if (top + rect.height > window.innerHeight - 12) top = event.clientY - rect.height - pad;

  imageHoverPreview.style.left = `${Math.max(12, left)}px`;
  imageHoverPreview.style.top = `${Math.max(12, top)}px`;
}

function showImageHoverPreview(imgEl, event) {
  if (!imageHoverPreview || !imageHoverPreviewImg || !imgEl) return;
  const src = imgEl.dataset.previewSrc || imgEl.currentSrc || imgEl.src || '';
  if (!src) {
    hideImageHoverPreview();
    return;
  }

  if (activePreviewSrc !== src) {
    imageHoverPreviewImg.src = src;
    imageHoverPreviewImg.alt = imgEl.alt || 'Product preview';
    activePreviewSrc = src;
  }

  imageHoverPreview.classList.remove('d-none');
  imageHoverPreview.setAttribute('aria-hidden', 'false');
  positionImageHoverPreview(event);
}

function handleTableImageHover(event) {
  const imgEl = event.target instanceof Element ? event.target.closest('.table-img') : null;
  if (!imgEl) {
    hideImageHoverPreview();
    return;
  }
  showImageHoverPreview(imgEl, event);
}

// ── Main fetch ────────────────────────────────────────────────────────────────
function formatFetchErrorMessage(err) {
  const rawMessage = String(err?.message || '').trim();
  const failedToFetch =
    err instanceof TypeError ||
    /^failed to fetch$/i.test(rawMessage) ||
    /networkerror/i.test(rawMessage);

  if (!failedToFetch) return rawMessage || 'Unknown error';

  const sameOriginHint = window.location.href.startsWith('http')
    ? `Make sure the Flask server is running at ${window.location.origin}.`
    : 'Open the app from the Flask server URL instead of opening the HTML file directly.';

  return `Cannot reach the scraper API. ${sameOriginHint}`;
}

function summarizeTargetErrors(targetErrors) {
  if (!Array.isArray(targetErrors) || !targetErrors.length) return '';
  const first = targetErrors.find(error => error?.error) || targetErrors[0];
  const detail = String(first?.error || first || '').replace(/\s+/g, ' ').trim();
  if (!detail) return '';
  return detail.length > 240 ? `${detail.slice(0, 237)}...` : detail;
}

function renderTableSkeleton() {
  if (!tbody) return;
  const resultsEmpty = $('resultsEmpty');
  if (resultsEmpty) resultsEmpty.classList.add('d-none');
  const resultsWrap = $('resultsTable') || document.querySelector('.results-table-wrap') || (tbody.closest('table') ? tbody.closest('table').parentElement : null);
  if (resultsWrap) resultsWrap.classList.remove('d-none');

  tbody.innerHTML = Array.from({ length: 8 }).map(() => `
    <tr class="skeleton-table-tr">
      <td style="width:50px;"><div class="skeleton-box" style="width:40px; height:40px; border-radius:6px;"></div></td>
      <td><div class="skeleton-box" style="width:85%; height:14px; margin-bottom:4px;"></div><div class="skeleton-box" style="width:45%; height:11px;"></div></td>
      <td style="width:120px;"><div class="skeleton-box" style="width:80px; height:18px; border-radius:999px;"></div></td>
      <td style="width:110px;"><div class="skeleton-box" style="width:70px; height:14px;"></div></td>
      <td style="width:90px;"><div class="skeleton-box" style="width:55px; height:16px;"></div></td>
      <td style="width:90px;"><div class="skeleton-box" style="width:55px; height:16px;"></div></td>
      <td style="width:100px;"><div class="skeleton-box" style="width:75px; height:18px; border-radius:999px;"></div></td>
      <td style="width:60px;"><div class="skeleton-box" style="width:30px; height:24px; border-radius:4px;"></div></td>
    </tr>
  `).join('');
}

async function doFetch() {
  clearAlert();
  const urls = (urlsTA?.value || '').trim();
  if (!urls) { showToast('warn', 'Paste at least one URL first.'); return; }

  const urlList = urls.split('\n').map(s => s.trim()).filter(Boolean);
  const payload = {
    urls,
    percent_off: parseFloat(percentInput?.value || '0') || 0,
    absolute_off: parseFloat(absOffInput?.value || '0') || 0,
    add_percent: parseFloat(addPercentInput?.value || '0') || 0,
    drop_pct: Math.max(1, parseFloat(dropPct?.value || '10') || 10),
    enrich_details: true,
    use_browser: true,
    crawl_pagination: true,
    max_pages: 20,
    delay_ms: 300,
  };

  rawItems = []; rows = [];
  viewingWatchlist = false;
  if (exportActions) exportActions.style.display = 'none';
  hideComparison();
  clearResults();
  renderTableSkeleton();
  setLoading(true, urls);

  const controller = new AbortController();
  const cancelScrapeBtn = $('cancelScrapeBtn');
  const onCancelClick = () => {
    controller.abort();
    showToast('info', 'Scrape cancelled by user.');
  };
  if (cancelScrapeBtn) cancelScrapeBtn.addEventListener('click', onCancelClick);

  let requestTimedOut = false;
  const requestTimeout = setTimeout(() => {
    requestTimedOut = true;
    controller.abort();
  }, SCRAPE_REQUEST_TIMEOUT_MS);

  try {
    const res = await fetch('/api/scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    let data = {};
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      if (Array.isArray(err.items) && err.items.length > 0) {
        data = err;
        showToast('warn', err.error || 'Scraper guard flagged this run.');
      } else {
        throw new Error(err.error || `Server error ${res.status}`);
      }
    } else {
      data = await res.json();
      if (data.error && Array.isArray(data.items) && data.items.length > 0) {
        showToast('warn', data.error);
      }
    }

    setDisplayedResults(data.items || [], {
      models: deriveModelNames(urlList),
      persist: true,
      viewing: false,
    });

    const drops = Array.isArray(data.price_drops) ? data.price_drops : [];
    render();
    renderComparison(data.comparison);

    const totalItems = rawItems.length;
    const matchingItems = rows.length;
    const filteredSummary = hasActiveNarrowingFilters()
      ? `Found ${totalItems} item${totalItems === 1 ? '' : 's'} total. ${matchingItems} match current filters.`
      : `Fetched ${totalItems} item${totalItems === 1 ? '' : 's'} successfully.`;
    const detailSummary = data.enrich_details
      ? data.auto_enrich_details
        ? ` Auto detail scan refreshed ${data.details_enriched || 0} item${(data.details_enriched || 0) === 1 ? '' : 's'} to capture stock values.`
        : ` Deep detail scan refreshed ${data.details_enriched || 0} item${(data.details_enriched || 0) === 1 ? '' : 's'}.`
      : '';
    const browserSummary = data.using_browser ? ' Headless Botasaurus rendering was used.' : '';

    if (!rawItems.length) {
      const targetError = summarizeTargetErrors(data.target_errors);
      showToast('warn', targetError
        ? `No products found. Target fetch error: ${targetError}`
        : (data.error || 'No products found. Check the URL or try a different page.'));
    } else if (drops.length) {
      showToast('success', `Detected ${drops.length} price drop${drops.length > 1 ? 's' : ''}. ${filteredSummary}${detailSummary}${browserSummary}`);
    } else if (!data.error) {
      showToast('success', `${filteredSummary}${detailSummary}${browserSummary}`);
    }

  } catch (err) {
    console.error('[fetch]', err);
    const message = requestTimedOut
      ? 'Scrape timed out while waiting for browser verification. Try again after completing Cloudflare in the opened browser, or check the browser/proxy account.'
      : formatFetchErrorMessage(err);
    showToast('error', `Fetch failed: ${message}`);
    hideComparison();
    render();
  } finally {
    clearTimeout(requestTimeout);
    if (cancelScrapeBtn) cancelScrapeBtn.removeEventListener('click', onCancelClick);
    setLoading(false);
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {

  // Restore page size
  const storedPS = parseInt(localStorage.getItem(STORAGE_PAGESIZE) || '25', 10);
  if ([25, 50, 100].includes(storedPS)) {
    pageSize = storedPS;
    if (pageSizeSelect) pageSizeSelect.value = String(storedPS);
  }

  // Restore model chips
  try {
    const m = JSON.parse(localStorage.getItem(STORAGE_MODELS) || '[]');
    if (Array.isArray(m) && m.length) { currentModels = m; renderModelChips(m); }
  } catch { }

  // Restore last results
  const saved = loadResults();
  if (saved?.items?.length) {
    setDisplayedResults(saved.items, {
      models: saved.models?.length ? saved.models : null,
      persist: false,
      viewing: false,
    });
    render();
  } else {
    hideComparison();
    render(); // show empty state
  }

  startClock();
  updateUrlCounter();
  updateWatchUI();
  await loadWatchlistFromServer({ silent: true, rerender: true });

  // ── Event bindings ──────────────────────────────────────────────────────────

  // Fetch button
  if (runBtn) runBtn.addEventListener('click', doFetch);

  // URL textarea
  if (urlsTA) {
    urlsTA.addEventListener('input', updateUrlCounter);
    urlsTA.addEventListener('paste', () => setTimeout(updateUrlCounter, 50));
  }

  // Advanced filters toggle
  if (advancedToggle) advancedToggle.addEventListener('click', toggleFilters);
  if (resetAllBtn) resetAllBtn.addEventListener('click', resetFilters);

  // Keyword chips — Enter key
  if (kwInclude) {
    kwInclude.addEventListener('input', () => { updateFilterBadge(); refilter(); });
    kwInclude.addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); addKeyword(kwInclude, incKeywords, includeChipsCt, includeHidden); }
    });
  }
  if (kwExclude) {
    kwExclude.addEventListener('input', () => { updateFilterBadge(); refilter(); });
    kwExclude.addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); addKeyword(kwExclude, excKeywords, excludeChipsCt, excludeHidden); }
    });
  }

  // All filter inputs → refilter + update badge
  for (const el of [percentInput, absOffInput, addPercentInput, priceMin, priceMax, sortBy, hideDupes, showInStockOnly, showOutOfStockOnly, groupModel, showWatchlistOnly, searchInput]) {
    if (el) {
      el.addEventListener('input', () => { updateFilterBadge(); refilter(); });
      el.addEventListener('change', () => { updateFilterBadge(); refilter(); });
    }
  }

  // Pagination
  if (prevPageBtn) prevPageBtn.addEventListener('click', () => { if (currentPage > 1) { currentPage--; render(); } });
  if (nextPageBtn) nextPageBtn.addEventListener('click', () => {
    const tp = Math.max(1, Math.ceil(rows.length / pageSize));
    if (currentPage < tp) { currentPage++; render(); }
  });

  // Page size
  if (pageSizeSelect) pageSizeSelect.addEventListener('change', () => {
    pageSize = parseInt(pageSizeSelect.value, 10) || 25;
    currentPage = 1;
    localStorage.setItem(STORAGE_PAGESIZE, String(pageSize));
    render();
  });

  if (tbody) {
    tbody.addEventListener('mousemove', handleTableImageHover);
    tbody.addEventListener('mouseleave', hideImageHoverPreview);
  }
  window.addEventListener('scroll', hideImageHoverPreview, true);
  window.addEventListener('blur', hideImageHoverPreview);

  // CSV download
  if (csvBtn) csvBtn.addEventListener('click', () => {
    if (!lastExportRows.length) return;
    const ts = new Date().toISOString().slice(0, 10);
    downloadBlob(new Blob([toCSV(lastExportRows)], { type: 'text/csv;charset=utf-8;' }), `parts_${ts}.csv`);
    showToast('success', `Exported ${lastExportRows.length} rows as CSV.`);
  });

  // XLSX download
  if (xlsxBtn) xlsxBtn.addEventListener('click', async () => {
    if (!lastExportRows.length) return;
    xlsxBtn.disabled = true;
    xlsxBtn.textContent = '...';
    try {
      const res = await fetch('/api/export/xlsx', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows: lastExportRows }),
      });
      if (!res.ok) throw new Error(`Server ${res.status}`);
      const blob = await res.blob();
      const ts = new Date().toISOString().slice(0, 10);
      downloadBlob(blob, `parts_${ts}.xlsx`);
      showToast('success', `Exported ${lastExportRows.length} rows as XLSX.`);
    } catch (err) {
      console.error('[xlsx]', err);
      showToast('error', `XLSX export failed: ${err.message}`);
    } finally {
      xlsxBtn.disabled = false;
      xlsxBtn.textContent = 'XLSX';
    }
  });

  // Copy CSV
  if (copyBtn) copyBtn.addEventListener('click', async () => {
    if (!lastExportRows.length) return;
    try {
      await navigator.clipboard.writeText(toCSV(lastExportRows));
      showToast('success', 'Copied to clipboard as CSV.');
    } catch {
      showToast('warn', 'Clipboard access denied - use Download CSV instead.');
    }
  });

  // Export watchlist
  if (exportWatchlistBtn) exportWatchlistBtn.addEventListener('click', async () => {
    if (!watchlistLoaded) await loadWatchlistFromServer({ silent: false, rerender: false });
    if (!watchlistItems.length) return;
    const exportRows = buildWatchlistExportRows();
    downloadBlob(new Blob([toCSV(exportRows)], { type: 'text/csv;charset=utf-8;' }), 'watchlist.csv');
    showToast('info', `Exported ${watchlistItems.length} saved watchlist item${watchlistItems.length === 1 ? '' : 's'}.`);
  });

  if (viewWatchlistBtn) viewWatchlistBtn.addEventListener('click', () => {
    viewWatchlistResults();
  });

  // Clear watchlist
  if (clearWatchlistBtn) clearWatchlistBtn.addEventListener('click', () => {
    clearWatchlistFromServer();
  });

  // Clear results
  if (clearResultsBtn) clearResultsBtn.addEventListener('click', async () => {
    const confirmed = await showConfirmDialog({
      title: 'Clear Results?',
      message: 'This clears the current on-screen results from this browser tab. Saved watchlist items stay intact.',
      confirmLabel: 'Clear Results',
      cancelLabel: 'Keep Results',
      danger: true,
    });
    if (!confirmed) return;
    setDisplayedResults([], { models: [], viewing: false });
    lastExportRows = [];
    clearResults();
    if (tbody) tbody.innerHTML = '';
    if (exportActions) exportActions.style.display = 'none';
    hideComparison();
    clearAlert();
    render();
    showToast('info', 'Results cleared.');
  });

  // Dark mode toggle
  if (darkMode) {
    const savedTheme = sessionStorage.getItem('cy_theme') || 'dark';
    document.documentElement.setAttribute('data-bs-theme', savedTheme);
    document.documentElement.style.colorScheme = savedTheme;
    darkMode.checked = savedTheme === 'dark';
    darkMode.addEventListener('change', e => {
      const t = e.target.checked ? 'dark' : 'light';
      document.documentElement.setAttribute('data-bs-theme', t);
      document.documentElement.style.colorScheme = t;
      sessionStorage.setItem('cy_theme', t);
    });
  }

  syncFiltersDisclosure();

  // ── File upload for comparison ──────────────────────────────────────────────
  if (uploadZone && csvUpload) {
    uploadZone.addEventListener('click', e => {
      if (e.target !== clearFileBtn) csvUpload.click();
    });
    uploadZone.addEventListener('dragover', e => {
      e.preventDefault();
      uploadZone.style.borderColor = 'var(--primary)';
    });
    uploadZone.addEventListener('dragleave', () => {
      uploadZone.style.borderColor = '';
    });
    uploadZone.addEventListener('drop', e => {
      e.preventDefault();
      uploadZone.style.borderColor = '';
      const f = e.dataTransfer.files[0];
      if (f) processCompareFile(f);
    });
    csvUpload.addEventListener('change', e => {
      const f = e.target.files[0];
      if (f) processCompareFile(f);
    });
    if (clearFileBtn) clearFileBtn.addEventListener('click', e => {
      e.stopPropagation();
      csvUpload.value = '';
      compareMap.clear();
      if (uploadText) uploadText.textContent = 'Drop CSV/XLSX or click to upload';
      clearFileBtn.style.display = 'none';
      render();
      showToast('info', 'Comparison data cleared.');
    });
  }
});

// ── Compare file processing ───────────────────────────────────────────────────
async function processCompareFile(file) {
  const ext = (file.name.split('.').pop() || '').toLowerCase();
  if (!['csv', 'txt', 'xlsx', 'xls'].includes(ext)) {
    showToast('warn', 'Unsupported file. Use CSV or XLSX.'); return;
  }
  if (uploadText) uploadText.textContent = `Uploading ${file.name}...`;
  const fd = new FormData();
  fd.append('file', file);
  try {
    const res = await fetch('/api/comparison/upload', { method: 'POST', body: fd });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.status !== 'success') throw new Error(data.error || 'Upload failed');

    compareMap = new Map();
    for (const row of (data.rows || [])) {
      const title = (row.title || '').trim(); if (!title) continue;
      let price = typeof row.price === 'string' ? parseMoney(row.price) : row.price;
      if (!Number.isFinite(price)) continue;
      const tl = title.toLowerCase(), nk = norm(title), mk = modelKey(title);
      const sk = String(row.site || row.source || '').trim().toLowerCase();
      const uk = String(row.url || '').trim().toLowerCase();
      const addKey = k => k && compareMap.set(k, price);
      if (uk) addKey(`url:${uk}`);
      if (sk && tl) addKey(`site:${sk}:${tl}`);
      addKey(`title:${tl}`);
      if (sk && mk) addKey(`site-model:${sk}:${mk}`);
      addKey(`norm:${nk}`);
      addKey(`model:${mk}`);
    }

    currentPage = 1; render();
    if (uploadText) uploadText.textContent = `Loaded: ${file.name}`;
    if (clearFileBtn) clearFileBtn.style.display = 'block';
    showToast('success', `Comparison data loaded (${data.rows?.length || 0} rows).`);
  } catch (err) {
    console.error('[compare]', err);
    compareMap.clear();
    if (uploadText) uploadText.textContent = 'Drop CSV/XLSX or click to upload';
    showToast('error', err.message || 'Failed to process comparison file.');
  }
}
