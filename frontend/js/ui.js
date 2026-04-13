/* =============================================
   UI.JS - DOM manipulation and UI updates
   ============================================= */

import { state, MAX_CONCURRENT, persistToStorage } from './state.js';
import { showToast } from './toast.js';
import { playSound } from './sound.js';
import { deleteJobAPI, resetJobsAPI, startScrapeAPI, pauseAllJobsAPI, resumeAllJobsAPI } from './api.js';
import { loadImages } from './gallery.js';

// Counter animation state
const counterAnimations = {};

function escapeInlineString(value) {
    return String(value ?? '')
        .replace(/\\/g, '\\\\')
        .replace(/'/g, "\\'")
        .replace(/\r?\n/g, ' ');
}

// Animate counter with requestAnimationFrame
export function animateCounter(elementId, targetValue) {
    const element = document.getElementById(elementId);
    if (!element) return;

    const currentValue = parseInt(element.textContent.replace(/,/g, '')) || 0;
    if (currentValue === targetValue) return;

    // Cancel existing animation
    if (counterAnimations[elementId]) {
        cancelAnimationFrame(counterAnimations[elementId]);
    }

    const duration = 500;
    const startTime = performance.now();
    const startValue = currentValue;

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Easing function (ease-out cubic)
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const value = Math.round(startValue + (targetValue - startValue) * easeOut);

        element.textContent = value.toLocaleString();

        if (progress < 1) {
            counterAnimations[elementId] = requestAnimationFrame(update);
        } else {
            delete counterAnimations[elementId];
        }
    }

    counterAnimations[elementId] = requestAnimationFrame(update);
}

// Update all stats displays
export function updateStats() {
    const running = state.allJobs.filter(j => j.status === 'running').length;
    const queued = state.allJobs.filter(j => j.status === 'queued').length;
    const completed = state.allJobs.filter(j => j.status === 'completed').length;
    const failed = state.allJobs.filter(j => j.status === 'failed').length;
    const totalImages = state.allJobs.reduce((sum, j) => sum + (j.images || 0), 0);
    const totalJobs = state.allJobs.length;

    // Update stat elements safely
    const updates = {
        'stat-running': running,
        'stat-queued': queued,
        'stat-completed': completed,
        'stat-failed': failed,
        'stat-running-count': running,
        'stat-completed-count': completed,
        'stat-failed-count': failed,
        'stat-total-jobs': totalJobs
    };

    Object.entries(updates).forEach(([id, value]) => {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    });

    // Animate total images counter
    animateCounter('stat-total-images', totalImages);

    // Calculate and display success rate
    const finishedJobs = completed + failed;
    const rate = finishedJobs > 0 ? Math.round((completed / finishedJobs) * 100) : 0;
    const successRate = document.getElementById('success-rate');
    const successRateBar = document.getElementById('success-rate-bar');
    if (successRate) successRate.textContent = `${rate}%`;
    if (successRateBar) successRateBar.style.width = `${rate}%`;

    // Update global status indicator
    updateGlobalStatus(running);
}

// Update global status indicator
function updateGlobalStatus(running) {
    const status = document.getElementById('global-status');
    if (!status) return;

    if (running > 0) {
        status.className = 'flex items-center gap-2 px-3 py-1.5 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded-full text-sm font-medium';
        status.innerHTML = `<span class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></span><span>Running ${running} job${running > 1 ? 's' : ''}</span>`;
    } else {
        status.className = 'flex items-center gap-2 px-3 py-1.5 bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 rounded-full text-sm font-medium';
        status.innerHTML = '<span class="w-2 h-2 bg-emerald-500 rounded-full"></span><span>Ready</span>';
    }
}

// Update warning banner visibility
export function updateWarning() {
    const running = state.allJobs.filter(j => j.status === 'running').length;
    const warning = document.getElementById('warning-banner');
    const btn = document.getElementById('start-btn');

    if (warning) warning.classList.toggle('hidden', running < MAX_CONCURRENT);
    if (btn) btn.disabled = running >= MAX_CONCURRENT;
}

// Format time duration
export function formatTime(ms) {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    if (hours > 0) return `${hours}h ${minutes % 60}m`;
    if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
    return `${seconds}s`;
}

