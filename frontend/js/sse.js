/* =============================================
   SSE.JS - Real-time job updates from backend
   ============================================= */

import { state } from './state.js';
import { applyJobUpdateFromServer } from './api.js';

const API_BASE = (() => {
    const explicit = String(window.__SCRAPER_API_BASE__ || '').trim();
    if (explicit) return explicit.replace(/\/+$/, '');
    return window.location.protocol === 'file:' ? 'http://localhost:3001' : '';
})();

let eventSource = null;
let reconnectTimer = null;
let refreshTimer = null;

function scheduleRefresh(delayMs = 120) {
    if (refreshTimer) return;

    refreshTimer = setTimeout(async () => {
        refreshTimer = null;
        try {
            const { refreshJobs } = await import('./main.js');
            await refreshJobs();
        } catch (error) {
            console.warn('Failed to refresh jobs after SSE update:', error);
        }
    }, delayMs);
}

function connect() {
    const streamUrl = `${API_BASE}/events`;

    try {
        eventSource = new EventSource(streamUrl);
    } catch (error) {
        console.error('Failed to create SSE connection:', error);
        state.sseConnected = false;
        return;
    }

    eventSource.onopen = () => {
        state.sseConnected = true;
        state.lastSseUpdateAt = Date.now();
    };

    eventSource.addEventListener('ready', () => {
        state.lastSseUpdateAt = Date.now();
    });

    eventSource.addEventListener('ping', () => {
        state.lastSseUpdateAt = Date.now();
    });

    eventSource.addEventListener('job_update', (event) => {
        state.lastSseUpdateAt = Date.now();

        try {
            const payload = JSON.parse(event.data);
            const updatedJob = applyJobUpdateFromServer(payload);
            if (updatedJob) {
                scheduleRefresh();
            }
        } catch (error) {
            console.warn('Invalid job_update payload:', error);
        }
    });

    eventSource.onerror = () => {
        state.sseConnected = false;

        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }

        if (!reconnectTimer) {
            reconnectTimer = setTimeout(() => {
                reconnectTimer = null;
                connect();
            }, 2500);
        }
    };
}

export function setupSSE() {
    closeSSE();
    connect();
}

export function closeSSE() {
    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }

    if (refreshTimer) {
        clearTimeout(refreshTimer);
        refreshTimer = null;
    }

    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }

    state.sseConnected = false;
}
