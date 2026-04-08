// History Page JavaScript - Optimized
// No jQuery dependency, pure vanilla JS

(function() {
  'use strict';

  // DOM element cache
  const $ = id => document.getElementById(id);
  const elements = {
    historyContainer: $('historyContainer'),
    emptyState: $('emptyState'),
    historyModal: $('historyModal'),
    modalContent: $('modalContent'),
    closeModal: $('closeModal'),
    darkMode: $('darkMode'),
    alertBox: $('alert'),
    overlay: $('overlay'),
    refreshBtn: $('refreshBtn'),
    cleanupBtn: $('cleanupBtn'),
    historyDateValue: $('historyDateValue'),
    historyTimeValue: $('historyTimeValue'),
    historyDateChip: $('historyDateChip'),
    historyTimeChip: $('historyTimeChip'),
    historySearch: $('historySearch'),
    historyStartDate: $('historyStartDate'),
    historyEndDate: $('historyEndDate'),
    historyMinItems: $('historyMinItems'),
    historyMinItemsValue: $('historyMinItemsValue'),
    historySiteSelect: $('historySiteSelect'),
    historyClearFilters: $('historyClearFilters'),
    historyResultSummary: $('historyResultSummary')
  };

  let historyData = [];
  let filteredHistory = [];
  const defaultFilterState = {
    search: '',
    startDate: null,
    endDate: null,
    minItems: 0,
    site: ''
  };
  const filterState = { ...defaultFilterState };

  // Utility Functions
  const utils = {
    setLoading(on) {
      if (elements.overlay) {
        elements.overlay.style.display = on ? 'flex' : 'none';
      }
    },

    showAlert(type, msg) {
      if (!elements.alertBox) return;
      elements.alertBox.className = `alert cy-card p-3 alert-${type}`;
      elements.alertBox.textContent = msg;
      elements.alertBox.classList.remove('d-none');
      setTimeout(() => elements.alertBox.classList.add('d-none'), 5000);
    },

    formatDate(isoString) {
      if (!isoString) return 'Unknown';
      const tz = 'Asia/Karachi';
      try {
        // Parse the ISO string and ensure it's treated correctly
        let date;
        if (typeof isoString === 'string') {
          // If the string doesn't have timezone info, assume it's already in Pakistan time
          if (!isoString.includes('+') && !isoString.includes('Z')) {
            // Add Pakistan timezone offset manually
            date = new Date(isoString + '+05:00');
          } else {
            date = new Date(isoString);
          }
        } else {
          date = new Date(isoString);
        }
        
        return new Intl.DateTimeFormat('en-PK', {
          day: '2-digit',
          month: 'short',
          year: 'numeric',
          hour: 'numeric',
          minute: '2-digit',
          hour12: true,
          timeZone: tz
        }).format(date);
      } catch (err) {
        console.warn('Failed to format date', isoString, err);
        return new Date(isoString).toLocaleString();
      }
    },

    formatDuration(timestamp) {
      const now = new Date();
      let then;
      
      try {
        if (typeof timestamp === 'string') {
          // If the string doesn't have timezone info, assume it's already in Pakistan time
          if (!timestamp.includes('+') && !timestamp.includes('Z')) {
            // Add Pakistan timezone offset manually
            then = new Date(timestamp + '+05:00');
          } else {
            then = new Date(timestamp);
          }
        } else {
          then = new Date(timestamp);
        }
        
        const diffMs = now - then;
        const diffMinutes = Math.floor(diffMs / (1000 * 60));
        const diffHours = Math.floor(diffMinutes / 60);
        const diffDays = Math.floor(diffHours / 24);
        
        if (diffDays > 0) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
        if (diffHours > 0) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
        if (diffMinutes > 0) return `${diffMinutes} minute${diffMinutes > 1 ? 's' : ''} ago`;
        return 'Just now';
      } catch (err) {
        console.warn('Failed to format duration', timestamp, err);
        return 'Unknown time';
      }
    },

    escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }
  };

  function startHistoryClock() {
    const dateEl = elements.historyDateValue;
    const timeEl = elements.historyTimeValue;
    if (!dateEl && !timeEl) return;

    const tz = 'Asia/Karachi';
    const tzLabel = 'Pakistan Standard Time (UTC+05:00)';
    const dateFormatter = new Intl.DateTimeFormat('en-PK', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      timeZone: tz
    });
    const timeFormatter = new Intl.DateTimeFormat('en-PK', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
      timeZone: tz
    });

    const apply = () => {
      const now = new Date();
      const dateText = dateFormatter.format(now);
      const timeText = timeFormatter.format(now);
      if (dateEl) dateEl.textContent = dateText;
      if (timeEl) timeEl.textContent = timeText;
      if (elements.historyDateChip) elements.historyDateChip.title = `${dateText} • ${tzLabel}`;
      if (elements.historyTimeChip) elements.historyTimeChip.title = `${timeText} • ${tzLabel}`;
    };

    const schedule = () => {
      apply();
      const now = new Date();
      const msUntilNextMinute = 60000 - (now.getSeconds() * 1000 + now.getMilliseconds());
      setTimeout(schedule, Math.max(1000, msUntilNextMinute));
    };

    schedule();
  }

  function normalizeHistoryEntry(entry) {
    const safeEntry = entry && typeof entry === 'object' ? entry : {};
    const urls = Array.isArray(safeEntry.urls) ? safeEntry.urls.filter(Boolean) : [];
    const items = Array.isArray(safeEntry.items) ? safeEntry.items : [];
    
    let timestampObj = null;
    if (safeEntry.timestamp) {
      try {
        let timestamp = safeEntry.timestamp;
        if (typeof timestamp === 'string') {
          // If the string doesn't have timezone info, assume it's already in Pakistan time
          if (!timestamp.includes('+') && !timestamp.includes('Z')) {
            // Add Pakistan timezone offset manually for proper parsing
            timestamp = timestamp + '+05:00';
          }
        }
        timestampObj = new Date(timestamp);
        // Validate the date
        if (isNaN(timestampObj.getTime())) {
          timestampObj = null;
        }
      } catch (e) {
        console.warn('Failed to parse timestamp:', safeEntry.timestamp, e);
        timestampObj = null;
      }
    }

    const hostSet = new Set();
    urls.forEach(url => {
      try {
        const host = new URL(url).hostname.replace(/^www\./, '');
        if (host) hostSet.add(host);
      } catch {
        if (url) hostSet.add(url);
      }
    });

    const hostList = Array.from(hostSet);
    const rawRules = safeEntry.rules || {};
    const rules = {
      add_percent: Number(rawRules.add_percent) || 0,
      percent_off: Number(rawRules.percent_off) || 0,
      absolute_off: Number(rawRules.absolute_off) || 0
    };
    const itemsCount = Number.isFinite(Number(safeEntry.items_count))
      ? Number(safeEntry.items_count)
      : items.length;

    const searchParts = [
      safeEntry.id || '',
      itemsCount,
      urls.join(' '),
      hostList.join(' '),
      rules.add_percent,
      rules.percent_off,
      rules.absolute_off
    ];

    items.slice(0, 25).forEach(item => {
      if (!item || typeof item !== 'object') return;
      if (item.title) searchParts.push(item.title);
      if (item.site) searchParts.push(item.site);
    });

    const searchIndex = searchParts
      .map(part => String(part).toLowerCase())
      .join(' | ');

    return {
      ...safeEntry,
      urls,
      items,
      items_count: itemsCount,
      rules,
      host_list: hostList,
      timestamp_obj: timestampObj instanceof Date && !Number.isNaN(timestampObj.valueOf()) ? timestampObj : null,
      timestamp_ms: timestampObj instanceof Date && !Number.isNaN(timestampObj.valueOf()) ? timestampObj.getTime() : 0,
      search_index: searchIndex
    };
  }

  function parseDateInput(value, endOfDay = false) {
    if (!value) return null;
    const [year, month, day] = value.split('-').map(Number);
    if (!year || !month || !day) return null;
    
    // Create date in Pakistan timezone
    const date = new Date(year, month - 1, day, 0, 0, 0, 0);
    if (Number.isNaN(date.valueOf())) return null;
    
    if (endOfDay) {
      date.setHours(23, 59, 59, 999);
    }
    
    // Convert to Pakistan timezone by adjusting for the timezone offset
    // Pakistan is UTC+5, so we need to account for this when filtering
    const pakistanOffset = 5 * 60; // 5 hours in minutes
    const localOffset = date.getTimezoneOffset(); // Local timezone offset from UTC in minutes
    const adjustmentMinutes = pakistanOffset + localOffset;
    
    // Adjust the date to account for Pakistan timezone
    date.setMinutes(date.getMinutes() - adjustmentMinutes);
    
    return date;
  }

  function updateSiteFilterOptions() {
    if (!elements.historySiteSelect) return;
    const select = elements.historySiteSelect;
    const previousValue = filterState.site;
    const siteSet = new Set();
    historyData.forEach(entry => {
      (entry.host_list || []).forEach(host => siteSet.add(host));
    });
    const sites = Array.from(siteSet).sort((a, b) => a.localeCompare(b));
    const baseOption = '<option value="">All sites</option>';
    const optionsHtml = sites.map(site => `<option value="${utils.escapeHtml(site)}">${utils.escapeHtml(site)}</option>`).join('');
    select.innerHTML = baseOption + optionsHtml;
    if (previousValue && sites.includes(previousValue)) {
      select.value = previousValue;
    } else {
      select.value = '';
      filterState.site = '';
    }
  }

  function updateMinItemsSlider() {
    if (!elements.historyMinItems) return;
    const maxItems = historyData.reduce((max, entry) => {
      const count = Number(entry.items_count) || 0;
      return count > max ? count : max;
    }, 0);
    const computedMax = Math.max(50, Math.ceil((maxItems || 0) / 10) * 10);
    elements.historyMinItems.max = String(computedMax);
    if (filterState.minItems > computedMax) {
      filterState.minItems = computedMax;
      elements.historyMinItems.value = String(computedMax);
      if (elements.historyMinItemsValue) {
        elements.historyMinItemsValue.textContent = computedMax.toString();
      }
    }
  }

  function updateResultSummary(visible, total) {
    if (!elements.historyResultSummary) return;
    if (!total) {
      if (!visible) {
        elements.historyResultSummary.textContent = 'No sessions';
      } else {
        const label = visible === 1 ? 'session' : 'sessions';
        elements.historyResultSummary.textContent = `${visible} ${label}`;
      }
      return;
    }

    const sessionLabel = total === 1 ? 'session' : 'sessions';
    if (visible === total) {
      elements.historyResultSummary.textContent = `${total} ${sessionLabel}`;
      return;
    }

    elements.historyResultSummary.textContent = `${visible} of ${total} ${sessionLabel}`;
  }

  function applyFilters() {
    const { search, startDate, endDate, minItems, site } = filterState;
    const effectiveSearch = search.trim();

    filteredHistory = historyData.filter(entry => {
      if (effectiveSearch && !(entry.search_index || '').includes(effectiveSearch)) {
        return false;
      }

      if (startDate) {
        if (!entry.timestamp_obj) {
          return false;
        }
        // Convert entry timestamp to comparable format
        let entryTime = entry.timestamp_obj.getTime();
        let startTime = startDate.getTime();
        
        if (entryTime < startTime) {
          return false;
        }
      }

      if (endDate) {
        if (!entry.timestamp_obj) {
          return false;
        }
        // Convert entry timestamp to comparable format
        let entryTime = entry.timestamp_obj.getTime();
        let endTime = endDate.getTime();
        
        if (entryTime > endTime) {
          return false;
        }
      }

      if (minItems && (entry.items_count || 0) < minItems) {
        return false;
      }

      if (site && !(entry.host_list || []).includes(site)) {
        return false;
      }

      return true;
    });

    updateResultSummary(filteredHistory.length, historyData.length);
    renderHistory(filteredHistory);
  }

  function resetFilters(options = {}) {
    Object.assign(filterState, defaultFilterState);
    if (elements.historySearch) elements.historySearch.value = '';
    if (elements.historyStartDate) elements.historyStartDate.value = '';
    if (elements.historyEndDate) elements.historyEndDate.value = '';
    if (elements.historyMinItems) elements.historyMinItems.value = '0';
    if (elements.historyMinItemsValue) elements.historyMinItemsValue.textContent = '0';
    if (elements.historySiteSelect) elements.historySiteSelect.value = '';
    if (!options.skipApply) applyFilters();
  }

  // History Rendering
  function renderHistory(list) {
    if (!elements.historyContainer) return;

    const entries = Array.isArray(list) ? list : historyData;
    const emptyTitle = elements.emptyState ? elements.emptyState.querySelector('h3') : null;
    const emptyText = elements.emptyState ? elements.emptyState.querySelector('p') : null;

    elements.historyContainer.innerHTML = '';

    if (entries.length === 0) {
      if (emptyTitle && emptyText) {
        const hasAnyHistory = historyData.length > 0;
        if (hasAnyHistory) {
          emptyTitle.textContent = 'No matching sessions';
          emptyText.textContent = 'Try adjusting your search, date range, item count, or site filters.';
        } else {
          emptyTitle.textContent = 'No history yet';
          emptyText.innerHTML = 'Start by <a href="/" style="color:var(--primary)">running a fetch</a> to see your sessions here.';
        }
      }
      if (elements.emptyState) elements.emptyState.classList.remove('d-none');
      return;
    }

    if (elements.emptyState) elements.emptyState.classList.add('d-none');

    const sortedHistory = [...entries].sort((a, b) => (b.timestamp_ms || 0) - (a.timestamp_ms || 0));

    const fragment = document.createDocumentFragment();
    
    sortedHistory.forEach(entry => {
      const card = createHistoryCard(entry);
      fragment.appendChild(card);
    });

    elements.historyContainer.appendChild(fragment);
  }

  function createHistoryCard(entry) {
    const card = document.createElement('div');
    card.className = 'history-card';
    
    const urlList = Array.isArray(entry.urls) ? entry.urls : [];
    const rules = entry.rules || { add_percent: 0, percent_off: 0, absolute_off: 0 };
    const addPercent = Number(rules.add_percent) || 0;
    const percentOff = Number(rules.percent_off) || 0;
    const absoluteOff = Number(rules.absolute_off) || 0;
    const itemsCount = Number(entry.items_count) || 0;
    const urlsPreview = urlList.slice(0, 2).map(url => {
      try {
        return new URL(url).hostname.replace('www.', '');
      } catch {
        return url;
      }
    }).join(', ');
    const remainingUrls = urlList.length > 2 ? ` +${urlList.length - 2} more` : '';
    
    card.innerHTML = `
      <div class="history-header">
        <div>
          <h3 class="history-title">Fetch Session</h3>
          <div class="history-timestamp">${utils.formatDate(entry.timestamp)} • ${utils.formatDuration(entry.timestamp)}</div>
        </div>
        <div class="history-actions">
          <button class="btn btn-sm btn-ghost" data-action="export" data-id="${entry.id}">Export XLSX</button>
          <button class="btn btn-sm btn-ghost" data-action="view" data-id="${entry.id}">View Details</button>
          <button class="btn btn-sm btn-ghost danger" data-action="delete" data-id="${entry.id}">Delete</button>
        </div>
      </div>
      
      <div class="history-meta">
        <div class="meta-item">
          <span class="meta-label">Items:</span>
          <span class="meta-value">${itemsCount}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">URLs:</span>
          <span class="meta-value">${urlList.length}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Pricing:</span>
          <span class="meta-value">+${addPercent}% / -${percentOff}% / $${absoluteOff}</span>
        </div>
      </div>
      
      <div class="history-urls">
        <div class="meta-label mb-2">Target URLs:</div>
        <div class="text-muted" style="font-size: 0.85rem;">
          ${utils.escapeHtml(urlsPreview)}${utils.escapeHtml(remainingUrls)}
        </div>
      </div>
    `;
    
    // Event delegation for buttons
    card.querySelector('[data-action="export"]').addEventListener('click', () => exportHistory(entry.id));
    card.querySelector('[data-action="view"]').addEventListener('click', () => viewHistory(entry.id));
    card.querySelector('[data-action="delete"]').addEventListener('click', () => deleteHistory(entry.id));
    
    return card;
  }

  // API Functions
  async function loadHistory() {
    try {
      utils.setLoading(true);
      const response = await fetch('/api/history?limit=50');
      if (!response.ok) throw new Error('Failed to load history');
      const data = await response.json();
      const rawHistory = data.histories || data || [];
      historyData = rawHistory.map(normalizeHistoryEntry);
      updateSiteFilterOptions();
      updateMinItemsSlider();
      applyFilters();
      loadStatistics();
    } catch (error) {
      console.error('Error loading history:', error);
      utils.showAlert('danger', 'Failed to load history');
      historyData = [];
      filteredHistory = [];
      updateSiteFilterOptions();
      updateMinItemsSlider();
      updateResultSummary(0, 0);
      renderHistory([]);
    } finally {
      utils.setLoading(false);
    }
  }

  async function loadStatistics() {
    try {
      const response = await fetch('/api/statistics');
      if (!response.ok) throw new Error('Failed to load statistics');
      const stats = await response.json();
      
      updateStatCard('totalHistories', stats.total_histories || 0);
      updateStatCard('totalItems', (stats.total_items || 0).toLocaleString());
      updateStatCard('uniqueModels', stats.unique_models || 0);
      updateStatCard('recentSessions', stats.recent_histories || 0);
      updateStatCard('uniqueSites', stats.unique_sites || 0);
      updateStatCard('avgPrice', stats.avg_price ? `$${stats.avg_price}` : '$0');
      updateStatCard('successRate', stats.success_rate ? `${stats.success_rate}%` : '0%');
      updateStatCard('topSite', stats.top_site || 'N/A');
      updateStatCard('latestSession', stats.latest_session || 'Never');
      
      const sizeInMB = (stats.database_size || 0) / 1024 / 1024;
      updateStatCard('dbSize', sizeInMB < 1 
        ? `${(sizeInMB * 1024).toFixed(0)} KB`
        : `${sizeInMB.toFixed(1)} MB`
      );
      
      // Update new stats
      updateStatCard('avgItemsPerSession', stats.avg_items_per_session || 0);
      updateStatCard('totalValue', stats.total_value ? `$${stats.total_value.toLocaleString()}` : '$0');
      updateStatCard('highestPrice', stats.highest_price ? `$${stats.highest_price}` : '$0');
      updateStatCard('lowestPrice', stats.lowest_price ? `$${stats.lowest_price}` : '$0');
    } catch (error) {
      console.error('Error loading statistics:', error);
      setDefaultStats();
    }
  }

  function updateStatCard(id, value) {
    const element = $(id);
    if (element) element.textContent = value;
  }

  function setDefaultStats() {
    ['totalHistories', 'totalItems', 'uniqueModels', 'recentSessions', 'uniqueSites'].forEach(id => updateStatCard(id, '0'));
    updateStatCard('dbSize', '0 KB');
    updateStatCard('avgPrice', '$0');
    updateStatCard('successRate', '0%');
    updateStatCard('topSite', 'N/A');
    updateStatCard('latestSession', 'Never');
    updateStatCard('avgItemsPerSession', '0');
    updateStatCard('totalValue', '$0');
    updateStatCard('highestPrice', '$0');
    updateStatCard('lowestPrice', '$0');
  }

  function normalizeHistoryId(historyId) {
    if (historyId === null || historyId === undefined) return '';
    return String(historyId).trim();
  }

  async function requestDeleteHistory(normalizedHistoryId) {
    const encodedId = encodeURIComponent(normalizedHistoryId);
    let response = await fetch(`/api/history/${encodedId}`, { method: 'DELETE' });

    // Some deployments/proxies block DELETE; fallback route keeps behavior consistent.
    if (response.status === 405 || response.status === 501) {
      response = await fetch(`/api/history/${encodedId}/delete`, { method: 'POST' });
    }

    return response;
  }

  async function deleteHistory(historyId) {
    const normalizedHistoryId = normalizeHistoryId(historyId);
    if (!normalizedHistoryId) {
      utils.showAlert('danger', 'Invalid history entry ID');
      return;
    }

    if (!confirm('Are you sure you want to delete this history entry?')) return;
    
    try {
      utils.setLoading(true);
      const response = await requestDeleteHistory(normalizedHistoryId);
      let payload = null;

      try {
        payload = await response.json();
      } catch {
        payload = null;
      }

      if (!response.ok || !payload || payload.success !== true) {
        const message = payload && payload.error ? payload.error : 'Failed to delete history';
        throw new Error(message);
      }

      historyData = historyData.filter(entry => normalizeHistoryId(entry.id) !== normalizedHistoryId);
      filteredHistory = filteredHistory.filter(entry => normalizeHistoryId(entry.id) !== normalizedHistoryId);
      updateSiteFilterOptions();
      updateMinItemsSlider();
      applyFilters();
      loadStatistics();
      utils.showAlert('success', 'History entry deleted');
    } catch (error) {
      console.error('Error deleting history:', error);
      utils.showAlert('danger', 'Failed to delete history entry');
    } finally {
      utils.setLoading(false);
    }
  }

  async function viewHistory(historyId) {
    try {
      utils.setLoading(true);
      const normalizedHistoryId = normalizeHistoryId(historyId);
      const response = await fetch(`/api/history/${encodeURIComponent(normalizedHistoryId)}`);
      if (!response.ok) throw new Error('Failed to load history details');
      const entry = await response.json();
      showHistoryDetail(entry);
    } catch (error) {
      console.error('Error loading history details:', error);
      utils.showAlert('danger', 'Failed to load history details');
    } finally {
      utils.setLoading(false);
    }
  }

  async function exportHistory(historyId) {
    try {
      utils.setLoading(true);
      const normalizedHistoryId = normalizeHistoryId(historyId);
      const response = await fetch(`/api/history/${encodeURIComponent(normalizedHistoryId)}/export/xlsx`, { method: 'POST' });
      if (!response.ok) throw new Error('Failed to export session');
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `history_${normalizedHistoryId}.xlsx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      utils.showAlert('success', 'Download started');
    } catch (error) {
      console.error('Error exporting history:', error);
      utils.showAlert('danger', 'Failed to export session');
    } finally {
      utils.setLoading(false);
    }
  }

  function showHistoryDetail(entry) {
    if (!elements.modalContent || !elements.historyModal) return;

    const urlList = Array.isArray(entry.urls) ? entry.urls : [];
    const urlsList = urlList.map(url => 
      `<div class="url-item">${utils.escapeHtml(url)}</div>`
    ).join('');

    const items = Array.isArray(entry.items) ? entry.items : [];
    const rules = entry.rules || { add_percent: 0, percent_off: 0, absolute_off: 0 };
    const addPercent = Number(rules.add_percent) || 0;
    const percentOff = Number(rules.percent_off) || 0;
    const absoluteOff = Number(rules.absolute_off) || 0;
    const itemsCount = Number(entry.items_count) || items.length;

    const itemsTable = items.length > 0 ? `
      <h4 style="color: var(--text); margin: 1.5rem 0 0.75rem 0; font-size: 1rem;">Items (${items.length})</h4>
      <div style="overflow-x: auto;">
        <table class="table">
          <thead>
            <tr>
              <th>Image</th>
              <th>Title</th>
              <th>Original</th>
              <th>Final</th>
              <th>URL</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            ${items.map(item => `
              <tr>
                <td>${item.image_url ? `<img src="${utils.escapeHtml(item.image_url)}" class="table-img" alt="">` : ''}</td>
                <td style="max-width: 300px; word-wrap: break-word;">${utils.escapeHtml(item.title || '')}</td>
                <td>${utils.escapeHtml(item.original_formatted || '')}</td>
                <td>${utils.escapeHtml(item.discounted_formatted || '')}</td>
                <td><a class="url-link" href="${utils.escapeHtml(item.url)}" target="_blank" rel="noopener">Open</a></td>
                <td><small>${utils.escapeHtml(item.site || '')}</small></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    ` : '<p style="color: var(--muted); text-align: center; padding: 1.5rem;">No items found in this session</p>';

    elements.modalContent.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-bottom: 1rem; padding-right: 3rem;">
        <h3 style="color: var(--text); margin: 0; font-size: 1.25rem; flex: 1; min-width: 0;">Fetch Session Details</h3>
        <button class="btn btn-sm btn-ghost" id="historyModalExport" data-id="${entry.id}" style="white-space: nowrap; flex-shrink: 0;">Export XLSX</button>
      </div>
      <div style="color: var(--muted); font-size: 0.875rem; margin-bottom: 1.5rem;">
        ${utils.formatDate(entry.timestamp)} • ${utils.formatDuration(entry.timestamp)}
      </div>
      
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem; margin-bottom: 1.5rem;">
        <div style="background: rgba(255,255,255,0.05); padding: 0.875rem; border-radius: 12px;">
          <div style="color: var(--muted); font-size: 0.75rem; text-transform: uppercase; margin-bottom: 0.375rem;">Items Found</div>
          <div style="color: var(--text); font-size: 1.375rem; font-weight: 700;">${itemsCount}</div>
        </div>
        <div style="background: rgba(255,255,255,0.05); padding: 0.875rem; border-radius: 12px;">
          <div style="color: var(--muted); font-size: 0.75rem; text-transform: uppercase; margin-bottom: 0.375rem;">Add %</div>
          <div style="color: var(--text); font-size: 1.375rem; font-weight: 700;">${addPercent}%</div>
        </div>
        <div style="background: rgba(255,255,255,0.05); padding: 0.875rem; border-radius: 12px;">
          <div style="color: var(--muted); font-size: 0.75rem; text-transform: uppercase; margin-bottom: 0.375rem;">Discount %</div>
          <div style="color: var(--text); font-size: 1.375rem; font-weight: 700;">${percentOff}%</div>
        </div>
        <div style="background: rgba(255,255,255,0.05); padding: 0.875rem; border-radius: 12px;">
          <div style="color: var(--muted); font-size: 0.75rem; text-transform: uppercase; margin-bottom: 0.375rem;">Absolute Off</div>
          <div style="color: var(--text); font-size: 1.375rem; font-weight: 700;">$${absoluteOff}</div>
        </div>
      </div>

      <h4 style="color: var(--text); margin: 0 0 0.75rem 0; font-size: 1rem;">Target URLs (${urlList.length})</h4>
      <div class="url-list" style="margin-bottom: 1.5rem;">
        ${urlsList}
      </div>

      ${itemsTable}
    `;
    
    elements.historyModal.style.display = 'flex';

    const modalExportBtn = document.getElementById('historyModalExport');
    if (modalExportBtn) {
      modalExportBtn.addEventListener('click', () => exportHistory(entry.id));
    }
  }

  const cleanupModal = {
    modal: null,
    closeBtn: null,
    cancelBtn: null,
    confirmBtn: null,
    daysInput: null,
    dateInput: null,
    previewText: null,
    quickBtns: null,
    currentDays: 90,

    init() {
      this.modal = $('cleanupModal');
      this.closeBtn = $('closeCleanupModal');
      this.cancelBtn = $('cancelCleanup');
      this.confirmBtn = $('confirmCleanup');
      this.daysInput = $('cleanupDays');
      this.dateInput = $('cleanupDate');
      this.previewText = $('cleanupPreviewText');
      this.quickBtns = document.querySelectorAll('.cleanup-quick-btn');

      if (!this.modal) return;

      // Close handlers
      if (this.closeBtn) {
        this.closeBtn.addEventListener('click', () => this.hide());
      }
      if (this.cancelBtn) {
        this.cancelBtn.addEventListener('click', () => this.hide());
      }
      this.modal.addEventListener('click', (e) => {
        if (e.target === this.modal) this.hide();
      });

      // Quick button handlers
      this.quickBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
          this.quickBtns.forEach(b => b.classList.remove('active'));
          e.target.classList.add('active');
          this.currentDays = parseInt(e.target.dataset.days);
          if (this.daysInput) this.daysInput.value = this.currentDays;
          if (this.dateInput) this.dateInput.value = '';
          this.updatePreview();
        });
      });

      // Days input handler
      if (this.daysInput) {
        this.daysInput.addEventListener('input', (e) => {
          this.quickBtns.forEach(b => b.classList.remove('active'));
          this.currentDays = parseInt(e.target.value) || 90;
          if (this.dateInput) this.dateInput.value = '';
          this.updatePreview();
        });
      }

      // Date input handler
      if (this.dateInput) {
        this.dateInput.addEventListener('change', (e) => {
          if (e.target.value) {
            this.quickBtns.forEach(b => b.classList.remove('active'));
            const selectedDate = new Date(e.target.value);
            const today = new Date();
            const diffTime = today - selectedDate;
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            this.currentDays = diffDays;
            if (this.daysInput) this.daysInput.value = diffDays;
            this.updatePreview();
          }
        });
      }

      // Confirm handler
      if (this.confirmBtn) {
        this.confirmBtn.addEventListener('click', () => this.executeCleanup());
      }
    },

    show() {
      if (this.modal) {
        this.modal.style.display = 'flex';
        this.updatePreview();
      }
    },

    hide() {
      if (this.modal) {
        this.modal.style.display = 'none';
      }
    },

    updatePreview() {
      if (!this.previewText) return;
      
      const dateValue = this.dateInput ? this.dateInput.value : '';
      if (this.currentDays >= 99999) {
        this.previewText.innerHTML = `<strong style="color: #dc3545;">⚠️ ALL HISTORY SESSIONS</strong> will be permanently deleted!`;
      } else if (dateValue) {
        const date = new Date(dateValue);
        const formattedDate = date.toLocaleDateString('en-US', { 
          year: 'numeric', 
          month: 'long', 
          day: 'numeric' 
        });
        this.previewText.textContent = `All sessions before ${formattedDate} will be permanently deleted`;
      } else {
        this.previewText.textContent = `Sessions older than ${this.currentDays} days will be permanently deleted`;
      }
    },

    async executeCleanup() {
      const warningMsg = this.currentDays >= 99999
        ? `🚨 CRITICAL WARNING: This will DELETE ALL HISTORY!\n\nThis action is IRREVERSIBLE and will permanently delete EVERY scraping session in your database.\n\nAre you ABSOLUTELY CERTAIN you want to proceed?`
        : `⚠️ WARNING: This action cannot be undone!\n\nAre you absolutely sure you want to delete all sessions older than ${this.currentDays} days?`;
      
      if (!confirm(warningMsg)) {
        return;
      }

      try {
        utils.setLoading(true);
        this.hide();
        
        const response = await fetch('/api/cleanup', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ days: this.currentDays })
        });
        
        if (!response.ok) throw new Error('Failed to cleanup');
        const result = await response.json();
        
        const message = this.currentDays >= 99999
          ? `🗑️ All history deleted! Removed ${result.deleted_entries} session(s)`
          : `✅ Successfully deleted ${result.deleted_entries} old session(s)`;
        
        utils.showAlert('success', message);
        
        // Reset data and reload everything
        historyData = [];
        filteredHistory = [];
        loadHistory();
        loadStatistics();
        updateSiteFilterOptions();
        updateMinItemsSlider();
      } catch (error) {
        console.error('Error cleaning up:', error);
        utils.showAlert('danger', '❌ Failed to cleanup old entries');
      } finally {
        utils.setLoading(false);
      }
    }
  };

  function showCleanupModal() {
    cleanupModal.show();
  }

  // Event Listeners
  function initializeEventListeners() {
    if (elements.closeModal) {
      elements.closeModal.addEventListener('click', () => {
        if (elements.historyModal) elements.historyModal.style.display = 'none';
      });
    }

    if (elements.historyModal) {
      elements.historyModal.addEventListener('click', (e) => {
        if (e.target === elements.historyModal) {
          elements.historyModal.style.display = 'none';
        }
      });
    }

    if (elements.refreshBtn) {
      elements.refreshBtn.addEventListener('click', () => {
        loadHistory();
        loadStatistics();
      });
    }

    if (elements.cleanupBtn) {
      elements.cleanupBtn.addEventListener('click', showCleanupModal);
    }

    if (elements.historySearch) {
      elements.historySearch.addEventListener('input', (e) => {
        filterState.search = e.target.value.trim().toLowerCase();
        applyFilters();
      });
    }

    if (elements.historyStartDate) {
      elements.historyStartDate.addEventListener('change', (e) => {
        filterState.startDate = parseDateInput(e.target.value, false);
        applyFilters();
      });
    }

    if (elements.historyEndDate) {
      elements.historyEndDate.addEventListener('change', (e) => {
        filterState.endDate = parseDateInput(e.target.value, true);
        applyFilters();
      });
    }

    if (elements.historyMinItems) {
      elements.historyMinItems.addEventListener('input', (e) => {
        const value = Math.max(0, Number(e.target.value) || 0);
        filterState.minItems = value;
        if (elements.historyMinItemsValue) {
          elements.historyMinItemsValue.textContent = value.toString();
        }
        applyFilters();
      });
    }

    if (elements.historySiteSelect) {
      elements.historySiteSelect.addEventListener('change', (e) => {
        filterState.site = e.target.value;
        applyFilters();
      });
    }

    if (elements.historyClearFilters) {
      elements.historyClearFilters.addEventListener('click', () => resetFilters());
    }

    // Theme handling
    if (elements.darkMode) {
      const savedTheme = sessionStorage.getItem('cy_theme');
      if (savedTheme) {
        document.documentElement.setAttribute('data-bs-theme', savedTheme);
      }
      elements.darkMode.checked = (savedTheme || 'dark') === 'dark';
      elements.darkMode.addEventListener('change', (e) => {
        const theme = e.target.checked ? 'dark' : 'light';
        document.documentElement.setAttribute('data-bs-theme', theme);
        sessionStorage.setItem('cy_theme', theme);
      });
    }
  }

  // Initialize
  function init() {
    initializeEventListeners();
    cleanupModal.init();
    resetFilters({ skipApply: true });
    startHistoryClock();
    loadHistory();
  }

  // Start when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
