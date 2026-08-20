/* =============================================
   MAIN.JS - App initialization and entry point
   ============================================= */

import { state, MAX_CONCURRENT, persistToStorage } from './state.js';
import { fetchJobs, startScrapeAPI, startModelScrapeAPI } from './api.js';
import { showToast } from './toast.js';
import { playSound, toggleSound, updateSoundIcon } from './sound.js';
import {
    updateStats, renderJobs, updateWarning,
    filterJobs, searchJobs, deleteJob, resetJobs, retryJob, pauseJob, resumeJob, togglePauseAll,
    toggleDarkMode, updateDarkMode, initFilterButtons,
    showConfirm, closeConfirm, formatTime
} from './ui.js';
import {
    loadImages, renderGallery, filterImages, clearSearch,
    setGridSize, applyGridSize, cycleGridSize,
    copyImageUrl, copyAllUrls, refreshCurrentJob, openRandomImage,
    downloadZip, downloadBulkZip, toggleImageSelection, toggleSelectAll, deleteSelectedImages,
    syncCurrentJobImages
} from './gallery.js';
import {
    openModalWithSrc, openModal, closeModal, showModal,
    updateModalImage, updateImageDimensions,
    goToImage, prevImage, nextImage,
    zoomIn, zoomOut, resetZoom,
    copyCurrentFilename, copyCurrentImageUrl,
    startSlideshow, stopSlideshow
} from './modal.js';
import { setupKeyboardShortcuts, showShortcuts, toggleBulkMode } from './keyboard.js';
import { setupSSE } from './sse.js';
import { setupLogsSSE, clearLogUI } from './logs.js';
import { launchConfetti } from './effects.js';

// Request notification permission
if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
}

// Refresh jobs from server
export async function refreshJobs() {
    if (state.refreshInFlight) return;
    state.refreshInFlight = true;
    try {
        const prevJobs = [...state.allJobs];
        const fetchedJobs = await fetchJobs();

        // Safety: filter out null/undefined
        state.allJobs = fetchedJobs.filter(job => job != null);

        const signature = state.allJobs
            .map(job => `${job.id}:${job.status}:${job.images || 0}:${job.processed_items || 0}:${job.total_items || 0}:${job.model || ''}`)
            .join('|');
        const changed = signature !== state.lastJobsSignature;
        state.lastJobsSignature = signature;

        // Track job start times
        state.allJobs.forEach(job => {
            if (job && job.status === 'running' && !state.jobStartTimes[job.id]) {
                state.jobStartTimes[job.id] = Date.now();
            }
        });

        // Check for newly completed jobs
        state.allJobs.forEach(job => {
            if (!job) return;
            const prevJob = prevJobs.find(j => j && j.id === job.id);
            if (prevJob && prevJob.status === 'running' && job.status === 'completed') {
                delete state.jobStartTimes[job.id];
            }
        });

        // Skip expensive repaint when data is unchanged
        if (changed) {
            updateStats();
            renderJobs();
            updateWarning();
        }

        // Live-sync selected gallery while job updates stream in.
        if (state.currentJob) {
            const activeJob = state.allJobs.find((job) => job && job.id === state.currentJob);
            if (activeJob) {
                const expected = Number.isFinite(Number(activeJob.images)) ? Number(activeJob.images) : 0;
                if (expected !== state.images.length || activeJob.status === 'running') {
                    await syncCurrentJobImages();
                }
            }
        }
    } catch (e) {
        console.error('Failed to refresh jobs:', e);
    } finally {
        state.refreshInFlight = false;
    }
}

