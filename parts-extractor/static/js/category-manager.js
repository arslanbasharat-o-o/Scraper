(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const elements = {
    alertBox: $('alert'),
    overlay: $('overlay'),
    darkMode: $('darkMode'),
    categoryDirtyState: $('categoryDirtyState'),
    categoryStatJobs: $('categoryStatJobs'),
    categoryStatTargets: $('categoryStatTargets'),
    categoryStatActive: $('categoryStatActive'),
    categoryStatSkipped: $('categoryStatSkipped'),
    categoryJobs: $('categoryJobs'),
    categoryWorkspaceEmpty: $('categoryWorkspaceEmpty'),
    categoryWorkspaceContent: $('categoryWorkspaceContent'),
    categoryCurrentName: $('categoryCurrentName'),
    categoryCurrentMeta: $('categoryCurrentMeta'),
    categoryCurrentChips: $('categoryCurrentChips'),
    categoryCurrentStats: $('categoryCurrentStats'),
    categorySearch: $('categorySearch'),
    categoryStatusFilter: $('categoryStatusFilter'),
    categoryGroupFilter: $('categoryGroupFilter'),
    categoryIncludeVisibleBtn: $('categoryIncludeVisibleBtn'),
    categorySkipVisibleBtn: $('categorySkipVisibleBtn'),
    categoryRefreshBtn: $('categoryRefreshBtn'),
    categoryRunBtn: $('categoryRunBtn'),
    categorySaveBtn: $('categorySaveBtn'),
    categoryClearFilters: $('categoryClearFilters'),
    categoryVisibleSummary: $('categoryVisibleSummary'),
    categoryGroupSummary: $('categoryGroupSummary'),
    categorySelectionSummary: $('categorySelectionSummary'),
    categorySelectionList: $('categorySelectionList'),
    categoryTargets: $('categoryTargets')
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
    drafts: {},
    selectedJobId: null,
    filters: {
      search: '',
      status: 'all',
      group: ''
    }
  };

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = String(text ?? '');
    return div.innerHTML;
  }

  function setLoading(on) {
    elements.overlay?.classList.toggle('d-none', !on);
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

  function formatDateTime(value) {
    if (!value) return 'Never';
    try {
      return new Intl.DateTimeFormat('en-PK', {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: 'Asia/Karachi'
      }).format(new Date(value));
    } catch {
      return String(value);
    }
  }

  function relativeTime(value) {
    if (!value) return 'Pending';
    try {
      const now = Date.now();
      const then = new Date(value).getTime();
      const diffMs = Math.abs(then - now);
      const suffix = then >= now ? 'from now' : 'ago';
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

  function toBooleanFlag(value, fallback = true) {
    if (value === undefined || value === null || value === '') return Boolean(fallback);
    if (typeof value === 'boolean') return value;
    const normalized = String(value).trim().toLowerCase();
    if (['0', 'false', 'no', 'off'].includes(normalized)) return false;
    if (['1', 'true', 'yes', 'on'].includes(normalized)) return true;
    return Boolean(value);
  }

  function normalizeTarget(target, index) {
    const url = String(target?.url || '').trim();
    const urlKey = String(target?.url_key || url).trim().toLowerCase();
    return {
      ...target,
      label: String(target?.label || '').trim() || url,
      group_label: String(target?.group_label || '').trim(),
      url,
      url_key: urlKey,
      active: toBooleanFlag(target?.active, true),
      position: Number.isFinite(Number(target?.position)) ? Number(target.position) : index
    };
  }

  function cloneTargets(targets) {
    return (Array.isArray(targets) ? targets : [])
      .map((target, index) => normalizeTarget(target, index))
      .filter(target => target.url && target.url_key);
  }

  function normalizeJob(job) {
    const targets = cloneTargets(job?.targets || []);
    return {
      ...job,
      targets,
      target_count: targets.length,
      active_target_count: targets.filter(target => target.active).length,
      skipped_target_count: targets.filter(target => !target.active).length
    };
  }

  function computeTargetSignature(targets) {
    return cloneTargets(targets)
      .map(target => [
        target.url_key,
        target.active ? '1' : '0',
        target.label,
        target.group_label,
        String(target.position)
      ].join('|'))
      .join('||');
  }

  function getJob(jobId = state.selectedJobId) {
    return state.jobs.find(job => Number(job.id) === Number(jobId)) || null;
  }

  function syncDraftFromJob(job, force = false) {
    if (!job) return null;
    const key = String(job.id);
    const normalizedTargets = cloneTargets(job.targets);
    const nextBaseSignature = computeTargetSignature(normalizedTargets);
    const existing = state.drafts[key];
    if (!existing || force || !existing.dirty) {
      state.drafts[key] = {
        targets: normalizedTargets,
        baseSignature: nextBaseSignature,
        dirty: false
      };
    }
    return state.drafts[key];
  }

  function getDraft(jobId = state.selectedJobId) {
    const job = getJob(jobId);
    if (!job) return null;
    return syncDraftFromJob(job);
  }

  function getEffectiveTargets(job) {
    const draft = state.drafts[String(job.id)];
    return draft ? draft.targets : cloneTargets(job.targets);
  }

  function getAllDirtyDrafts() {
    return Object.values(state.drafts).filter(draft => draft?.dirty);
  }

  function getCurrentTargets() {
    return getDraft()?.targets || [];
  }

  function summarizeTargets(targets) {
    const safeTargets = cloneTargets(targets);
    const active = safeTargets.filter(target => target.active).length;
    const groups = new Set(safeTargets.map(target => target.group_label || 'Ungrouped'));
    return {
      total: safeTargets.length,
      active,
      skipped: Math.max(0, safeTargets.length - active),
      groups: groups.size
    };
  }

  function buildOverview() {
    return state.jobs.reduce((summary, job) => {
      const counts = summarizeTargets(getEffectiveTargets(job));
      summary.jobs += 1;
      summary.targets += counts.total;
      summary.active += counts.active;
      summary.skipped += counts.skipped;
      return summary;
    }, { jobs: 0, targets: 0, active: 0, skipped: 0 });
  }

  function getFilteredTargets() {
    const search = state.filters.search.trim().toLowerCase();
    const status = state.filters.status;
    const group = state.filters.group;
    return getCurrentTargets().filter(target => {
      const matchesSearch = !search || [
        target.label,
        target.group_label,
        target.url
      ].some(value => String(value || '').toLowerCase().includes(search));
      const matchesStatus = status === 'all'
        || (status === 'active' && target.active)
        || (status === 'skipped' && !target.active);
      const matchesGroup = !group || (target.group_label || 'Ungrouped') === group;
      return matchesSearch && matchesStatus && matchesGroup;
    });
  }

  function getGroupStats() {
    const groups = new Map();
    getCurrentTargets().forEach(target => {
      const name = target.group_label || 'Ungrouped';
      if (!groups.has(name)) {
        groups.set(name, { name, total: 0, active: 0, skipped: 0 });
      }
      const entry = groups.get(name);
      entry.total += 1;
      if (target.active) entry.active += 1;
      else entry.skipped += 1;
    });
    return Array.from(groups.values()).sort((a, b) => {
      if (b.active !== a.active) return b.active - a.active;
      if (b.total !== a.total) return b.total - a.total;
      return a.name.localeCompare(b.name);
    });
  }

  function statusChip(status) {
    const normalized = String(status || 'idle').trim().toLowerCase();
    return `<span class="category-status-chip is-${escapeHtml(normalized)}">${escapeHtml(normalized)}</span>`;
  }

  function setSelectedJob(jobId) {
    if (!jobId || !getJob(jobId)) return;
    state.selectedJobId = Number(jobId);
    syncDraftFromJob(getJob(jobId));
    if (!getGroupStats().some(group => group.name === state.filters.group)) {
      state.filters.group = '';
      if (elements.categoryGroupFilter) elements.categoryGroupFilter.value = '';
    }
    renderPage();
  }

  function updateDraft(mutator) {
    const draft = getDraft();
    if (!draft) return;
    mutator(draft.targets);
    draft.targets = cloneTargets(draft.targets)
      .map((target, index) => ({ ...target, position: index }));
    draft.dirty = computeTargetSignature(draft.targets) !== draft.baseSignature;
    renderPage();
  }

  function setTargetActive(urlKey, active) {
    updateDraft(targets => {
      const match = targets.find(target => target.url_key === urlKey);
      if (match) match.active = Boolean(active);
    });
  }

  function setVisibleTargetsActive(active) {
    const visibleKeys = new Set(getFilteredTargets().map(target => target.url_key));
    if (!visibleKeys.size) return;
    updateDraft(targets => {
      targets.forEach(target => {
        if (visibleKeys.has(target.url_key)) {
          target.active = Boolean(active);
        }
      });
    });
  }

  function renderSummaryStatus() {
    const dirtyCount = getAllDirtyDrafts().length;
    if (!elements.categoryDirtyState) return;
    if (dirtyCount) {
      elements.categoryDirtyState.textContent = `${dirtyCount} job${dirtyCount === 1 ? '' : 's'} need saving.`;
      elements.categoryDirtyState.classList.add('is-dirty');
      return;
    }
    elements.categoryDirtyState.textContent = 'All changes saved.';
    elements.categoryDirtyState.classList.remove('is-dirty');
  }

  function renderOverallStats() {
    const summary = buildOverview();
    if (elements.categoryStatJobs) elements.categoryStatJobs.textContent = String(summary.jobs);
    if (elements.categoryStatTargets) elements.categoryStatTargets.textContent = String(summary.targets);
    if (elements.categoryStatActive) elements.categoryStatActive.textContent = String(summary.active);
    if (elements.categoryStatSkipped) elements.categoryStatSkipped.textContent = String(summary.skipped);
  }

  function renderJobs() {
    if (!elements.categoryJobs) return;
    if (!state.jobs.length) {
      elements.categoryJobs.innerHTML = `
        <div class="category-empty" style="min-height: 260px">
          <div>
            <h3>Nothing saved yet</h3>
            <p>Build the first job in Automation and the categories will show up here.</p>
          </div>
        </div>
      `;
      return;
    }
    elements.categoryJobs.innerHTML = state.jobs.map(job => {
      const counts = summarizeTargets(getEffectiveTargets(job));
      const draft = state.drafts[String(job.id)];
      const subtitle = `${job.site_label || 'Supplier'} - ${job.category_query || 'Saved targets'}`;
      return `
        <button type="button" class="category-job ${Number(job.id) === Number(state.selectedJobId) ? 'is-selected' : ''}" data-job-id="${escapeHtml(String(job.id))}">
          <div class="category-job__top">
            <div>
              <div class="category-job__title">${escapeHtml(job.name || 'Untitled Job')}</div>
              <div class="category-job__subtitle">${escapeHtml(subtitle)}</div>
            </div>
            ${statusChip(job.last_status)}
          </div>
          <div class="category-job__chips">
            <span class="category-pill category-pill--site">${escapeHtml(job.site_label || 'Supplier')}</span>
            <span class="category-pill">${escapeHtml(`${counts.total} total`)}</span>
            <span class="category-pill category-pill--ok">${escapeHtml(`${counts.active} ready`)}</span>
            <span class="category-pill category-pill--danger">${escapeHtml(`${counts.skipped} skipped`)}</span>
            ${draft?.dirty ? '<span class="category-pill category-pill--dirty">Unsaved</span>' : ''}
          </div>
          <div class="category-job__chips">
            <span class="category-pill">${escapeHtml(`Last discovery ${relativeTime(job.last_discovery_at)}`)}</span>
            <span class="category-pill">${escapeHtml(`Next run ${relativeTime(job.next_run_at)}`)}</span>
          </div>
        </button>
      `;
    }).join('');
  }

  function renderCurrentJob() {
    const job = getJob();
    const draft = getDraft();
    const targets = draft?.targets || [];
    const counts = summarizeTargets(targets);
    const groupStats = getGroupStats();

    if (!job || !draft) {
      elements.categoryWorkspaceEmpty?.classList.remove('d-none');
      elements.categoryWorkspaceContent?.classList.add('d-none');
      return;
    }

    elements.categoryWorkspaceEmpty?.classList.add('d-none');
    elements.categoryWorkspaceContent?.classList.remove('d-none');

    if (elements.categoryCurrentName) elements.categoryCurrentName.textContent = job.name || 'Untitled Job';
    if (elements.categoryCurrentMeta) {
      elements.categoryCurrentMeta.textContent = `${job.site_label || 'Supplier'} - ${job.category_query || 'Saved categories'} - ${job.interval_label || 'Manual review'}`;
    }
    if (elements.categoryCurrentChips) {
      elements.categoryCurrentChips.innerHTML = [
        `<span class="category-pill">${escapeHtml(`Last discovery ${formatDateTime(job.last_discovery_at)}`)}</span>`,
        `<span class="category-pill">${escapeHtml(`Next run ${job.next_run_at ? formatDateTime(job.next_run_at) : 'Not scheduled'}`)}</span>`,
        `<span class="category-pill">${escapeHtml(job.auto_discover ? 'Refresh before run' : 'Use saved targets')}</span>`,
        `${draft.dirty ? '<span class="category-pill category-pill--dirty">Unsaved changes</span>' : ''}`
      ].join('');
    }
    if (elements.categoryCurrentStats) {
      elements.categoryCurrentStats.innerHTML = `
        <div class="category-overview-card">
          <span class="category-overview-card__value">${escapeHtml(String(counts.total))}</span>
          <span class="category-overview-card__label">Saved Categories</span>
        </div>
        <div class="category-overview-card">
          <span class="category-overview-card__value">${escapeHtml(String(counts.active))}</span>
          <span class="category-overview-card__label">Ready To Run</span>
        </div>
        <div class="category-overview-card">
          <span class="category-overview-card__value">${escapeHtml(String(counts.skipped))}</span>
          <span class="category-overview-card__label">Skipped</span>
        </div>
        <div class="category-overview-card">
          <span class="category-overview-card__value">${escapeHtml(String(groupStats.length))}</span>
          <span class="category-overview-card__label">Groups</span>
        </div>
      `;
    }
  }

  function renderGroupFilter() {
    if (!elements.categoryGroupFilter) return;
    const currentValue = state.filters.group;
    const groups = getGroupStats().map(group => group.name);
    elements.categoryGroupFilter.innerHTML = '<option value="">All groups</option>' + groups
      .map(group => `<option value="${escapeHtml(group)}">${escapeHtml(group)}</option>`)
      .join('');
    if (groups.includes(currentValue)) {
      elements.categoryGroupFilter.value = currentValue;
    } else {
      elements.categoryGroupFilter.value = '';
      state.filters.group = '';
    }
  }

  function renderVisibleSummary() {
    const job = getJob();
    const filtered = getFilteredTargets();
    const total = getCurrentTargets().length;
    const activeVisible = filtered.filter(target => target.active).length;
    if (elements.categoryVisibleSummary) {
      elements.categoryVisibleSummary.textContent = job
        ? `${filtered.length} of ${total} categories showing - ${activeVisible} ready to run`
        : '0 categories';
    }
    const hasVisibleTargets = filtered.length > 0;
    if (elements.categoryIncludeVisibleBtn) elements.categoryIncludeVisibleBtn.disabled = !hasVisibleTargets;
    if (elements.categorySkipVisibleBtn) elements.categorySkipVisibleBtn.disabled = !hasVisibleTargets;
    const draft = getDraft();
    if (elements.categorySaveBtn) elements.categorySaveBtn.disabled = !(job && draft?.dirty);
    if (elements.categoryRefreshBtn) elements.categoryRefreshBtn.disabled = !job;
    if (elements.categoryRunBtn) elements.categoryRunBtn.disabled = !job;
  }

  function renderGroupSummary() {
    if (!elements.categoryGroupSummary) return;
    const groups = getGroupStats();
    if (!groups.length) {
      elements.categoryGroupSummary.innerHTML = '';
      return;
    }
    elements.categoryGroupSummary.innerHTML = groups.map(group => `
      <button type="button" class="category-group-card ${group.name === state.filters.group ? 'is-active' : ''}" data-group-filter="${escapeHtml(group.name)}">
        <div class="category-group-card__name">${escapeHtml(group.name)}</div>
        <div class="category-group-card__meta">${escapeHtml(`${group.active} ready - ${group.skipped} skipped - ${group.total} total`)}</div>
      </button>
    `).join('');
  }

  function renderSelection() {
    if (!elements.categorySelectionSummary || !elements.categorySelectionList) return;
    const activeTargets = getCurrentTargets().filter(target => target.active);
    elements.categorySelectionSummary.textContent = activeTargets.length
      ? `${activeTargets.length} categories will run on the next session.`
      : 'Everything is skipped right now.';
    if (!activeTargets.length) {
      elements.categorySelectionList.innerHTML = '<span class="category-selection__chip is-muted">No categories ready</span>';
      return;
    }
    const displayTargets = activeTargets.slice(0, 24);
    elements.categorySelectionList.innerHTML = displayTargets
      .map(target => `<span class="category-selection__chip">${escapeHtml(target.label)}</span>`)
      .join('');
    if (activeTargets.length > displayTargets.length) {
      elements.categorySelectionList.innerHTML += `<span class="category-selection__chip is-muted">+${escapeHtml(String(activeTargets.length - displayTargets.length))} more</span>`;
    }
  }

  function renderTargets() {
    if (!elements.categoryTargets) return;
    const targets = getFilteredTargets();
    if (!targets.length) {
      elements.categoryTargets.innerHTML = `
        <div class="category-empty" style="min-height: 240px">
          <div>
            <h3>No categories match right now</h3>
            <p>Try a different search, status, or group filter.</p>
          </div>
        </div>
      `;
      return;
    }
    elements.categoryTargets.innerHTML = targets.map(target => `
      <div class="category-target ${target.active ? '' : 'is-skipped'}">
        <div class="category-target__top">
          <div class="category-target__copy">
            <div class="category-target__group">${escapeHtml(target.group_label || 'Ungrouped')}</div>
            <div class="category-target__label">${escapeHtml(target.label || target.url)}</div>
          </div>
          <button type="button" class="category-target__toggle ${target.active ? 'is-active' : 'is-skipped'}" data-action="toggle-target" data-url-key="${escapeHtml(target.url_key)}">
            ${escapeHtml(target.active ? 'Included' : 'Skipped')}
          </button>
        </div>
        <a class="category-target__url" href="${escapeHtml(target.url)}" target="_blank" rel="noreferrer">${escapeHtml(target.url)}</a>
        <div class="category-target__meta">
          <span class="category-pill">${escapeHtml(`Position ${target.position + 1}`)}</span>
          <span class="category-pill ${target.active ? 'category-pill--ok' : 'category-pill--danger'}">${escapeHtml(target.active ? 'Ready for next run' : 'Held back')}</span>
        </div>
      </div>
    `).join('');
  }

  function renderPage() {
    renderSummaryStatus();
    renderOverallStats();
    renderJobs();
    renderCurrentJob();
    renderGroupFilter();
    renderVisibleSummary();
    renderGroupSummary();
    renderSelection();
    renderTargets();
  }

  async function loadJobs(options = {}) {
    const silent = Boolean(options.silent);
    try {
      if (!silent) setLoading(true);
      const data = await api('/api/automation/jobs');
      state.jobs = (data.jobs || []).map(normalizeJob);

      const activeJobIds = new Set(state.jobs.map(job => String(job.id)));
      Object.keys(state.drafts).forEach(jobId => {
        if (!activeJobIds.has(jobId)) delete state.drafts[jobId];
      });
      state.jobs.forEach(job => syncDraftFromJob(job));

      if (!state.jobs.length) {
        state.selectedJobId = null;
      } else if (!getJob(state.selectedJobId)) {
        state.selectedJobId = Number(state.jobs[0].id);
      }
      renderPage();
    } catch (err) {
      showAlert('error', err.message || 'Failed to load saved jobs.');
    } finally {
      if (!silent) setLoading(false);
    }
  }

  async function saveCategories() {
    const job = getJob();
    const draft = getDraft();
    if (!job || !draft?.dirty) {
      showAlert('info', 'Nothing new to save.');
      return;
    }
    try {
      setLoading(true);
      const data = await api(`/api/automation/jobs/${encodeURIComponent(job.id)}/targets`, {
        method: 'POST',
        body: JSON.stringify({ targets: draft.targets })
      });
      const updatedJob = normalizeJob(data.job || job);
      state.jobs = state.jobs.map(entry => Number(entry.id) === Number(updatedJob.id) ? updatedJob : entry);
      syncDraftFromJob(updatedJob, true);
      renderPage();
      showAlert('success', `${updatedJob.active_target_count || 0} categories are ready for ${updatedJob.name}.`);
    } catch (err) {
      showAlert('error', err.message || 'Failed to save categories.');
    } finally {
      setLoading(false);
    }
  }

  async function refreshCategories() {
    const job = getJob();
    const draft = getDraft();
    if (!job) return;
    if (draft?.dirty) {
      showAlert('warning', 'Save the current category edits before refreshing links.');
      return;
    }
    try {
      setLoading(true);
      const data = await api(`/api/automation/jobs/${encodeURIComponent(job.id)}/refresh-targets`, {
        method: 'POST'
      });
      const updatedJob = normalizeJob(data.job || job);
      state.jobs = state.jobs.map(entry => Number(entry.id) === Number(updatedJob.id) ? updatedJob : entry);
      syncDraftFromJob(updatedJob, true);
      renderPage();
      showAlert('success', `${updatedJob.target_count || 0} categories refreshed for ${updatedJob.name}.`);
    } catch (err) {
      const message = String(err.message || '');
      if (message.includes('403') && String(job.scraper_key || '').toLowerCase() === 'xcell') {
        showAlert('warning', 'XCell blocked live discovery right now. The saved categories are still available for editing and runs.');
      } else {
        showAlert('error', message || 'Failed to refresh categories.');
      }
    } finally {
      setLoading(false);
    }
  }

  async function runSelectedJob() {
    const job = getJob();
    if (!job) return;
    try {
      setLoading(true);
      await api(`/api/automation/jobs/${encodeURIComponent(job.id)}/run`, {
        method: 'POST'
      });
      showAlert('success', `${job.name} is running now.`);
      await loadJobs({ silent: true });
    } catch (err) {
      showAlert('error', err.message || 'Failed to start the job.');
    } finally {
      setLoading(false);
    }
  }

  function clearFilters() {
    state.filters = { search: '', status: 'all', group: '' };
    if (elements.categorySearch) elements.categorySearch.value = '';
    if (elements.categoryStatusFilter) elements.categoryStatusFilter.value = 'all';
    if (elements.categoryGroupFilter) elements.categoryGroupFilter.value = '';
    renderPage();
  }

  function bindEvents() {
    elements.categoryJobs?.addEventListener('click', event => {
      const button = event.target.closest('[data-job-id]');
      if (!button) return;
      setSelectedJob(button.dataset.jobId);
    });

    elements.categoryTargets?.addEventListener('click', event => {
      const button = event.target.closest('[data-action="toggle-target"]');
      if (!button) return;
      const urlKey = String(button.dataset.urlKey || '').trim().toLowerCase();
      const target = getCurrentTargets().find(entry => entry.url_key === urlKey);
      if (!target) return;
      setTargetActive(urlKey, !target.active);
    });

    elements.categoryGroupSummary?.addEventListener('click', event => {
      const button = event.target.closest('[data-group-filter]');
      if (!button) return;
      const nextGroup = String(button.dataset.groupFilter || '');
      state.filters.group = state.filters.group === nextGroup ? '' : nextGroup;
      if (elements.categoryGroupFilter) elements.categoryGroupFilter.value = state.filters.group;
      renderPage();
    });

    elements.categorySearch?.addEventListener('input', event => {
      state.filters.search = String(event.target.value || '');
      renderPage();
    });

    elements.categoryStatusFilter?.addEventListener('change', event => {
      state.filters.status = String(event.target.value || 'all');
      renderPage();
    });

    elements.categoryGroupFilter?.addEventListener('change', event => {
      state.filters.group = String(event.target.value || '');
      renderPage();
    });

    elements.categoryIncludeVisibleBtn?.addEventListener('click', () => setVisibleTargetsActive(true));
    elements.categorySkipVisibleBtn?.addEventListener('click', () => setVisibleTargetsActive(false));
    elements.categorySaveBtn?.addEventListener('click', saveCategories);
    elements.categoryRefreshBtn?.addEventListener('click', refreshCategories);
    elements.categoryRunBtn?.addEventListener('click', runSelectedJob);
    elements.categoryClearFilters?.addEventListener('click', clearFilters);
  }

  async function boot() {
    initTheme();
    bindEvents();
    renderPage();
    await loadJobs({ silent: false });
    window.setInterval(() => {
      loadJobs({ silent: true }).catch(() => { });
    }, 30000);
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