// Update Pause All button text dynamically
function updatePauseAllButton() {
    const pauseBtn = document.getElementById('pause-resume-btn');
    const pauseText = document.getElementById('pause-resume-text');
    if (!pauseBtn) return;

    const runningCount = state.allJobs.filter(j => j.status === 'running').length;
    const pausedCount = state.allJobs.filter(j => j.status === 'paused').length;

    if (pausedCount > 0 && runningCount === 0) {
        // All jobs are paused, show Resume All
        if (pauseText) pauseText.textContent = 'Resume All';
        pauseBtn.className = 'flex items-center gap-2 px-3 py-1.5 bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-100 dark:hover:bg-emerald-900/50 rounded-full text-sm font-medium transition-all cursor-pointer';
    } else {
        // Jobs are running or mixed state, show Pause All
        if (pauseText) pauseText.textContent = 'Pause All';
        pauseBtn.className = 'flex items-center gap-2 px-3 py-1.5 bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400 hover:bg-amber-100 dark:hover:bg-amber-900/50 rounded-full text-sm font-medium transition-all cursor-pointer';
    }
}

// Render jobs list
export function renderJobs() {
    const container = document.getElementById('jobs-list');
    if (!container) return;
    const prevScrollTop = container.scrollTop;
    const wasNearBottom = (container.scrollTop + container.clientHeight) >= (container.scrollHeight - 24);

    let jobs = state.currentFilter === 'all'
        ? state.allJobs
        : state.allJobs.filter(j => j.status === state.currentFilter);

    // Apply search filter
    if (state.jobSearchQuery) {
        const query = state.jobSearchQuery.toLowerCase();
        jobs = jobs.filter(j =>
            (j.model && j.model.toLowerCase().includes(query)) ||
            (j.url && j.url.toLowerCase().includes(query))
        );
    }

    // Update job count
    const jobCountEl = document.getElementById('job-count');
    if (jobCountEl) {
        const suffix = state.jobSearchQuery ? ' found' : ' jobs';
        jobCountEl.textContent = `${jobs.length}${suffix}`;
    }

    if (jobs.length === 0) {
        container.innerHTML = `<div class="text-center py-8 text-slate-400"><svg class="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg><p class="text-sm">${state.jobSearchQuery ? 'No matching jobs' : `No ${state.currentFilter !== 'all' ? state.currentFilter + ' ' : ''}jobs`}</p></div>`;
        container.scrollTop = 0;
        updatePauseAllButton();
        return;
    }

    container.innerHTML = jobs.map(job => renderJobCard(job)).join('');
    if (wasNearBottom) {
        container.scrollTop = container.scrollHeight;
    } else {
        container.scrollTop = Math.min(prevScrollTop, Math.max(container.scrollHeight - container.clientHeight, 0));
    }

    // Update Pause All button text based on job states
    updatePauseAllButton();
}

// Render single job card
function renderJobCard(job) {
    const progress = job.total_items ? Math.round((job.processed_items / job.total_items) * 100) : 0;
    const isActive = state.currentJob === job.id;

    // Time elapsed for running jobs
    let timeInfo = '';
    if (job.status === 'running' && state.jobStartTimes[job.id]) {
        const elapsed = Date.now() - state.jobStartTimes[job.id];
        timeInfo = `<span class="inline-flex items-center gap-1 text-blue-600 dark:text-blue-400 animate-pulse whitespace-nowrap">⏱ ${formatTime(elapsed)}</span>`;
    }

    const modelName = escapeInlineString(job.model || '');
    const safeUrl = escapeInlineString(job.url || '');
    const safeId = escapeInlineString(job.id);

    return `
        <div data-job-id="${safeId}" onclick="window.appFunctions.loadImages('${safeId}', '${modelName}')" 
             class="group p-3 rounded-xl border ${isActive ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20' : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 hover:shadow-sm'} cursor-pointer transition-all relative">
            
            <!-- Action buttons (show on hover) -->
            <div class="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-all z-10">
                ${job.status === 'failed' ? `
                    <button onclick="event.stopPropagation(); window.appFunctions.retryJob('${safeId}', '${safeUrl}')" 
                            class="p-1.5 rounded-lg text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-900/30 bg-white dark:bg-slate-800 shadow-sm"
                            title="Retry job">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                        </svg>
                    </button>
                ` : ''}
                <button onclick="event.stopPropagation(); window.appFunctions.deleteJob('${safeId}')" 
                        class="p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 bg-white dark:bg-slate-800 shadow-sm"
                        title="Delete job">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                    </svg>
                </button>
            </div>
            
            <!-- Status indicator + Title -->
            <div class="flex items-center gap-2 mb-2">
                <span class="flex-shrink-0 w-2 h-2 rounded-full ${job.status === 'running' ? 'bg-blue-500 animate-pulse' : job.status === 'completed' ? 'bg-emerald-500' : job.status === 'failed' ? 'bg-red-500' : 'bg-amber-500'}"></span>
                <p class="font-semibold text-sm text-slate-900 dark:text-white flex-1 truncate" title="${job.model || ''}">${job.model || 'Processing...'}</p>
            </div>
            
            <!-- Progress bar -->
            <div class="h-1 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden mb-2">
                <div class="h-full ${job.status === 'completed' ? 'bg-emerald-500' : job.status === 'failed' ? 'bg-red-400' : 'bg-gradient-to-r from-brand-500 to-blue-500'} rounded-full transition-all ${job.status === 'running' ? 'animate-pulse' : ''}" style="width: ${progress}%"></div>
            </div>
            
            <!-- Stats row -->
            <div class="grid grid-cols-2 gap-2 text-xs text-slate-400 dark:text-slate-500">
                <span class="min-w-0 truncate whitespace-nowrap">${job.processed_items}/${job.total_items || '?'} ${progress > 0 ? `• ${progress}%` : ''}</span>
                <span class="min-w-0 flex items-center justify-end gap-1.5 font-medium whitespace-nowrap">
                    ${timeInfo}
                    <span class="text-slate-500 dark:text-slate-400 whitespace-nowrap">${job.images} images</span>
                </span>
            </div>
        </div>
    `;
}

