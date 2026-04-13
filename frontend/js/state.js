/* =============================================
   STATE.JS - Global state management
   ============================================= */

// Generate or retrieve user ID for session isolation
function getUserId() {
    let userId = localStorage.getItem('userId');
    if (!userId) {
        // Generate a new UUID for this user
        userId = crypto.randomUUID ? crypto.randomUUID() :
            'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
                const r = Math.random() * 16 | 0;
                return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
            });
        localStorage.setItem('userId', userId);
        console.log('🆔 New user session created:', userId);
    }
    return userId;
}

// State object
export const state = {
    userId: getUserId(), // Unique user identifier for session isolation
    allJobs: [],
    currentJob: null,
    images: [],
    filteredImages: [],

    bulkMode: false,
    modalIndex: 0,
    modalImages: [],
    currentFilter: 'all',
    jobSearchQuery: '',
    gridSize: localStorage.getItem('gridSize') || 'medium',
    soundEnabled: localStorage.getItem('soundEnabled') !== 'false',
    darkMode: false,
    slideshowInterval: null,
    recentUrls: JSON.parse(localStorage.getItem('recentUrls') || '[]'),
    jobStartTimes: {},
    currentZoom: 100,
    selectedImages: new Set(), // Track selected images for bulk operations
    refreshInFlight: false,
    lastJobsSignature: '',
    sseConnected: false,
    lastSseUpdateAt: 0
};

// Constants
export const MAX_CONCURRENT = 3;

// State update helpers
export function setState(key, value) {
    state[key] = value;
}

export function getState(key) {
    return state[key];
}

// Persistence helpers
export function persistToStorage(key, value) {
    try {
        localStorage.setItem(key, typeof value === 'string' ? value : JSON.stringify(value));
    } catch (e) {
        console.warn('Failed to persist to localStorage:', e);
    }
}

export function loadFromStorage(key, defaultValue = null) {
    try {
        const value = localStorage.getItem(key);
        if (value === null) return defaultValue;
        try {
            return JSON.parse(value);
        } catch {
            return value;
        }
    } catch (e) {
        console.warn('Failed to load from localStorage:', e);
        return defaultValue;
    }
}
