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
    automationJobs: $('automationJobs'),
    automationRuns: $('automationRuns'),
    automationRunDetail: $('automationRunDetail'),
    automationModelFilter: $('automationModelFilter'),
    automationStatJobs: $('automationStatJobs'),
    automationStatEnabled: $('automationStatEnabled'),
    automationStatTargets: $('automationStatTargets'),
    automationStatChangedRuns: $('automationStatChangedRuns')
  };

  const SITE_ROOTS = {
    standard: 'https://www.mobilesentrix.com/',
    xcell: 'https://xcellparts.com/',
    txparts: 'https://txparts.com/',
    parts4cells: 'https://parts4cells.com/'
  };

  const NOTIF_CLS = {
    success: 'alert-success',
    error: 'alert-danger',
    danger: 'alert-danger',
    warn: 'alert-warning',
    warning: 'alert-warning',
    info: 'alert-info'
  };

  const state = {
    jobs: [],
    runs: [],
    selectedJobId: null,
    selectedRunId: null,
    discovery: null,
    discoveryFingerprint: '',
    loadedFingerprint: '',
    runDetail: null
  };

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
    if (!elements.overlay) return;
    elements.overlay.classList.toggle('d-none', !on);
  }

  function showAlert(type, msg, duration = 5000) {
    const alertBox = elements.alertBox;
    if (!alertBox) return;
    alertBox.className = `alert-banner ${NOTIF_CLS[type] || 'alert-info'}`;
    alertBox.innerHTML = `${escapeHtml(msg)}<button type="button" style="margin-left:auto;background:none;border:none;color:inherit;cursor:pointer;font-size:1rem;padding:0 .2rem">x</button>`;
    const button = alertBox.querySelector('button');
    if (button) button.addEventListener('click', () => alertBox.classList.add('d-none'));
    alertBox.classList.remove('d-none');
    clearTimeout(alertBox._timer);
    alertBox._timer = setTimeout(() => alertBox.classList.add('d-none'), duration);
  }

  async function api(url, options = {}) {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.error || `Request failed (${res.status})`);
    }
    return data;
  }

  function formatDateTime(value) {
    if (!value) return 'Never';
    try {
      const date = new Date(value);
      return new Intl.DateTimeFormat('en-PK', {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: 'Asia/Karachi'
      }).format(date);
    } catch {
      return String(value);
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

  function resetForm() {
    if (elements.automationJobId) elements.automationJobId.value = '';
    if (elements.automationName) elements.automationName.value = '';
    if (elements.automationSite) elements.automationSite.value = 'xcell';
    if (elements.automationCategoryQuery) elements.automationCategoryQuery.value = '';
    if (elements.automationRootUrl) elements.automationRootUrl.value = SITE_ROOTS.xcell;
    if (elements.automationIntervalValue) elements.automationIntervalValue.value = '1';
    if (elements.automationIntervalUnit) elements.automationIntervalUnit.value = 'days';
    if (elements.automationMaxPages) elements.automationMaxPages.value = '10';
    if (elements.automationDelayMs) elements.automationDelayMs.value = '50';
    if (elements.automationEnabled) elements.automationEnabled.checked = true;
    if (elements.automationAutoDiscover) elements.automationAutoDiscover.checked = true;
    if (elements.automationParallel) elements.automationParallel.checked = true;
    if (elements.automationEnrich) elements.automationEnrich.checked = false;
    state.selectedJobId = null;
    state.loadedFingerprint = '';
    resetDiscovery();
    syncFormMode();
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
      auto_discover: Boolean(elements.automationAutoDiscover?.checked),
      use_parallel: Boolean(elements.automationParallel?.checked),
      enrich_details: Boolean(elements.automationEnrich?.checked),
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
        : value === 'running' ? 'automation-chip automation-chip--warn'
          : 'automation-chip';
    return `<span class="${cls}">${escapeHtml(value)}</span>`;
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
      summary.textContent = 'Run discovery to preview which category URLs will be scraped.';
      meta.textContent = '';
      selection.textContent = 'All discovered links will run by default.';
      includeAllBtn.disabled = true;
      skipAllBtn.disabled = true;
      container.innerHTML = '<div class="automation-target"><div class="automation-target__label">No discovered targets yet</div><div class="automation-target__url">Use a site and section query, then click Discover Links.</div></div>';
      return;
    }

    const counts = getDiscoveryCounts(discovery);
    summary.textContent = `Found ${counts.total} target link${counts.total === 1 ? '' : 's'} for "${discovery.query}".`;
    meta.textContent = `${discovery.site_label} - ${discovery.candidate_count} candidate links scanned`;
    selection.textContent = counts.skipped
      ? `${counts.active} included, ${counts.skipped} skipped. Skipped links stay out of scheduled runs.`
      : `All ${counts.active} discovered link${counts.active === 1 ? '' : 's'} are included in this job.`;
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
    if (elements.automationStatJobs) elements.automationStatJobs.textContent = String(overview.total_jobs || 0);
    if (elements.automationStatEnabled) elements.automationStatEnabled.textContent = String(overview.enabled_jobs || 0);
    if (elements.automationStatTargets) elements.automationStatTargets.textContent = String(overview.total_targets || 0);
    if (elements.automationStatChangedRuns) elements.automationStatChangedRuns.textContent = String(overview.changed_runs || 0);
  }

  function renderJobs(jobs) {
    const container = elements.automationJobs;
    if (!container) return;
    state.jobs = Array.isArray(jobs) ? jobs : [];
    if (!state.jobs.length) {
      container.innerHTML = '<div class="automation-job"><div class="automation-job__title">No jobs saved yet</div><div class="automation-job__subtitle">Create one from the form on the left.</div></div>';
      return;
    }

    container.innerHTML = state.jobs.map(job => {
      const selected = Number(job.id) === Number(state.selectedJobId) ? ' is-selected' : '';
      const nextRun = job.enabled ? `${formatDateTime(job.next_run_at)} (${relativeTime(job.next_run_at)})` : 'Paused';
      const lastRun = job.last_run_at ? formatDateTime(job.last_run_at) : 'Never';
      return `
        <div class="automation-job${selected}" data-job-id="${job.id}">
          <div class="automation-job__top">
            <div>
              <div class="automation-job__title">${escapeHtml(job.name)}</div>
              <div class="automation-job__subtitle">${escapeHtml(job.site_label)} - ${escapeHtml(job.category_query)}</div>
            </div>
            ${statusChip(job.last_status)}
          </div>
          <div class="automation-job__chips">
            <span class="automation-chip">${escapeHtml(job.interval_label || '')}</span>
            <span class="automation-chip">${escapeHtml(`${job.target_count || 0} targets`)}</span>
            <span class="automation-chip automation-chip--ok">${escapeHtml(`${job.active_target_count || 0} included`)}</span>
            ${(job.skipped_target_count || 0) > 0 ? `<span class="automation-chip automation-chip--danger">${escapeHtml(`${job.skipped_target_count || 0} skipped`)}</span>` : ''}
            ${job.auto_discover ? '<span class="automation-chip">Auto refresh links</span>' : ''}
          </div>
          <div class="automation-job__meta">
            <div class="automation-meta">
              <span class="automation-meta__label">Next Run</span>
              <span class="automation-meta__value">${escapeHtml(nextRun)}</span>
            </div>
            <div class="automation-meta">
              <span class="automation-meta__label">Last Run</span>
              <span class="automation-meta__value">${escapeHtml(lastRun)}</span>
            </div>
            <div class="automation-meta">
              <span class="automation-meta__label">Root URL</span>
              <span class="automation-meta__value">${escapeHtml(job.root_url || '')}</span>
            </div>
            <div class="automation-meta">
              <span class="automation-meta__label">Latest History</span>
              <span class="automation-meta__value">${escapeHtml((job.last_history_ids || []).join(', ') || 'None yet')}</span>
            </div>
          </div>
          ${job.last_error ? `<div class="automation-job__subtitle" style="margin-top:.7rem;color:var(--danger)">${escapeHtml(job.last_error)}</div>` : ''}
          <div class="automation-job__actions">
            <button type="button" class="btn-export" data-action="edit" data-job-id="${job.id}">Edit</button>
            <button type="button" class="btn-export" data-action="run" data-job-id="${job.id}">Run Now</button>
            <button type="button" class="btn-export" data-action="refresh" data-job-id="${job.id}">Refresh Links</button>
            <button type="button" class="btn-export" data-action="toggle" data-job-id="${job.id}">${job.enabled ? 'Pause' : 'Enable'}</button>
            <button type="button" class="btn-danger-sm" data-action="delete" data-job-id="${job.id}">Delete</button>
          </div>
        </div>
      `;
    }).join('');
  }

  function renderRuns(runs) {
    const container = elements.automationRuns;
    if (!container) return;
    state.runs = Array.isArray(runs) ? runs : [];
    if (!state.runs.length) {
      container.innerHTML = '<div class="automation-run"><div class="automation-run__title">No runs yet</div><div class="automation-run__subtitle">Run a saved job to capture its first snapshot.</div></div>';
      return;
    }

    container.innerHTML = state.runs.map(run => {
      const summary = run.summary || {};
      const selected = Number(run.id) === Number(state.selectedRunId) ? ' is-selected' : '';
      const runStatus = String(run.status || '').toLowerCase();
      const totalTargets = Number(summary.total_targets || summary.target_count || (run.target_urls || []).length || 0);
      const completedTargets = Number(summary.completed_targets || 0);
      const progressValue = runStatus === 'running' && totalTargets
        ? `${completedTargets} / ${totalTargets} targets`
        : String(summary.target_count || (run.target_urls || []).length || 0);
      return `
        <button type="button" class="automation-run${selected}" data-run-id="${run.id}" style="text-align:left">
          <div class="automation-run__top">
            <div>
              <div class="automation-run__title">${escapeHtml(run.job_name || 'Automation Run')}</div>
              <div class="automation-run__subtitle">${escapeHtml(run.trigger_type)} - ${escapeHtml(formatDateTime(run.started_at))}</div>
            </div>
            ${statusChip(run.status)}
          </div>
          <div class="automation-run__chips">
            <span class="automation-chip">${escapeHtml(`${summary.current_items || run.items_count || 0} items`)}</span>
            <span class="automation-chip">${escapeHtml(`${summary.changed || 0} changed`)}</span>
            <span class="automation-chip">${escapeHtml(`${summary.added || 0} added`)}</span>
            <span class="automation-chip">${escapeHtml(`${summary.removed || 0} removed`)}</span>
          </div>
          <div class="automation-run__meta">
            <div class="automation-meta">
              <span class="automation-meta__label">${runStatus === 'running' && totalTargets ? 'Progress' : 'Targets'}</span>
              <span class="automation-meta__value">${escapeHtml(progressValue)}</span>
            </div>
            <div class="automation-meta">
              <span class="automation-meta__label">Price Drops</span>
              <span class="automation-meta__value">${escapeHtml(String(summary.price_drop_alerts || 0))}</span>
            </div>
          </div>
        </button>
      `;
    }).join('');
  }

  function getModelLabel(item) {
    return item?.model_label || item?.target_label || item?.title || 'Uncategorized';
  }

  function filterByModel(items, modelFilter) {
    if (!modelFilter) return items;
    return items.filter(item => {
      const candidate = item?.after || item?.before || item;
      return getModelLabel(candidate) === modelFilter;
    });
  }

  function renderChangedEntry(entry) {
    const after = entry.after || {};
    const before = entry.before || {};
    const title = after.title || before.title || 'Untitled Item';
    const model = getModelLabel(after.title ? after : before);
    const chips = Object.entries(entry.changes || {}).map(([key, value]) => {
      if (key === 'price') {
        return `<span class="automation-chip automation-chip--warn">${escapeHtml(`${value.before_formatted || value.before} -> ${value.after_formatted || value.after}`)}</span>`;
      }
      return `<span class="automation-chip">${escapeHtml(`${key.replace('_', ' ')} changed`)}</span>`;
    }).join('');
    return `
      <div class="automation-change">
        <div class="automation-change__model">${escapeHtml(model)}</div>
        <div class="automation-change__top">
          <div class="automation-change__title">${escapeHtml(title)}</div>
          ${after.url ? `<a class="automation-inline-link" href="${escapeHtml(after.url)}" target="_blank" rel="noreferrer">Open</a>` : ''}
        </div>
        <div class="automation-change__chips">${chips}</div>
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

  function renderRunDetail(detail) {
    const container = elements.automationRunDetail;
    const modelFilter = elements.automationModelFilter?.value || '';
    if (!container) return;
    state.runDetail = detail;

    if (!detail || !detail.run) {
      container.className = 'automation-run-detail automation-run-detail--empty';
      container.textContent = 'Select a run to load its changes.';
      return;
    }

    const comparison = detail.comparison || { summary: {}, changed: [], added: [], removed: [] };
    const summary = comparison.summary || {};
    const run = detail.run || {};
    const runStatus = String(run.status || 'idle').toLowerCase();
    const runSummary = run.summary || {};
    const targetCount = Number(runSummary.total_targets || runSummary.target_count || (run.target_urls || []).length || 0);
    const models = Array.isArray(detail.models) ? detail.models : [];
    const changed = filterByModel(comparison.changed || [], modelFilter);
    const added = filterByModel(comparison.added || [], modelFilter);
    const removed = filterByModel(comparison.removed || [], modelFilter);

    container.className = 'automation-run-detail';
    container.innerHTML = `
      <div class="automation-detail-summary">
        <div class="automation-detail-card">
          <div class="automation-detail-card__value">${escapeHtml(String(summary.current_items || run.items_count || 0))}</div>
          <div class="automation-detail-card__label">Items Scraped</div>
        </div>
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
      </div>
      <div class="automation-job__meta" style="margin-bottom:1rem">
        <div class="automation-meta">
          <span class="automation-meta__label">Run Status</span>
          <span class="automation-meta__value">${statusChip(run.status)}</span>
        </div>
        <div class="automation-meta">
          <span class="automation-meta__label">Started</span>
          <span class="automation-meta__value">${escapeHtml(formatDateTime(run.started_at))}</span>
        </div>
        <div class="automation-meta">
          <span class="automation-meta__label">Completed</span>
          <span class="automation-meta__value">${escapeHtml(run.completed_at ? formatDateTime(run.completed_at) : (runStatus === 'running' ? 'In progress' : 'Pending'))}</span>
        </div>
        <div class="automation-meta">
          <span class="automation-meta__label">Targets</span>
          <span class="automation-meta__value">${escapeHtml(String(targetCount))}</span>
        </div>
      </div>
      <div class="automation-job__meta" style="margin-bottom:1rem">
        <div class="automation-meta">
          <span class="automation-meta__label">Current Session</span>
          <span class="automation-meta__value">${escapeHtml(detail.current_history?.id || 'N/A')}</span>
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
      ${changed.length ? `<div class="automation-change-group"><div class="automation-change-group__title">Changed Items (${changed.length})</div><div class="automation-change-list">${changed.slice(0, 120).map(renderChangedEntry).join('')}</div></div>` : ''}
      ${added.length ? `<div class="automation-change-group"><div class="automation-change-group__title">Added Items (${added.length})</div><div class="automation-change-list">${added.slice(0, 120).map(item => renderSimpleItem(item, 'Added')).join('')}</div></div>` : ''}
      ${removed.length ? `<div class="automation-change-group"><div class="automation-change-group__title">Removed Items (${removed.length})</div><div class="automation-change-list">${removed.slice(0, 120).map(item => renderSimpleItem(item, 'Removed')).join('')}</div></div>` : ''}
      ${!changed.length && !added.length && !removed.length ? '<div class="automation-run-detail--empty" style="min-height:unset;border:none;padding:0">No items match the selected model filter.</div>' : ''}
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
  }
  async function loadRunDetail(runId, { silent = false } = {}) {
    if (!runId) return;
    try {
      if (!silent) setLoading(true);
      const detail = await api(`/api/automation/runs/${encodeURIComponent(runId)}`);
      state.selectedRunId = Number(runId);
      populateModelFilter(detail);
      renderRunDetail(detail);
      renderRuns(state.runs);
    } catch (err) {
      showAlert('error', err.message || 'Failed to load run detail.');
    } finally {
      if (!silent) setLoading(false);
    }
  }

  async function loadRuns(jobId = state.selectedJobId, { silent = false } = {}) {
    try {
      const query = jobId ? `?job_id=${encodeURIComponent(jobId)}&limit=25` : '?limit=25';
      if (!silent) setLoading(true);
      const data = await api(`/api/automation/runs${query}`);
      const runs = data.runs || [];
      renderRuns(runs);
      if (state.selectedRunId && !runs.some(run => Number(run.id) === Number(state.selectedRunId))) {
        state.selectedRunId = null;
      }
      if (state.selectedRunId) {
        await loadRunDetail(state.selectedRunId, { silent: true });
      } else if (runs.length) {
        state.selectedRunId = Number(runs[0].id);
        await loadRunDetail(state.selectedRunId, { silent: true });
      } else {
        renderRunDetail(null);
      }
    } catch (err) {
      showAlert('error', err.message || 'Failed to load automation runs.');
    } finally {
      if (!silent) setLoading(false);
    }
  }

  async function loadJobs({ silent = false } = {}) {
    try {
      if (!silent) setLoading(true);
      const data = await api('/api/automation/jobs');
      renderOverview(data.overview || {});
      renderJobs(data.jobs || []);
      if (state.selectedJobId && !(data.jobs || []).some(job => Number(job.id) === Number(state.selectedJobId))) {
        state.selectedJobId = null;
      }
      renderJobs(data.jobs || []);
      await loadRuns(state.selectedJobId, { silent: true });
    } catch (err) {
      showAlert('error', err.message || 'Failed to load automation jobs.');
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
        ? 'Automation job updated. Cached links were cleared; discover or run the job to refresh targets.'
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
    if (elements.automationAutoDiscover) elements.automationAutoDiscover.checked = Boolean(job.auto_discover);
    if (elements.automationParallel) elements.automationParallel.checked = Boolean(job.use_parallel);
    if (elements.automationEnrich) elements.automationEnrich.checked = Boolean(job.enrich_details);
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

  async function handleJobAction(action, jobId) {
    const job = state.jobs.find(item => Number(item.id) === Number(jobId));
    if (!job && action !== 'delete') return;

    try {
      if (action === 'edit') {
        state.selectedJobId = Number(jobId);
        populateForm(job);
        renderJobs(state.jobs);
        await loadRuns(jobId, { silent: false });
        return;
      }

      if (action === 'run') {
        await api(`/api/automation/jobs/${encodeURIComponent(jobId)}/run`, { method: 'POST', body: JSON.stringify({}) });
        showAlert('success', 'Automation run queued.');
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
        const res = await fetch(`/api/automation/jobs/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
        const payload = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(payload.error || 'Failed to delete automation job.');
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
    elements.automationResetBtn?.addEventListener('click', resetForm);
    elements.automationIncludeAllBtn?.addEventListener('click', () => setAllDiscoveryTargetsActive(true));
    elements.automationSkipAllBtn?.addEventListener('click', () => setAllDiscoveryTargetsActive(false));

    elements.automationDiscoveredTargets?.addEventListener('click', event => {
      const button = event.target.closest('[data-action="toggle-target"]');
      if (!button) return;
      toggleDiscoveryTarget(String(button.dataset.urlKey || '').trim().toLowerCase());
    });

    elements.automationJobs?.addEventListener('click', event => {
      const button = event.target.closest('[data-action]');
      if (!button) return;
      handleJobAction(button.dataset.action, button.dataset.jobId);
    });

    elements.automationRuns?.addEventListener('click', event => {
      const runButton = event.target.closest('[data-run-id]');
      if (!runButton) return;
      state.selectedRunId = Number(runButton.dataset.runId);
      loadRunDetail(state.selectedRunId, { silent: false });
    });

    elements.automationModelFilter?.addEventListener('change', () => {
      renderRunDetail(state.runDetail);
    });
  }

  async function boot() {
    initTheme();
    bindEvents();
    resetForm();
    syncFormMode();
    renderDiscovery();
    await loadJobs({ silent: false });
    window.setInterval(() => {
      loadJobs({ silent: true }).catch(() => { });
      if (state.selectedRunId) {
        loadRunDetail(state.selectedRunId, { silent: true }).catch(() => { });
      }
    }, 20000);
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