// Filter jobs
export function filterJobs(filter) {
    playSound('click');
    state.currentFilter = filter;

    document.querySelectorAll('.filter-btn').forEach(btn => {
        const isActive = btn.dataset.filter === filter;
        btn.classList.toggle('active', isActive);
        btn.classList.toggle('bg-brand-600', isActive);
        btn.classList.toggle('text-white', isActive);
        btn.classList.toggle('bg-slate-100', !isActive);
        btn.classList.toggle('text-slate-600', !isActive);
    });

    renderJobs();
}

// Search jobs
export function searchJobs(query) {
    state.jobSearchQuery = query.toLowerCase().trim();
    renderJobs();
}

// Delete job with confirmation
export async function deleteJob(jobId) {
    playSound('click');

    const confirmed = await showConfirm(
        'Delete Job?',
        'This will permanently delete the job and all downloaded images.',
        'danger'
    );

    if (!confirmed) return;

    try {
        await deleteJobAPI(jobId);

        state.allJobs = state.allJobs.filter(j => j.id !== jobId);

        if (state.currentJob === jobId) {
            state.currentJob = null;
            state.images = [];
            resetGalleryUI();
        }

        updateStats();
        renderJobs();
        const { refreshJobs } = await import('./main.js');
        await refreshJobs();
        showToast('success', 'Job Deleted', 'The job and its images have been removed');
    } catch (err) {
        showToast('error', 'Delete Failed', 'Could not delete the job. Please try again.');
    }
}

// Reset all jobs
export async function resetJobs() {
    const confirmed = await showConfirm(
        'Reset All Jobs?',
        'This will delete ALL jobs and downloaded images. This action cannot be undone!',
        'danger'
    );

    if (!confirmed) return;

    playSound('click');
    try {
        await resetJobsAPI();

        state.allJobs = [];
        state.currentJob = null;
        state.images = [];

        resetGalleryUI();
        updateStats();
        renderJobs();

        showToast('success', 'All Clear! 🧹', 'All jobs and images have been reset');
    } catch (err) {
        showToast('error', 'Reset Failed', 'Could not reset jobs. Please try again.');
    }
}

// Toggle pause/resume all jobs
export async function togglePauseAll() {
    playSound('click');

    const pausedCount = state.allJobs.filter(j => j.status === 'paused').length;
    const runningCount = state.allJobs.filter(j => j.status === 'running').length;

    try {
        if (runningCount > 0) {
            // Pause all running jobs
            await pauseAllJobsAPI();
            showToast('info', 'Jobs Paused ⏸️', `Paused ${runningCount} running job${runningCount > 1 ? 's' : ''}`);
        } else if (pausedCount > 0) {
            // Resume all paused jobs
            await resumeAllJobsAPI();
            showToast('success', 'Jobs Resumed ▶️', `Resumed ${pausedCount} paused job${pausedCount > 1 ? 's' : ''}`);
        } else {
            showToast('info', 'No Jobs', 'No jobs to pause or resume');
            return;
        }

        // Refresh jobs list
        const { refreshJobs } = await import('./main.js');
        await refreshJobs();
    } catch (err) {
        showToast('error', 'Action Failed', 'Could not pause/resume jobs. Please try again.');
    }
}

