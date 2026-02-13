/* =============================================
   MODAL.JS - Image modal system
   ============================================= */

import { state } from './state.js';
import { playSound } from './sound.js';
import { showToast } from './toast.js';

function toDisplayUrl(src) {
    if (!src) return '';
    if (/^https?:\/\//i.test(src)) return src;
    if (/^data:/i.test(src)) return src;
    if (src.startsWith('//')) return `${window.location.protocol}${src}`;
    if (src.startsWith('/')) return `${window.location.origin}${src}`;
    try {
        return new URL(src, window.location.origin).href;
    } catch {
        return src;
    }
}

// Open modal with specific image source
export function openModalWithSrc(src) {
    state.modalImages = [...state.filteredImages];
    const idx = state.modalImages.indexOf(src);
    if (idx >= 0) {
        state.modalIndex = idx;
        state.currentZoom = 100;
        showModal();
    }
}

// Open modal at specific index
export function openModal(idx) {
    state.modalImages = [...state.images];
    if (idx < 0 || idx >= state.modalImages.length) {
        console.error('Invalid modal index:', idx);
        return;
    }
    state.modalIndex = idx;
    state.currentZoom = 100;
    showModal();
}

// Show modal
export function showModal() {
    updateModalImage();
    const modal = document.getElementById('modal');
    if (modal) {
        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }
}

// Close modal
export function closeModal() {
    stopSlideshow();
    const modal = document.getElementById('modal');
    if (modal) {
        modal.classList.add('hidden');
        document.body.style.overflow = '';
    }
    state.currentZoom = 100;
}

// Update modal image display
export function updateModalImage() {
    const src = state.modalImages[state.modalIndex];
    if (!src) return;

    const img = document.getElementById('modal-image');
    const counter = document.getElementById('modal-counter');
    const title = document.getElementById('modal-title');
    const subtitle = document.getElementById('modal-subtitle');
    const dimEl = document.getElementById('modal-dimensions');
    const downloadLink = document.getElementById('modal-download');
    const zoomLevel = document.getElementById('zoom-level');

    if (img) {
        img.src = src;
        img.style.transform = `scale(${state.currentZoom / 100})`;
    }

    if (zoomLevel) zoomLevel.textContent = `${state.currentZoom}%`;
    if (counter) counter.textContent = `${state.modalIndex + 1}/${state.modalImages.length}`;
    if (title) title.textContent = 'Image Preview';

    // Show full filename
    const filename = decodeURIComponent(src.split('/').pop());
    if (subtitle) subtitle.textContent = filename;

    // Reset dimensions until image loads
    if (dimEl) {
        const span = dimEl.querySelector('span:last-child');
        if (span) span.textContent = 'Loading...';
    }

    if (downloadLink) {
        downloadLink.href = src;
        downloadLink.download = filename;
    }

    updateThumbnails();
}

// Update image dimensions when loaded
export function updateImageDimensions(img) {
    const dimEl = document.getElementById('modal-dimensions');
    if (dimEl && img.naturalWidth && img.naturalHeight) {
        const span = dimEl.querySelector('span:last-child');
        if (span) span.textContent = `${img.naturalWidth} × ${img.naturalHeight}px`;
    }
}

// Update thumbnails strip
function updateThumbnails() {
    const container = document.getElementById('modal-thumbnails');
    if (!container) return;

    // Show only nearby thumbnails for performance
    const start = Math.max(0, state.modalIndex - 5);
    const end = Math.min(state.modalImages.length, state.modalIndex + 6);

    container.innerHTML = state.modalImages.slice(start, end).map((src, i) => {
        const actualIdx = start + i;
        const isActive = actualIdx === state.modalIndex;
        return `
            <button onclick="window.appFunctions.goToImage(${actualIdx})" class="flex-shrink-0 w-12 h-12 rounded-lg overflow-hidden transition-all bg-white dark:bg-slate-800 ${isActive ? 'ring-2 ring-brand-500 ring-offset-2' : 'opacity-60 hover:opacity-100'}">
                <img src="${src}" alt="" class="w-full h-full object-contain p-0.5" loading="lazy" />
            </button>
        `;
    }).join('');

    // Scroll to center the active thumbnail
    const activeThumb = container.querySelector('.ring-2');
    if (activeThumb) {
        activeThumb.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
    }
}

// Navigation
export function goToImage(idx) {
    state.modalIndex = idx;
    state.currentZoom = 100;
    updateModalImage();
}

export function prevImage() {
    if (state.modalIndex > 0) {
        state.modalIndex--;
        state.currentZoom = 100;
        updateModalImage();
    }
}

export function nextImage() {
    if (state.modalIndex < state.modalImages.length - 1) {
        state.modalIndex++;
        state.currentZoom = 100;
        updateModalImage();
    }
}

// Zoom controls
export function zoomIn() {
    if (state.currentZoom < 300) {
        state.currentZoom += 25;
        applyZoom();
    }
}

export function zoomOut() {
    if (state.currentZoom > 25) {
        state.currentZoom -= 25;
        applyZoom();
    }
}

export function resetZoom() {
    state.currentZoom = 100;
    applyZoom();
}

function applyZoom() {
    const img = document.getElementById('modal-image');
    const zoomLevel = document.getElementById('zoom-level');

    if (img) img.style.transform = `scale(${state.currentZoom / 100})`;
    if (zoomLevel) zoomLevel.textContent = `${state.currentZoom}%`;
}

// Copy current filename
export function copyCurrentFilename() {
    const src = state.modalImages[state.modalIndex];
    if (!src) return;

    const filename = decodeURIComponent(src.split('/').pop());
    navigator.clipboard.writeText(filename).then(() => {
        showToast('success', 'Copied!', filename.substring(0, 50) + (filename.length > 50 ? '...' : ''));
    }).catch(() => {
        showToast('error', 'Copy Failed', 'Could not copy to clipboard');
    });
}

// Copy current image URL
export function copyCurrentImageUrl() {
    const src = state.modalImages[state.modalIndex];
    if (src) {
        navigator.clipboard.writeText(toDisplayUrl(src));
        showToast('success', 'Copied!', 'Image URL copied to clipboard');
        playSound('click');
    }
}

// Slideshow
export function startSlideshow() {
    if (state.filteredImages.length === 0) {
        showToast('warning', 'No Images', 'Select a job with images first');
        return;
    }

    state.modalImages = [...state.filteredImages];
    state.modalIndex = 0;
    showModal();

    state.slideshowInterval = setInterval(() => {
        if (state.modalIndex < state.modalImages.length - 1) {
            nextImage();
        } else {
            stopSlideshow();
        }
    }, 3000);

    showToast('info', 'Slideshow Started', 'Press Escape to stop');
    playSound('click');
}

export function stopSlideshow() {
    if (state.slideshowInterval) {
        clearInterval(state.slideshowInterval);
        state.slideshowInterval = null;
    }
}
