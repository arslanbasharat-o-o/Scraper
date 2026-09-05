'use strict';

const $ = id => document.getElementById(id);

const elements = {
  alert: $('alert'),
  darkMode: $('darkMode'),
  refreshBtn: $('refreshBtn'),
  clearRunSelectedBtn: $('clearRunSelectedBtn'),
  runSelectedBtn: $('runSelectedBtn'),
  runAllBtn: $('runAllBtn'),
  visibleMode: $('visibleMode'),
  validateUrls: $('validateUrls'),
  inspectOnly: $('inspectOnly'),
  siteCards: $('siteCards'),
  siteTitle: $('siteTitle'),
  siteSubtitle: $('siteSubtitle'),
  siteBadges: $('siteBadges'),
  siteBehavior: $('siteBehavior'),
  fileStrip: $('fileStrip'),
  exportTargetSummary: $('exportTargetSummary'),
  exportVisibleCsvBtn: $('exportVisibleCsvBtn'),
  exportVisibleXlsxBtn: $('exportVisibleXlsxBtn'),
  exportFullCsvBtn: $('exportFullCsvBtn'),
  exportFullXlsxBtn: $('exportFullXlsxBtn'),
  automationTargetSummary: $('automationTargetSummary'),
  runAutomationForSiteBtn: $('runAutomationForSiteBtn'),
  treeContainer: $('treeContainer'),
  treeSearch: $('treeSearch'),
  resetHiddenBtn: $('resetHiddenBtn'),
  expandAllBtn: $('expandAllBtn'),
  collapseAllBtn: $('collapseAllBtn'),
  hiddenSummary: $('hiddenSummary'),
  jobPanel: $('jobPanel'),
  statSites: $('statSites'),
  statParents: $('statParents'),
  statSubs: $('statSubs'),
  statChildren: $('statChildren'),
  statIssues: $('statIssues'),
  detailParents: $('detailParents'),
  detailSubs: $('detailSubs'),
  detailChildren: $('detailChildren'),
  detailMissing: $('detailMissing'),
  detailDuplicates: $('detailDuplicates'),
  detailErrors: $('detailErrors'),
  treeSummary: $('treeSummary'),
  scrollTopBtn: $('scrollTopBtn'),
};

let sites = [];
let selectedSite = '';
let selectedRunSites = new Set();
let runSelectionInitialized = false;
let activeJobId = '';
let activeJobStatus = '';
let pollTimer = null;
let pollRequestPending = false;
let pollFailureCount = 0;
let sitesLoadPending = false;
let completedJobClearTimer = null;
let jobPanelMode = 'idle';
let runSubmissionPending = false;
let automationSubmissionPending = false;
let excludedBySite = loadExclusions();
let treeOpenStateBySite = loadTreeOpenState();
let activeTreeFilter = 'all';
const MENU_POLL_BASE_MS = 2500;
const MENU_POLL_MAX_MS = 30000;
const MAX_JOB_OUTPUT_CHARS = 1600;

const AUTOMATION_SITE_KEY = {
  xcellparts: 'xcell',
  parts4cells: 'parts4cells',
  phonelcdparts: 'phonelcdparts',
  mobilesentrix: 'standard',
  mobilesentrix_canada: 'mobilesentrix_canada',
  txparts: 'txparts',
  txparts_canada: 'txparts',
  gadgetfix: 'gadgetfix',
};

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

let menuMapConfirmResolver = null;
let menuMapConfirmReturnFocus = null;
let menuMapConfirmBound = false;

function resolveMenuMapConfirm(result) {
  const modal = document.getElementById('menuMapConfirmModal');
  const resolver = menuMapConfirmResolver;
  const returnFocus = menuMapConfirmReturnFocus;
  menuMapConfirmResolver = null;
  menuMapConfirmReturnFocus = null;
  if (modal) {
    modal.classList.add('d-none');
    modal.setAttribute('aria-hidden', 'true');
  }
  document.body.classList.remove('modal-open');
  if (returnFocus?.isConnected && typeof returnFocus.focus === 'function' && !returnFocus.disabled) {
    returnFocus.focus({ preventScroll: true });
  }
  if (typeof resolver === 'function') resolver(Boolean(result));
}