// Start scrape
async function startScrape() {
    playSound('click');
    const urlInput = document.getElementById('url-input');
    const inputValue = urlInput ? urlInput.value.trim() : '';

    if (!inputValue) {
        showToast('error', 'Input Required', 'Enter a category URL or a model name');
        if (urlInput) {
            urlInput.classList.add('animate-shake', 'ring-2', 'ring-red-500');
            setTimeout(() => {
                urlInput.classList.remove('animate-shake', 'ring-2', 'ring-red-500');
            }, 500);
        }
        return;
    }

    const isUrl = /^https?:\/\//i.test(inputValue);
    const valueLabel = isUrl ? 'URL' : 'Model';

    // Check for duplicate URL
    const existingJob = isUrl
        ? state.allJobs.find(j => j.url === inputValue && j.status !== 'failed')
        : null;
    if (isUrl && existingJob) {
        const confirmed = await showConfirm(
            'Duplicate URL',
            'This URL is already in your jobs list. Start a new scrape anyway?',
            'warning'
        );
        if (!confirmed) return;
    }

    // Check concurrent limit
    const running = state.allJobs.filter(j => j.status === 'running').length;
    if (running >= MAX_CONCURRENT) {
        showToast('warning', 'Queue Full', `Maximum ${MAX_CONCURRENT} concurrent jobs allowed. Please wait for a job to finish.`);
        return;
    }

    // Add to recent URLs
    if (isUrl) addToRecentUrls(inputValue);

    const btn = document.getElementById('start-btn');
    const btnText = document.getElementById('btn-text');

    if (btn) {
        btn.disabled = true;
        btn.classList.add('animate-glow');
    }
    if (btnText) {
        btnText.innerHTML = '<svg class="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke-width="2" opacity="0.3"/><path d="M4 12a8 8 0 018-8" stroke-width="2"/></svg> Starting...';
    }

    try {
        if (isUrl) {
            const data = await startScrapeAPI(inputValue);

            if (urlInput) urlInput.value = '';

            const hasProducts = Array.isArray(data?.products);

            if (data.job_id && !hasProducts) {
                const newJob = {
                    id: data.job_id,
                    url: inputValue,
                    status: 'queued',
                    model: null,
                    images: 0,
                    total_items: 0,
                    processed_items: 0
                };
                state.allJobs.unshift(newJob);
                updateStats();
                renderJobs();

                playSound('success');
                showToast('success', 'Scrape Started! 🚀', `Job #${data.job_id} has been queued successfully`);
            }

            if (hasProducts) {
                await refreshJobs();
                const productCount = data.products.length;
                playSound('success');
                showToast(
                    'success',
                    'Scrape Complete',
                    `Found ${productCount} product${productCount !== 1 ? 's' : ''}`
                );

                if (data.job_id) {
                    const completedJob = state.allJobs.find(j => j.id === data.job_id);
                    if (completedJob) {
                        loadImages(completedJob.id, completedJob.model || completedJob.url || 'Scrape Result');
                    }
                }
            } else {
                // Fallback for queued mode
                setTimeout(refreshJobs, 500);
            }
        } else {
            const data = await startModelScrapeAPI(inputValue);
            if (urlInput) urlInput.value = '';

            if (data && Array.isArray(data.jobs) && data.jobs.length > 0) {
                data.jobs.forEach(j => {
                    state.allJobs.unshift({
                        id: j.job_id,
                        url: j.url,
                        status: 'queued',
                        model: data.model,
                        images: 0,
                        total_items: 0,
                        processed_items: 0
                    });
                });
                updateStats();
                renderJobs();
                playSound('success');
                showToast('success', 'Model Scrape Started', `Queued ${data.jobs.length} jobs for "${data.model}"`);
            }

            setTimeout(refreshJobs, 500);
        }
    } catch (e) {
        showToast('error', `Failed to Start ${valueLabel}`, e.message || 'Could not start the scrape. Please try again.');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.classList.remove('animate-glow');
        }
        if (btnText) {
            btnText.textContent = 'Start Scrape';
        }
    }
}

