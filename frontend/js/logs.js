/* =============================================
   LOGS.JS - Real-time server logs panel
   ============================================= */

const API_BASE = (() => {
    const explicit = String(window.__SCRAPER_API_BASE__ || '').trim();
    if (explicit) return explicit.replace(/\/+$/, '');
    return window.location.protocol === 'file:' ? 'http://localhost:3001' : '';
})();

const MAX_LOG_ROWS = 300;

let logsSource = null;
let reconnectTimer = null;
let flushRafId = 0;
let pendingEntries = [];
let lastEntryKey = '';
let lastEntryNode = null;
let lastEntryRepeat = 1;

function formatTime(isoTime) {
    try {
        return new Date(isoTime).toLocaleTimeString();
    } catch {
        return '--:--:--';
    }
}

function getLogContainer() {
    return document.getElementById('server-logs');
}

function normalizeLevel(level) {
    const value = String(level || 'info').toLowerCase();
    if (value === 'warn') return 'warning';
    if (value === 'ok') return 'success';
    return ['info', 'warning', 'error', 'success'].includes(value) ? value : 'info';
}

function trimLogRows(container) {
    while (container.children.length > MAX_LOG_ROWS) {
        container.removeChild(container.firstElementChild);
    }
}

function ensureNotEmpty(container) {
    const empty = container.querySelector('.log-empty');
    if (empty) empty.remove();
}

function entryKey(entry) {
    return [entry.level, entry.source, entry.message, entry.job_id || ''].join('|');
}

function isNearBottom(container) {
    const distance = container.scrollHeight - container.scrollTop - container.clientHeight;
    return distance < 28;
}

function appendLogNow(entry, container, autoScroll) {
    const normalized = {
        time: entry?.time || new Date().toISOString(),
        level: normalizeLevel(entry?.level),
        source: String(entry?.source || 'server'),
        message: String(entry?.message || ''),
        job_id: entry?.job_id ? String(entry.job_id) : null
    };

    const key = entryKey(normalized);

    if (lastEntryNode && key === lastEntryKey) {
        lastEntryRepeat += 1;
        const repeatEl = lastEntryNode.querySelector('.log-repeat');
        if (repeatEl) repeatEl.textContent = `x${lastEntryRepeat}`;

        const timeEl = lastEntryNode.querySelector('.log-time');
        if (timeEl) timeEl.textContent = formatTime(normalized.time);

        if (autoScroll) {
            container.scrollTop = container.scrollHeight;
        }
        return;
    }

    lastEntryKey = key;
    lastEntryRepeat = 1;

    const row = document.createElement('div');
    row.className = `log-entry log-${normalized.level}`;
    row.innerHTML = `
        <span class="log-time">${formatTime(normalized.time)}</span>
        <span class="log-level">${normalized.level.toUpperCase()}</span>
        <span class="log-source">[${normalized.source}]</span>
        <span class="log-line"><span class="log-message"></span></span>
        <span class="log-repeat"></span>
    `;

    const messageNode = row.querySelector('.log-message');
    if (messageNode) {
        messageNode.textContent = normalized.job_id
            ? `${normalized.message} (job ${normalized.job_id})`
            : normalized.message;
    }

    container.appendChild(row);
    lastEntryNode = row;
}

function flushPendingLogs() {
    flushRafId = 0;

    const container = getLogContainer();
    if (!container || pendingEntries.length === 0) {
        pendingEntries = [];
        return;
    }

    ensureNotEmpty(container);

    const autoScroll = isNearBottom(container);
    const toFlush = pendingEntries;
    pendingEntries = [];

    for (const entry of toFlush) {
        appendLogNow(entry, container, autoScroll);
    }

    trimLogRows(container);

    if (autoScroll) {
        container.scrollTop = container.scrollHeight;
    }
}

function scheduleFlush() {
    if (flushRafId) return;
    flushRafId = window.requestAnimationFrame(flushPendingLogs);
}

function queueLog(entry) {
    pendingEntries.push(entry);
    scheduleFlush();
}

async function loadRecentLogs() {
    try {
        const response = await fetch(`${API_BASE}/logs?limit=80`);
        if (!response.ok) return;

        const payload = await response.json();
        if (!payload?.success || !Array.isArray(payload.logs)) return;

        payload.logs.forEach(queueLog);
    } catch (error) {
        queueLog({
            level: 'warning',
            source: 'logs',
            message: `Could not load recent logs: ${error.message}`
        });
    }
}

function connectStream() {
    const streamUrl = `${API_BASE}/logs/stream`;

    try {
        logsSource = new EventSource(streamUrl);
    } catch (error) {
        queueLog({ level: 'error', source: 'logs', message: `Failed to connect logs stream: ${error.message}` });
        return;
    }

    logsSource.onopen = () => {
        queueLog({ level: 'success', source: 'logs', message: 'Live logs connected' });
    };

    logsSource.addEventListener('log', (event) => {
        try {
            queueLog(JSON.parse(event.data));
        } catch (error) {
            queueLog({ level: 'warning', source: 'logs', message: `Malformed log payload: ${error.message}` });
        }
    });

    logsSource.onerror = () => {
        if (logsSource) {
            logsSource.close();
            logsSource = null;
        }

        queueLog({ level: 'warning', source: 'logs', message: 'Log stream disconnected, retrying...' });

        if (!reconnectTimer) {
            reconnectTimer = setTimeout(() => {
                reconnectTimer = null;
                connectStream();
            }, 3000);
        }
    };
}

export function setupLogsSSE() {
    closeLogsSSE();

    const container = getLogContainer();
    if (container && container.children.length === 0) {
        container.innerHTML = '<div class="log-empty">Connecting to logs...</div>';
    }

    loadRecentLogs().finally(connectStream);
}

export function closeLogsSSE() {
    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }

    if (logsSource) {
        logsSource.close();
        logsSource = null;
    }

    if (flushRafId) {
        window.cancelAnimationFrame(flushRafId);
        flushRafId = 0;
    }
}

export function clearLogUI() {
    const container = getLogContainer();
    if (!container) return;

    container.innerHTML = '<div class="log-empty">System ready. Waiting for events...</div>';
    pendingEntries = [];
    lastEntryKey = '';
    lastEntryNode = null;
    lastEntryRepeat = 1;
}