// Reset gallery UI
function resetGalleryUI() {
    const elements = {
        'gallery-title': 'Image Gallery',
        'gallery-subtitle': 'Click on a job to view images',
        'image-count': '0 images'
    };

    Object.entries(elements).forEach(([id, text]) => {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    });

    const gallery = document.getElementById('gallery');
    if (gallery) {
        gallery.innerHTML = `<div class="flex flex-col items-center justify-center py-16 text-slate-400"><svg class="w-16 h-16 mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg><p class="text-sm font-medium">No images to display</p><p class="text-xs mt-1">Select a job from the sidebar</p></div>`;
    }

    const zipBtn = document.getElementById('zip-btn');
    if (zipBtn) zipBtn.disabled = true;

    const toolsEl = document.getElementById('gallery-tools');
    if (toolsEl) toolsEl.classList.add('hidden');
}

// Retry failed job
export async function retryJob(jobId, url) {
    playSound('click');

    try {
        await deleteJobAPI(jobId);
    } catch (e) {
        console.error('Failed to delete job:', e);
    }

    try {
        await startScrapeAPI(url);
        showToast('info', 'Retrying...', 'Started new scrape for the same URL');

        // Refresh jobs list
        const { refreshJobs } = await import('./main.js');
        refreshJobs();
    } catch (e) {
        showToast('error', 'Retry Failed', 'Could not start new scrape');
    }
}

// Confirmation dialog
let confirmResolve = null;

export function showConfirm(title, message, type = 'info') {
    return new Promise((resolve) => {
        confirmResolve = resolve;

        const modal = document.getElementById('confirm-modal');
        const iconEl = document.getElementById('confirm-icon');
        const titleEl = document.getElementById('confirm-title');
        const messageEl = document.getElementById('confirm-message');
        const btnEl = document.getElementById('confirm-btn');

        if (!modal || !iconEl || !titleEl || !messageEl || !btnEl) {
            resolve(false);
            return;
        }

        titleEl.textContent = title;
        messageEl.textContent = message;

        const configs = {
            danger: {
                iconBg: 'bg-red-100 dark:bg-red-900/30',
                icon: '<svg class="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>',
                btnClass: 'bg-red-600 hover:bg-red-700'
            },
            warning: {
                iconBg: 'bg-amber-100 dark:bg-amber-900/30',
                icon: '<svg class="w-6 h-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>',
                btnClass: 'bg-amber-600 hover:bg-amber-700'
            },
            info: {
                iconBg: 'bg-blue-100 dark:bg-blue-900/30',
                icon: '<svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
                btnClass: 'bg-blue-600 hover:bg-blue-700'
            }
        };

        const config = configs[type] || configs.info;
        iconEl.className = `w-12 h-12 rounded-full flex items-center justify-center ${config.iconBg}`;
        iconEl.innerHTML = config.icon;
        btnEl.className = `px-4 py-2 text-sm font-medium text-white rounded-lg transition-all ${config.btnClass}`;

        modal.classList.remove('hidden');
    });
}

export function closeConfirm(result) {
    const modal = document.getElementById('confirm-modal');
    if (modal) modal.classList.add('hidden');

    if (confirmResolve) {
        confirmResolve(result);
        confirmResolve = null;
    }
}

// Dark mode
export function toggleDarkMode() {
    state.darkMode = !state.darkMode;
    persistToStorage('darkMode', state.darkMode);
    updateDarkMode();
    playSound('click');
}

export function updateDarkMode() {
    document.documentElement.classList.toggle('dark', state.darkMode);

    const sunIcon = document.getElementById('sun-icon');
    const moonIcon = document.getElementById('moon-icon');

    if (sunIcon) sunIcon.classList.toggle('hidden', !state.darkMode);
    if (moonIcon) moonIcon.classList.toggle('hidden', state.darkMode);
}

// Initialize filter buttons
export function initFilterButtons() {
    document.querySelectorAll('.filter-btn').forEach(btn => {
        const isActive = btn.classList.contains('active');
        if (isActive) {
            btn.classList.add('bg-brand-600', 'text-white');
        } else {
            btn.classList.add('bg-slate-100', 'text-slate-600', 'hover:bg-slate-200');
        }
    });
}