function parseBulkScrapeLine(line) {
    const value = String(line || '').trim();
    if (!value) return null;

    const urlMatch = value.match(/https?:\/\/[^\s<>"']+/i);
    if (!urlMatch) return null;

    const url = urlMatch[0]
        .replace(/^[([{]+/g, '')
        .replace(/[\])}"',.;]+$/g, '');
    const labelText = value.slice(0, urlMatch.index).trim();
    const label = labelText
        .replace(/\s*[-:|,]\s*$/g, '')
        .replace(/^\[/, '')
        .replace(/\]\($/, '')
        .replace(/^[("']+|[)"',]+$/g, '')
        .trim();

    return { url, folderName: label, rawLine: value };
}

function parseBulkScrapeEntries(text) {
    return String(text || '')
        .split(/\r?\n/)
        .map((line, index) => {
            const entry = parseBulkScrapeLine(line);
            return entry ? { ...entry, lineNumber: index + 1 } : null;
        })
        .filter(Boolean);
}

function formatBulkScrapeEntry(entry) {
    if (!entry) return '';
    return entry.folderName ? `${entry.folderName} - ${entry.url}` : entry.url;
}

const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Bulk scrape
async function startBulkScrape() {
    playSound('click');
    const textarea = document.getElementById('bulk-urls');
    if (!textarea) return;

    const entries = parseBulkScrapeEntries(textarea.value);
    const titleFilter = String(document.getElementById('bulk-title-filter')?.value || '').trim();

    if (entries.length === 0) {
        showToast('warning', 'No URLs', 'Please paste at least one URL');
        return;
    }

    let started = 0;
    let duplicates = 0;
    let failed = 0;
    const failedEntries = [];
    const queuedUrls = new Set(
        state.allJobs
            .filter(job => job && job.url && job.status !== 'failed')
            .map(job => job.url)
    );

    showToast(
        'info',
        'Queueing Jobs...',
        titleFilter
            ? `Queueing ${entries.length} folder${entries.length !== 1 ? 's' : ''} with filter "${titleFilter}"`
            : `Queueing ${entries.length} folder${entries.length !== 1 ? 's' : ''}`
    );

    for (const entry of entries) {
        if (queuedUrls.has(entry.url)) {
            duplicates++;
            continue;
        }

        try {
            await startScrapeAPI(entry.url, {
                titleFilter,
                folderName: entry.folderName
            });
            started++;
            queuedUrls.add(entry.url);

            if (started % 10 === 0) {
                state.allJobs = await fetchJobs();
                updateStats();
                renderJobs();
                updateWarning();
            }

            await delay(150);
        } catch (e) {
            failed++;
            failedEntries.push({
                ...entry,
                error: e?.message || 'Could not start this URL'
            });
            console.error('Failed to start:', entry.url, e);
        }
    }

    if (started > 0) {
        showToast('success', 'Bulk Import Queued', `Queued ${started} job${started !== 1 ? 's' : ''}`);
        playSound('success');
    }

    if (failedEntries.length > 0) {
        textarea.value = failedEntries
            .map(entry => entry.rawLine || formatBulkScrapeEntry(entry))
            .join('\n');
        updateBulkUrlCount();
    } else if (started > 0 || duplicates > 0) {
        textarea.value = '';
        updateBulkUrlCount();
    }

    if (duplicates > 0) {
        showToast('info', 'Skipped Duplicates', `${duplicates} URL${duplicates !== 1 ? 's were' : ' was'} already queued`);
    }

    if (failed > 0) {
        const firstError = failedEntries[0]?.error;
        showToast(
            'error',
            'Some Failed',
            firstError
                ? `${failed} URL${failed !== 1 ? 's' : ''} failed. Kept them in the box. First error: ${firstError}`
                : `${failed} URL${failed !== 1 ? 's' : ''} failed. Kept them in the box.`
        );
    }

    refreshJobs();
}

// Bulk URL counter
function setupBulkUrlCounter() {
    const textarea = document.getElementById('bulk-urls');
    if (textarea) {
        textarea.addEventListener('input', updateBulkUrlCount);
        textarea.addEventListener('change', updateBulkUrlCount);
        textarea.addEventListener('paste', () => setTimeout(updateBulkUrlCount, 0));
        updateBulkUrlCount();
    }
}

function updateBulkUrlCount() {
    const textarea = document.getElementById('bulk-urls');
    const countEl = document.getElementById('bulk-url-count');
    if (!textarea || !countEl) return;

    const entries = parseBulkScrapeEntries(textarea.value);
    countEl.textContent = `${entries.length} URL${entries.length !== 1 ? 's' : ''} detected`;
}

// Recent URLs
function loadRecentUrls() {
    const input = document.getElementById('url-input');
    if (!input || state.recentUrls.length === 0) return;

    let datalist = document.getElementById('recent-urls-list');
    if (!datalist) {
        datalist = document.createElement('datalist');
        datalist.id = 'recent-urls-list';
        document.body.appendChild(datalist);
        input.setAttribute('list', 'recent-urls-list');
    }

    datalist.innerHTML = state.recentUrls.slice(0, 10).map(url =>
        `<option value="${url}">`
    ).join('');
}

function addToRecentUrls(url) {
    if (!url) return;
    state.recentUrls = [url, ...state.recentUrls.filter(u => u !== url)].slice(0, 20);
    persistToStorage('recentUrls', state.recentUrls);
    loadRecentUrls();
}

// Drag and drop for URL input
function setupDragDrop() {
    const dropZone = document.getElementById('url-input');
    if (!dropZone) return;

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
        });
    });

    dropZone.addEventListener('dragenter', () => {
        dropZone.classList.add('ring-2', 'ring-brand-500', 'border-brand-500');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('ring-2', 'ring-brand-500', 'border-brand-500');
    });

    dropZone.addEventListener('drop', (e) => {
        dropZone.classList.remove('ring-2', 'ring-brand-500', 'border-brand-500');
        const text = e.dataTransfer.getData('text');
        if (text) {
            dropZone.value = text.trim();
            showToast('info', 'URL Dropped', 'Press Enter to start scraping');
            playSound('click');
        }
    });
}

// Export/Import Jobs
function exportJobs() {
    if (state.allJobs.length === 0) {
        showToast('warning', 'No Jobs', 'No jobs to export');
        return;
    }
    const data = {
        exported: new Date().toISOString(),
        jobs: state.allJobs.map(j => ({
            url: j.url,
            status: j.status,
            images: j.images,
            error: j.error
        }))
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const filename = `xcellparts-jobs-${new Date().toISOString().split('T')[0]}.json`;
    saveAs(blob, filename);
    showToast('success', 'Exported!', `${state.allJobs.length} jobs exported to JSON`);
    playSound('download');
}

async function importJobs(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (e) => {
        try {
            const data = JSON.parse(e.target.result);
            if (!data.jobs || !Array.isArray(data.jobs)) {
                throw new Error('Invalid format');
            }

            const urls = data.jobs.map(j => j.url).filter(u => u && u.trim().length > 0);

            if (urls.length === 0) {
                showToast('warning', 'No URLs Found', 'No URLs found in import file');
                return;
            }

            const confirmed = await showConfirm(
                `Import ${urls.length} Jobs?`,
                `This will start scraping ${urls.length} URLs from the imported file.`,
                'info'
            );

            if (confirmed) {
                for (const url of urls) {
                    try {
                        await startScrapeAPI(url);
                    } catch (e) {
                        console.warn('Failed to import URL:', url);
                    }
                }
                showToast('success', 'Imported!', `${urls.length} jobs added to queue`);
                playSound('success');
                refreshJobs();
            }
        } catch (e) {
            showToast('error', 'Import Failed', 'Could not parse import file');
        }
    };
    reader.readAsText(file);
    event.target.value = '';
}

// Expose functions globally for onclick handlers
window.appFunctions = {
    startScrape,
    startBulkScrape,
    updateBulkUrlCount,
    loadImages,
    deleteJob,
    retryJob,
    pauseJob,
    resumeJob,
    resetJobs,
    togglePauseAll,
    filterJobs,
    searchJobs,
    filterImages,
    clearSearch,
    setGridSize,
    cycleGridSize,
    copyImageUrl,
    copyAllUrls,
    refreshCurrentJob,
    openRandomImage,
    downloadZip,
    downloadBulkZip,
    openModalWithSrc,
    openModal,
    closeModal,
    goToImage,
    prevImage,
    nextImage,
    zoomIn,
    zoomOut,
    resetZoom,
    copyCurrentFilename,
    copyCurrentImageUrl,
    startSlideshow,
    toggleDarkMode,
    toggleSound,
    toggleBulkMode,
    showShortcuts,
    showConfirm,
    closeConfirm,
    exportJobs,
    importJobs,
    playSound,
    updateImageDimensions,
    toggleImageSelection,
    toggleSelectAll,
    deleteSelectedImages
};
window.appFunctions.clearLogUI = clearLogUI;

// Single DOMContentLoaded handler
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Initializing MobileSentrix & XCellParts Image Scraper...');

    try {
        // Initialize UI
        updateSoundIcon();
        updateDarkMode();
        initFilterButtons();
        applyGridSize();

        // Setup features
        setupBulkUrlCounter();
        setupDragDrop();
        loadRecentUrls();
        setupKeyboardShortcuts();

        // Start SSE for real-time updates
        setupSSE();
        setupLogsSSE();

        // Initial data load
        refreshJobs();

        // Periodic refresh as fallback (only when SSE is stale/disconnected)
        setInterval(() => {
            if (document.hidden) return;
            if (state.sseConnected && (Date.now() - state.lastSseUpdateAt) < 7000) return;
            refreshJobs();
        }, 7000);

        console.log('✅ Initialization complete!');
    } catch (error) {
        console.error('❌ Initialization error:', error);
        showToast('error', 'Initialization Error', error.message);
    }
});

console.log('📦 Main module loaded');
