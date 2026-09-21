/**
 * Server Logs Frontend Controller
 * Parts Extractor - v8.5.5
 */

(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);

  const elements = {
    darkMode: $('darkMode'),
    logFileSelect: $('logFileSelect'),
    logLevelSelect: $('logLevelSelect'),
    logSearchInput: $('logSearchInput'),
    logLinesSelect: $('logLinesSelect'),
    autoRefreshToggle: $('autoRefreshToggle'),
    autoScrollToggle: $('autoScrollToggle'),
    refreshLogsBtn: $('refreshLogsBtn'),
    downloadLogBtn: $('downloadLogBtn'),
    downloadAllLogsBtn: $('downloadAllLogsBtn'),
    copyLogsBtn: $('copyLogsBtn'),
    logConsoleBody: $('logConsoleBody'),
    statPillFile: $('statPillFile'),
    statPillSize: $('statPillSize'),
    statPillLines: $('statPillLines'),
    statPillTime: $('statPillTime'),
    liveBadge: $('liveBadge'),
  };

  let autoRefreshTimer = null;
  let searchDebounceTimer = null;
  let isFetching = false;
  let currentRawLines = [];

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function initTheme() {
    if (!elements.darkMode) return;
    const savedTheme = sessionStorage.getItem('cy_theme') || 'dark';
    elements.darkMode.checked = savedTheme === 'dark';
    document.documentElement.setAttribute('data-bs-theme', savedTheme);

    elements.darkMode.addEventListener('change', (e) => {
      const theme = e.target.checked ? 'dark' : 'light';
      document.documentElement.setAttribute('data-bs-theme', theme);
      sessionStorage.setItem('cy_theme', theme);
    });
  }

  async function loadAvailableLogFiles() {
    try {
      const res = await fetch('/api/logs/files');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (data.status !== 'success' || !Array.isArray(data.files)) {
        throw new Error(data.error || 'Failed to list log files');
      }

      const prevSelected = elements.logFileSelect.value;
      elements.logFileSelect.innerHTML = '';

      if (data.files.length === 0) {
        const opt = document.createElement('option');
        opt.value = 'server.log';
        opt.textContent = 'server.log (Empty)';
        elements.logFileSelect.appendChild(opt);
      } else {
        data.files.forEach((f) => {
          const opt = document.createElement('option');
          opt.value = f.file_id || f.name;
          const activeTag = f.is_active ? ' (Active)' : '';
          const sizeTag = f.size_formatted ? ` [${f.size_formatted}]` : '';
          opt.textContent = `${f.name}${activeTag}${sizeTag}`;
          elements.logFileSelect.appendChild(opt);
        });
      }

      if (prevSelected && Array.from(elements.logFileSelect.options).some(o => o.value === prevSelected)) {
        elements.logFileSelect.value = prevSelected;
      }
    } catch (err) {
      console.warn('Could not load log file list:', err);
    }
  }

  function highlightLine(escapedLine) {
    // Match common log formats: 2026-09-21 20:53:12,123 LEVEL [logger] message
    let lineClass = 'logs-line';
    let formatted = escapedLine;

    const isError = /\b(ERROR|CRITICAL)\b/.test(escapedLine);
    const isWarning = /\b(WARNING|WARN)\b/.test(escapedLine);
    const isInfo = /\bINFO\b/.test(escapedLine);

    if (isError) {
      lineClass += ' is-error';
    } else if (isWarning) {
      lineClass += ' is-warning';
    } else if (isInfo) {
      lineClass += ' is-info';
    }

    // Highlight timestamps: YYYY-MM-DD HH:MM:SS or ISO format
    formatted = formatted.replace(
      /^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:\d{2})?)/,
      '<span class="logs-highlight-ts">$1</span>'
    );

    // Highlight level tags
    formatted = formatted.replace(
      /\b(ERROR|CRITICAL)\b/g,
      '<span class="logs-highlight-error">$1</span>'
    );
    formatted = formatted.replace(
      /\b(WARNING|WARN)\b/g,
      '<span class="logs-highlight-warn">$1</span>'
    );
    formatted = formatted.replace(
      /\b(INFO)\b/g,
      '<span class="logs-highlight-info">$1</span>'
    );

    return { lineClass, formatted };
  }

  async function fetchLogTail() {
    if (isFetching) return;
    isFetching = true;

    const selectedFile = elements.logFileSelect.value || 'server.log';
    const maxLines = elements.logLinesSelect.value || '500';
    const level = elements.logLevelSelect.value || 'ALL';
    const search = (elements.logSearchInput.value || '').trim();

    if (elements.statPillFile) {
      elements.statPillFile.textContent = selectedFile;
    }

    try {
      const params = new URLSearchParams({
        file: selectedFile,
        lines: maxLines,
        level: level,
        search: search,
      });

      const res = await fetch(`/api/logs/tail?${params.toString()}`);
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.error || `Server returned ${res.status}`);
      }

      const data = await res.json();
      if (data.status !== 'success') {
        throw new Error(data.error || 'Failed to fetch log lines');
      }

      currentRawLines = data.lines || [];

      // Update statistics
      if (elements.statPillSize && data.size_formatted) {
        elements.statPillSize.textContent = data.size_formatted;
      }
      if (elements.statPillLines) {
        elements.statPillLines.textContent = `${data.returned_lines || currentRawLines.length} lines`;
      }
      if (elements.statPillTime) {
        const now = new Date();
        elements.statPillTime.textContent = now.toLocaleTimeString();
      }

      // Render lines into console
      if (currentRawLines.length === 0) {
        elements.logConsoleBody.innerHTML = `
          <div class="logs-empty-state">
            <div class="logs-empty-icon">&#128269;</div>
            <p>No log lines matched the active filters (${escapeHtml(selectedFile)}, Level: ${escapeHtml(level)}${search ? `, Query: "${escapeHtml(search)}"` : ''}).</p>
          </div>
        `;
      } else {
        const frag = document.createDocumentFragment();
        currentRawLines.forEach((raw, idx) => {
          const rowDiv = document.createElement('div');
          const escaped = escapeHtml(raw);
          const { lineClass, formatted } = highlightLine(escaped);
          rowDiv.className = lineClass;

          const numSpan = document.createElement('span');
          numSpan.className = 'logs-line-number';
          numSpan.textContent = String(idx + 1);

          const contentSpan = document.createElement('span');
          contentSpan.className = 'logs-line-content';
          contentSpan.innerHTML = formatted;

          rowDiv.appendChild(numSpan);
          rowDiv.appendChild(contentSpan);
          frag.appendChild(rowDiv);
        });

        elements.logConsoleBody.innerHTML = '';
        elements.logConsoleBody.appendChild(frag);

        if (elements.autoScrollToggle && elements.autoScrollToggle.checked) {
          elements.logConsoleBody.scrollTop = elements.logConsoleBody.scrollHeight;
        }
      }
    } catch (err) {
      elements.logConsoleBody.innerHTML = `
        <div class="logs-empty-state" style="color: #f43f5e;">
          <div class="logs-empty-icon">&#9888;</div>
          <p><strong>Error loading logs:</strong> ${escapeHtml(err.message)}</p>
        </div>
      `;
    } finally {
      isFetching = false;
    }
  }

  function setupAutoRefresh() {
    if (!elements.autoRefreshToggle) return;

    function updateTimer() {
      if (elements.autoRefreshToggle.checked) {
        if (!autoRefreshTimer) {
          autoRefreshTimer = setInterval(() => {
            fetchLogTail();
          }, 4000);
        }
        if (elements.liveBadge) {
          elements.liveBadge.className = 'logs-badge-live';
          elements.liveBadge.innerHTML = '<span class="pulse-dot"></span> LIVE (4s)';
        }
      } else {
        if (autoRefreshTimer) {
          clearInterval(autoRefreshTimer);
          autoRefreshTimer = null;
        }
        if (elements.liveBadge) {
          elements.liveBadge.className = 'logs-badge-paused';
          elements.liveBadge.innerHTML = 'PAUSED';
        }
      }
    }

    elements.autoRefreshToggle.addEventListener('change', updateTimer);
    updateTimer();
  }

  function setupEvents() {
    if (elements.logFileSelect) {
      elements.logFileSelect.addEventListener('change', () => fetchLogTail());
    }
    if (elements.logLevelSelect) {
      elements.logLevelSelect.addEventListener('change', () => fetchLogTail());
    }
    if (elements.logLinesSelect) {
      elements.logLinesSelect.addEventListener('change', () => fetchLogTail());
    }

    if (elements.logSearchInput) {
      elements.logSearchInput.addEventListener('input', () => {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
          fetchLogTail();
        }, 300);
      });
    }

    if (elements.refreshLogsBtn) {
      elements.refreshLogsBtn.addEventListener('click', async () => {
        elements.refreshLogsBtn.disabled = true;
        await loadAvailableLogFiles();
        await fetchLogTail();
        setTimeout(() => {
          elements.refreshLogsBtn.disabled = false;
        }, 400);
      });
    }

    if (elements.downloadLogBtn) {
      elements.downloadLogBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const file = elements.logFileSelect.value || 'server.log';
        window.location.href = `/api/logs/download?file=${encodeURIComponent(file)}`;
      });
    }

    if (elements.downloadAllLogsBtn) {
      elements.downloadAllLogsBtn.addEventListener('click', (e) => {
        e.preventDefault();
        window.location.href = '/api/logs/download-all';
      });
    }

    if (elements.copyLogsBtn) {
      elements.copyLogsBtn.addEventListener('click', async () => {
        if (currentRawLines.length === 0) return;
        try {
          await navigator.clipboard.writeText(currentRawLines.join('\n'));
          const orig = elements.copyLogsBtn.innerHTML;
          elements.copyLogsBtn.innerHTML = '&#10003; Copied!';
          setTimeout(() => {
            elements.copyLogsBtn.innerHTML = orig;
          }, 2000);
        } catch (err) {
          console.warn('Clipboard write failed:', err);
        }
      });
    }
  }

  // Initialize
  document.addEventListener('DOMContentLoaded', async () => {
    initTheme();
    setupEvents();
    setupAutoRefresh();
    await loadAvailableLogFiles();
    await fetchLogTail();
  });
})();
