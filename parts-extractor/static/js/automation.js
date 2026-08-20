(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const elements = {
    alertBox: $('alert'),
    overlay: $('overlay'),
    darkMode: $('darkMode'),
    automationJobId: $('automationJobId'),
    automationName: $('automationName'),
    automationSite: $('automationSite'),
    automationCategoryQuery: $('automationCategoryQuery'),
    automationRootUrl: $('automationRootUrl'),
    automationIntervalValue: $('automationIntervalValue'),
    automationIntervalUnit: $('automationIntervalUnit'),
    automationMaxPages: $('automationMaxPages'),
    automationDelayMs: $('automationDelayMs'),
    automationEnabled: $('automationEnabled'),
    automationAutoDiscover: $('automationAutoDiscover'),
    automationParallel: $('automationParallel'),
    automationEnrich: $('automationEnrich'),
    automationDiscoverBtn: $('automationDiscoverBtn'),
    automationSaveBtn: $('automationSaveBtn'),
    automationResetBtn: $('automationResetBtn'),
    automationDiscoverySummary: $('automationDiscoverySummary'),
    automationDiscoveryMeta: $('automationDiscoveryMeta'),
    automationDiscoverySelection: $('automationDiscoverySelection'),
    automationIncludeAllBtn: $('automationIncludeAllBtn'),
    automationSkipAllBtn: $('automationSkipAllBtn'),
    automationDiscoveredTargets: $('automationDiscoveredTargets'),
    automationSupplierTabs: document.querySelector('.automation-supplier-tabs'),
    automationJobs: $('automationJobs'),
    automationRuns: $('automationRuns'),
    automationScrapedProducts: $('automationScrapedProducts'),
    automationProductsCsvBtn: $('automationProductsCsvBtn'),
    automationProductsXlsxBtn: $('automationProductsXlsxBtn'),
    automationRunDetail: $('automationRunDetail'),
    automationModelFilter: $('automationModelFilter'),
    automationReviewFilters: $('automationReviewFilters'),
    automationJobEditor: $('automationJobEditor')
  };

  const SITE_ROOTS = {
    standard: 'https://www.mobilesentrix.com/',
    mobilesentrix_canada: 'https://www.mobilesentrix.ca/',
    xcell: 'https://xcellparts.com/',
    txparts: 'https://txparts.com/',
    parts4cells: 'https://parts4cells.com/',
    phonelcdparts: 'https://www.phonelcdparts.com/',
    gadgetfix: 'https://gadgetfix.com/'
  };

  const NOTIF_CLS = {
    success: 'alert-success',
    error: 'alert-danger',
    danger: 'alert-danger',
    warn: 'alert-warning',
    warning: 'alert-warning',
    info: 'alert-info'
  };

  const CHANGE_VIEW_CONFIG = [
    { key: 'all', label: 'All Activity' },
    { key: 'duplicates', label: 'Duplicate Listings' },
    { key: 'stock_status', label: 'Stock Changes' },
    { key: 'price', label: 'Price Changes' },
    { key: 'title', label: 'Title Changes' },
    { key: 'sku', label: 'SKU Changes' },
    { key: 'description', label: 'Description Changes' },
    { key: 'added', label: 'Added Items' },
    { key: 'removed', label: 'Removed Items' }
  ];

  const SUPPLIER_SITE_KEYS = new Set(['xcell', 'parts4cells', 'phonelcdparts', 'standard', 'mobilesentrix_canada', 'txparts', 'gadgetfix']);
  const ACTIVE_POLL_MS = 3000;
  const IDLE_POLL_MS = 30000;
  const LIVE_DETAIL_REFRESH_MS = 12000;

  function normalizeSupplierSite(siteKey) {
    const normalized = String(siteKey || '').trim().toLowerCase();
    return SUPPLIER_SITE_KEYS.has(normalized) ? normalized : 'xcell';
  }

  function initialSupplierSite() {
    try {
      return normalizeSupplierSite(new URLSearchParams(window.location.search).get('site'));
    } catch {
      return 'xcell';
    }
  }

  const state = {
    activeSite: initialSupplierSite(),
    allJobs: [],
    jobs: [],
    runs: [],
    selectedJobId: null,
    selectedRunId: null,
    selectedChangeView: 'all',
    discovery: null,
    discoveryFingerprint: '',
    loadedFingerprint: '',
    runDetail: null,
    productExportRows: [],
    productFilters: {
      search: '',
      mode: 'all',
      source: '',
      minPrice: '',
      maxPrice: '',
      sortKey: '',
      sortDir: 'asc',
      page: 1,
      pageSize: 100
    },
    productFilterTimer: null,
    loadingCount: 0,
    jobsRequestId: 0,
    runsRequestId: 0,
    runDetailRequestId: 0,
    lastRunDetailFetchAt: 0,
    realtimePollTimer: null,
    realtimeClockTimer: null,
    realtimePollInFlight: false
  };

  function preserveLiveScroll(callback) {
    const pageScroll = {
      left: window.scrollX,
      top: window.scrollY
    };
    const trackedScroll = [
      elements.automationRuns,
      elements.automationScrapedProducts,
      elements.automationRunDetail
    ].filter(Boolean).map(element => ({
      element,
      left: element.scrollLeft,
      top: element.scrollTop
    }));

    const result = callback();

    trackedScroll.forEach(({ element, left, top }) => {
      element.scrollLeft = left;
      element.scrollTop = top;
    });
    if (window.scrollX !== pageScroll.left || window.scrollY !== pageScroll.top) {
      window.scrollTo(pageScroll.left, pageScroll.top);
    }
    return result;
  }

  function isEditingProductFilters() {
    const activeElement = document.activeElement;
    return Boolean(
      activeElement
      && elements.automationScrapedProducts
      && elements.automationScrapedProducts.contains(activeElement)
      && activeElement.matches('input, select, textarea')
    );
  }

  function getSaveButtonLabel() {
    return (elements.automationJobId?.value || '').trim() ? 'Update Job' : 'Save Job';
  }

  function syncFormMode() {
    if (!elements.automationSaveBtn) return;
    elements.automationSaveBtn.innerHTML = `<span>${escapeHtml(getSaveButtonLabel())}</span>`;
  }

  function hasFreshDiscoveryForCurrentForm() {
    return Boolean(state.discovery && state.discoveryFingerprint === currentFingerprint());
  }

  function isEditingScopeChanged() {
    return Boolean((elements.automationJobId?.value || '').trim() && state.loadedFingerprint && state.loadedFingerprint !== currentFingerprint());
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = String(text ?? '');
    return div.innerHTML;
  }

  function setLoading(on) {
    state.loadingCount = Math.max(0, state.loadingCount + (on ? 1 : -1));
    const busy = state.loadingCount > 0;
    document.querySelector('.automation-dashboard')?.setAttribute('aria-busy', busy ? 'true' : 'false');
  }

  function renderInspectorSkeleton() {
    const container = elements.automationRunDetail;
    if (!container) return;
    container.className = 'automation-run-detail';
    container.innerHTML = `
      <div class="skeleton-container">
        <div class="skeleton-stats">
          <div class="skeleton-stat-card"><div class="skeleton-box" style="width: 40%; height: 18px;"></div><div class="skeleton-box" style="width: 70%; height: 11px;"></div></div>
          <div class="skeleton-stat-card"><div class="skeleton-box" style="width: 30%; height: 18px;"></div><div class="skeleton-box" style="width: 60%; height: 11px;"></div></div>
          <div class="skeleton-stat-card"><div class="skeleton-box" style="width: 35%; height: 18px;"></div><div class="skeleton-box" style="width: 65%; height: 11px;"></div></div>
          <div class="skeleton-stat-card"><div class="skeleton-box" style="width: 25%; height: 18px;"></div><div class="skeleton-box" style="width: 55%; height: 11px;"></div></div>
          <div class="skeleton-stat-card"><div class="skeleton-box" style="width: 45%; height: 18px;"></div><div class="skeleton-box" style="width: 75%; height: 11px;"></div></div>
        </div>
        <div class="skeleton-row"><div class="skeleton-box" style="width: 40px; height: 40px; border-radius: 6px;"></div><div style="flex:1;"><div class="skeleton-box" style="width: 70%; height: 14px; margin-bottom: 6px;"></div><div class="skeleton-box" style="width: 40%; height: 11px;"></div></div><div class="skeleton-box" style="width: 80px; height: 24px;"></div></div>
        <div class="skeleton-row"><div class="skeleton-box" style="width: 40px; height: 40px; border-radius: 6px;"></div><div style="flex:1;"><div class="skeleton-box" style="width: 60%; height: 14px; margin-bottom: 6px;"></div><div class="skeleton-box" style="width: 35%; height: 11px;"></div></div><div class="skeleton-box" style="width: 80px; height: 24px;"></div></div>
      </div>
    `;
  }

  function renderProductsSkeleton() {
    const container = elements.automationScrapedProducts;
    if (!container) return;
    container.className = 'automation-products';
    container.innerHTML = `
      <div class="skeleton-container">
        <div style="display:flex; justify-content:space-between; margin-bottom:1rem;">
          <div class="skeleton-box" style="width: 260px; height: 36px; border-radius: 8px;"></div>
          <div class="skeleton-box" style="width: 140px; height: 36px; border-radius: 8px;"></div>
        </div>
        ${Array.from({ length: 6 }).map(() => `
          <div class="skeleton-row">
            <div class="skeleton-box" style="width: 44px; height: 44px; border-radius: 8px;"></div>
            <div style="flex:1;">
              <div class="skeleton-box" style="width: 65%; height: 15px; margin-bottom: 6px;"></div>
              <div class="skeleton-box" style="width: 35%; height: 12px;"></div>
            </div>
            <div class="skeleton-box" style="width: 90px; height: 20px; border-radius: 4px;"></div>
            <div class="skeleton-box" style="width: 70px; height: 20px; border-radius: 4px;"></div>
          </div>
        `).join('')}
      </div>
    `;
  }

  function renderRunsSkeleton() {
    const container = elements.automationRuns;
    if (!container) return;
    container.innerHTML = Array.from({ length: 4 }).map(() => `
      <div class="skeleton-row" style="margin-bottom:0.5rem; padding: 1rem;">
        <div style="flex:1;">
          <div class="skeleton-box" style="width: 60%; height: 14px; margin-bottom: 6px;"></div>
          <div class="skeleton-box" style="width: 85%; height: 11px;"></div>
        </div>
        <div class="skeleton-box" style="width: 60px; height: 22px; border-radius: 12px;"></div>
      </div>
    `).join('');
  }

  function showAlert(type, msg, duration = 5000) {
    const alertBox = elements.alertBox;
    if (!alertBox) return;
    alertBox.className = `alert-banner ${NOTIF_CLS[type] || 'alert-info'}`;
    alertBox.innerHTML = `${escapeHtml(msg)}<button type="button" aria-label="Close notification" style="margin-left:auto;background:none;border:none;color:inherit;cursor:pointer;font-size:1rem;padding:0 .2rem">x</button>`;
    const button = alertBox.querySelector('button');
    if (button) button.addEventListener('click', () => alertBox.classList.add('d-none'));
    alertBox.classList.remove('d-none');
    clearTimeout(alertBox._timer);
    if (duration > 0) {
      alertBox._timer = setTimeout(() => alertBox.classList.add('d-none'), duration);
    }
  }

  function removeDiscoveryControls() {
    elements.automationDiscoverBtn?.remove();
    const autoDiscoverWrapper = elements.automationAutoDiscover?.closest('label');
    if (autoDiscoverWrapper) {
      autoDiscoverWrapper.remove();
    } else {
      elements.automationAutoDiscover?.classList.add('d-none');
    }
  }

  async function api(url, options = {}) {
    const { headers: optionHeaders = {}, ...requestOptions } = options;
    const res = await fetch(url, {
      cache: 'no-store',
      ...requestOptions,
      headers: { 'Content-Type': 'application/json', ...optionHeaders }
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.error || `Request failed (${res.status})`);
    }
    return data;
  }

  let _pkDateTimeFormatter = null;
  const _dateTimeCache = new Map();

  function formatDateTime(value) {
    if (!value) return 'Never';
    const key = String(value);
    const cached = _dateTimeCache.get(key);
    if (cached !== undefined) return cached;

    try {
      if (!_pkDateTimeFormatter) {
        _pkDateTimeFormatter = new Intl.DateTimeFormat('en-PK', {
          dateStyle: 'medium',
          timeStyle: 'short',
          timeZone: 'Asia/Karachi'
        });
      }
      const formatted = _pkDateTimeFormatter.format(new Date(value));
      if (_dateTimeCache.size > 500) _dateTimeCache.clear();
      _dateTimeCache.set(key, formatted);
      return formatted;
    } catch {
      return key;
    }
  }

  function relativeTime(value) {
    if (!value) return 'Pending';
    try {
      const now = Date.now();
      const then = new Date(value).getTime();
      const isFuture = then >= now;
      const diffMs = Math.abs(then - now);
      const suffix = isFuture ? 'from now' : 'ago';
      const diffMin = Math.max(1, Math.floor(diffMs / 60000));
      if (diffMin < 60) return `${diffMin} min${diffMin === 1 ? '' : 's'} ${suffix}`;
      const diffHours = Math.max(1, Math.floor(diffMs / 3600000));
      if (diffHours < 48) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ${suffix}`;
      const diffDays = Math.max(1, Math.floor(diffMs / 86400000));
      return `${diffDays} day${diffDays === 1 ? '' : 's'} ${suffix}`;
    } catch {
      return '';
    }
  }

  function formatDuration(ms) {
    const totalSeconds = Math.max(0, Math.round(Number(ms || 0) / 1000));
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    const parts = [];
    if (days) parts.push(`${days}d`);
    if (hours || days) parts.push(`${hours}h`);
    if (minutes || hours || days) parts.push(`${minutes}m`);
    if (!parts.length) parts.push(`${seconds}s`);
    return parts.slice(0, 3).join(' ');
  }

  function getRunTiming(run) {
    const summary = run?.summary || {};
    const status = String(run?.status || '').toLowerCase();
    const startedAt = new Date(run?.started_at || '').getTime();
    const completedAt = run?.completed_at ? new Date(run.completed_at).getTime() : NaN;
    const pausedAt = summary.paused_at ? new Date(summary.paused_at).getTime() : NaN;
    const endAt = Number.isFinite(completedAt) && completedAt > 0
      ? completedAt
      : status !== 'running' && Number.isFinite(pausedAt) && pausedAt > 0
        ? pausedAt
        : Date.now();
    const elapsedMs = Number.isFinite(startedAt) && startedAt > 0 ? Math.max(0, endAt - startedAt) : 0;
    const completedTargets = Number(summary.completed_targets || 0);
    const totalTargets = Number(summary.total_targets || summary.target_count || (run?.target_urls || []).length || 0);
    const remainingTargets = Math.max(0, totalTargets - completedTargets);
    const averageMsPerTarget = completedTargets > 0 && elapsedMs > 0 ? elapsedMs / completedTargets : 0;
    const rawRecent = Number(summary.recent_targets_per_min || 0);
    const recentTargetsPerMin = rawRecent > 0 ? rawRecent : (averageMsPerTarget > 0 && averageMsPerTarget < 5000 ? (60000 / averageMsPerTarget) : 45.0);
    const currentPhase = Number(summary.phase || 0);
    const phase2Total = Number(summary.phase2_total || 0);
    const phase2Completed = Number(summary.phase2_completed || 0);
    const recentItemsPerMin = Number(summary.recent_items_per_min || 0);
    const isPhase2 = ['running', 'resuming'].includes(status) && (currentPhase === 2 || phase2Total > 0);
    const remainingUnits = isPhase2 ? Math.max(0, phase2Total - phase2Completed) : remainingTargets;
    const unitsPerMin = isPhase2 ? Math.max(recentItemsPerMin, 25) : Math.max(recentTargetsPerMin, 0.5);
    const etaMs = ['running', 'resuming'].includes(status) && unitsPerMin > 0 && remainingUnits > 0
      ? (remainingUnits / unitsPerMin) * 60000
      : 0;
    const rateLabel = isPhase2
      ? `${recentItemsPerMin > 0 ? recentItemsPerMin.toFixed(1) : 'estimating'} products/min`
      : `${recentTargetsPerMin.toFixed(1)} categories/min`;
    const progressText = isPhase2
      ? `${phase2Completed.toLocaleString()} / ${Math.max(phase2Total, phase2Completed).toLocaleString()} products`
      : `${completedTargets.toLocaleString()} / ${Math.max(totalTargets, completedTargets).toLocaleString()} categories`;
    return {
      completedTargets,
      totalTargets,
      remainingTargets,
      elapsedLabel: elapsedMs ? formatDuration(elapsedMs) : 'Estimating',
      etaLabel: etaMs ? formatDuration(etaMs) : (['running', 'resuming'].includes(status) ? 'Estimating' : 'Done'),
      rateLabel,
      progressText,
      phaseLabel: isPhase2 ? 'Products' : 'Categories',
      finishLabel: etaMs ? formatDateTime(new Date(Date.now() + etaMs).toISOString()) : '',
    };
  }

  function clampPercent(value, fallback = 0) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return fallback;
    return Math.max(0, Math.min(100, numeric));
  }

  function getRunProgressPercent(run) {
    const summary = run?.summary || {};
    if (summary.progress_percent !== undefined && summary.progress_percent !== null) {
      return clampPercent(summary.progress_percent, 0);
    }
    const phase = Number(summary.phase || 0);
    if (phase === 2) {
      return clampPercent((Number(summary.phase2_completed || 0) / Math.max(1, Number(summary.phase2_total || 1))) * 100, 0);
    }
    const totalTargets = Number(summary.total_targets || summary.target_count || (run?.target_urls || []).length || 0);
    if (totalTargets > 0) {
      return clampPercent((Number(summary.completed_targets || 0) / totalTargets) * 100, 0);
    }
    return String(run?.status || '').toLowerCase() === 'completed' ? 100 : 0;
  }

  function getRunPhaseName(run) {
    const summary = run?.summary || {};
    const explicit = compactAutomationLabel(summary.phase_name || summary.activity_label || '');
    if (explicit) return explicit;
    const status = String(run?.status || '').toLowerCase();
    if (status === 'paused') return 'Paused';
    if (status === 'interrupted') return 'Interrupted';
    if (status === 'failed') return 'Failed';
    if (status === 'completed') return 'Completed';
    const phase = Number(summary.phase || 1);
    if (phase === 2) return 'Phase 2: Product Detail & SKU Scan';
    if (phase === 3) return 'Phase 3: Validation & Comparison';
    if (phase >= 4) return 'Phase 4: Saving Snapshot';
    return 'Phase 1: Category Crawling';
  }

  function getRunActivityMessage(run) {
    const summary = run?.summary || {};
    const explicit = compactAutomationLabel(summary.status_message || '');
    if (explicit) return explicit;
    const status = String(run?.status || '').toLowerCase();
    if (['running', 'resuming'].includes(status)) {
      const phase = Number(summary.phase || 1);
      if (phase === 2) return 'Enriching product details and SKU metadata.';
      if (phase === 3) return 'Validating scraped products and comparing against the previous snapshot.';
      if (phase >= 4) return 'Saving the product snapshot and run history to the database.';
      return 'Fetching category pages and collecting product cards.';
    }
    if (status === 'paused') return 'This run is paused and can be resumed.';
    if (status === 'interrupted') return 'This run was interrupted and can be resumed.';
    if (status === 'failed') return compactAutomationLabel(run?.error_text || 'This run failed before completion.');
    return 'Snapshot is saved.';
  }

  function intervalToMinutes() {
    const value = Math.max(1, parseInt(elements.automationIntervalValue?.value || '1', 10));
    const unit = elements.automationIntervalUnit?.value || 'days';
    if (unit === 'weeks') return value * 7 * 24 * 60;
    if (unit === 'hours') return value * 60;
    return value * 24 * 60;
  }

  function setIntervalFromMinutes(minutes) {
    const total = Math.max(1, parseInt(minutes || 1440, 10));
    if (total % (7 * 24 * 60) === 0) {
      elements.automationIntervalUnit.value = 'weeks';
      elements.automationIntervalValue.value = String(total / (7 * 24 * 60));
      return;
    }
    if (total % (24 * 60) === 0) {
      elements.automationIntervalUnit.value = 'days';
      elements.automationIntervalValue.value = String(total / (24 * 60));
      return;
    }
    elements.automationIntervalUnit.value = 'hours';
    elements.automationIntervalValue.value = String(Math.max(1, Math.round(total / 60)));
  }

  function currentFingerprint() {
    return JSON.stringify({
      scraper_key: elements.automationSite?.value || 'xcell',
      category_query: (elements.automationCategoryQuery?.value || '').trim(),
      root_url: (elements.automationRootUrl?.value || '').trim()
    });
  }

  function targetUrlKey(target) {
    return String(target?.url_key || target?.url || '').trim().toLowerCase();
  }

  function toBooleanFlag(value, fallback = true) {
    if (value === undefined || value === null || value === '') return Boolean(fallback);
    if (typeof value === 'boolean') return value;
    const normalized = String(value).trim().toLowerCase();
    if (['0', 'false', 'no', 'off'].includes(normalized)) return false;
    if (['1', 'true', 'yes', 'on'].includes(normalized)) return true;
    return Boolean(value);
  }

  function normalizeDiscoveryTargets(targets, previousTargets = []) {
    const previousActive = new Map(
      (Array.isArray(previousTargets) ? previousTargets : [])
        .map(target => [targetUrlKey(target), toBooleanFlag(target?.active, true)])
        .filter(([urlKey]) => Boolean(urlKey))
    );
    const normalized = [];
    const seen = new Set();
    (Array.isArray(targets) ? targets : []).forEach((target, index) => {
      const url = String(target?.url || '').trim();
      const urlKey = targetUrlKey(target);
      if (!url || !urlKey || seen.has(urlKey)) return;
      seen.add(urlKey);
      const hasExplicitActive = target && Object.prototype.hasOwnProperty.call(target, 'active');
      normalized.push({
        ...target,
        label: String(target?.label || '').trim() || url,
        group_label: String(target?.group_label || '').trim(),
        url,
        url_key: urlKey,
        active: hasExplicitActive
          ? toBooleanFlag(target?.active, true)
          : previousActive.has(urlKey)
            ? previousActive.get(urlKey)
            : true,
        position: Number.isFinite(Number(target?.position)) ? Number(target.position) : index
      });
    });
    return normalized;
  }

  function normalizeDiscovery(discovery, previousTargets = []) {
    const safeDiscovery = discovery && typeof discovery === 'object' ? discovery : {};
    return {
      ...safeDiscovery,
      query: String(safeDiscovery.query || '').trim(),
      site_label: String(safeDiscovery.site_label || '').trim(),
      scraper_key: String(safeDiscovery.scraper_key || '').trim(),
      root_url: String(safeDiscovery.root_url || '').trim(),
      candidate_count: Number(safeDiscovery.candidate_count || 0),
      targets: normalizeDiscoveryTargets(safeDiscovery.targets || [], previousTargets)
    };
  }

  function getDiscoveryCounts(discovery = state.discovery) {
    const targets = Array.isArray(discovery?.targets) ? discovery.targets : [];
    const total = targets.length;
    const active = targets.filter(target => toBooleanFlag(target?.active, true)).length;
    return {
      total,
      active,
      skipped: Math.max(0, total - active)
    };
  }

  function toggleDiscoveryTarget(urlKey) {
    if (!state.discovery || !urlKey) return;
    state.discovery = {
      ...state.discovery,
      targets: (state.discovery.targets || []).map(target => {
        if (targetUrlKey(target) !== urlKey) return target;
        return { ...target, active: !toBooleanFlag(target?.active, true) };
      })
    };
    renderDiscovery();
  }

  function setAllDiscoveryTargetsActive(active) {
    if (!state.discovery || !Array.isArray(state.discovery.targets)) return;
    state.discovery = {
      ...state.discovery,
      targets: state.discovery.targets.map(target => ({ ...target, active: Boolean(active) }))
    };
    renderDiscovery();
  }

  function resetDiscovery() {
    state.discovery = null;
    state.discoveryFingerprint = '';
    renderDiscovery();
  }

  function resetForm({ clearSelection = true } = {}) {
    if (elements.automationJobId) elements.automationJobId.value = '';
    if (elements.automationName) elements.automationName.value = '';
    if (elements.automationSite) elements.automationSite.value = state.activeSite || 'xcell';
    if (elements.automationCategoryQuery) elements.automationCategoryQuery.value = '';
    if (elements.automationRootUrl) elements.automationRootUrl.value = SITE_ROOTS[state.activeSite] || SITE_ROOTS.xcell;
    if (elements.automationIntervalValue) elements.automationIntervalValue.value = '1';
    if (elements.automationIntervalUnit) elements.automationIntervalUnit.value = 'days';
    if (elements.automationMaxPages) elements.automationMaxPages.value = '10';
    if (elements.automationDelayMs) elements.automationDelayMs.value = '50';
    if (elements.automationEnabled) elements.automationEnabled.checked = true;
    if (elements.automationAutoDiscover) elements.automationAutoDiscover.checked = false;
    if (elements.automationParallel) elements.automationParallel.checked = true;
    if (elements.automationEnrich) elements.automationEnrich.checked = true;
    if (clearSelection) state.selectedJobId = null;
    state.loadedFingerprint = '';
    elements.automationJobEditor?.classList.add('d-none');
    resetDiscovery();
    syncFormMode();
  }

  function openJobEditor() {
    elements.automationJobEditor?.classList.remove('d-none');
    elements.automationJobEditor?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    elements.automationName?.focus({ preventScroll: true });
  }

  function closeJobEditor() {
    resetForm({ clearSelection: false });
    renderJobs(state.jobs);
  }

  function collectPayload() {
    return {
      id: elements.automationJobId?.value || undefined,
      name: (elements.automationName?.value || '').trim(),
      scraper_key: elements.automationSite?.value || 'xcell',
      category_query: (elements.automationCategoryQuery?.value || '').trim(),
      root_url: (elements.automationRootUrl?.value || '').trim(),
      interval_minutes: intervalToMinutes(),
      enabled: Boolean(elements.automationEnabled?.checked),
      auto_discover: false,
      use_parallel: Boolean(elements.automationParallel?.checked),
      enrich_details: true,
      crawl_pagination: true,
      verify_ssl: true,
      retries: 1,
      max_pages: Math.max(1, parseInt(elements.automationMaxPages?.value || '10', 10)),
      delay_ms: Math.max(0, parseInt(elements.automationDelayMs?.value || '50', 10)),
      drop_pct: 10,
      rules: {}
    };
  }

  function statusChip(status) {
    const value = String(status || 'idle').toLowerCase();
    const cls = value === 'completed' ? 'automation-chip automation-chip--ok'
      : value === 'failed' ? 'automation-chip automation-chip--danger'
        : ['running', 'resuming', 'paused', 'interrupted'].includes(value) ? 'automation-chip automation-chip--warn'
          : 'automation-chip';
    return `<span class="${cls}">${escapeHtml(formatStatusLabel(value))}</span>`;
  }

  function formatStatusLabel(status, fallback = 'Not run') {
    const value = String(status || '').trim().toLowerCase();
    if (!value) return fallback;
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  function scheduleStatusChip(job) {
    const enabled = Boolean(job?.enabled);
    const cls = enabled ? 'automation-chip automation-chip--ok' : 'automation-chip';
    return `<span class="${cls}">${enabled ? 'Active' : 'Paused'}</span>`;
  }

  function activeSiteLabel() {
    const activeTab = Array.from(elements.automationSupplierTabs?.querySelectorAll('[data-site-key]') || [])
      .find(tab => siteKeyMatches(tab.dataset.siteKey));
    return activeTab?.textContent?.trim() || 'this site';
  }

  function compactAutomationLabel(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function cleanLegacyAutomationLabel(value) {
    return compactAutomationLabel(value)
      .replace(/^menu\s+map\s*[-:]\s*/i, '')
      .replace(/\s*[-:]\s*20\d{2}(?:[-/]\d{1,2})?(?:[-/]\d{1,2})?(?:\s+\d{1,2}:\d{2})?\s*$/i, '')
      .replace(/\b20\d{2}[-/]\d{1,2}(?:[-/]\d{1,2})?(?:\s+\d{1,2}:\d{2})?\b/g, '')
      .replace(/\s*[-:]\s*$/g, '')
      .trim();
  }

  function automationScopeLabel(record) {
    const category = cleanLegacyAutomationLabel(record?.category_query || '');
    if (!category || /^menu\s+map\s+selection$/i.test(category) || /^[a-z0-9.-]+\.[a-z]{2,}$/i.test(category)) {
      return 'Visible Categories';
    }
    return category;
  }

  function automationDisplayName(record) {
    const raw = compactAutomationLabel(record?.name || record?.job_name || '');
    const cleaned = cleanLegacyAutomationLabel(raw);
    const scope = automationScopeLabel(record);
    const legacy = /^menu\s+map\b/i.test(raw) || /\b20\d{2}[-/]\d{1,2}/.test(raw) || /^menu\s+map\s+selection$/i.test(record?.category_query || '');
    if (raw && !legacy) return cleaned || raw;
    const base = cleaned || compactAutomationLabel(record?.site_label || activeSiteLabel()) || 'Automation';
    return scope && !base.toLowerCase().endsWith(scope.toLowerCase()) ? `${base} - ${scope}` : base;
  }

  function siteKeyMatches(value) {
    return String(value || '').trim().toLowerCase() === String(state.activeSite || '').trim().toLowerCase();
  }

  function filterJobsByActiveSite(jobs) {
    return (Array.isArray(jobs) ? jobs : []).filter(job => siteKeyMatches(job?.scraper_key));
  }

  function filterRunsByActiveSite(runs) {
    return (Array.isArray(runs) ? runs : []).filter(run => siteKeyMatches(run?.scraper_key));
  }

  function isCurrentRunStatus(value) {
    return ['running', 'resuming', 'paused', 'interrupted'].includes(String(value || '').trim().toLowerCase());
  }

  function syncActivityPanelCopy() {
    const panel = document.getElementById('automationActivityPanel');
    const runsPanel = document.getElementById('automationRunsPanel');
    const title = panel?.querySelector('.section-title');
    const subtitle = panel?.querySelector('.section-subtitle');
    const hint = panel?.querySelector('.automation-activity-hint');
    const runsTitle = runsPanel?.querySelector('.automation-activity-section__head h3');
    const runsSubtitle = runsPanel?.querySelector('.automation-activity-section__head span');
    if (title) title.textContent = 'Schedules & Runs';
    if (subtitle) subtitle.remove();
    if (hint) hint.remove();
    if (runsTitle) runsTitle.textContent = 'Runs';
    if (runsSubtitle) runsSubtitle.textContent = 'Current and past';
  }

  function syncSupplierTabs() {
    let activeTab = null;
    const tabList = elements.automationSupplierTabs;
    tabList?.querySelectorAll('[data-site-key]').forEach(tab => {
      const isActive = siteKeyMatches(tab.dataset.siteKey);
      tab.classList.toggle('is-active', isActive);
      tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
      if (isActive) activeTab = tab;
    });
    window.requestAnimationFrame(() => {
      if (!tabList || !activeTab) return;
      const centeredLeft = activeTab.offsetLeft - ((tabList.clientWidth - activeTab.offsetWidth) / 2);
      const left = Math.max(0, centeredLeft);
      if (typeof tabList.scrollTo === 'function') {
        tabList.scrollTo({ left, behavior: 'auto' });
      } else {
        tabList.scrollLeft = left;
      }
    });
  }

  function updateSupplierUrl(siteKey, mode = 'push') {
    try {
      const url = new URL(window.location.href);
      url.searchParams.set('site', siteKey);
      const method = mode === 'replace' ? 'replaceState' : 'pushState';
      window.history[method]({ automationSite: siteKey }, '', url);
    } catch { }
  }

  async function selectSupplier(siteKey, { silent = false, updateUrl = true, urlMode = 'push' } = {}) {
    const nextSite = normalizeSupplierSite(siteKey);
    if (!nextSite || nextSite === state.activeSite) return;
    state.activeSite = nextSite;
    state.selectedJobId = null;
    state.selectedRunId = null;
    state.selectedChangeView = 'all';
    state.runDetail = null;
    resetProductFilters();
    state.runsRequestId += 1;
    state.runDetailRequestId += 1;
    elements.automationJobEditor?.classList.add('d-none');
    populateModelFilter(null);
    renderRunDetail(null);
    syncSupplierTabs();
    renderJobs(filterJobsByActiveSite(state.allJobs));
    if (updateUrl) updateSupplierUrl(nextSite, urlMode);
    await loadRuns(null, { silent });
  }

  function renderDiscovery() {
    const summary = elements.automationDiscoverySummary;
    const meta = elements.automationDiscoveryMeta;
    const selection = elements.automationDiscoverySelection;
    const includeAllBtn = elements.automationIncludeAllBtn;
    const skipAllBtn = elements.automationSkipAllBtn;
    const container = elements.automationDiscoveredTargets;
    if (!summary || !meta || !selection || !includeAllBtn || !skipAllBtn || !container) return;

    const discovery = state.discovery;
    if (!discovery || !Array.isArray(discovery.targets) || !discovery.targets.length) {
      summary.textContent = 'Targets are selected from Menu Map and saved with the job.';
      meta.textContent = '';
      selection.textContent = 'Open Menu Map, hide categories you do not want, then run automation for that site.';
      includeAllBtn.disabled = true;
      skipAllBtn.disabled = true;
      container.innerHTML = '<div class="automation-target"><div class="automation-target__label">No saved targets yet</div><div class="automation-target__url">Use the Menu Map page to create an automation job from selected categories.</div></div>';
      return;
    }

    const counts = getDiscoveryCounts(discovery);
    summary.textContent = `Saved ${counts.total} target link${counts.total === 1 ? '' : 's'} for "${discovery.query}".`;
    meta.textContent = `${discovery.site_label} - ${discovery.candidate_count || counts.total} target links`;
    selection.textContent = counts.skipped
      ? `${counts.active} included, ${counts.skipped} skipped. Skipped links stay out of scheduled runs.`
      : `All ${counts.active} saved link${counts.active === 1 ? '' : 's'} are included in this job.`;
    includeAllBtn.disabled = counts.total === 0 || counts.active === counts.total;
    skipAllBtn.disabled = counts.total === 0 || counts.skipped === counts.total;
    container.innerHTML = discovery.targets.map(target => `
      <div class="automation-target${target.active ? '' : ' is-skipped'}">
        <div class="automation-target__top">
          <div class="automation-target__copy">
            ${target.group_label ? `<div class="automation-target__group">${escapeHtml(target.group_label)}</div>` : ''}
            <div class="automation-target__label">${escapeHtml(target.label)}</div>
          </div>
          <button
            type="button"
            class="automation-target__toggle ${target.active ? 'is-active' : 'is-skipped'}"
            data-action="toggle-target"
            data-url-key="${escapeHtml(target.url_key || '')}"
            aria-pressed="${target.active ? 'true' : 'false'}"
          >${target.active ? 'Included' : 'Skipped'}</button>
        </div>
        <div class="automation-target__url">${escapeHtml(target.url)}</div>
        <div class="automation-target__hint">${target.active ? 'This link will be scraped when the job runs.' : 'This link will be skipped when the job runs.'}</div>
      </div>
    `).join('');
  }

  function renderOverview(overview) {
    if (!overview) return;
  }

  function renderJobs(jobs) {
    const container = elements.automationJobs;
    if (!container) return;
    state.jobs = Array.isArray(jobs) ? jobs : [];
    if (!state.jobs.length) {
      container.innerHTML = `<div class="automation-job automation-empty-state"><div class="automation-job__title">No jobs for ${escapeHtml(activeSiteLabel())}</div><div class="automation-job__subtitle">Use Menu Map to queue visible categories.</div></div>`;
      return;
    }

    container.innerHTML = state.jobs.map(job => {
      const selected = Number(job.id) === Number(state.selectedJobId) ? ' is-selected' : '';
      const displayName = automationDisplayName(job);
      const scopeLabel = automationScopeLabel(job);
      const nextRunHtml = job.enabled
        ? `<span>${escapeHtml(formatDateTime(job.next_run_at))}</span> <span style="font-size:0.7rem; color:var(--text-3);">(${escapeHtml(relativeTime(job.next_run_at))})</span>`
        : '<span class="automation-chip">Paused</span>';
      const lastRunHtml = job.last_run_at
        ? `<span class="automation-chip ${job.last_status === 'completed' ? 'automation-chip--ok' : 'automation-chip--warn'}" style="margin-right:4px;">${escapeHtml(formatStatusLabel(job.last_status))}</span><span>${escapeHtml(formatDateTime(job.last_run_at))}</span>`
        : '<span style="color:var(--text-3);">Never</span>';
      const resumableRun = state.runs.find(run => Number(run.job_id) === Number(job.id) && isResumableRun(run));
      const runActionLabel = resumableRun ? 'Resume' : 'Run Now';
      return `
        <div class="automation-job${selected}">
          <button type="button" class="automation-card-select" data-job-id="${job.id}" aria-pressed="${selected ? 'true' : 'false'}">
            <div class="automation-job__top">
              <div class="automation-job__copy">
                <div class="automation-card-kind">Saved schedule</div>
                <div class="automation-job__title">${escapeHtml(displayName)}</div>
                <div class="automation-job__subtitle">${escapeHtml(job.site_label || activeSiteLabel())} - ${escapeHtml(scopeLabel)}</div>
              </div>
              <div class="automation-job__status">
                ${scheduleStatusChip(job)}
              </div>
            </div>
            <div class="automation-job__chips">
              <span class="automation-chip">${escapeHtml(job.interval_label || '')}</span>
              <span class="automation-chip">${escapeHtml(
                (job.skipped_target_count || 0) > 0
                  ? `${job.active_target_count || 0}/${job.target_count || 0} targets`
                  : `${job.target_count || 0} targets`
              )}</span>
              ${(job.skipped_target_count || 0) > 0 ? `<span class="automation-chip automation-chip--danger">${escapeHtml(`${job.skipped_target_count} skipped`)}</span>` : ''}
            </div>
            <div class="automation-job__meta">
              <div class="automation-meta">
                <span class="automation-meta__label">Next Run</span>
                <span class="automation-meta__value">${nextRunHtml}</span>
              </div>
              <div class="automation-meta">
                <span class="automation-meta__label">Last Run</span>
                <span class="automation-meta__value">${lastRunHtml}</span>
              </div>
            </div>
            ${job.last_error ? `<div class="automation-job__subtitle automation-job__error">${escapeHtml(job.last_error)}</div>` : ''}
          </button>
          <div class="automation-job__actions" aria-label="Job actions">
            <button type="button" class="btn-export automation-job__action" data-action="edit" data-job-id="${job.id}">Edit</button>
            <button type="button" class="btn-export automation-job__action${resumableRun ? ' automation-job__action--primary' : ''}" data-action="run" data-job-id="${job.id}">${runActionLabel}</button>
            <button type="button" class="btn-export automation-job__action" data-action="toggle" data-job-id="${job.id}">${job.enabled ? 'Pause' : 'Enable'}</button>
            <button type="button" class="btn-danger-sm automation-job__action" data-action="delete" data-job-id="${job.id}">Delete</button>
          </div>
        </div>
      `;
    }).join('');
  }

  function renderRuns(runs) {
    const container = elements.automationRuns;
    if (!container) return;
    syncActivityPanelCopy();
    const detailRun = state.runDetail?.run;
    state.runs = (Array.isArray(runs) ? runs : []).map(run => {
      if (!detailRun || Number(detailRun.id) !== Number(run.id)) return run;
      return {
        ...run,
        items_count: detailRun.items_count ?? run.items_count,
        summary: {
          ...(run.summary || {}),
          ...(detailRun.summary || {})
        }
      };
    });
    if (!state.runs.length) {
      container.innerHTML = `<div class="automation-run automation-empty-state"><div class="automation-run__title">No runs for ${escapeHtml(activeSiteLabel())}</div><div class="automation-run__subtitle">Run a job to capture the first snapshot.</div></div>`;
      return;
    }

    const renderRunCard = run => {
      const summary = run.summary || {};
      const selected = Number(run.id) === Number(state.selectedRunId) ? ' is-selected' : '';
      const runStatus = String(run.status || '').toLowerCase();
      const displayName = automationDisplayName(run);
      const totalTargets = Number(summary.total_targets || summary.target_count || (run.target_urls || []).length || 0);
      const completedTargets = Number(summary.completed_targets || 0);
      const timing = getRunTiming(run);
      const activeRunStatus = isCurrentRunStatus(runStatus);
      const progressPct = getRunProgressPercent(run);
      const phaseName = getRunPhaseName(run);
      const runKind = activeRunStatus ? 'Active run' : 'Run snapshot';
      const progressValue = activeRunStatus
        ? timing.progressText
        : String(summary.target_count || (run.target_urls || []).length || 0);
      const progressPercentLabel = `${progressPct.toFixed(0)}%`;
      const progressInlineLabel = activeRunStatus
        ? `${phaseName} - ${progressValue}`
        : progressValue;
      const timeValue = ['running', 'resuming'].includes(runStatus)
        ? `${timing.etaLabel} left`
        : activeRunStatus
          ? timing.elapsedLabel
          : (run.completed_at ? formatDuration(new Date(run.completed_at).getTime() - new Date(run.started_at || run.completed_at).getTime()) : 'N/A');
      const actionButtons = `
        ${runStatus === 'running' ? `<button type="button" class="btn-export automation-run__action" data-action="pause-run" data-run-id="${run.id}" aria-label="Pause run ${escapeHtml(displayName)}">Pause</button>` : ''}
        ${isResumableRun(run) ? `<button type="button" class="btn-export automation-run__action" data-action="resume-run" data-run-id="${run.id}" aria-label="Resume run ${escapeHtml(displayName)}">Resume</button>` : ''}
        <button type="button" class="btn-danger-sm automation-run__action" data-action="delete" data-run-id="${run.id}" aria-label="Delete run ${escapeHtml(displayName)}">Delete</button>
      `;
      return `
        <div class="automation-run${selected}">
          <button type="button" class="automation-card-select automation-run__select" data-run-id="${run.id}" aria-pressed="${selected ? 'true' : 'false'}">
            <div class="automation-run__top">
              <div style="min-width: 0; flex: 1;">
                ${activeRunStatus
                  ? '<div class="automation-card-kind">Active run</div>'
                  : '<div class="automation-card-kind">Run snapshot</div>'}
                <div class="automation-run__title">${escapeHtml(displayName)}</div>
                <div class="automation-run__subtitle">${escapeHtml(run.trigger_type)} - ${escapeHtml(formatDateTime(run.started_at))}</div>
              </div>
              <div class="automation-run__status">${statusChip(run.status)}</div>
            </div>
            <div class="automation-run__chips">
              <span class="automation-chip">${escapeHtml(`${summary.current_items || run.items_count || 0} items`)}</span>
              ${(Number(summary.changed) || Number(summary.added) || Number(summary.removed)) ? `
                ${Number(summary.changed) > 0 ? `<span class="automation-chip automation-chip--warn">${escapeHtml(`${summary.changed} changed`)}</span>` : ''}
                ${Number(summary.added) > 0 ? `<span class="automation-chip automation-chip--ok">${escapeHtml(`${summary.added} added`)}</span>` : ''}
                ${Number(summary.removed) > 0 ? `<span class="automation-chip automation-chip--danger">${escapeHtml(`${summary.removed} removed`)}</span>` : ''}
              ` : '<span class="automation-chip">No changes</span>'}
            </div>
            <div class="automation-run__meta">
              <div class="automation-meta">
                <span class="automation-meta__label">${activeRunStatus ? 'Phase' : 'Targets'}</span>
                <span class="automation-meta__value">${escapeHtml(activeRunStatus ? phaseName : progressValue)}</span>
              </div>
              <div class="automation-meta">
                <span class="automation-meta__label">${['running', 'resuming'].includes(runStatus) ? 'ETA' : activeRunStatus ? 'Elapsed' : 'Duration'}</span>
                <span class="automation-meta__value">${escapeHtml(timeValue)}</span>
              </div>
            </div>
            ${activeRunStatus ? `
              <div class="automation-run-progress" aria-label="${escapeHtml(`${phaseName} ${progressPercentLabel}`)}" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progressPct.toFixed(0)}">
                <div class="automation-run-progress__track">
                  <div class="automation-run-progress__fill" style="width:${progressPct.toFixed(1)}%"></div>
                  <div class="automation-run-progress__label">
                    <span>${escapeHtml(progressInlineLabel)}</span>
                    <strong>${escapeHtml(progressPercentLabel)}</strong>
                  </div>
                </div>
              </div>
            ` : ''}
          </button>
          <div class="automation-job__actions" aria-label="Run actions">${actionButtons}</div>
        </div>
      `;
    };
    const currentRuns = state.runs.filter(run => isCurrentRunStatus(run?.status));
    const pastRuns = state.runs.filter(run => !isCurrentRunStatus(run?.status));
    const groups = [
      currentRuns.length
        ? `<div class="automation-run-group"><div class="automation-run-group__heading">Current Runs</div>${currentRuns.map(renderRunCard).join('')}</div>`
        : '',
      pastRuns.length
        ? `<div class="automation-run-group"><div class="automation-run-group__heading">Past Snapshots</div>${pastRuns.map(renderRunCard).join('')}</div>`
        : ''
    ].filter(Boolean);
    container.innerHTML = groups.join('');
  }

  function isRunningStatus(value) {
    return ['running', 'resuming'].includes(String(value || '').trim().toLowerCase());
  }

  function isResumableRun(run) {
    const status = String(run?.status || '').trim().toLowerCase();
    return ['paused', 'interrupted', 'failed'].includes(status);
  }

  function hasRunningActivity() {
    return state.runs.some(run => isRunningStatus(run?.status))
      || state.allJobs.some(job => isRunningStatus(job?.last_status));
  }

  function refreshLiveClock() {
    if (!hasRunningActivity()) return;
    if (state.runs.length) {
      preserveLiveScroll(() => renderRuns(state.runs));
    }
  }

  function startRealtimeClock() {
    if (state.realtimeClockTimer) {
      window.clearInterval(state.realtimeClockTimer);
    }
    state.realtimeClockTimer = window.setInterval(refreshLiveClock, 1000);
  }

  function scheduleRealtimePoll(delayMs) {
    if (state.realtimePollTimer) {
      window.clearTimeout(state.realtimePollTimer);
    }
    state.realtimePollTimer = window.setTimeout(runRealtimePoll, Math.max(1000, delayMs));
  }

  async function runRealtimePoll() {
    if (state.realtimePollInFlight) {
      scheduleRealtimePoll(hasRunningActivity() ? ACTIVE_POLL_MS : IDLE_POLL_MS);
      return;
    }
    state.realtimePollInFlight = true;
    try {
      await loadJobs({ silent: true });
    } catch { }
    finally {
      state.realtimePollInFlight = false;
      scheduleRealtimePoll(hasRunningActivity() ? ACTIVE_POLL_MS : IDLE_POLL_MS);
    }
  }

  function startRealtimeUpdates() {
    startRealtimeClock();
    scheduleRealtimePoll(1000);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        scheduleRealtimePoll(1000);
      }
    });
  }

  function getRunTimestamp(run) {
    const candidates = [run?.started_at, run?.created_at, run?.completed_at];
    for (const value of candidates) {
      const timestamp = new Date(value || '').getTime();
      if (!Number.isNaN(timestamp) && timestamp > 0) return timestamp;
    }
    const idValue = Number(run?.id);
    return Number.isFinite(idValue) ? idValue : 0;
  }

  function collapseRunsByJob(runs) {
    const sortedRuns = (Array.isArray(runs) ? [...runs] : []).sort((left, right) => {
      const timeDiff = getRunTimestamp(right) - getRunTimestamp(left);
      if (timeDiff !== 0) return timeDiff;
      return Number(right?.id || 0) - Number(left?.id || 0);
    });
    const visibleRuns = [];
    const seenJobKeys = new Set();
    sortedRuns.forEach(run => {
      const numericJobId = Number(run?.job_id);
      const jobKey = Number.isFinite(numericJobId) && numericJobId > 0
        ? `job:${numericJobId}`
        : `run:${String(run?.id || '')}`;
      if (seenJobKeys.has(jobKey)) return;
      seenJobKeys.add(jobKey);
      visibleRuns.push(run);
    });
    return visibleRuns;
  }

  function getModelLabel(item) {
    const extra = item?.extra && typeof item.extra === 'object' ? item.extra : {};
    return item?.model_label
      || item?.target_label
      || extra.model_label
      || extra.target_label
      || formatCategoryLabelFromUrl(item?.target_url || extra.target_url)
      || item?.title
      || 'Uncategorized';
  }

  function formatCategoryLabelFromUrl(url) {
    try {
      const parsed = new URL(String(url || ''), window.location.origin);
      const segments = parsed.pathname.replace(/\.html$/i, '').split('/').filter(Boolean);
      const tail = segments.pop() || '';
      return tail
        .replace(/[-_]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .replace(/\b\w/g, char => char.toUpperCase());
    } catch {
      return '';
    }
  }

  function filterByModel(items, modelFilter) {
    if (!modelFilter) return items;
    return items.filter(item => {
      const candidate = item?.after || item?.before || item;
      return getModelLabel(candidate) === modelFilter;
    });
  }

  function formatChangeLabel(key) {
    const labels = {
      stock_status: 'Stock',
      price: 'Price',
      title: 'Title',
      sku: 'SKU',
      description: 'Description',
      url: 'URL'
    };
    return labels[key] || key.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
  }

  function formatChangeValue(key, change, side) {
    if (!change || typeof change !== 'object') return '--';
    if (key === 'price') {
      const formattedKey = side === 'before' ? 'before_formatted' : 'after_formatted';
      const formatted = change[formattedKey];
      if (formatted !== undefined && formatted !== null && String(formatted).trim()) return String(formatted);
    }
    const raw = change[side];
    if (raw === undefined || raw === null || String(raw).trim() === '') return '--';
    return String(raw);
  }

  function getChangedEntriesForView(changedEntries, changeView) {
    const entries = Array.isArray(changedEntries) ? changedEntries : [];
    if (!changeView || changeView === 'all') return entries;
    return entries.filter(entry => Object.prototype.hasOwnProperty.call(entry?.changes || {}, changeView));
  }

  function getChangeViewCounts(changedEntries, addedItems, removedItems, allProducts = []) {
    const changed = Array.isArray(changedEntries) ? changedEntries : [];
    const added = Array.isArray(addedItems) ? addedItems : [];
    const removed = Array.isArray(removedItems) ? removedItems : [];
    const products = Array.isArray(allProducts) ? allProducts : [];
    const duplicates = products.filter(item => item?.is_duplicate || (item?.duplicate_categories && item.duplicate_categories.length > 1));
    return {
      all: changed.length + added.length + removed.length,
      duplicates: duplicates.length,
      stock_status: getChangedEntriesForView(changed, 'stock_status').length,
      price: getChangedEntriesForView(changed, 'price').length,
      title: getChangedEntriesForView(changed, 'title').length,
      sku: getChangedEntriesForView(changed, 'sku').length,
      description: getChangedEntriesForView(changed, 'description').length,
      added: added.length,
      removed: removed.length
    };
  }

  function renderChangeFilterBar(changeCounts, activeChangeView, modelFilter) {
    const activeConfig = CHANGE_VIEW_CONFIG.find(config => config.key === activeChangeView) || CHANGE_VIEW_CONFIG[0];
    const visibleConfigs = CHANGE_VIEW_CONFIG.filter(config => {
      const count = Number(changeCounts?.[config.key] || 0);
      return config.key === 'all' || config.key === activeChangeView || count > 0;
    });
    return `
      <div class="automation-review">
        <div class="automation-review__header">
          <div>
            <div class="automation-change-group__title" style="margin-bottom:.2rem">Review Changes</div>
            <div class="automation-review__hint">
              ${escapeHtml(modelFilter || 'All models')}
            </div>
          </div>
          <div class="automation-review__active">${escapeHtml(activeConfig.label)}</div>
        </div>
        <div class="automation-review__filters">
          ${visibleConfigs.map(config => {
            const count = Number(changeCounts?.[config.key] || 0);
            const isActive = config.key === activeChangeView;
            return `
              <button
                type="button"
                class="automation-review-filter${isActive ? ' is-active' : ''}"
                data-change-view="${escapeHtml(config.key)}"
                aria-pressed="${isActive ? 'true' : 'false'}"
              >
                <span class="automation-review-filter__count">${escapeHtml(String(count))}</span>
                <span class="automation-review-filter__label">${escapeHtml(config.label)}</span>
              </button>
            `;
          }).join('')}
        </div>
      </div>
    `;
  }

  function renderReviewFilters(changeCounts = null, activeChangeView = state.selectedChangeView || 'all', modelFilter = '') {
    if (!elements.automationReviewFilters) return;
    const totalCount = changeCounts ? Object.values(changeCounts).reduce((sum, n) => sum + (Number(n) || 0), 0) : 0;
    if (!changeCounts || totalCount === 0) {
      elements.automationReviewFilters.innerHTML = '';
      elements.automationReviewFilters.classList.add('d-none');
      return;
    }
    elements.automationReviewFilters.classList.remove('d-none');
    elements.automationReviewFilters.innerHTML = renderChangeFilterBar(changeCounts, activeChangeView, modelFilter);
  }

  function renderChangedEntry(entry) {
    const after = entry.after || {};
    const before = entry.before || {};
    const title = after.title || before.title || 'Untitled Item';
    const model = getModelLabel(after.title ? after : before);
    const chips = Object.entries(entry.changes || {}).map(([key, value]) => {
      if (key === 'price') {
        return `<span class="automation-chip automation-chip--warn">${escapeHtml(`${formatChangeValue(key, value, 'before')} -> ${formatChangeValue(key, value, 'after')}`)}</span>`;
      }
      return `<span class="automation-chip">${escapeHtml(`${formatChangeLabel(key)} changed`)}</span>`;
    }).join('');
    const details = Object.entries(entry.changes || {}).map(([key, change]) => `
      <div class="automation-change__diff">
        <span class="automation-change__diff-label">${escapeHtml(formatChangeLabel(key))}</span>
        <span class="automation-change__diff-values">
          <span>${escapeHtml(formatChangeValue(key, change, 'before'))}</span>
          <span class="automation-change__diff-arrow">-></span>
          <span>${escapeHtml(formatChangeValue(key, change, 'after'))}</span>
        </span>
      </div>
    `).join('');
    return `
      <div class="automation-change">
        <div class="automation-change__model">${escapeHtml(model)}</div>
        <div class="automation-change__top">
          <div class="automation-change__title">${escapeHtml(title)}</div>
          ${after.url ? `<a class="automation-inline-link" href="${escapeHtml(after.url)}" target="_blank" rel="noreferrer">Open</a>` : ''}
        </div>
        <div class="automation-change__chips">${chips}</div>
        ${details ? `<div class="automation-change__diffs">${details}</div>` : ''}
      </div>
    `;
  }

  function renderSimpleItem(item, toneLabel) {
    const title = item?.title || 'Untitled Item';
    const model = getModelLabel(item);
    const stock = item?.stock_status ? `<span class="automation-chip">${escapeHtml(item.stock_status)}</span>` : '';
    const price = item?.price_formatted ? `<span class="automation-chip automation-chip--warn">${escapeHtml(item.price_formatted)}</span>` : '';
    return `
      <div class="automation-change">
        <div class="automation-change__model">${escapeHtml(model)}</div>
        <div class="automation-change__top">
          <div class="automation-change__title">${escapeHtml(title)}</div>
          ${item?.url ? `<a class="automation-inline-link" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">Open</a>` : ''}
        </div>
        <div class="automation-change__chips">
          <span class="automation-chip ${toneLabel === 'Added' ? 'automation-chip--ok' : 'automation-chip--danger'}">${escapeHtml(toneLabel)}</span>
          ${price}
          ${stock}
        </div>
      </div>
    `;
  }

  function formatProductPrice(item) {
    const candidates = [
      item?.discounted_formatted,
      item?.original_formatted,
      item?.price_formatted,
      item?.price_text
    ];
    for (const value of candidates) {
      const text = String(value ?? '').trim();
      if (!text) continue;
      const parsed = priceNumberFromText(text);
      if (parsed === 0) continue;
      return text;
    }
    const numeric = item?.discounted_value ?? item?.price_value ?? item?.original;
    if (numeric !== undefined && numeric !== null && Number(numeric) > 0) {
      const currency = item?.price_currency || '$';
      return `${currency === 'USD' ? '$' : currency}${Number(numeric).toFixed(2)}`;
    }
    return '';
  }

  function formatOriginalPrice(item) {
    for (const value of [item?.original_formatted, item?.price_text, formatProductPrice(item)]) {
      const text = String(value ?? '').trim();
      if (!text) continue;
      const parsed = priceNumberFromText(text);
      if (parsed === 0) continue;
      return text;
    }
    return '';
  }

  function formatFinalPrice(item) {
    return item?.discounted_formatted || formatProductPrice(item);
  }

  function compactProductText(value, maxLength = 220) {
    const text = String(value || '').replace(/\s+/g, ' ').trim();
    if (text.length <= maxLength) return text;
    return `${text.slice(0, maxLength - 1).trim()}...`;
  }

  function productImageSrc(item) {
    const src = String(item?.image_url || '').trim();
    if (!src || /\/woocommerce-placeholder(?:-\d+x\d+)?\.(?:png|jpe?g|webp)(?:[?#]|$)/i.test(src)) return '';
    return `/api/image-proxy?url=${encodeURIComponent(src)}`;
  }

  function productImageFallback(hidden = false) {
    return `<span class="automation-product-no-image" title="Supplier provided no product image" aria-label="No product image"${hidden ? ' hidden' : ''}>N/A</span>`;
  }

  function productSource(item) {
    if (item?.site) return item.site;
    if (item?.source) return item.source;
    if (item?.url) {
      try {
        const host = new URL(item.url, window.location.origin).hostname.replace(/^www\./i, '');
        const name = host.split('.')[0];
        if (name && name !== '127' && name !== 'localhost') return name;
      } catch {}
    }
    return state.activeSite || 'parts4cells';
  }

  function priceNumberFromText(value) {
    const match = String(value ?? '').replace(/,/g, '').match(/-?\d+(?:\.\d+)?/);
    if (!match) return null;
    const parsed = Number(match[0]);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function productPriceNumber(item) {
    for (const value of [item?.original, item?.original_value, item?.price_value, item?.discounted_value]) {
      const parsed = Number(value);
      if (Number.isFinite(parsed) && parsed > 0) return parsed;
    }
    for (const value of [item?.original_formatted, item?.price_text, item?.price_formatted, item?.discounted_formatted]) {
      const parsed = priceNumberFromText(value);
      if (parsed !== null && parsed > 0) return parsed;
    }
    return null;
  }

  function normalizeProductFilterText(value) {
    return String(value ?? '').replace(/\s+/g, ' ').trim().toLowerCase();
  }

  function productFieldValue(item, key) {
    if (key === 'image') return item?.image_url || '';
    if (key === 'title') return item?.title || '';
    if (key === 'sku') return item?.sku || '';
    if (key === 'category') return item?.category || getModelLabel(item) || '';
    if (key === 'description') return item?.description || '';
    if (key === 'original') return formatOriginalPrice(item);
    if (key === 'url') return item?.url || '';
    if (key === 'source') return productSource(item);
    return item?.[key] || '';
  }

  const PRODUCT_TABLE_COLUMNS = [
    { key: 'image', label: 'Image', sortable: false },
    { key: 'title', label: 'Title', sortable: true },
    { key: 'sku', label: 'SKU', sortable: true },
    { key: 'category', label: 'Category', sortable: true },
    { key: 'description', label: 'Description', sortable: true },
    { key: 'original', label: 'Price', sortable: true },
    { key: 'url', label: 'URL', sortable: false },
    { key: 'source', label: 'Source', sortable: true }
  ];

  function productExportRow(item, group = null) {
    return {
      image: item?.image_url || '',
      title: item?.title || '',
      sku: item?.sku || '',
      description: item?.description || '',
      original: formatOriginalPrice(item),
      url: item?.url || '',
      source: productSource(item),
      website: group?.site || productSource(item),
      category: group?.child || getModelLabel(item),
      change_type: item?._changeLabel || '',
      change_details: item?._changeDetails || ''
    };
  }

  function applyProductTableFilters(items) {
    let filtered = Array.isArray(items) ? [...items] : [];
    const search = normalizeProductFilterText(state.productFilters.search);
    if (search) {
      filtered = filtered.filter(item => {
        const haystack = [
          ...PRODUCT_TABLE_COLUMNS.map(column => productFieldValue(item, column.key)),
          getModelLabel(item)
        ].join(' ');
        return normalizeProductFilterText(haystack).includes(search);
      });
    }

    const mode = String(state.productFilters.mode || 'all');
    if (mode === 'duplicates') filtered = filtered.filter(item => item?.is_duplicate || (item?.duplicate_categories && item.duplicate_categories.length > 1));
    if (mode === 'unique_only') filtered = filtered.filter(item => !item?.is_duplicate && (!item?.duplicate_categories || item.duplicate_categories.length <= 1));
    if (mode === 'priced') filtered = filtered.filter(item => productPriceNumber(item) !== null);
    if (mode === 'missing_price') filtered = filtered.filter(item => productPriceNumber(item) === null);
    if (mode === 'with_sku') filtered = filtered.filter(item => normalizeProductFilterText(item?.sku));
    if (mode === 'missing_sku') filtered = filtered.filter(item => !normalizeProductFilterText(item?.sku));
    if (mode === 'with_image') filtered = filtered.filter(item => normalizeProductFilterText(item?.image_url));
    if (mode === 'missing_image') filtered = filtered.filter(item => !normalizeProductFilterText(item?.image_url));

    const source = normalizeProductFilterText(state.productFilters.source);
    if (source) {
      filtered = filtered.filter(item => normalizeProductFilterText(productSource(item)) === source);
    }

    const minPrice = priceNumberFromText(state.productFilters.minPrice);
    const maxPrice = priceNumberFromText(state.productFilters.maxPrice);
    if (minPrice !== null) {
      filtered = filtered.filter(item => {
        const price = productPriceNumber(item);
        return price !== null && price >= minPrice;
      });
    }
    if (maxPrice !== null) {
      filtered = filtered.filter(item => {
        const price = productPriceNumber(item);
        return price !== null && price <= maxPrice;
      });
    }

    const sortKey = state.productFilters.sortKey;
    if (sortKey) {
      const dir = state.productFilters.sortDir === 'desc' ? -1 : 1;
      const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
      filtered.sort((a, b) => {
        const aValue = productFieldValue(a, sortKey);
        const bValue = productFieldValue(b, sortKey);
        if (sortKey === 'original') {
          const aNum = productPriceNumber(a);
          const bNum = productPriceNumber(b);
          if (aNum === null && bNum === null) return 0;
          if (aNum === null) return 1;
          if (bNum === null) return -1;
          return (aNum - bNum) * dir;
        }
        return collator.compare(String(aValue || ''), String(bValue || '')) * dir;
      });
    }

    return filtered;
  }

  function hasProductTableFilters() {
    return Boolean(
      normalizeProductFilterText(state.productFilters.search) ||
      String(state.productFilters.mode || 'all') !== 'all' ||
      normalizeProductFilterText(state.productFilters.source) ||
      String(state.productFilters.minPrice || '').trim() ||
      String(state.productFilters.maxPrice || '').trim() ||
      state.productFilters.sortKey ||
      String(state.selectedChangeView || 'all') !== 'all' ||
      Boolean(elements.automationModelFilter?.value)
    );
  }

  function renderProductFilterToolbar(totalCount, filteredCount, items) {
    const mode = String(state.productFilters.mode || 'all');
    const source = String(state.productFilters.source || '');
    const sortValue = state.productFilters.sortKey
      ? `${state.productFilters.sortKey}:${state.productFilters.sortDir || 'asc'}`
      : '';
    const sources = [...new Set(
      (Array.isArray(items) ? items : [])
        .map(item => String(productSource(item) || '').trim())
        .filter(Boolean)
    )].sort((left, right) => left.localeCompare(right, undefined, { sensitivity: 'base' }));
    const selectedChangeView = String(state.selectedChangeView || 'all');
    const modelFilter = String(elements.automationModelFilter?.value || '');
    const activeControlCount = [
      normalizeProductFilterText(state.productFilters.search),
      mode !== 'all' ? mode : '',
      source,
      String(state.productFilters.minPrice || '').trim(),
      String(state.productFilters.maxPrice || '').trim(),
      sortValue,
      selectedChangeView !== 'all' ? selectedChangeView : '',
      modelFilter
    ].filter(Boolean).length;
    const status = filteredCount === totalCount
      ? `${totalCount.toLocaleString()} products`
      : `${filteredCount.toLocaleString()} of ${totalCount.toLocaleString()} products`;
    const option = (value, current, label) =>
      `<option value="${escapeHtml(value)}" ${value === current ? 'selected' : ''}>${escapeHtml(label)}</option>`;
    return `
      <div class="automation-product-toolbar" role="search">
        <div class="automation-product-toolbar__controls">
          <label class="automation-product-control automation-product-control--search">
            <span>Find products</span>
            <input
              type="search"
              data-product-search
              value="${escapeHtml(state.productFilters.search || '')}"
              placeholder="Title, SKU, description, model or URL"
              autocomplete="off"
            >
          </label>
          <label class="automation-product-control">
            <span>Show</span>
            <select data-product-mode>
              ${option('all', mode, 'All products')}
              ${option('duplicates', mode, 'Duplicate category listings')}
              ${option('unique_only', mode, 'Unique products only')}
              ${option('priced', mode, 'With price')}
              ${option('missing_price', mode, 'Missing price')}
              ${option('with_sku', mode, 'With SKU')}
              ${option('missing_sku', mode, 'Missing SKU')}
              ${option('with_image', mode, 'With image')}
              ${option('missing_image', mode, 'Missing image')}
            </select>
          </label>
          <label class="automation-product-control">
            <span>Source</span>
            <select data-product-source>
              ${option('', source, 'All sources')}
              ${sources.map(value => option(value, source, value)).join('')}
            </select>
          </label>
          <label class="automation-product-control">
            <span>Min price</span>
            <input type="number" min="0" step="0.01" inputmode="decimal" data-product-min-price
              value="${escapeHtml(state.productFilters.minPrice || '')}" placeholder="No min">
          </label>
          <label class="automation-product-control">
            <span>Max price</span>
            <input type="number" min="0" step="0.01" inputmode="decimal" data-product-max-price
              value="${escapeHtml(state.productFilters.maxPrice || '')}" placeholder="No max">
          </label>
          <label class="automation-product-control automation-product-control--sort">
            <span>Sort</span>
            <select data-product-sort-select>
              ${option('', sortValue, 'Default order')}
              ${option('title:asc', sortValue, 'Title A to Z')}
              ${option('title:desc', sortValue, 'Title Z to A')}
              ${option('original:asc', sortValue, 'Price low to high')}
              ${option('original:desc', sortValue, 'Price high to low')}
              ${option('source:asc', sortValue, 'Source A to Z')}
            </select>
          </label>
          <label class="automation-product-control automation-product-control--rows">
            <span>Rows</span>
            <select data-product-page-size>
              ${[50, 100, 250, 500].map(value => option(String(value), String(state.productFilters.pageSize || 100), String(value))).join('')}
            </select>
          </label>
        </div>
        <div class="automation-product-toolbar__footer">
          <div class="automation-product-toolbar__meta" aria-live="polite">
            <strong>${escapeHtml(status)}</strong>
            <span>${activeControlCount ? `${activeControlCount} active control${activeControlCount === 1 ? '' : 's'}` : 'No filters applied'}</span>
          </div>
          <button type="button" class="btn-export automation-product-clear" data-product-clear ${hasProductTableFilters() ? '' : 'disabled'}>Reset filters</button>
        </div>
      </div>
    `;
  }

  function renderProductHeaderCell(column) {
    const isSorted = state.productFilters.sortKey === column.key;
    const ariaSort = isSorted
      ? (state.productFilters.sortDir === 'desc' ? 'descending' : 'ascending')
      : 'none';
    if (!column.sortable) {
      return `<th aria-sort="none">${escapeHtml(column.label)}</th>`;
    }
    return `
      <th aria-sort="${ariaSort}">
        <button type="button" class="automation-product-sort${isSorted ? ' is-active' : ''}" data-product-sort="${escapeHtml(column.key)}">
          <span>${escapeHtml(column.label)}</span>
          <span class="automation-product-sort__indicator" aria-hidden="true">${isSorted ? (state.productFilters.sortDir === 'desc' ? '&#9660;' : '&#9650;') : '&#8645;'}</span>
        </button>
      </th>
    `;
  }

  function productTableSummary(totalCount, filteredCount, startIndex, endIndex) {
    if (!totalCount) return '';
    const range = filteredCount ? `${startIndex + 1}-${endIndex}` : '0';
    const scopeParts = [];
    const changeView = String(state.selectedChangeView || 'all');
    if (changeView !== 'all') {
      const config = CHANGE_VIEW_CONFIG.find(item => item.key === changeView);
      scopeParts.push(config?.label || formatChangeLabel(changeView));
    }
    const model = String(elements.automationModelFilter?.value || '').trim();
    if (model) scopeParts.push(model);
    const scope = scopeParts.length ? ` in ${scopeParts.join(' / ')}` : '';
    if (filteredCount !== totalCount) {
      return `Showing ${range} of ${filteredCount.toLocaleString()} matching products${scope} (${totalCount.toLocaleString()} in this view).`;
    }
    return `Showing ${range} of ${totalCount.toLocaleString()} products${scope}.`;
  }

  function renderProductPagination(filteredCount, page, pageSize) {
    const totalPages = Math.max(1, Math.ceil(filteredCount / pageSize));
    if (totalPages <= 1) return '';
    return `
      <nav class="automation-product-pagination" aria-label="Product table pages">
        <button type="button" class="btn-export" data-product-page="previous" ${page <= 1 ? 'disabled' : ''}>Previous</button>
        <span>Page <strong>${page.toLocaleString()}</strong> of ${totalPages.toLocaleString()}</span>
        <button type="button" class="btn-export" data-product-page="next" ${page >= totalPages ? 'disabled' : ''}>Next</button>
      </nav>
    `;
  }

  function setProductExportRows(rows) {
    state.productExportRows = Array.isArray(rows) ? rows : [];
    const hasRows = state.productExportRows.length > 0;
    if (elements.automationProductsCsvBtn) elements.automationProductsCsvBtn.disabled = !hasRows;
    if (elements.automationProductsXlsxBtn) elements.automationProductsXlsxBtn.disabled = !hasRows;
  }

  function renderProductTable(items, { groups = null } = {}) {
    const container = elements.automationScrapedProducts;
    if (!container) return;
    const allItems = Array.isArray(items) ? items : [];
    const filteredItems = applyProductTableFilters(allItems);
    const pageSize = [50, 100, 250, 500].includes(Number(state.productFilters.pageSize))
      ? Number(state.productFilters.pageSize)
      : 100;
    const totalPages = Math.max(1, Math.ceil(filteredItems.length / pageSize));
    const page = Math.min(Math.max(1, Number(state.productFilters.page) || 1), totalPages);
    const startIndex = (page - 1) * pageSize;
    const endIndex = Math.min(startIndex + pageSize, filteredItems.length);
    const visibleItems = filteredItems.slice(startIndex, endIndex);
    state.productFilters.page = page;
    state.productFilters.pageSize = pageSize;
    const rows = filteredItems.map(item => {
      const group = item?._verificationGroup || null;
      return productExportRow(item, group);
    });
    setProductExportRows(rows);

    if (!allItems.length) {
      container.className = 'automation-products automation-products--empty';
      container.textContent = 'No products to show.';
      return;
    }

    container.className = 'automation-products';
    const toolbarMarkup = renderProductFilterToolbar(allItems.length, filteredItems.length, allItems);
    const finalSummary = productTableSummary(allItems.length, filteredItems.length, startIndex, endIndex);
    const summaryMarkup = finalSummary ? `<div class="automation-products__summary">${escapeHtml(finalSummary)}</div>` : '';
    const paginationMarkup = renderProductPagination(filteredItems.length, page, pageSize);
    const groupMarkup = Array.isArray(groups) && groups.length ? `
      <div class="automation-verification-groups">
        ${groups.map(group => `
          <div class="automation-model-badge">
            <div class="automation-model-badge__name">${escapeHtml(`${group.site || 'site'} - ${group.child || 'category'}`)}</div>
            <div class="automation-model-badge__meta">${escapeHtml(`${group.items_count || 0} products - ${group.history_id || ''}`)}</div>
          </div>
        `).join('')}
      </div>
    ` : '';

    container.innerHTML = `
      ${toolbarMarkup}
      ${summaryMarkup}
      ${groupMarkup}
      ${!visibleItems.length ? `<div class="automation-products__no-match">No products match the current filters.</div>` : ''}
      ${visibleItems.length ? `
      <div class="automation-product-table-wrap">
        <table class="automation-product-table">
          <thead>
            <tr>
              ${PRODUCT_TABLE_COLUMNS.map(renderProductHeaderCell).join('')}
            </tr>
          </thead>
          <tbody>
            ${visibleItems.map(item => {
              const image = productImageSrc(item);
              const title = item?.title || 'Untitled product';
              const sku = item?.sku || '';
              const category = item?.category || getModelLabel(item) || 'General';
              const duplicateCats = (item?.duplicate_categories || []).filter(Boolean);
              const showDuplicateBadge = duplicateCats.length > 1;
              const description = compactProductText(item?.description || '');
              const changeDetails = compactProductText(item?._changeDetails || '', 260);
              const original = formatOriginalPrice(item);
              const source = productSource(item);
              return `
                <tr>
                  <td class="automation-product-table__image">
                    ${image
                      ? `<img data-product-image src="${escapeHtml(image)}" alt="" title="${escapeHtml(title)}" loading="lazy">${productImageFallback(true)}`
                      : productImageFallback()}
                  </td>
                  <td class="automation-product-table__title">${escapeHtml(title)}</td>
                  <td>${escapeHtml(sku || '-')}</td>
                  <td class="automation-product-table__category">
                    <span class="automation-chip">${escapeHtml(category)}</span>
                    ${showDuplicateBadge ? `
                      <div class="mt-1">
                        <span class="automation-chip automation-chip--info" title="${escapeHtml(`Found in ${duplicateCats.length} categories: ${duplicateCats.join(', ')}`)}">
                          ${escapeHtml(`${duplicateCats.length} categories`)}
                        </span>
                      </div>
                    ` : ''}
                  </td>
                  <td class="automation-product-table__description" title="${escapeHtml([item?.description || '', item?._changeDetails || ''].filter(Boolean).join(' | '))}">
                    ${description ? `<div>${escapeHtml(description)}</div>` : ''}
                    ${changeDetails ? `<div class="automation-product-diff-note">${escapeHtml(changeDetails)}</div>` : ''}
                    ${!description && !changeDetails ? '-' : ''}
                  </td>
                  <td>${escapeHtml(original || '-')}</td>
                  <td>${item?.url ? `<a class="automation-product-open" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">Open</a>` : '-'}</td>
                  <td><span class="automation-chip automation-chip--ok">${escapeHtml(source || 'parts4cells')}</span></td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
      ${paginationMarkup}
      ` : ''}
    `;
  }

  function csvEscape(value) {
    const text = String(value ?? '');
    return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  }

  function rowsToCsv(rows) {
    const headers = ['image', 'title', 'sku', 'description', 'original', 'url', 'source', 'website', 'category', 'change_type', 'change_details'];
    return [
      headers.join(','),
      ...rows.map(row => headers.map(header => csvEscape(row[header])).join(','))
    ].join('\r\n');
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function exportTimestamp() {
    return new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  }

  async function exportProductsCsv() {
    if (!state.productExportRows.length) {
      showAlert('warn', 'No products to export.');
      return;
    }
    downloadBlob(
      new Blob([rowsToCsv(state.productExportRows)], { type: 'text/csv;charset=utf-8;' }),
      `automation_products_${exportTimestamp()}.csv`
    );
    showAlert('success', `Exported ${state.productExportRows.length} products as CSV.`);
  }

  async function exportProductsXlsx() {
    if (!state.productExportRows.length) {
      showAlert('warn', 'No products to export.');
      return;
    }
    const button = elements.automationProductsXlsxBtn;
    const oldText = button?.textContent || 'XLSX';
    try {
      if (button) {
        button.disabled = true;
        button.textContent = 'Exporting...';
      }
      const response = await fetch('/api/export/xlsx', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows: state.productExportRows })
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || `Export failed (${response.status})`);
      }
      const blob = await response.blob();
      downloadBlob(blob, `automation_products_${exportTimestamp()}.xlsx`);
      showAlert('success', `Exported ${state.productExportRows.length} products as XLSX.`);
    } catch (err) {
      showAlert('error', err.message || 'XLSX export failed.');
    } finally {
      if (button) {
        button.textContent = oldText;
        button.disabled = state.productExportRows.length === 0;
      }
    }
  }

  function getChangeDetailsForEntry(entry, selectedChangeView = 'all') {
    const changes = entry?.changes || {};
    return Object.entries(changes)
      .filter(([key]) => selectedChangeView === 'all' || key === selectedChangeView)
      .map(([key, change]) => `${formatChangeLabel(key)}: ${formatChangeValue(key, change, 'before')} -> ${formatChangeValue(key, change, 'after')}`)
      .join(' | ');
  }

  function changedEntryToProduct(entry, selectedChangeView = 'all') {
    const after = entry?.after || {};
    const before = entry?.before || {};
    const product = { ...before, ...after };
    const changes = entry?.changes || {};
    const activeKeys = Object.keys(changes).filter(key => selectedChangeView === 'all' || key === selectedChangeView);
    const firstKey = activeKeys[0] || Object.keys(changes)[0] || 'changed';
    const priceChange = changes.price;
    if (priceChange) {
      product.original_formatted = priceChange.before_formatted || formatChangeValue('price', priceChange, 'before');
      product.discounted_formatted = priceChange.after_formatted || formatChangeValue('price', priceChange, 'after');
      product.price_formatted = product.discounted_formatted;
      product.price_text = product.discounted_formatted;
    }
    product._changeLabel = selectedChangeView === 'all' ? 'Changed' : formatChangeLabel(firstKey);
    product._changeDetails = getChangeDetailsForEntry(entry, selectedChangeView) || `${product._changeLabel} changed`;
    return product;
  }

  function simpleDifferenceProduct(item, toneLabel) {
    return {
      ...(item || {}),
      _changeLabel: toneLabel,
      _changeDetails: `${toneLabel} item`
    };
  }

  function getDifferenceProductRows(detail, modelFilter, selectedChangeView) {
    const comparison = detail?.comparison || {};
    const allChanged = filterByModel(comparison.changed || [], modelFilter);
    const allAdded = filterByModel(comparison.added || [], modelFilter);
    const allRemoved = filterByModel(comparison.removed || [], modelFilter);
    const view = selectedChangeView || 'all';
    const changed = getChangedEntriesForView(allChanged, view).map(entry => changedEntryToProduct(entry, view));
    const added = view === 'all' || view === 'added' ? allAdded.map(item => simpleDifferenceProduct(item, 'Added')) : [];
    const removed = view === 'all' || view === 'removed' ? allRemoved.map(item => simpleDifferenceProduct(item, 'Removed')) : [];
    return [...changed, ...added, ...removed];
  }

  function renderScrapedProducts(detail) {
    const container = elements.automationScrapedProducts;
    if (!container) return;

    if (!detail || !detail.run) {
      setProductExportRows([]);
      container.className = 'automation-products automation-products--empty';
      container.textContent = 'Select a past run to see scraped products.';
      return;
    }

    const modelFilter = elements.automationModelFilter?.value || '';
    const selectedChangeView = state.selectedChangeView || 'all';
    const allItems = Array.isArray(detail.current_history?.items) ? detail.current_history.items : [];
    const livePreview = Boolean(detail.current_history?.is_live_preview);
    const runTotalItems = Number(
      detail.current_history?.items_count
      || detail.run?.summary?.current_items
      || detail.run?.items_count
      || allItems.length
      || 0
    );
    const isDuplicateView = selectedChangeView === 'duplicates';
    const differenceItems = isDuplicateView ? [] : getDifferenceProductRows(detail, modelFilter, selectedChangeView);
    const shouldShowDifferences = selectedChangeView !== 'all' && !isDuplicateView;
    let productItems = filterByModel(allItems, modelFilter);
    if (isDuplicateView) {
      productItems = productItems.filter(item => item?.is_duplicate || (item?.duplicate_categories && item.duplicate_categories.length > 1));
    }
    const items = shouldShowDifferences ? differenceItems : productItems;
    const activeConfig = CHANGE_VIEW_CONFIG.find(config => config.key === selectedChangeView) || CHANGE_VIEW_CONFIG[0];
    if (!items.length) {
      setProductExportRows([]);
      container.className = 'automation-products automation-products--empty';
      container.textContent = shouldShowDifferences
        ? (modelFilter
          ? `No products match ${activeConfig.label.toLowerCase()} for the selected model.`
          : `No products match ${activeConfig.label.toLowerCase()} for this run.`)
        : (modelFilter
          ? 'No scraped products match the selected model.'
          : (livePreview && runTotalItems
            ? `Live preview products are still loading. Run total is ${runTotalItems} item${runTotalItems === 1 ? '' : 's'} so far.`
            : 'No scraped products were saved for this run yet.'));
      return;
    }

    container.className = 'automation-products';
    renderProductTable(items);
  }

  function resetProductFilters() {
    const pageSize = Number(state.productFilters.pageSize) || 100;
    state.productFilters = {
      search: '',
      mode: 'all',
      source: '',
      minPrice: '',
      maxPrice: '',
      sortKey: '',
      sortDir: 'asc',
      page: 1,
      pageSize
    };
  }

  function resetAllProductFilters() {
    resetProductFilters();
    state.selectedChangeView = 'all';
    if (elements.automationModelFilter) elements.automationModelFilter.value = '';
  }

  function restoreProductFilterFocus(focusState) {
    if (!focusState || !elements.automationScrapedProducts) return;
    if (focusState.kind === 'search') {
      const input = elements.automationScrapedProducts.querySelector('[data-product-search]');
      if (!input) return;
      input.focus({ preventScroll: true });
      try {
        input.setSelectionRange(focusState.start, focusState.end);
      } catch { }
      return;
    }
    if (focusState.kind !== 'control') return;
    const input = elements.automationScrapedProducts.querySelector(focusState.selector);
    if (!input) return;
    input.focus({ preventScroll: true });
    try {
      input.setSelectionRange(focusState.start, focusState.end);
    } catch { }
  }

  function scheduleProductTableRender(focusState = null) {
    window.clearTimeout(state.productFilterTimer);
    state.productFilterTimer = window.setTimeout(() => {
      renderRunDetail(state.runDetail);
      window.requestAnimationFrame(() => restoreProductFilterFocus(focusState));
    }, 220);
  }

  function renderVerificationProducts(payload) {
    const container = elements.automationScrapedProducts;
    if (!container) return;
    const groups = Array.isArray(payload?.groups) ? payload.groups : [];
    const items = groups.flatMap(group => {
      const groupItems = Array.isArray(group.items) ? group.items : [];
      return groupItems.map(item => ({ ...item, _verificationGroup: group }));
    });
    if (!items.length) {
      setProductExportRows([]);
      container.className = 'automation-products automation-products--empty';
      container.textContent = 'No verification products are available yet.';
      return;
    }

    renderProductTable(items, { groups });
  }

  async function loadVerificationProducts({ silent = false } = {}) {
    try {
      const payload = await api('/api/automation/verification-products');
      renderVerificationProducts(payload);
      if (!state.selectedRunId && elements.automationRunDetail) {
        elements.automationRunDetail.className = 'automation-run-detail automation-run-detail--empty';
        elements.automationRunDetail.textContent = 'Verification products are shown above. Run an automation job to compare differences.';
      }
    } catch (err) {
      if (!silent) showAlert('error', err.message || 'Failed to load verification products.');
    }
  }

  function renderRunDetail(detail) {
    const container = elements.automationRunDetail;
    const modelFilter = elements.automationModelFilter?.value || '';
    if (!container) return;
    state.runDetail = detail;

    if (!detail || !detail.run) {
      renderReviewFilters(null);
      renderScrapedProducts(null);
      container.className = 'automation-run-detail automation-run-detail--empty';
      container.textContent = 'Select a run to load its differences.';
      return;
    }
    renderScrapedProducts(detail);

    const comparison = detail.comparison || { summary: {}, changed: [], added: [], removed: [] };
    const summary = comparison.summary || {};
    const run = detail.run || {};
    const runStatus = String(run.status || 'idle').toLowerCase();
    const runSummary = run.summary || {};
    const targetCount = Number(runSummary.total_targets || runSummary.target_count || (run.target_urls || []).length || 0);
    const completedTargets = Number(runSummary.completed_targets || 0);
    const timing = getRunTiming(run);
    const liveRunStatus = ['running', 'resuming'].includes(runStatus);
    const currentRunStatus = isCurrentRunStatus(runStatus);
    const completionLabel = liveRunStatus
      ? 'Progress'
      : runStatus === 'paused'
        ? 'Paused'
        : runStatus === 'interrupted'
          ? 'Interrupted'
          : 'Completed';
    const completionValue = run.completed_at
      ? formatDateTime(run.completed_at)
      : runStatus === 'paused' && runSummary.paused_at
        ? formatDateTime(runSummary.paused_at)
        : liveRunStatus
          ? 'In progress'
          : runStatus === 'interrupted'
            ? 'Waiting to resume'
            : 'Not completed';
    const comparisonPending = Boolean(detail.current_history?.is_live_preview)
      && currentRunStatus;
    const models = Array.isArray(detail.models) ? detail.models : [];
    const allProducts = Array.isArray(detail.current_history?.items) ? detail.current_history.items : [];
    const allChanged = filterByModel(comparison.changed || [], modelFilter);
    const allAdded = filterByModel(comparison.added || [], modelFilter);
    const allRemoved = filterByModel(comparison.removed || [], modelFilter);
    const changeCounts = getChangeViewCounts(allChanged, allAdded, allRemoved, allProducts);
    const selectedChangeView = state.selectedChangeView || 'all';
    renderReviewFilters(comparisonPending ? null : changeCounts, selectedChangeView, modelFilter);
    const changed = getChangedEntriesForView(allChanged, selectedChangeView);
    const added = selectedChangeView === 'all' || selectedChangeView === 'added' ? allAdded : [];
    const removed = selectedChangeView === 'all' || selectedChangeView === 'removed' ? allRemoved : [];
    const activeViewLabel = (CHANGE_VIEW_CONFIG.find(config => config.key === selectedChangeView) || CHANGE_VIEW_CONFIG[0]).label;
    const emptyMessage = selectedChangeView === 'all'
      ? (comparisonPending
        ? 'The product checkpoint is safe. Differences will be calculated when this run completes.'
        : modelFilter ? 'No changes match the selected model.' : 'No changes were found for this run.')
      : (modelFilter
        ? `No ${activeViewLabel.toLowerCase()} match the selected model.`
        : `No ${activeViewLabel.toLowerCase()} were found for this run.`);

    const totalHarvested = Number(runSummary.current_items || run.items_count || summary.current_items || 0);
    const currentPhase = Number(runSummary.phase || (liveRunStatus ? 1 : 3));
    const isCompleted = !liveRunStatus;

    let phaseName = getRunPhaseName(run);
    let activeSpeed = timing.rateLabel || 'Done';
    let activeEta = timing.etaLabel || 'Done';
    let activeRemaining = '0 items';
    let activeProgressText = `${totalHarvested > 0 ? totalHarvested.toLocaleString() : '0'} products`;
    let activeProgressPct = getRunProgressPercent(run);
    let stepCountLabel = 'Categories Done';
    let stepCountValue = `${completedTargets} / ${targetCount}`;

    if (liveRunStatus) {
      if (currentPhase === 2) {
        phaseName = getRunPhaseName(run);
        const p2Done = Number(runSummary.phase2_completed || totalHarvested || 0);
        const p2Total = Number(runSummary.phase2_total || totalHarvested || 1);
        activeProgressPct = getRunProgressPercent(run);
        activeProgressText = `${p2Done.toLocaleString()} / ${p2Total.toLocaleString()} products`;
        activeSpeed = runSummary.phase2_speed || (timing.itemsPerMin ? `${timing.itemsPerMin} items/min` : '~440 items/min');
        activeEta = runSummary.phase2_eta || timing.etaLabel || '1.4m';
        activeRemaining = `${Math.max(0, p2Total - p2Done).toLocaleString()} products`;
        stepCountLabel = 'Products Enriched';
        stepCountValue = `${p2Done.toLocaleString()} / ${p2Total.toLocaleString()}`;
      } else if (currentPhase === 1) {
        phaseName = getRunPhaseName(run);
        const p1Done = Number(runSummary.phase1_completed || completedTargets || 0);
        const p1Total = Number(runSummary.phase1_total || targetCount || 1);
        activeProgressPct = getRunProgressPercent(run);
        activeProgressText = `${p1Done} / ${p1Total} categories`;
        activeSpeed = runSummary.phase1_speed || (timing.targetsPerMin ? `${timing.targetsPerMin} cats/min` : '~45 cats/min');
        activeEta = runSummary.phase1_eta || timing.etaLabel || '20.0m';
        activeRemaining = `${Math.max(0, p1Total - p1Done)} categories`;
        stepCountLabel = 'Categories Done';
        stepCountValue = `${p1Done} / ${p1Total}`;
      } else {
        phaseName = getRunPhaseName(run);
        activeSpeed = currentPhase >= 4 ? 'Writing database' : 'Validating';
        activeEta = 'Final step';
        activeRemaining = currentPhase >= 4 ? 'Saving snapshot' : 'Preparing comparison';
        activeProgressText = `${totalHarvested.toLocaleString()} products collected`;
        activeProgressPct = getRunProgressPercent(run);
        stepCountLabel = 'Status';
        stepCountValue = currentPhase >= 4 ? 'Saving SQLite' : 'Comparing';
      }
    }

    const activeProgressPercentLabel = `${activeProgressPct.toFixed(0)}%`;
    const activeProgressInlineLabel = `${phaseName} - ${activeProgressText}`;

    container.className = 'automation-run-detail';
    container.innerHTML = `
      <div class="automation-detail-summary">
        <div class="automation-detail-card">
          <div class="automation-detail-card__value">${escapeHtml(totalHarvested > 0 ? totalHarvested.toLocaleString() : '0')}</div>
          <div class="automation-detail-card__label">${liveRunStatus ? 'Harvested Products' : 'Unique Products'}</div>
        </div>
        ${Number(summary.current_rows || 0) > totalHarvested ? `
          <div class="automation-detail-card">
            <div class="automation-detail-card__value">${escapeHtml(Number(summary.current_rows).toLocaleString())}</div>
            <div class="automation-detail-card__label">Scraped Rows</div>
          </div>
        ` : ''}
        <div class="automation-detail-card">
          <div class="automation-detail-card__value">${escapeHtml(String(summary.changed || 0))}</div>
          <div class="automation-detail-card__label">Changed</div>
        </div>
        <div class="automation-detail-card">
          <div class="automation-detail-card__value">${escapeHtml(String(summary.added || 0))}</div>
          <div class="automation-detail-card__label">Added</div>
        </div>
        <div class="automation-detail-card">
          <div class="automation-detail-card__value">${escapeHtml(String(summary.removed || 0))}</div>
          <div class="automation-detail-card__label">Removed</div>
        </div>
        ${liveRunStatus ? `
          <div class="automation-detail-card">
            <div class="automation-detail-card__value" style="color:var(--primary); font-weight:700;">${escapeHtml(activeEta)}</div>
            <div class="automation-detail-card__label">Total Time Left</div>
          </div>
          <div class="automation-detail-card">
            <div class="automation-detail-card__value">${escapeHtml(stepCountValue)}</div>
            <div class="automation-detail-card__label">${escapeHtml(stepCountLabel)}</div>
          </div>
        ` : ''}
      </div>
      ${liveRunStatus ? `
        <div class="automation-run-progress automation-run-progress--detail" aria-label="${escapeHtml(`${phaseName} ${activeProgressPercentLabel}`)}" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${activeProgressPct.toFixed(0)}">
          <div class="automation-run-progress__track">
            <div class="automation-run-progress__fill" style="width:${activeProgressPct.toFixed(1)}%"></div>
            <div class="automation-run-progress__label">
              <span>${escapeHtml(activeProgressInlineLabel)}</span>
              <strong>${escapeHtml(activeProgressPercentLabel)}</strong>
            </div>
          </div>
        </div>
      ` : ''}
      ${Number(summary.excluded_previous_non_products || 0) || Number(summary.duplicate_current_rows || 0) || Number(summary.out_of_scope_previous_products || 0) ? `
        <div class="automation-comparison-note" role="status">
          ${escapeHtml(
            [
              Number(summary.excluded_previous_non_products || 0)
                ? `${summary.excluded_previous_non_products} previous category/navigation rows excluded`
                : '',
              Number(summary.duplicate_current_rows || 0)
                ? `${summary.duplicate_current_rows} repeated current rows consolidated`
                : ''
              ,
              Number(summary.out_of_scope_previous_products || 0)
                ? `${summary.out_of_scope_previous_products} previous product outside this run's target scope`
                : ''
            ].filter(Boolean).join(' - ')
          )}
        </div>
      ` : ''}
      <div class="automation-job__meta" style="margin-bottom:1rem">
        <div class="automation-meta">
          <span class="automation-meta__label">Started</span>
          <span class="automation-meta__value">${escapeHtml(formatDateTime(run.started_at))}</span>
        </div>
        ${liveRunStatus ? '' : `
          <div class="automation-meta">
            <span class="automation-meta__label">${escapeHtml(completionLabel)}</span>
            <span class="automation-meta__value">${escapeHtml(completionValue)}</span>
          </div>
        `}
        <div class="automation-meta">
          <span class="automation-meta__label">Targets</span>
          <span class="automation-meta__value">${escapeHtml(String(targetCount))}</span>
        </div>
        ${liveRunStatus ? `
          <div class="automation-meta">
            <span class="automation-meta__label">Elapsed</span>
            <span class="automation-meta__value">${escapeHtml(timing.elapsedLabel)}</span>
          </div>
          <div class="automation-meta">
            <span class="automation-meta__label">Remaining</span>
            <span class="automation-meta__value">${escapeHtml(activeRemaining)}</span>
          </div>
          <div class="automation-meta">
            <span class="automation-meta__label">Speed</span>
            <span class="automation-meta__value">${escapeHtml(activeSpeed)}</span>
          </div>
          <div class="automation-meta">
            <span class="automation-meta__label">Estimated Finish</span>
            <span class="automation-meta__value">${escapeHtml(timing.finishLabel || (activeEta + ' remaining'))}</span>
          </div>
        ` : ''}
        <div class="automation-meta">
          <span class="automation-meta__label">Current Session</span>
          <span class="automation-meta__value">${escapeHtml(
            detail.current_history?.id
            || (comparisonPending ? `Live checkpoint (${runSummary.current_items || run.items_count || 0} products)` : 'N/A')
          )}</span>
        </div>
        <div class="automation-meta">
          <span class="automation-meta__label">Previous Session</span>
          <span class="automation-meta__value">${escapeHtml(detail.previous_history?.id || 'First run')}</span>
        </div>
      </div>
      ${models.length ? `
        <div class="automation-model-summary">
          ${models.map(model => `
            <div class="automation-model-badge">
              <div class="automation-model-badge__name">${escapeHtml(model.model)}</div>
              <div class="automation-model-badge__meta">${escapeHtml(`${model.changed || 0} changed - ${model.added || 0} added - ${model.removed || 0} removed`)}</div>
            </div>
          `).join('')}
        </div>
      ` : ''}
      ${selectedChangeView === 'duplicates' ? `
        <div class="automation-change-group">
          <div class="automation-change-group__title">Duplicate Category Listings (${changeCounts.duplicates.toLocaleString()})</div>
          <div class="alert alert-info py-2 px-3 mb-3 d-flex justify-content-between align-items-center" style="font-size:0.9rem; border-radius:8px;">
            <span>Showing products that appear in multiple category listings.</span>
            <button type="button" class="btn btn-sm btn-primary" onclick="if(window.switchToTab) window.switchToTab('table-view');">Open Full Products Table</button>
          </div>
          <div class="automation-change-list">
            ${allProducts.filter(item => item?.is_duplicate || (item?.duplicate_categories && item.duplicate_categories.length > 1)).slice(0, 100).map(item => `
              <div class="automation-change">
                <div class="automation-change__model">${escapeHtml(item.category || getModelLabel(item) || 'General')}</div>
                <div class="automation-change__top">
                  <div class="automation-change__title">${escapeHtml(item.title || 'Untitled Item')}</div>
                  ${item.url ? `<a class="automation-inline-link" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">Open</a>` : ''}
                </div>
                <div class="automation-change__chips">
                  <span class="automation-chip automation-chip--info">${escapeHtml(`${item.duplicate_count || (item.duplicate_categories || []).length || 2} categories`)}</span>
                  ${(item.duplicate_categories || []).map(cat => `<span class="automation-chip">${escapeHtml(cat)}</span>`).join('')}
                  ${item.sku ? `<span class="automation-chip">SKU: ${escapeHtml(item.sku)}</span>` : ''}
                  ${item.discounted_formatted || item.original_formatted ? `<span class="automation-chip automation-chip--warn">${escapeHtml(item.discounted_formatted || item.original_formatted)}</span>` : ''}
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      ` : ''}
      ${changed.length ? `<div class="automation-change-group"><div class="automation-change-group__title">${escapeHtml(selectedChangeView === 'all' ? `Changed Items (${changed.length})` : `${activeViewLabel} (${changed.length})`)}</div><div class="automation-change-list">${changed.slice(0, 120).map(renderChangedEntry).join('')}</div></div>` : ''}
      ${added.length ? `<div class="automation-change-group"><div class="automation-change-group__title">Added Items (${added.length})</div><div class="automation-change-list">${added.slice(0, 120).map(item => renderSimpleItem(item, 'Added')).join('')}</div></div>` : ''}
      ${removed.length ? `<div class="automation-change-group"><div class="automation-change-group__title">Removed Items (${removed.length})</div><div class="automation-change-list">${removed.slice(0, 120).map(item => renderSimpleItem(item, 'Removed')).join('')}</div></div>` : ''}
      ${selectedChangeView !== 'duplicates' && !changed.length && !added.length && !removed.length ? `<div class="automation-run-detail--empty" style="min-height:unset;border:none;padding:0">${escapeHtml(emptyMessage)}</div>` : ''}
    `;
  }

  function populateModelFilter(detail) {
    const select = elements.automationModelFilter;
    if (!select) return;
    const models = Array.isArray(detail?.models) ? detail.models : [];
    const currentValue = select.value;
    select.innerHTML = '<option value="">All models</option>' + models.map(model => `<option value="${escapeHtml(model.model)}">${escapeHtml(model.model)}</option>`).join('');
    if (models.some(model => model.model === currentValue)) {
      select.value = currentValue;
    }
    select.disabled = !detail?.run;
  }
  async function loadRunDetail(runId, { silent = false } = {}) {
    if (!runId) return;
    const requestedRunId = Number(runId);
    const requestedSite = state.activeSite;
    const requestId = ++state.runDetailRequestId;
    try {
      if (!silent) {
        setLoading(true);
        if (Number(state.selectedRunId) !== requestedRunId || !state.runDetail) {
          renderInspectorSkeleton();
          renderProductsSkeleton();
        }
      }
      const detail = await api(`/api/automation/runs/${encodeURIComponent(runId)}`);
      if (requestId !== state.runDetailRequestId || state.activeSite !== requestedSite || Number(state.selectedRunId) !== requestedRunId) return;
      if (!siteKeyMatches(detail?.run?.scraper_key)) {
        state.selectedRunId = null;
        preserveLiveScroll(() => {
          populateModelFilter(null);
          renderRunDetail(null);
        });
        return;
      }
      state.selectedRunId = requestedRunId;
      state.lastRunDetailFetchAt = Date.now();
      if (silent && isEditingProductFilters()) {
        state.runDetail = detail;
        preserveLiveScroll(() => renderRuns(state.runs));
      } else {
        preserveLiveScroll(() => {
          populateModelFilter(detail);
          renderRunDetail(detail);
          renderRuns(state.runs);
        });
      }
    } catch (err) {
      if (requestId === state.runDetailRequestId) {
        renderRunDetail(null);
        showAlert('error', err.message || 'Failed to load run detail.', 0);
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }

  async function loadRuns(jobId = state.selectedJobId, { silent = false } = {}) {
    const requestedSite = state.activeSite;
    const requestedJobId = jobId ? Number(jobId) : null;
    const requestId = ++state.runsRequestId;
    try {
      const params = new URLSearchParams({
        limit: '50',
        scraper_key: state.activeSite || 'xcell',
        include_models: '0'
      });
      if (jobId) params.set('job_id', String(jobId));
      if (!silent) {
        setLoading(true);
        if (!state.runs.length) {
          renderRunsSkeleton();
        }
      }
      const data = await api(`/api/automation/runs?${params.toString()}`);
      if (requestId !== state.runsRequestId || state.activeSite !== requestedSite || (requestedJobId !== null && Number(state.selectedJobId) !== requestedJobId)) return;
      const runs = filterRunsByActiveSite(data.runs || []);
      if (silent) {
        preserveLiveScroll(() => {
          renderRuns(runs);
          renderJobs(state.jobs);
        });
      } else {
        renderRuns(runs);
        renderJobs(state.jobs);
      }
      if (state.selectedRunId && !runs.some(run => Number(run.id) === Number(state.selectedRunId))) {
        state.selectedRunId = null;
      }
      if (state.selectedRunId) {
        const selectedRun = runs.find(run => Number(run.id) === Number(state.selectedRunId));
        const loadedRun = state.runDetail?.run;
        const statusChanged = selectedRun && loadedRun
          && String(selectedRun.status || '') !== String(loadedRun.status || '');
        const detailExpired = selectedRun && isRunningStatus(selectedRun.status)
          && Date.now() - state.lastRunDetailFetchAt >= LIVE_DETAIL_REFRESH_MS;
        if (!loadedRun || !silent || statusChanged || detailExpired) {
          await loadRunDetail(state.selectedRunId, { silent: true });
        }
      } else if (runs.length) {
        state.selectedRunId = Number(runs[0].id);
        await loadRunDetail(state.selectedRunId, { silent: true });
      } else {
        renderRunDetail(null);
      }
    } catch (err) {
      if (requestId === state.runsRequestId) {
        if (!state.runs.length && elements.automationRuns) {
          elements.automationRuns.innerHTML = '<div class="automation-empty-state automation-error-state" role="alert"><div class="automation-run__title">Runs could not be loaded</div><button type="button" class="btn-export" data-action="retry-runs">Retry</button></div>';
        }
        showAlert('error', err.message || 'Failed to load automation runs.', 0);
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }

  async function loadJobs({ silent = false } = {}) {
    const requestId = ++state.jobsRequestId;
    try {
      if (!silent) setLoading(true);
      const data = await api('/api/automation/jobs');
      if (requestId !== state.jobsRequestId) return;
      state.allJobs = Array.isArray(data.jobs) ? data.jobs : [];
      const jobs = filterJobsByActiveSite(state.allJobs);
      if (state.selectedJobId && !jobs.some(job => Number(job.id) === Number(state.selectedJobId))) {
        state.selectedJobId = null;
      }
      if (silent) {
        preserveLiveScroll(() => {
          renderOverview(data.overview || {});
          renderJobs(jobs);
        });
      } else {
        renderOverview(data.overview || {});
        renderJobs(jobs);
      }
      await loadRuns(state.selectedJobId, { silent: true });
    } catch (err) {
      if (requestId === state.jobsRequestId) {
        if (!state.allJobs.length && elements.automationJobs) {
          elements.automationJobs.innerHTML = '<div class="automation-empty-state automation-error-state" role="alert"><div class="automation-job__title">Jobs could not be loaded</div><button type="button" class="btn-export" data-action="retry-jobs">Retry</button></div>';
        }
        showAlert('error', err.message || 'Failed to load automation jobs.', 0);
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }

  async function discoverTargets() {
    const payload = collectPayload();
    if (!payload.category_query) {
      showAlert('warn', 'Enter a section or category name first.');
      return;
    }

    try {
      setLoading(true);
      const previousTargets = state.discovery?.targets || [];
      const discovery = normalizeDiscovery(await api('/api/automation/discover', {
        method: 'POST',
        body: JSON.stringify(payload)
      }), previousTargets);
      state.discovery = discovery;
      state.discoveryFingerprint = currentFingerprint();
      renderDiscovery();
      showAlert('success', `Discovered ${discovery.targets?.length || 0} target link(s).`);
    } catch (err) {
      showAlert('error', err.message || 'Discovery failed.');
    } finally {
      setLoading(false);
    }
  }

  async function saveJob() {
    const payload = collectPayload();
    const wasEditing = Boolean(String(payload.id || '').trim());
    const scopeChangedWhileEditing = isEditingScopeChanged();
    const hasFreshDiscovery = hasFreshDiscoveryForCurrentForm();
    if (!payload.category_query) {
      showAlert('warn', 'Category query is required.');
      return;
    }

    if (hasFreshDiscovery) {
      payload.targets = state.discovery.targets || [];
    }

    try {
      setLoading(true);
      const data = await api('/api/automation/jobs', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      const successMessage = scopeChangedWhileEditing && !hasFreshDiscovery
        ? 'Automation job updated. Cached links were cleared; update targets from Menu Map when needed.'
        : wasEditing
          ? 'Automation job updated.'
          : 'Automation job saved.';
      showAlert('success', successMessage);
      resetForm();
      await loadJobs({ silent: true });
    } catch (err) {
      showAlert('error', err.message || 'Failed to save automation job.');
    } finally {
      setLoading(false);
    }
  }

  function populateForm(job) {
    if (!job) return;
    if (elements.automationJobId) elements.automationJobId.value = String(job.id || '');
    if (elements.automationName) elements.automationName.value = job.name || '';
    if (elements.automationSite) elements.automationSite.value = job.scraper_key || 'xcell';
    if (elements.automationCategoryQuery) elements.automationCategoryQuery.value = job.category_query || '';
    if (elements.automationRootUrl) elements.automationRootUrl.value = job.root_url || SITE_ROOTS[job.scraper_key] || '';
    setIntervalFromMinutes(job.interval_minutes || 1440);
    if (elements.automationMaxPages) elements.automationMaxPages.value = String(job.max_pages || 10);
    if (elements.automationDelayMs) elements.automationDelayMs.value = String(job.delay_ms || 50);
    if (elements.automationEnabled) elements.automationEnabled.checked = Boolean(job.enabled);
    if (elements.automationAutoDiscover) elements.automationAutoDiscover.checked = false;
    if (elements.automationParallel) elements.automationParallel.checked = Boolean(job.use_parallel);
    if (elements.automationEnrich) elements.automationEnrich.checked = job.enrich_details !== undefined && job.enrich_details !== null ? Boolean(job.enrich_details) : true;
    state.loadedFingerprint = currentFingerprint();
    state.discovery = normalizeDiscovery({
      query: job.category_query || '',
      site_label: job.site_label || '',
      scraper_key: job.scraper_key || '',
      candidate_count: job.target_count || 0,
      targets: job.targets || []
    }, job.targets || []);
    state.discoveryFingerprint = currentFingerprint();
    renderDiscovery();
    syncFormMode();
  }

  async function selectJob(jobId, { edit = false, silent = false } = {}) {
    const job = state.jobs.find(item => Number(item.id) === Number(jobId));
    if (!job || !siteKeyMatches(job.scraper_key)) return;
    state.selectedJobId = Number(jobId);
    state.selectedRunId = null;
    state.selectedChangeView = 'all';
    state.lastRunDetailFetchAt = 0;
    resetProductFilters();
    if (edit) {
      const detail = await api(`/api/automation/jobs/${encodeURIComponent(jobId)}`);
      if (!detail?.job || !siteKeyMatches(detail.job.scraper_key)) return;
      populateForm(detail.job);
      openJobEditor();
    }
    populateModelFilter(null);
    renderRunDetail(null);
    renderJobs(state.jobs);
    await loadRuns(jobId, { silent });
  }

  async function handleJobAction(action, jobId) {
    const job = state.jobs.find(item => Number(item.id) === Number(jobId));
    if (!job && action !== 'delete') return;

    try {
      if (action === 'edit') {
        await selectJob(jobId, { edit: true, silent: false });
        return;
      }

      if (action === 'run') {
        state.selectedJobId = Number(jobId);
        const data = await api(`/api/automation/jobs/${encodeURIComponent(jobId)}/run`, { method: 'POST', body: JSON.stringify({}) });
        if (data.resumed && data.run_id) {
          state.selectedRunId = Number(data.run_id);
          state.lastRunDetailFetchAt = 0;
          showAlert('success', 'Existing run resumed from its saved checkpoint.');
        } else {
          showAlert('success', 'New automation run queued.');
        }
      } else if (action === 'refresh') {
        setLoading(true);
        const data = await api(`/api/automation/jobs/${encodeURIComponent(jobId)}/refresh-targets`, { method: 'POST', body: JSON.stringify({}) });
        if (Number(state.selectedJobId) === Number(jobId)) {
          populateForm(data.job);
        }
        showAlert('success', `Refreshed ${data.targets?.length || 0} target link(s).`);
      } else if (action === 'toggle') {
        await api(`/api/automation/jobs/${encodeURIComponent(jobId)}/toggle`, {
          method: 'POST',
          body: JSON.stringify({ enabled: !job.enabled })
        });
        showAlert('info', job.enabled ? 'Automation job paused.' : 'Automation job enabled.');
      } else if (action === 'delete') {
        if (!window.confirm('Delete this automation job and its run history?')) return;
        await api(`/api/automation/jobs/${encodeURIComponent(jobId)}`, {
          method: 'DELETE',
          headers: { 'X-Confirm-Destructive': 'permanently-delete' }
        });
        showAlert('info', 'Automation job deleted.');
        if (Number(state.selectedJobId) === Number(jobId)) {
          resetForm();
        }
      }

      await loadJobs({ silent: true });
    } catch (err) {
      showAlert('error', err.message || 'Action failed.');
    } finally {
      setLoading(false);
    }
  }

  function initTheme() {
    if (!elements.darkMode) return;
    const savedTheme = sessionStorage.getItem('cy_theme') || 'dark';
    document.documentElement.setAttribute('data-bs-theme', savedTheme);
    elements.darkMode.checked = savedTheme === 'dark';
    elements.darkMode.addEventListener('change', event => {
      const theme = event.target.checked ? 'dark' : 'light';
      document.documentElement.setAttribute('data-bs-theme', theme);
      sessionStorage.setItem('cy_theme', theme);
    });
  }

  function bindEvents() {
    elements.automationSupplierTabs?.addEventListener('click', event => {
      const tab = event.target.closest('[data-site-key]');
      if (!tab) return;
      selectSupplier(tab.dataset.siteKey, { silent: false });
    });

    window.addEventListener('popstate', () => {
      selectSupplier(initialSupplierSite(), { silent: false, updateUrl: false });
    });

    window.addEventListener('resize', syncSupplierTabs);

    elements.automationSite?.addEventListener('change', () => {
      const suggested = SITE_ROOTS[elements.automationSite.value] || '';
      if (!elements.automationRootUrl.value || Object.values(SITE_ROOTS).includes(elements.automationRootUrl.value)) {
        elements.automationRootUrl.value = suggested;
      }
      resetDiscovery();
    });

    elements.automationCategoryQuery?.addEventListener('input', () => {
      if (!elements.automationName.value.trim()) {
        const site = elements.automationSite?.selectedOptions?.[0]?.textContent || 'Automation';
        const category = elements.automationCategoryQuery.value.trim();
        elements.automationName.value = category ? `${site} ${category}` : '';
      }
      resetDiscovery();
    });

    elements.automationRootUrl?.addEventListener('input', resetDiscovery);
    elements.automationDiscoverBtn?.addEventListener('click', discoverTargets);
    elements.automationSaveBtn?.addEventListener('click', saveJob);
    elements.automationResetBtn?.addEventListener('click', closeJobEditor);
    elements.automationIncludeAllBtn?.addEventListener('click', () => setAllDiscoveryTargetsActive(true));
    elements.automationSkipAllBtn?.addEventListener('click', () => setAllDiscoveryTargetsActive(false));
    elements.automationProductsCsvBtn?.addEventListener('click', exportProductsCsv);
    elements.automationProductsXlsxBtn?.addEventListener('click', exportProductsXlsx);

    elements.automationDiscoveredTargets?.addEventListener('click', event => {
      const button = event.target.closest('[data-action="toggle-target"]');
      if (!button) return;
      toggleDiscoveryTarget(String(button.dataset.urlKey || '').trim().toLowerCase());
    });

    elements.automationJobs?.addEventListener('click', event => {
      const button = event.target.closest('[data-action]');
      if (button) {
        if (button.dataset.action === 'retry-jobs') {
          loadJobs({ silent: false });
          return;
        }
        handleJobAction(button.dataset.action, button.dataset.jobId);
        return;
      }
      const jobCard = event.target.closest('[data-job-id]');
      if (!jobCard) return;
      selectJob(jobCard.dataset.jobId, { silent: false });
    });

    elements.automationRuns?.addEventListener('click', async event => {
      const retryButton = event.target.closest('[data-action="retry-runs"]');
      if (retryButton) {
        await loadRuns(state.selectedJobId, { silent: false });
        return;
      }
      const pauseBtn = event.target.closest('[data-action="pause-run"]');
      if (pauseBtn) {
        event.preventDefault();
        event.stopPropagation();
        const runId = pauseBtn.dataset.runId;
        try {
          await api(`/api/automation/runs/${encodeURIComponent(runId)}/pause`, { method: 'POST', body: JSON.stringify({}) });
          showAlert('info', 'Run pause requested. Active browser pages will finish before the worker stops.');
          await loadRuns(state.selectedJobId, { silent: true });
          if (Number(state.selectedRunId) === Number(runId)) {
            await loadRunDetail(runId, { silent: true });
          }
        } catch (err) {
          showAlert('error', err.message || 'Failed to pause run.');
        }
        return;
      }
      const resumeBtn = event.target.closest('[data-action="resume-run"]');
      if (resumeBtn) {
        event.preventDefault();
        event.stopPropagation();
        const runId = resumeBtn.dataset.runId;
        try {
          await api(`/api/automation/runs/${encodeURIComponent(runId)}/resume`, { method: 'POST', body: JSON.stringify({}) });
          showAlert('success', 'Run resumed from its saved checkpoint.');
          state.selectedRunId = Number(runId);
          state.lastRunDetailFetchAt = 0;
          await loadRuns(state.selectedJobId, { silent: true });
          await loadRunDetail(runId, { silent: true });
        } catch (err) {
          showAlert('error', err.message || 'Failed to resume run.');
        }
        return;
      }
      const deleteBtn = event.target.closest('[data-action="delete"]');
      if (deleteBtn) {
        event.preventDefault();
        event.stopPropagation();
        const runId = deleteBtn.dataset.runId;
        if (window.confirm('Are you sure you want to delete this past run?')) {
          try {
            await api(`/api/automation/runs/${encodeURIComponent(runId)}/delete`, {
              method: 'POST',
              headers: { 'X-Confirm-Destructive': 'permanently-delete' }
            });
            showAlert('success', 'Run deleted successfully');
            if (Number(state.selectedRunId) === Number(runId)) {
              state.selectedRunId = null;
            }
            await loadRuns(null, { silent: false });
          } catch (err) {
            showAlert('error', err.message || 'Failed to delete run');
          }
        }
        return;
      }

      const runCard = event.target.closest('[data-run-id]');
      if (!runCard) return;
      if (Number(state.selectedRunId) !== Number(runCard.dataset.runId)) {
        resetProductFilters();
      }
      state.selectedRunId = Number(runCard.dataset.runId);
      state.lastRunDetailFetchAt = 0;
      loadRunDetail(state.selectedRunId, { silent: false });
    });

    elements.automationRunDetail?.addEventListener('click', event => {
      const filterButton = event.target.closest('[data-change-view]');
      if (!filterButton) return;
      state.selectedChangeView = String(filterButton.dataset.changeView || 'all');
      state.productFilters.page = 1;
      renderRunDetail(state.runDetail);
    });

    elements.automationReviewFilters?.addEventListener('click', event => {
      const filterButton = event.target.closest('[data-change-view]');
      if (!filterButton) return;
      const changeView = String(filterButton.dataset.changeView || 'all');
      state.selectedChangeView = changeView;
      state.productFilters.page = 1;
      // Duplicate Listings lives in the Products Table tab — auto-switch there
      if (changeView === 'duplicates' && typeof window.switchToTab === 'function') {
        window.switchToTab('table-view');
      }
      renderRunDetail(state.runDetail);
    });

    elements.automationScrapedProducts?.addEventListener('click', event => {
      const clearButton = event.target.closest('[data-product-clear]');
      if (clearButton) {
        resetAllProductFilters();
        renderRunDetail(state.runDetail);
        return;
      }

      const pageButton = event.target.closest('[data-product-page]');
      if (pageButton && !pageButton.disabled) {
        const direction = String(pageButton.dataset.productPage || '');
        const currentPage = Math.max(1, Number(state.productFilters.page) || 1);
        state.productFilters.page = direction === 'previous' ? Math.max(1, currentPage - 1) : currentPage + 1;
        renderRunDetail(state.runDetail);
        const tableWrap = elements.automationScrapedProducts?.querySelector('.automation-product-table-wrap');
        if (tableWrap) tableWrap.scrollTop = 0;
        return;
      }

      const sortButton = event.target.closest('[data-product-sort]');
      if (sortButton) {
        const key = String(sortButton.dataset.productSort || '').trim();
        if (key) {
          if (state.productFilters.sortKey === key) {
            state.productFilters.sortDir = state.productFilters.sortDir === 'asc' ? 'desc' : 'asc';
          } else {
            state.productFilters.sortKey = key;
            state.productFilters.sortDir = 'asc';
          }
          state.productFilters.page = 1;
          renderRunDetail(state.runDetail);
        }
        return;
      }

      const filterButton = event.target.closest('[data-change-view]');
      if (!filterButton) return;
      state.selectedChangeView = String(filterButton.dataset.changeView || 'all');
      state.productFilters.page = 1;
      renderRunDetail(state.runDetail);
    });

    elements.automationScrapedProducts?.addEventListener('error', event => {
      const image = event.target;
      if (!(image instanceof HTMLImageElement) || !image.matches('[data-product-image]')) return;
      image.hidden = true;
      const fallback = image.nextElementSibling;
      if (fallback?.classList.contains('automation-product-no-image')) fallback.hidden = false;
    }, true);

    elements.automationScrapedProducts?.addEventListener('input', event => {
      const target = event.target;
      if (!(target instanceof HTMLInputElement)) return;
      if (target.matches('[data-product-search]')) {
        state.productFilters.search = target.value;
        state.productFilters.page = 1;
        scheduleProductTableRender({
          kind: 'search',
          start: target.selectionStart,
          end: target.selectionEnd
        });
        return;
      }
      if (target.matches('[data-product-min-price], [data-product-max-price]')) {
        const isMinimum = target.matches('[data-product-min-price]');
        const key = isMinimum ? 'minPrice' : 'maxPrice';
        const selector = isMinimum ? '[data-product-min-price]' : '[data-product-max-price]';
        state.productFilters[key] = target.value;
        state.productFilters.page = 1;
        scheduleProductTableRender({
          kind: 'control',
          selector,
          start: target.selectionStart,
          end: target.selectionEnd
        });
      }
    });

    elements.automationScrapedProducts?.addEventListener('change', event => {
      const target = event.target;
      if (!(target instanceof HTMLSelectElement)) return;
      if (target.matches('[data-product-mode]')) {
        state.productFilters.mode = target.value || 'all';
        state.productFilters.page = 1;
        renderRunDetail(state.runDetail);
        return;
      }
      if (target.matches('[data-product-source]')) {
        state.productFilters.source = target.value || '';
        state.productFilters.page = 1;
        renderRunDetail(state.runDetail);
        return;
      }
      if (target.matches('[data-product-sort-select]')) {
        const [sortKey = '', sortDir = 'asc'] = String(target.value || '').split(':');
        state.productFilters.sortKey = sortKey;
        state.productFilters.sortDir = sortDir === 'desc' ? 'desc' : 'asc';
        state.productFilters.page = 1;
        renderRunDetail(state.runDetail);
        return;
      }
      if (target.matches('[data-product-page-size]')) {
        const pageSize = Number(target.value);
        state.productFilters.pageSize = [50, 100, 250, 500].includes(pageSize) ? pageSize : 100;
        state.productFilters.page = 1;
        renderRunDetail(state.runDetail);
      }
    });

    elements.automationModelFilter?.addEventListener('change', () => {
      state.productFilters.page = 1;
      renderRunDetail(state.runDetail);
    });
  }

  async function boot() {
    initTheme();
    removeDiscoveryControls();
    bindEvents();
    resetForm();
    syncSupplierTabs();
    updateSupplierUrl(state.activeSite, 'replace');
    syncFormMode();
    renderDiscovery();
    // Yield to main thread so initial paint (LCP) occurs immediately without blocking
    await new Promise(resolve => window.requestAnimationFrame ? window.requestAnimationFrame(() => setTimeout(resolve, 0)) : setTimeout(resolve, 0));
    await loadJobs({ silent: false });
    startRealtimeUpdates();
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
