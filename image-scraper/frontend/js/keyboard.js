/* =============================================
   KEYBOARD.JS - Keyboard shortcuts
   ============================================= */

import { state } from './state.js';
import { playSound, toggleSound } from './sound.js';
import { toggleDarkMode, resetJobs, closeConfirm } from './ui.js';
import {
    closeModal, prevImage, nextImage,
    zoomIn, zoomOut, resetZoom, startSlideshow
} from './modal.js';
import {
    copyAllUrls, refreshCurrentJob, openRandomImage,
    downloadZip, cycleGridSize, filterImages
} from './gallery.js';

// Show shortcuts modal
export function showShortcuts() {
    const modal = document.getElementById('shortcuts-modal');
    if (modal) {
        modal.classList.toggle('hidden');
        playSound('click');
    }
}

// Toggle bulk mode
export function toggleBulkMode() {
    state.bulkMode = !state.bulkMode;

    const singleMode = document.getElementById('single-url-mode');
    const bulkMode = document.getElementById('bulk-url-mode');
    const toggle = document.getElementById('bulk-toggle');

    if (singleMode) singleMode.classList.toggle('hidden', state.bulkMode);
    if (bulkMode) bulkMode.classList.toggle('hidden', !state.bulkMode);
    if (toggle) toggle.classList.toggle('text-brand-600', state.bulkMode);

    playSound('click');
}

// Setup global keyboard listener
export function setupKeyboardShortcuts() {
    // Modal keyboard navigation
    document.addEventListener('keydown', (e) => {
        const modal = document.getElementById('modal');
        if (modal && !modal.classList.contains('hidden')) {
            switch (e.key) {
                case 'ArrowLeft':
                    e.preventDefault();
                    prevImage();
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    nextImage();
                    break;
                case 'Escape':
                    closeModal();
                    break;
                case '+':
                case '=':
                    zoomIn();
                    break;
                case '-':
                    zoomOut();
                    break;
                case '0':
                    resetZoom();
                    break;
            }
            return;
        }

        // Don't trigger if typing in input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            if (e.key === 'Enter') {
                const { startScrape } = window.appFunctions || {};
                if (startScrape) startScrape();
            }
            return;
        }

        // Global shortcuts
        switch (e.key.toLowerCase()) {
            case 'd':
                toggleDarkMode();
                break;
            case 's':
                toggleSound();
                break;
            case 'r':
                if (state.currentJob) {
                    refreshCurrentJob();
                } else {
                    resetJobs();
                }
                break;
            case 'c':
                if (state.filteredImages.length > 0) {
                    copyAllUrls();
                }
                break;
            case 'o':
                if (state.filteredImages.length > 0) {
                    openRandomImage();
                }
                break;
            case 'z':
                const zipBtn = document.getElementById('zip-btn');
                if (zipBtn && !zipBtn.disabled) {
                    downloadZip();
                }
                break;
            case 'b':
                toggleBulkMode();
                break;
            case 'g':
                cycleGridSize();
                break;
            case 'f':
                const searchInput = document.getElementById('image-search');
                const toolsEl = document.getElementById('gallery-tools');
                if (searchInput && toolsEl && !toolsEl.classList.contains('hidden')) {
                    e.preventDefault();
                    searchInput.focus();
                }
                break;
            case 'j':
                const jobSearchInput = document.getElementById('job-search');
                if (jobSearchInput) {
                    e.preventDefault();
                    jobSearchInput.focus();
                }
                break;
            case 'p':
                if (state.filteredImages.length > 0) {
                    startSlideshow();
                }
                break;
            case '?':
                showShortcuts();
                break;
            case 'escape':
                document.getElementById('shortcuts-modal')?.classList.add('hidden');
                closeConfirm(false);
                closeModal();
                break;
        }
    });
}