function bindMenuMapConfirm() {
  if (menuMapConfirmBound) return;
  const modal = document.getElementById('menuMapConfirmModal');
  if (!modal) return;
  menuMapConfirmBound = true;
  const cancel = document.getElementById('menuMapConfirmCancelBtn');
  const confirm = document.getElementById('menuMapConfirmConfirmBtn');
  modal.addEventListener('click', event => {
    if (event.target === modal) resolveMenuMapConfirm(false);
  });
  cancel?.addEventListener('click', () => resolveMenuMapConfirm(false));
  confirm?.addEventListener('click', () => resolveMenuMapConfirm(true));
  document.addEventListener('keydown', event => {
    if (!menuMapConfirmResolver || modal.classList.contains('d-none')) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      resolveMenuMapConfirm(false);
      return;
    }
    if (event.key === 'Enter' && event.target !== cancel) {
      event.preventDefault();
      resolveMenuMapConfirm(true);
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = [cancel, confirm].filter(button => button && !button.disabled);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
}

function showMenuMapConfirm({
  title = 'Please confirm',
  message = 'Are you sure you want to continue?',
  confirmLabel = 'Continue',
  cancelLabel = 'Cancel',
  danger = false,
} = {}) {
  const modal = document.getElementById('menuMapConfirmModal');
  const titleEl = document.getElementById('menuMapConfirmModalTitle');
  const messageEl = document.getElementById('menuMapConfirmModalMessage');
  const confirm = document.getElementById('menuMapConfirmConfirmBtn');
  const cancel = document.getElementById('menuMapConfirmCancelBtn');
  if (!modal || !titleEl || !messageEl || !confirm || !cancel) {
    return Promise.resolve(window.confirm(message));
  }
  bindMenuMapConfirm();
  if (menuMapConfirmResolver) resolveMenuMapConfirm(false);
  menuMapConfirmReturnFocus = document.activeElement !== document.body ? document.activeElement : null;
  titleEl.textContent = title;
  messageEl.textContent = message;
  confirm.textContent = confirmLabel;
  cancel.textContent = cancelLabel;
  confirm.classList.toggle('btn-danger', danger);
  confirm.classList.toggle('btn-export', !danger);
  modal.classList.remove('d-none');
  modal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('modal-open');
  return new Promise(resolve => {
    menuMapConfirmResolver = resolve;
    requestAnimationFrame(() => (danger ? confirm : cancel).focus());
  });
}

function showAlert(type, message) {
  if (!elements.alert) return;
  const cls = type === 'error' ? 'alert-danger' : type === 'warn' ? 'alert-warning' : type === 'success' ? 'alert-success' : 'alert-info';
  elements.alert.className = `alert-banner ${cls}`;
  elements.alert.textContent = message;
  elements.alert.classList.remove('d-none');
  window.clearTimeout(elements.alert._timer);
  elements.alert._timer = window.setTimeout(() => elements.alert.classList.add('d-none'), 7000);
}

function ensureExclusionUi() {
  if (!elements.resetHiddenBtn) {
    const toolbar = document.querySelector('.toolbar-right');
    if (toolbar) {
      const button = document.createElement('button');
      button.id = 'resetHiddenBtn';
      button.className = 'btn-export';
      button.type = 'button';
      button.textContent = 'Reset Hidden';
      const expand = elements.expandAllBtn;
      toolbar.insertBefore(button, expand || null);
      elements.resetHiddenBtn = button;
    }
  }
  if (!elements.hiddenSummary && elements.treeContainer) {
    const summary = document.createElement('div');
    summary.id = 'hiddenSummary';
    summary.className = 'hidden-summary';
    elements.treeContainer.parentElement.insertBefore(summary, elements.treeContainer);
    elements.hiddenSummary = summary;
  }
  if (!elements.runAutomationForSiteBtn) {
    const fileStrip = elements.fileStrip;
    if (fileStrip?.parentElement) {
      const strip = document.createElement('div');
      strip.className = 'automation-launch-strip';
      strip.innerHTML = `
        <div>
          <div class="automation-launch-strip__title">Automation From Visible Categories</div>
          <div id="automationTargetSummary" class="automation-launch-strip__meta">Hide anything you do not want, then run automation for this website.</div>
        </div>
        <button id="runAutomationForSiteBtn" class="btn-run" type="button"><span>Run Automation</span></button>
      `;
      fileStrip.insertAdjacentElement('afterend', strip);
      elements.automationTargetSummary = $('automationTargetSummary');
      elements.runAutomationForSiteBtn = $('runAutomationForSiteBtn');
    }
  }
}

async function fetchJson(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
  const response = await fetch(url, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Server ${response.status}`);
  return data;
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString();
}

function loadExclusions() {
  try {
    const parsed = JSON.parse(localStorage.getItem('menu_map_exclusions') || '{}');
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (_err) {
    return {};
  }
}

function loadTreeOpenState() {
  try {
    const parsed = JSON.parse(localStorage.getItem('menu_map_tree_open_state') || '{}');
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (_err) {
    return {};
  }
}

function saveTreeOpenState() {
  localStorage.setItem('menu_map_tree_open_state', JSON.stringify(treeOpenStateBySite));
}

function saveExclusions() {
  localStorage.setItem('menu_map_exclusions', JSON.stringify(excludedBySite));
}

function exclusionSet(slug) {
  if (!excludedBySite[slug]) excludedBySite[slug] = [];
  return new Set(excludedBySite[slug]);
}

function setExclusionSet(slug, set) {
  excludedBySite[slug] = [...set];
  saveExclusions();
}

function makeKey(parts) {
  return parts.map(part => String(part || '').replace(/\s+/g, ' ').trim()).join('::');
}

function parentKey(parent) {
  return makeKey(['parent', parent.display_order || parent.order, parent.parent_name, parent.parent_url]);
}

function subKey(parent, sub) {
  return makeKey(['sub', parent.display_order || parent.order, parent.parent_name, sub.display_order || sub.order, sub.sub_child_name, sub.sub_child_url]);
}

function childKey(parent, sub, child) {
  return makeKey([
    'child',
    parent.display_order || parent.order,
    parent.parent_name,
    sub.display_order || sub.order,
    sub.sub_child_name,
    child.display_order || child.order,
    child.child_name,
    child.child_url,
  ]);
}

function isExcluded(slug, key) {
  return exclusionSet(slug).has(key);
}

function hiddenCount(slug) {
  return exclusionSet(slug).size;
}

function captureTreeOpenState(slug) {
  if (!slug || !elements.treeContainer) return;
  const nextState = { ...(treeOpenStateBySite[slug] || {}) };
  elements.treeContainer.querySelectorAll('details[data-tree-key]').forEach(detail => {
    nextState[detail.dataset.treeKey] = Boolean(detail.open);
  });
  if (Object.keys(nextState).length) {
    treeOpenStateBySite[slug] = nextState;
    saveTreeOpenState();
  }
}

function setAllTreeOpenState(slug, open) {
  if (!slug) return;
  const site = sites.find(item => item.slug === slug);
  if (!site) return;
  const nextState = {};
  (site.tree || []).forEach(parent => {
    nextState[parentKey(parent)] = open;
    (parent.sub_children || []).forEach(sub => {
      nextState[subKey(parent, sub)] = open;
    });
  });
  treeOpenStateBySite[slug] = nextState;
  saveTreeOpenState();
  elements.treeContainer?.querySelectorAll('details[data-tree-key]').forEach(detail => {
    detail.open = open;
  });
}

function excludeNode(slug, key, label) {
  captureTreeOpenState(slug);
  const set = exclusionSet(slug);
  set.add(key);
  setExclusionSet(slug, set);
  showAlert('info', `Hidden: ${label}`);
  render();
}

function clearExclusions(slug) {
  if (!slug) return;
  captureTreeOpenState(slug);
  excludedBySite[slug] = [];
  saveExclusions();
  showAlert('success', 'Hidden categories restored.');
  render();
}

function visibleSummary(site) {
  const slug = site.slug;
  const tree = Array.isArray(site.tree) ? site.tree : [];
  let parents = 0;
  let subChildren = 0;
  let children = 0;
  tree.forEach(parent => {
    if (isExcluded(slug, parentKey(parent))) return;
    parents += 1;
    (parent.sub_children || []).forEach(sub => {
      if (isExcluded(slug, subKey(parent, sub))) return;
      subChildren += 1;
      (sub.children || []).forEach(child => {
        if (!isExcluded(slug, childKey(parent, sub, child))) children += 1;
      });
    });
  });
  return { parents, sub_children: subChildren, children };
}

function isUsableUrl(url) {
  const value = String(url || '').trim();
  return Boolean(value) && !/^(#|javascript[:;]?|javascript:void\(0\))/i.test(value);
}

function addTarget(targets, seen, target) {
  const url = String(target.url || '').trim();
  if (!isUsableUrl(url)) return;
  const key = url.toLowerCase();
  if (seen.has(key)) return;
  seen.add(key);
  targets.push({
    label: String(target.label || url).trim(),
    group_label: String(target.group_label || '').trim(),
    url,
    active: true,
    position: targets.length + 1,
  });
}

function buildAutomationTargets(site, includeHidden = false) {
  const slug = site.slug;
  const tree = Array.isArray(site.tree) ? site.tree : [];
  const targets = [];
  const seen = new Set();

  tree.forEach(parent => {
    if (!includeHidden && isExcluded(slug, parentKey(parent))) return;
    const subs = Array.isArray(parent.sub_children) ? parent.sub_children : [];

    subs.forEach(sub => {
      if (!includeHidden && isExcluded(slug, subKey(parent, sub))) return;
      const children = Array.isArray(sub.children) ? sub.children : [];
      children.forEach(child => {
        if (!includeHidden && isExcluded(slug, childKey(parent, sub, child))) return;
        if (!isUsableUrl(child.child_url)) return;
        addTarget(targets, seen, {
          label: child.child_name,
          group_label: `${parent.parent_name} > ${sub.sub_child_name}`,
          url: child.child_url,
        });
      });

      if (children.length === 0 && isUsableUrl(sub.sub_child_url)) {
        addTarget(targets, seen, {
          label: sub.sub_child_name,
          group_label: parent.parent_name,
          url: sub.sub_child_url,
        });
      }
    });

    if (subs.length === 0 && isUsableUrl(parent.parent_url)) {
      addTarget(targets, seen, {
        label: parent.parent_name,
        group_label: site.name,
        url: parent.parent_url,
      });
    }
  });

  return targets;
}

function compactLabel(value) {
  return String(value || '')
    .replace(/\s+/g, ' ')
    .replace(/\s*>\s*/g, ' > ')
    .trim();
}

function cleanJobScopeLabel(label) {
  const cleaned = compactLabel(label)
    .replace(/^menu\s+map\s*[-:]\s*/i, '')
    .replace(/\b20\d{2,}\b/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  return cleaned || 'Visible Categories';
}

function targetScopeForJob(site, targets) {
  const query = compactLabel(elements.treeSearch?.value || '');
  if (query) return cleanJobScopeLabel(query);

  const topGroups = new Map();
  targets.forEach(target => {
    const group = compactLabel(target.group_label);
    const label = compactLabel(target.label);
    let top = group.split(' > ').filter(Boolean)[0] || label;
    if (top && top.toLowerCase() === String(site.name || '').toLowerCase()) top = label;
    top = cleanJobScopeLabel(top);
    if (!top) return;
    topGroups.set(top, (topGroups.get(top) || 0) + 1);
  });

  const ranked = [...topGroups.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .map(([name]) => name);

  if (ranked.length === 0) return 'Visible Categories';
  if (ranked.length === 1) return ranked[0];
  if (ranked.length <= 3 && targets.length <= 150) return ranked.join(', ');
  return 'Visible Categories';
}

function automationPayloadForSite(site, targets) {
  const scope = targetScopeForJob(site, targets);
  return {
    name: `${cleanJobScopeLabel(site.name)} - ${scope}`,
    scraper_key: AUTOMATION_SITE_KEY[site.slug] || 'standard',
    category_query: scope,
    root_url: site.url,
    interval_minutes: 24 * 60,
    enabled: false,
    auto_discover: false,
    use_parallel: true,
    enrich_details: true,
    crawl_pagination: true,
    verify_ssl: true,
    retries: 1,
    max_pages: 10,
    delay_ms: 50,
    drop_pct: 10,
    rules: {},
    targets,
  };
}

function selectedSites() {
  return sites.map(site => site.slug).filter(slug => selectedRunSites.has(slug));
}

function syncRunSelection() {
  const availableSlugs = new Set(sites.map(site => site.slug));
  if (!runSelectionInitialized) {
    selectedRunSites = new Set(availableSlugs);
    runSelectionInitialized = true;
    return;
  }
  selectedRunSites.forEach(slug => {
    if (!availableSlugs.has(slug)) selectedRunSites.delete(slug);
  });
}

function isMenuRunBusy() {
  return runSubmissionPending || ['queued', 'running'].includes(activeJobStatus);
}

function updateRunControls() {
  const menuRunBusy = isMenuRunBusy();
  if (elements.clearRunSelectedBtn) elements.clearRunSelectedBtn.disabled = sitesLoadPending || menuRunBusy || selectedSites().length === 0;
  if (elements.runSelectedBtn) elements.runSelectedBtn.disabled = sitesLoadPending || menuRunBusy || selectedSites().length === 0;
  if (elements.runAllBtn) elements.runAllBtn.disabled = sitesLoadPending || menuRunBusy || sites.length === 0;
  [elements.visibleMode, elements.validateUrls, elements.inspectOnly].forEach(control => {
    if (control) control.disabled = menuRunBusy;
  });
  elements.siteCards?.querySelectorAll('.site-select').forEach(input => {
    input.disabled = menuRunBusy;
  });

  const site = sites.find(item => item.slug === selectedSite);
  const hasAutomationTargets = Boolean(site?.has_output && buildAutomationTargets(site).length);
  const hasExportTargets = Boolean(site?.has_output && buildAutomationTargets(site, true).length);
  [elements.exportVisibleCsvBtn, elements.exportVisibleXlsxBtn, elements.exportFullCsvBtn, elements.exportFullXlsxBtn].forEach(button => {
    if (button) button.disabled = sitesLoadPending || !hasExportTargets;
  });
  if (elements.runAutomationForSiteBtn) {
    elements.runAutomationForSiteBtn.disabled = sitesLoadPending || menuRunBusy || automationSubmissionPending || !hasAutomationTargets;
  }
}

function statusFor(site) {
  if (!site.has_output) return { label: 'No Output', cls: 'no-output' };
  if (site.parse_error || site.output_valid === false) return { label: 'Invalid Output', cls: 'invalid' };
  if (site.output_empty) return { label: 'Empty Output', cls: 'empty-output' };
  return { label: 'Ready', cls: 'ready' };
}

function renderCards() {
  const menuRunBusy = isMenuRunBusy();
  elements.siteCards.innerHTML = sites.map(site => {
    const status = statusFor(site);
    const active = site.slug === selectedSite ? ' active' : '';
    const summary = visibleSummary(site);
    const hidden = hiddenCount(site.slug);
    return `
      <article class="site-card${active}" data-site="${escapeHtml(site.slug)}" role="button" tabindex="0" aria-label="Inspect ${escapeHtml(site.name)} hierarchy" aria-pressed="${site.slug === selectedSite}">
        <div class="site-card__top">
          <div>
            <div class="site-card__name">${escapeHtml(site.name)}</div>
            <div class="site-card__url">${escapeHtml(site.url)}</div>
          </div>
          <span class="status-pill ${status.cls}">${status.label}</span>
        </div>
        <div class="site-card__meta">
          ${formatNumber(summary.parents)} parents - ${formatNumber(summary.sub_children)} sub - ${formatNumber(summary.children)} children
          ${hidden ? `<span class="site-card__hidden">${formatNumber(hidden)} hidden</span>` : ''}
        </div>
        <div class="site-card__checks">
          <label><input class="site-select" type="checkbox" value="${escapeHtml(site.slug)}" aria-label="Run scraper for ${escapeHtml(site.name)}"${selectedRunSites.has(site.slug) ? ' checked' : ''}${menuRunBusy ? ' disabled' : ''}> Run</label>
        </div>
      </article>
    `;
  }).join('');

  elements.siteCards.querySelectorAll('.site-card').forEach(card => {
    card.addEventListener('click', event => {
      if (event.target.closest('.site-card__checks')) return;
      selectedSite = card.dataset.site;
      render();
    });
    card.addEventListener('keydown', event => {
      if (event.target.closest('.site-card__checks') || !['Enter', ' '].includes(event.key)) return;
      event.preventDefault();
      selectedSite = card.dataset.site;
      render();
    });
  });
  elements.siteCards.querySelectorAll('.site-select').forEach(input => {
    input.addEventListener('change', () => {
      if (input.checked) selectedRunSites.add(input.value);
      else selectedRunSites.delete(input.value);
      updateRunControls();
    });
  });
}

function renderOverall() {
  const totals = sites.reduce((acc, site) => {
    const summary = visibleSummary(site);
    acc.parents += summary.parents || 0;
    acc.subs += summary.sub_children || 0;
    acc.children += summary.children || 0;
    acc.issues += (site.error_count || 0) + (site.missing_urls || 0);
    return acc;
  }, { parents: 0, subs: 0, children: 0, issues: 0 });
  elements.statSites.textContent = formatNumber(sites.length);
  elements.statParents.textContent = formatNumber(totals.parents);
  elements.statSubs.textContent = formatNumber(totals.subs);
  elements.statChildren.textContent = formatNumber(totals.children);
  elements.statIssues.textContent = formatNumber(totals.issues);
}

function renderDetail() {
  const site = sites.find(item => item.slug === selectedSite) || sites[0];
  if (!site) return;
  selectedSite = site.slug;
  const status = statusFor(site);
  const summary = visibleSummary(site);
  elements.siteTitle.textContent = site.name;
  elements.siteSubtitle.textContent = site.last_modified ? `Last output: ${site.last_modified}` : 'No scraper output found yet.';
  elements.siteBadges.innerHTML = `
    <span class="status-pill ${status.cls}">${status.label}</span>
    <span class="badge-soft">${escapeHtml(site.slug)}</span>
  `;
  elements.siteBehavior.textContent = site.behavior || '';
  elements.detailParents.textContent = formatNumber(summary.parents);
  elements.detailSubs.textContent = formatNumber(summary.sub_children);
  elements.detailChildren.textContent = formatNumber(summary.children);
  elements.detailMissing.textContent = formatNumber(site.missing_urls);
  elements.detailDuplicates.textContent = formatNumber(site.duplicate_rows);
  elements.detailErrors.textContent = formatNumber(site.error_count);
  document.querySelectorAll('[data-detail-action]').forEach(card => {
    const action = card.dataset.detailAction;
    const summaryOnly = ['parents', 'subs', 'children'].includes(action);
    const active = action === 'missing' && activeTreeFilter === 'missing';
    card.disabled = summaryOnly;
    card.classList.toggle('active', active);
    if (action === 'missing') card.setAttribute('aria-pressed', String(active));
    else card.removeAttribute('aria-pressed');
  });
  document.querySelectorAll('[data-summary-action]').forEach(card => {
    card.disabled = ['parents', 'subs', 'children'].includes(card.dataset.summaryAction);
    card.classList.remove('active');
    card.removeAttribute('aria-pressed');
  });
  const automationTargets = buildAutomationTargets(site);
  if (elements.automationTargetSummary) {
    const hidden = hiddenCount(site.slug);
    elements.automationTargetSummary.textContent = site.has_output
      ? `${formatNumber(automationTargets.length)} visible target URL${automationTargets.length === 1 ? '' : 's'} will be saved and queued. ${hidden ? `${formatNumber(hidden)} hidden item${hidden === 1 ? ' is' : 's are'} excluded.` : 'Nothing is hidden.'}`
      : 'Run this scraper first so Menu Map has category targets for automation.';
  }
  if (elements.exportTargetSummary) {
    const fullTargets = buildAutomationTargets(site, true);
    elements.exportTargetSummary.textContent = site.has_output
      ? `${formatNumber(automationTargets.length)} visible link${automationTargets.length === 1 ? '' : 's'} or ${formatNumber(fullTargets.length)} full link${fullTargets.length === 1 ? '' : 's'} can be exported.`
      : 'Run this scraper first to create exportable menu links.';
  }
  renderFiles(site);
  renderTree(site);
}

function renderFiles(site) {
  const files = Object.values(site.files || {});
  if (!files.length) {
    elements.fileStrip.innerHTML = '<span class="section-subtitle">No output files yet. Run this scraper to create them.</span>';
    return;
  }
  elements.fileStrip.innerHTML = files.map(file => `
    <a class="file-link" href="${escapeHtml(file.download_url)}">${escapeHtml(file.name)}</a>
  `).join('');
}

function textMatches(text, query) {
  return !query || String(text || '').toLowerCase().includes(query);
}

function renderTree(site) {
  const tree = Array.isArray(site.tree) ? site.tree : [];
  const slug = site.slug;
  const query = (elements.treeSearch.value || '').trim().toLowerCase();
  if (!tree.length) {
    elements.treeSummary.textContent = 'No hierarchy loaded yet.';
    if (elements.hiddenSummary) elements.hiddenSummary.textContent = '';
    elements.treeContainer.className = 'menu-tree-empty';
    elements.treeContainer.textContent = 'Run this scraper or refresh outputs to load the category tree.';
    return;
  }

  let visibleParents = 0;
  let visibleSubs = 0;
  let visibleChildren = 0;
  const hidden = hiddenCount(slug);
  if (elements.hiddenSummary) {
    elements.hiddenSummary.textContent = hidden
      ? `${formatNumber(hidden)} hidden item${hidden === 1 ? '' : 's'} on this site. Hidden parents and sub-child groups also hide everything below them.`
      : 'Use X to hide a parent, sub-child group, or child from this dashboard view.';
  }
  const html = tree.map(parent => {
    const pKey = parentKey(parent);
    if (isExcluded(slug, pKey)) return '';
    const subs = Array.isArray(parent.sub_children) ? parent.sub_children : [];
    const renderedSubs = subs.map(sub => {
      const sKey = subKey(parent, sub);
      if (isExcluded(slug, sKey)) return '';
      const children = Array.isArray(sub.children) ? sub.children : [];
      const filteredChildren = children.filter(child => {
        if (isExcluded(slug, childKey(parent, sub, child))) return false;
        if (activeTreeFilter === 'missing' && isUsableUrl(child.child_url)) return false;
        const blob = `${child.child_name || ''} ${child.child_url || ''} ${sub.sub_child_name || ''} ${parent.parent_name || ''}`.toLowerCase();
        return textMatches(blob, query);
      });
      const subBlob = `${sub.sub_child_name || ''} ${sub.sub_child_url || ''} ${parent.parent_name || ''}`.toLowerCase();
      const subIsMissing = !isUsableUrl(sub.sub_child_url);
      if (activeTreeFilter === 'missing' && !subIsMissing && !filteredChildren.length) return '';
      if (query && !filteredChildren.length && !textMatches(subBlob, query)) return '';
      visibleSubs += 1;
      visibleChildren += filteredChildren.length;
      return `
        <details class="tree-sub" data-tree-key="${escapeHtml(sKey)}">
          <summary>
            <div class="tree-sub__head">
              <span class="tree-sub__name">${escapeHtml(sub.sub_child_name)}</span>
              <span class="tree-node-actions">
                <span class="tree-sub__meta">${formatNumber(filteredChildren.length)} children</span>
                <button class="tree-remove-btn" type="button" data-hide-key="${escapeHtml(sKey)}" data-hide-label="${escapeHtml(`${parent.parent_name} > ${sub.sub_child_name}`)}" title="Hide sub-child category" aria-label="Hide sub-child category ${escapeHtml(`${parent.parent_name} > ${sub.sub_child_name}`)}">X</button>
              </span>
            </div>
          </summary>
          <div class="tree-child-list">
            ${filteredChildren.map(child => `
              <div class="tree-child">
                <a class="tree-child__link" href="${escapeHtml(child.child_url || '#')}" target="_blank" rel="noreferrer">
                  <span>${escapeHtml(child.child_name)}</span>
                  <span class="tree-child__order">#${escapeHtml(child.display_order || '')}</span>
                </a>
                <button class="tree-remove-btn tree-remove-btn--child" type="button" data-hide-key="${escapeHtml(childKey(parent, sub, child))}" data-hide-label="${escapeHtml(`${parent.parent_name} > ${sub.sub_child_name} > ${child.child_name}`)}" title="Hide child category" aria-label="Hide child category ${escapeHtml(`${parent.parent_name} > ${sub.sub_child_name} > ${child.child_name}`)}">X</button>
              </div>
            `).join('') || '<div class="section-subtitle">No matching child links.</div>'}
          </div>
        </details>
      `;
    }).filter(Boolean).join('');
    const parentBlob = `${parent.parent_name || ''} ${parent.parent_url || ''}`.toLowerCase();
    const parentIsMissing = !isUsableUrl(parent.parent_url);
    if (activeTreeFilter === 'missing' && !parentIsMissing && !renderedSubs) return '';
    if (query && !renderedSubs && !textMatches(parentBlob, query)) return '';
    visibleParents += 1;
    return `
      <details class="tree-parent" data-tree-key="${escapeHtml(pKey)}">
        <summary>
          <div class="tree-parent__head">
            <span class="tree-parent__name">${escapeHtml(parent.parent_name)}</span>
            <span class="tree-node-actions">
              <span class="tree-parent__meta">${formatNumber(subs.length)} sub groups</span>
              <button class="tree-remove-btn" type="button" data-hide-key="${escapeHtml(pKey)}" data-hide-label="${escapeHtml(parent.parent_name)}" title="Hide parent category" aria-label="Hide parent category ${escapeHtml(parent.parent_name)}">X</button>
            </span>
          </div>
        </summary>
        <div class="tree-sub-list">${renderedSubs || '<div class="section-subtitle">No matching sub-child groups.</div>'}</div>
      </details>
    `;
  }).filter(Boolean).join('');

  const filterLabel = activeTreeFilter === 'missing' ? 'missing URLs' : 'all categories';
  elements.treeSummary.textContent = `${formatNumber(visibleParents)} visible parents - ${formatNumber(visibleSubs)} visible sub groups - ${formatNumber(visibleChildren)} visible child links - ${filterLabel}`;
  elements.treeContainer.className = 'menu-tree';
  elements.treeContainer.innerHTML = html || '<div class="menu-tree-empty">No categories match your search.</div>';
  const openState = treeOpenStateBySite[slug] || {};
  elements.treeContainer.querySelectorAll('details[data-tree-key]').forEach(detail => {
    detail.open = Boolean(openState[detail.dataset.treeKey]);
    detail.addEventListener('toggle', () => {
      if (!treeOpenStateBySite[slug]) treeOpenStateBySite[slug] = {};
      treeOpenStateBySite[slug][detail.dataset.treeKey] = Boolean(detail.open);
      saveTreeOpenState();
    });
  });
  elements.treeContainer.querySelectorAll('.tree-remove-btn').forEach(button => {
    button.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      excludeNode(slug, button.dataset.hideKey, button.dataset.hideLabel || 'category');
    });
  });
}

function focusElement(element) {
  element?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function setTreeFilter(filter) {
  activeTreeFilter = filter;
  elements.treeSearch.value = '';
  renderDetail();
  focusElement(elements.treeContainer.closest('.menu-map-panel'));
}

function showSiteErrors(site) {
  window.clearTimeout(completedJobClearTimer);
  completedJobClearTimer = null;
  jobPanelMode = 'site-errors';
  elements.jobPanel.setAttribute('aria-busy', 'false');
  const errors = Array.isArray(site.errors) ? site.errors : [];
  elements.jobPanel.className = errors.length ? 'job-event-list' : 'job-panel-empty';
  elements.jobPanel.innerHTML = errors.length
    ? errors.map(error => `
      <div class="job-event">
        <div class="job-event__head">
          <span>${escapeHtml(error.failed_action || 'Scraper issue')}</span>
          <span>${escapeHtml(error.error_type || '')}</span>
        </div>
        <div class="section-subtitle">${escapeHtml(error.error_message || 'No details were recorded.')}</div>
      </div>
    `).join('')
    : 'No scraper errors were recorded for this website.';
  focusElement(elements.jobPanel.closest('.menu-map-panel'));
}

function handleDetailAction(action) {
  const site = sites.find(item => item.slug === selectedSite);
  if (!site) return;
  if (['parents', 'subs', 'children'].includes(action)) return;
  if (action === 'missing') {
    setTreeFilter(activeTreeFilter === 'missing' ? 'all' : 'missing');
    return;
  }
  if (action === 'duplicates') {
    const report = site.files?.['duplicate_urls.csv'];
    if (report && site.duplicate_rows) window.location.assign(report.download_url);
    else showAlert('info', 'No duplicate rows were found for this website.');
    return;
  }
  if (action === 'errors') showSiteErrors(site);
}

function handleSummaryAction(action) {
  if (action === 'sites') {
    focusElement(elements.siteCards.closest('.menu-map-sidebar'));
    return;
  }
  if (action === 'issues') {
    const issueSite = sites.find(site => (site.error_count || 0) + (site.missing_urls || 0) > 0);
    if (!issueSite) {
      showAlert('success', 'No menu-map issues were found.');
      return;
    }
    selectedSite = issueSite.slug;
    render();
    if (issueSite.error_count) showSiteErrors(issueSite);
    else setTreeFilter('missing');
    return;
  }
}

function renderJob(job) {
  if (!job) {
    activeJobStatus = '';
    jobPanelMode = 'idle';
    elements.jobPanel.className = 'job-panel-empty';
    elements.jobPanel.textContent = 'No menu scraper is running.';
    elements.jobPanel.setAttribute('aria-busy', 'false');
    updateRunControls();
    return;
  }
  activeJobStatus = String(job.status || '');
  jobPanelMode = 'job';
  elements.jobPanel.className = 'job-event-list';
  elements.jobPanel.setAttribute('aria-busy', String(['queued', 'running'].includes(activeJobStatus)));
  const events = Array.isArray(job.events) ? job.events : [];
  const completedSites = Object.values(job.site_status || {}).filter(status => status === 'success' || status === 'failed').length;
  const totalSites = Array.isArray(job.sites) ? job.sites.length : 0;
  const statusLabel = ['queued', 'running'].includes(activeJobStatus) && totalSites
    ? `${activeJobStatus} • ${completedSites}/${totalSites} sites complete`
    : activeJobStatus;
  const compactOutput = value => {
    const text = String(value || '');
    if (text.length <= MAX_JOB_OUTPUT_CHARS) return text;
    return `…${text.slice(-MAX_JOB_OUTPUT_CHARS)}`;
  };
  const renderEvent = event => {
    const finished = event.returncode != null;
    const body = `
      ${event.command ? `<pre>${escapeHtml(compactOutput(event.command))}</pre>` : ''}
      ${event.stdout ? `<pre>${escapeHtml(compactOutput(event.stdout))}</pre>` : ''}
      ${event.stderr ? `<pre>${escapeHtml(compactOutput(event.stderr))}</pre>` : ''}
      ${event.message ? `<div class="section-subtitle">${escapeHtml(event.message)}</div>` : ''}
    `;
    const heading = `
      <div class="job-event__head">
        <span>${escapeHtml(event.site || 'command')}</span>
        <span>${event.returncode == null ? 'active' : `exit ${escapeHtml(event.returncode)}`}</span>
      </div>
    `;
    if (!finished) return `<div class="job-event job-event--active">${heading}${body}</div>`;
    return `<details class="job-event job-event--completed"><summary>${heading}</summary><div class="job-event__details">${body}</div></details>`;
  };
  elements.jobPanel.innerHTML = `
    <div class="job-event">
      <div class="job-event__head">
        <span>Status: ${escapeHtml(statusLabel)}</span>
        <span>${escapeHtml(job.current_site || job.completed_at || job.created_at || '')}</span>
      </div>
      <div class="section-subtitle">Sites: ${(job.sites || []).map(escapeHtml).join(', ')}</div>
    </div>
    ${events.slice().reverse().map(renderEvent).join('')}
  `;
  updateRunControls();
}

function render() {
  renderOverall();
  renderCards();
  renderDetail();
  updateRunControls();
}

function renderSiteCardsSkeleton() {
  if (!elements.siteCards) return;
  elements.siteCards.innerHTML = `
    <div class="skeleton-container">
      ${[1, 2, 3, 4, 5].map(() => `
        <div class="skeleton-site-card">
          <div style="display:flex; align-items:center; gap:0.75rem; flex:1;">
            <div class="skeleton-box" style="width: 18px; height: 18px; border-radius: 4px;"></div>
            <div class="skeleton-box" style="width: 140px; height: 16px;"></div>
          </div>
          <div class="skeleton-box" style="width: 70px; height: 20px; border-radius: 999px;"></div>
        </div>
      `).join('')}
    </div>
  `;
}

function renderTreeSkeleton() {
  if (!elements.treeContainer) return;
  elements.treeContainer.className = 'menu-tree';
  elements.treeContainer.innerHTML = `
    <div class="skeleton-container" style="padding: 0.5rem 0.25rem;">
      <div class="skeleton-tree-node"><div class="skeleton-box" style="width:16px; height:16px;"></div><div class="skeleton-box" style="width:45%; height:16px;"></div><div class="skeleton-box" style="width:50px; height:18px; border-radius:999px; margin-left:auto;"></div></div>
      <div class="skeleton-tree-node" style="margin-left: 1.5rem;"><div class="skeleton-box" style="width:14px; height:14px;"></div><div class="skeleton-box" style="width:35%; height:14px;"></div><div class="skeleton-box" style="width:40px; height:16px; border-radius:999px; margin-left:auto;"></div></div>
      <div class="skeleton-tree-node" style="margin-left: 3rem;"><div class="skeleton-box" style="width:12px; height:12px;"></div><div class="skeleton-box" style="width:50%; height:13px;"></div></div>
      <div class="skeleton-tree-node" style="margin-left: 3rem;"><div class="skeleton-box" style="width:12px; height:12px;"></div><div class="skeleton-box" style="width:42%; height:13px;"></div></div>
      <div class="skeleton-tree-node" style="margin-left: 1.5rem;"><div class="skeleton-box" style="width:14px; height:14px;"></div><div class="skeleton-box" style="width:40%; height:14px;"></div><div class="skeleton-box" style="width:40px; height:16px; border-radius:999px; margin-left:auto;"></div></div>
      <div class="skeleton-tree-node"><div class="skeleton-box" style="width:16px; height:16px;"></div><div class="skeleton-box" style="width:50%; height:16px;"></div><div class="skeleton-box" style="width:50px; height:18px; border-radius:999px; margin-left:auto;"></div></div>
      <div class="skeleton-tree-node" style="margin-left: 1.5rem;"><div class="skeleton-box" style="width:14px; height:14px;"></div><div class="skeleton-box" style="width:38%; height:14px;"></div><div class="skeleton-box" style="width:40px; height:16px; border-radius:999px; margin-left:auto;"></div></div>
    </div>
  `;
}

async function loadSites() {
  const hadSites = sites.length > 0;
  sitesLoadPending = true;
  elements.siteCards.setAttribute('aria-busy', 'true');
  if (!hadSites) {
    renderSiteCardsSkeleton();
    renderTreeSkeleton();
  }
  updateRunControls();

  try {
    const data = await fetchJson('/api/menu-map/sites?include_tree=1');
    sites = data.sites || [];
    syncRunSelection();
    if (!selectedSite && sites.length) selectedSite = sites[0].slug;

    const activeJobs = (Array.isArray(data.jobs) ? data.jobs : [])
      .map((job, index) => ({ job, index }))
      .filter(item => ['queued', 'running'].includes(item.job?.status))
      .sort((left, right) => {
        const byDate = String(right.job.created_at || '').localeCompare(String(left.job.created_at || ''));
        return byDate || right.index - left.index;
      });
    const latestActiveJob = activeJobs[0]?.job;
    if (latestActiveJob?.id) {
      activeJobId = latestActiveJob.id;
      activeJobStatus = latestActiveJob.status;
    }
    render();

    if (latestActiveJob?.id) {
      window.clearTimeout(completedJobClearTimer);
      completedJobClearTimer = null;
      activeJobId = latestActiveJob.id;
      renderJob(latestActiveJob);
      beginPolling();
    } else if (jobPanelMode === 'job') {
      stopPolling();
      activeJobId = '';
      renderJob(null);
    }
  } catch (error) {
    if (!hadSites) {
      elements.siteCards.innerHTML = `
        <div class="site-list-state site-list-state--error" role="alert">
          <span>Websites could not be loaded.</span>
          <button type="button" class="btn-export" data-retry-sites>Retry</button>
        </div>`;
      elements.siteCards.querySelector('[data-retry-sites]')?.addEventListener('click', () => {
        loadSites().catch(err => showAlert('error', err.message));
      });
    }
    throw error;
  } finally {
    sitesLoadPending = false;
    elements.siteCards.setAttribute('aria-busy', 'false');
    updateRunControls();
  }
}

async function startRun(siteList) {
  if (isMenuRunBusy()) {
    showAlert('info', 'A menu scraper job is already being submitted or is still active.');
    return;
  }
  if (!siteList.length) {
    showAlert('warn', 'Select at least one website.');
    return;
  }
  runSubmissionPending = true;
  updateRunControls();
  try {
    const data = await fetchJson('/api/menu-map/run', {
      method: 'POST',
      body: JSON.stringify({
        sites: siteList,
        visible: Boolean(elements.visibleMode.checked),
        validate_urls: Boolean(elements.validateUrls.checked),
        inspect_only: Boolean(elements.inspectOnly.checked),
      }),
    });
    window.clearTimeout(completedJobClearTimer);
    completedJobClearTimer = null;
    activeJobId = data.job.id;
    renderJob(data.job);
    showAlert('info', 'Menu scraper job started. This can take a few minutes.');
    beginPolling();
  } finally {
    runSubmissionPending = false;
    updateRunControls();
  }
}

async function clearAndRunSelected() {
  if (isMenuRunBusy()) {
    showAlert('info', 'A menu scraper job is already active.');
    return;
  }
  const siteList = selectedSites();
  if (!siteList.length) {
    showAlert('warn', 'Select at least one website.');
    return;
  }
  const names = siteList
    .map(slug => sites.find(site => site.slug === slug)?.name || slug)
    .join(', ');
  const confirmed = await showMenuMapConfirm({
    title: 'Clear old menu-map output?',
    message: `Delete old menu-map output for ${names}, then run a fresh scrape?`,
    confirmLabel: 'Clear & Run',
    cancelLabel: 'Keep Output',
    danger: true,
  });
  if (!confirmed) return;

  runSubmissionPending = true;
  updateRunControls();
  try {
    const data = await fetchJson('/api/menu-map/output/clear', {
      method: 'POST',
      body: JSON.stringify({ sites: siteList }),
    });
    siteList.forEach(slug => {
      excludedBySite[slug] = [];
      delete treeOpenStateBySite[slug];
    });
    saveExclusions();
    saveTreeOpenState();
    await loadSites();
    showAlert('success', `Cleared old menu-map output for ${formatNumber(data.cleared_count || 0)} selected site${Number(data.cleared_count || 0) === 1 ? '' : 's'}. Starting fresh scrape.`);
  } finally {
    runSubmissionPending = false;
    updateRunControls();
  }
  await startRun(siteList);
}

function filenameFromDisposition(disposition, fallback) {
  const match = String(disposition || '').match(/filename="?([^"]+)"?/i);
  return match?.[1] || fallback;
}

async function exportMenuLinks(scope, format) {
  const site = sites.find(item => item.slug === selectedSite);
  if (!site) {
    showAlert('warn', 'Select a website first.');
    return;
  }
  const response = await fetch('/api/menu-map/links/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sites: [site.slug],
      scope,
      format,
      excluded: excludedBySite,
    }),
  });
  const contentType = response.headers.get('Content-Type') || '';
  if (!response.ok) {
    const error = contentType.includes('application/json')
      ? await response.json().catch(() => ({}))
      : {};
    throw new Error(error.error || `Export failed with server ${response.status}`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filenameFromDisposition(
    response.headers.get('Content-Disposition'),
    `menu-map-${site.slug}-${scope}.${format === 'xlsx' ? 'xlsx' : 'csv'}`
  );
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  showAlert('success', `Exported ${scope === 'visible' ? 'visible' : 'full'} menu links for ${site.name}.`);
}

async function runAutomationForSelectedSite() {
  if (automationSubmissionPending || isMenuRunBusy()) return;
  const site = sites.find(item => item.slug === selectedSite);
  if (!site) {
    showAlert('warn', 'Select a website first.');
    return;
  }
  const targets = buildAutomationTargets(site);
  if (!targets.length) {
    showAlert('warn', 'No visible category URLs are available for automation.');
    return;
  }
  if (targets.length > 500) {
    const confirmed = await showMenuMapConfirm({
      title: 'Queue large automation run?',
      message: `This will queue automation for ${targets.length.toLocaleString()} category URLs. Continue?`,
      confirmLabel: 'Queue Automation',
      cancelLabel: 'Cancel',
    });
    if (!confirmed) return;
  }

  try {
    automationSubmissionPending = true;
    updateRunControls();
    const payload = automationPayloadForSite(site, targets);
    // Keep this response compact: large menu maps can contain thousands of
    // targets, and echoing them back causes a visible main-thread JSON pause.
    const saved = await fetchJson('/api/automation/jobs?compact=1', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    const jobId = saved?.job?.id;
    if (!jobId) throw new Error('Automation job was not saved.');
    await fetchJson(`/api/automation/jobs/${encodeURIComponent(jobId)}/run`, {
      method: 'POST',
      body: JSON.stringify({}),
    });
    showAlert('success', `Automation queued for ${site.name} with ${targets.length.toLocaleString()} visible target URL${targets.length === 1 ? '' : 's'}.`);
  } catch (err) {
    showAlert('error', err.message || 'Failed to queue automation.');
  } finally {
    automationSubmissionPending = false;
    updateRunControls();
  }
}

async function pollJob() {
  if (!activeJobId || pollRequestPending) return;
  const polledJobId = activeJobId;
  pollRequestPending = true;
  try {
    const data = await fetchJson(`/api/menu-map/jobs/${encodeURIComponent(polledJobId)}`);
    if (activeJobId !== polledJobId) return;
    renderJob(data.job);
    if (!['queued', 'running'].includes(data.job.status)) {
      stopPolling();
      await loadSites();
      showAlert(data.job.status === 'complete' ? 'success' : 'warn', `Menu scraper job ${data.job.status}.`);
      if (activeJobId === polledJobId) {
        activeJobId = '';
        renderJob(null);
      }
    }
  } finally {
    pollRequestPending = false;
  }
}

function stopPolling() {
  window.clearTimeout(pollTimer);
  pollTimer = null;
}

function nextPollingDelay() {
  return Math.min(MENU_POLL_BASE_MS * (2 ** pollFailureCount), MENU_POLL_MAX_MS);
}

function schedulePolling(delayMs = nextPollingDelay()) {
  stopPolling();
  if (!activeJobId || !['queued', 'running'].includes(activeJobStatus) || document.hidden) return;
  pollTimer = window.setTimeout(async () => {
    pollTimer = null;
    try {
      await pollJob();
      pollFailureCount = 0;
    } catch (err) {
      pollFailureCount += 1;
      showAlert('error', err.message || 'Menu scraper status could not be refreshed.');
    } finally {
      if (activeJobId && ['queued', 'running'].includes(activeJobStatus) && !document.hidden) {
        schedulePolling(nextPollingDelay());
      }
    }
  }, Math.max(0, Number(delayMs) || 0));
}

function beginPolling() {
  pollFailureCount = 0;
  schedulePolling(0);
}

function bindTheme() {
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

document.addEventListener('DOMContentLoaded', async () => {
  ensureExclusionUi();
  bindTheme();
  elements.jobPanel.setAttribute('role', 'status');
  elements.jobPanel.setAttribute('aria-live', 'polite');
  elements.jobPanel.setAttribute('aria-atomic', 'false');
  elements.jobPanel.setAttribute('aria-relevant', 'additions text');
  elements.jobPanel.setAttribute('aria-busy', 'false');
  elements.refreshBtn.addEventListener('click', () => loadSites().catch(err => showAlert('error', err.message)));
  elements.clearRunSelectedBtn?.addEventListener('click', () => clearAndRunSelected().catch(err => showAlert('error', err.message)));
  elements.exportVisibleCsvBtn?.addEventListener('click', () => exportMenuLinks('visible', 'csv').catch(err => showAlert('error', err.message)));
  elements.exportVisibleXlsxBtn?.addEventListener('click', () => exportMenuLinks('visible', 'xlsx').catch(err => showAlert('error', err.message)));
  elements.exportFullCsvBtn?.addEventListener('click', () => exportMenuLinks('full', 'csv').catch(err => showAlert('error', err.message)));
  elements.exportFullXlsxBtn?.addEventListener('click', () => exportMenuLinks('full', 'xlsx').catch(err => showAlert('error', err.message)));
  elements.runAllBtn.addEventListener('click', () => startRun(sites.map(site => site.slug)).catch(err => showAlert('error', err.message)));
  elements.runSelectedBtn.addEventListener('click', () => startRun(selectedSites()).catch(err => showAlert('error', err.message)));
  elements.runAutomationForSiteBtn?.addEventListener('click', () => runAutomationForSelectedSite());
  elements.treeSearch.addEventListener('input', renderDetail);
  if (elements.resetHiddenBtn) elements.resetHiddenBtn.addEventListener('click', () => clearExclusions(selectedSite));
  elements.expandAllBtn.addEventListener('click', () => setAllTreeOpenState(selectedSite, true));
  elements.collapseAllBtn.addEventListener('click', () => setAllTreeOpenState(selectedSite, false));
  document.querySelectorAll('[data-detail-action]').forEach(card => {
    card.addEventListener('click', () => handleDetailAction(card.dataset.detailAction));
  });
  document.querySelectorAll('[data-summary-action]').forEach(card => {
    card.addEventListener('click', () => handleSummaryAction(card.dataset.summaryAction));
  });

  if (elements.scrollTopBtn) {
    window.addEventListener('scroll', () => {
      if (window.scrollY > 300) {
        elements.scrollTopBtn.classList.add('visible');
      } else {
        elements.scrollTopBtn.classList.remove('visible');
      }
    });
    elements.scrollTopBtn.addEventListener('click', () => {
      window.scrollTo({
        top: 0,
        behavior: 'smooth'
      });
    });
  }

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      stopPolling();
    } else if (activeJobId && ['queued', 'running'].includes(activeJobStatus)) {
      schedulePolling(0);
    }
  });
  window.addEventListener('pagehide', stopPolling);

  await loadSites().catch(err => showAlert('error', err.message));
});
