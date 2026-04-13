/* =============================================
   GALLERY.JS - Image gallery functionality
   ============================================= */

import { state, persistToStorage } from './state.js';
import { showToast } from './toast.js';
import { playSound } from './sound.js';
import { fetchImagesAPI } from './api.js';
import { openModalWithSrc } from './modal.js';

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

function parseFilenameFromDisposition(dispositionHeader) {
    if (!dispositionHeader) return '';
    const utf8Match = dispositionHeader.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf8Match?.[1]) {
        try {
            return decodeURIComponent(utf8Match[1]).replace(/^["']|["']$/g, '');
        } catch {
            return utf8Match[1].replace(/^["']|["']$/g, '');
        }
    }
    const plainMatch = dispositionHeader.match(/filename=([^;]+)/i);
    if (plainMatch?.[1]) {
        return plainMatch[1].trim().replace(/^["']|["']$/g, '');
    }
    return '';
}

// Load images for a job
export async function loadImages(jobId, jobModel) {
    playSound('click');
    state.currentJob = jobId;
    state.selectedImages.clear(); // Clear selection when switching jobs


    const job = state.allJobs.find(j => j.id === jobId);

    const titleEl = document.getElementById('gallery-title');
    const subtitleEl = document.getElementById('gallery-subtitle');
    const toolsEl = document.getElementById('gallery-tools');
    const searchEl = document.getElementById('image-search');

    if (titleEl) {
        titleEl.textContent = jobModel || 'Loading...';
        titleEl.setAttribute('title', jobModel || 'Loading...');
    }
    if (subtitleEl) subtitleEl.textContent = 'Loading images...';
    if (toolsEl) toolsEl.classList.add('hidden');
    if (searchEl) searchEl.value = '';

    const gallery = document.getElementById('gallery');
    if (gallery) {
        // Animated skeleton loader with shimmer effect
        gallery.innerHTML = `
            <div class="flex flex-col items-center justify-center py-12">
                <!-- Animated spinner -->
                <div class="relative mb-6">
                    <div class="w-16 h-16 rounded-full border-4 border-slate-200 dark:border-slate-700"></div>
                    <div class="absolute inset-0 w-16 h-16 rounded-full border-4 border-transparent border-t-brand-500 animate-spin"></div>
                    <div class="absolute inset-2 w-12 h-12 rounded-full border-4 border-transparent border-t-blue-400 animate-spin" style="animation-direction: reverse; animation-duration: 0.8s;"></div>
                </div>
                
                <!-- Animated text -->
                <p class="text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">Loading images</p>
                <p class="text-xs text-slate-400 dark:text-slate-500 flex items-center gap-1">
                    <span class="inline-block animate-pulse">Fetching from server</span>
                    <span class="flex gap-0.5">
                        <span class="w-1 h-1 bg-slate-400 rounded-full animate-bounce" style="animation-delay: 0s;"></span>
                        <span class="w-1 h-1 bg-slate-400 rounded-full animate-bounce" style="animation-delay: 0.15s;"></span>
                        <span class="w-1 h-1 bg-slate-400 rounded-full animate-bounce" style="animation-delay: 0.3s;"></span>
                    </span>
                </p>
            </div>
            
            <!-- Skeleton grid -->
            <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 mt-4">
                ${Array(10).fill('').map((_, i) => `
                    <div class="aspect-square bg-slate-100 dark:bg-slate-800 rounded-xl overflow-hidden relative">
                        <div class="absolute inset-0 bg-gradient-to-r from-transparent via-slate-200/50 dark:via-slate-700/50 to-transparent skeleton-shimmer"></div>
                    </div>
                `).join('')}
            </div>
            
            <style>
                @keyframes shimmer {
                    0% { transform: translateX(-100%); }
                    100% { transform: translateX(100%); }
                }
                .skeleton-shimmer {
                    animation: shimmer 1.5s infinite;
                }
            </style>
        `;
    }

    try {
        state.images = await fetchImagesAPI(jobId);
        state.filteredImages = [...state.images];

        const imageCountEl = document.getElementById('image-count');
        const zipBtn = document.getElementById('zip-btn');

        if (imageCountEl) imageCountEl.textContent = `${state.images.length} images`;
        if (zipBtn) zipBtn.disabled = state.images.length === 0;

        if (job && subtitleEl) {
            subtitleEl.textContent = job.status === 'completed'
                ? `${state.images.length} images scraped`
                : job.status === 'running'
                    ? 'Scraping in progress...'
                    : job.status;
        }

        if (state.images.length === 0) {
            if (gallery) {
                gallery.innerHTML = `
                    <div class="flex flex-col items-center justify-center py-16 text-slate-400">
                        <svg class="w-12 h-12 mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                        </svg>
                        <p class="text-sm">No images yet</p>
                        <p class="text-xs mt-1">${job?.status === 'running' ? 'Scraping in progress...' : 'Job may have failed or not started'}</p>
                    </div>`;
            }
            return;
        }

        if (toolsEl) toolsEl.classList.remove('hidden');
        renderGallery();
        updateSelectionUI(); // Show selection controls
    } catch (e) {
        if (gallery) {
            gallery.innerHTML = '<div class="flex flex-col items-center justify-center py-16 text-red-400"><svg class="w-12 h-12 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg><p class="text-sm">Error loading images</p></div>';
        }
    }

    // Re-render jobs to show active state
    const { renderJobs } = await import('./ui.js');
    renderJobs();
}

// Keep selected job gallery in sync while scrape is running.
export async function syncCurrentJobImages() {
    if (!state.currentJob) return false;

    const job = state.allJobs.find((j) => j.id === state.currentJob);
    if (!job) return false;

    try {
        const latestImages = await fetchImagesAPI(state.currentJob);
        const normalized = Array.from(new Set((latestImages || []).filter(Boolean)));

        const sameLength = normalized.length === state.images.length;
        const sameOrder = sameLength && normalized.every((src, idx) => src === state.images[idx]);
        if (sameOrder) return false;

        const searchInput = document.getElementById('image-search');
        const query = searchInput ? searchInput.value.toLowerCase().trim() : '';
        const canIncremental = !query &&
            normalized.length >= state.images.length &&
            state.filteredImages.length === state.images.length;

        if (canIncremental) {
            const applied = updateGalleryIncremental(normalized);
            if (!applied) {
                state.images = normalized;
                state.filteredImages = [...normalized];
                renderGallery();
            }
        } else {
            state.images = normalized;
            state.filteredImages = query
                ? normalized.filter((src) => src.toLowerCase().includes(query))
                : [...normalized];
            renderGallery();
        }

        const countEl = document.getElementById('image-count');
        if (countEl) {
            countEl.textContent = state.filteredImages.length === state.images.length
                ? `${state.images.length} images`
                : `${state.filteredImages.length} of ${state.images.length} images`;
        }

        const zipBtn = document.getElementById('zip-btn');
        if (zipBtn) zipBtn.disabled = state.images.length === 0;

        const subtitleEl = document.getElementById('gallery-subtitle');
        if (subtitleEl && job.status === 'running') {
            subtitleEl.textContent = `${state.images.length} images scraped`;
        }

        return true;
    } catch (error) {
        console.warn('Failed to sync current gallery images:', error);
        return false;
    }
}

// Render image gallery with batch loading for performance
let renderBatchTimeout = null;
const INITIAL_BATCH = 90; // Render more immediately for faster first paint on active jobs
const BATCH_SIZE = 60; // Larger follow-up batches to catch up quickly

export function renderGallery() {
    const gallery = document.getElementById('gallery');
    if (!gallery) return;

    const gridClass = getGridClass();

    // Add animation styles if not already added
    if (!document.getElementById('gallery-animations')) {
        const style = document.createElement('style');
        style.id = 'gallery-animations';
        style.textContent = `
            @keyframes cardFadeIn {
                0% {
                    opacity: 0;
                    transform: translateY(10px) scale(0.98);
                }
                100% {
                    opacity: 1;
                    transform: translateY(0) scale(1);
                }
            }
            .card-animate {
                opacity: 0;
                animation: cardFadeIn 0.2s ease-out forwards;
            }
        `;
        document.head.appendChild(style);
    }

    gallery.innerHTML = `<div class="image-grid ${gridClass}"></div>`;
    const grid = gallery.querySelector('.image-grid');
    if (!grid) return;

    // Clear any pending batch renders
    if (renderBatchTimeout) {
        clearTimeout(renderBatchTimeout);
    }

    // Render in batches for better performance
    let currentIndex = 0;

    function renderBatch(batchSize, animate = true) {
        const endIndex = Math.min(currentIndex + batchSize, state.filteredImages.length);
        const fragment = document.createDocumentFragment();

        for (let idx = currentIndex; idx < endIndex; idx++) {
            const src = state.filteredImages[idx];
            const div = createImageCard(src, idx, animate && idx < INITIAL_BATCH);
            fragment.appendChild(div);
        }
        grid.appendChild(fragment);

        currentIndex = endIndex;

        // If there are more images, schedule next batch
        if (currentIndex < state.filteredImages.length) {
            renderBatchTimeout = setTimeout(() => renderBatch(BATCH_SIZE, false), 20);
        }
    }

    // Start rendering - first batch immediately
    renderBatch(INITIAL_BATCH, true);

    // Update image count display
    updateImageCount();
}

// Create a single image card element
function createImageCard(src, idx, animate) {
    const div = document.createElement('div');

    // Only animate first batch for instant feel
    const animClass = animate ? 'card-animate' : '';
    const delay = animate ? Math.min(idx, 20) * 20 : 0;

    div.className = `image-card group relative cursor-pointer transition-all ${animClass}`;
    if (delay > 0) div.style.animationDelay = `${delay}ms`;
    div.dataset.src = src;
    div.addEventListener('click', () => openModalWithSrc(src));

    const isSelected = state.selectedImages.has(src);

    if (isSelected) div.classList.add('selected');

    const selectionWrap = document.createElement('div');
    selectionWrap.className = 'select-toggle absolute top-2 left-2 z-10';

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.dataset.imageSrc = src;
    checkbox.checked = isSelected;
    checkbox.className = 'w-5 h-5 rounded border-2 border-white shadow-lg cursor-pointer text-brand-600 focus:ring-brand-500 focus:ring-offset-0';
    checkbox.addEventListener('click', (event) => {
        event.stopPropagation();
        window.appFunctions.toggleImageSelection(src);
        div.classList.toggle('selected', state.selectedImages.has(src));
    });

    selectionWrap.appendChild(checkbox);

    const skeleton = document.createElement('div');
    skeleton.className = 'img-skeleton';

    const frame = document.createElement('div');
    frame.className = 'image-frame';

    const img = document.createElement('img');
    img.src = src;
    img.alt = `Image ${idx + 1}`;
    img.loading = 'lazy';
    img.decoding = 'async';
    img.className = 'gallery-image';
    img.addEventListener('load', () => {
        img.classList.add('is-visible');
        div.classList.add('img-loaded');
    });
    img.addEventListener('error', () => {
        div.classList.remove('img-loaded');
        div.classList.add('img-error');
        frame.innerHTML = '';
        frame.appendChild(createImageErrorFallback());
    });
    frame.appendChild(img);

    const overlay = document.createElement('div');
    overlay.className = 'image-overlay absolute inset-0';

    const actionRow = document.createElement('div');
    actionRow.className = 'absolute bottom-2 left-2 right-2 flex gap-1';

    const copyBtn = document.createElement('button');
    copyBtn.type = 'button';
    copyBtn.title = 'Copy URL';
    copyBtn.className = 'p-1.5 bg-white/90 dark:bg-slate-800/90 rounded-lg text-slate-700 dark:text-slate-200 hover:bg-white text-xs';
    copyBtn.innerHTML = '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"/></svg>';
    copyBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        window.appFunctions.copyImageUrl(src);
    });

    const downloadLink = document.createElement('a');
    downloadLink.href = src;
    downloadLink.title = 'Download';
    downloadLink.className = 'p-1.5 bg-white/90 dark:bg-slate-800/90 rounded-lg text-slate-700 dark:text-slate-200 hover:bg-white text-xs';
    downloadLink.innerHTML = '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>';
    const rawName = decodeURIComponent((src.split('/').pop() || `image_${idx + 1}.jpg`).split('?')[0]);
    downloadLink.download = rawName || `image_${idx + 1}.jpg`;
    downloadLink.addEventListener('click', (event) => {
        event.stopPropagation();
        window.appFunctions.playSound('download');
    });

    actionRow.append(copyBtn, downloadLink);
    overlay.appendChild(actionRow);

    div.append(selectionWrap, skeleton, frame, overlay);

    return div;
}

function createImageErrorFallback() {
    const node = document.createElement('div');
    node.className = 'flex flex-col items-center justify-center text-slate-400 dark:text-slate-500';
    node.innerHTML = `
        <svg class="w-8 h-8 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
        </svg>
        <span class="text-[10px]">Failed</span>
    `;
    return node;
}

// Helper to update image count
function updateImageCount() {
    const countEl = document.getElementById('image-count');
    if (countEl) {
        countEl.textContent = state.filteredImages.length === state.images.length
            ? `${state.images.length} images`
            : `${state.filteredImages.length} of ${state.images.length} images`;
    }
}

// Smart incremental gallery update - only adds new images without full re-render
export function updateGalleryIncremental(newImages) {
    const grid = document.querySelector('.image-grid');
    if (!grid) return false;

    // Find images that aren't already displayed
    const existingSrcs = new Set(Array.from(grid.children).map(el => el.dataset.src));
    const imagesToAdd = newImages.filter(src => !existingSrcs.has(src));

    if (imagesToAdd.length === 0) return false;

    // Add new images without re-rendering entire gallery
    const fragment = document.createDocumentFragment();
    const startIndex = state.filteredImages.length;
    imagesToAdd.forEach((src, idx) => {
        fragment.appendChild(createImageCard(src, startIndex + idx, true));
    });
    grid.appendChild(fragment);

    // Update state
    state.images = newImages;
    state.filteredImages = [...newImages];

    // Update count
    const countEl = document.getElementById('image-count');
    if (countEl) {
        countEl.textContent = `${newImages.length} images`;
    }

    return true;
}

// Get grid class based on selected size
function getGridClass() {
    switch (state.gridSize) {
        case 'small': return 'grid-small';
        case 'large': return 'grid-large';
        default: return 'grid-medium';
    }
}

// Filter images by search
export function filterImages() {
    const searchInput = document.getElementById('image-search');
    const clearBtn = document.getElementById('clear-search-btn');
    const query = searchInput ? searchInput.value.toLowerCase().trim() : '';

    if (clearBtn) clearBtn.classList.toggle('hidden', !query);

    if (!query) {
        state.filteredImages = [...state.images];
    } else {
        state.filteredImages = state.images.filter(src => src.toLowerCase().includes(query));
    }
    renderGallery();
}

// Clear search
export function clearSearch() {
    const searchInput = document.getElementById('image-search');
    if (searchInput) searchInput.value = '';
    filterImages();
    playSound('click');
}

// Grid size management
export function setGridSize(size) {
    state.gridSize = size;
    persistToStorage('gridSize', size);
    applyGridSize();
    playSound('click');
}

export function applyGridSize() {
    document.querySelectorAll('.grid-btn').forEach(btn => {
        btn.classList.remove('text-slate-600', 'bg-slate-100');
        btn.classList.add('text-slate-400');
    });

    const activeBtn = document.getElementById(`grid-${state.gridSize}`);
    if (activeBtn) {
        activeBtn.classList.remove('text-slate-400');
        activeBtn.classList.add('text-slate-600', 'bg-slate-100');
    }

    renderGallery();
}

// Cycle grid size
export function cycleGridSize() {
    const sizes = ['small', 'medium', 'large'];
    const currentIdx = sizes.indexOf(state.gridSize);
    setGridSize(sizes[(currentIdx + 1) % sizes.length]);
}



// Copy image URL
export function copyImageUrl(url) {
    navigator.clipboard.writeText(toDisplayUrl(url));
    showToast('success', 'Copied!', 'Image URL copied to clipboard');
    playSound('click');
}

// Copy all URLs
export function copyAllUrls() {
    if (state.filteredImages.length === 0) {
        showToast('warning', 'No Images', 'No images to copy');
        return;
    }
    const urls = state.filteredImages.map(src => toDisplayUrl(src)).join('\n');
    navigator.clipboard.writeText(urls);
    showToast('success', 'Copied!', `${state.filteredImages.length} image URLs copied to clipboard`);
    playSound('click');
}

// Refresh current job
export function refreshCurrentJob() {
    if (!state.currentJob) {
        showToast('warning', 'No Job Selected', 'Select a job first');
        return;
    }
    const job = state.allJobs.find(j => j.id === state.currentJob);
    loadImages(state.currentJob, job?.model || job?.url || 'Unknown');
    showToast('info', 'Refreshed', 'Images reloaded');
}

// Open random image
export function openRandomImage() {
    if (state.filteredImages.length === 0) {
        showToast('warning', 'No Images', 'No images available');
        return;
    }
    const randomIdx = Math.floor(Math.random() * state.filteredImages.length);
    openModalWithSrc(state.filteredImages[randomIdx]);
    playSound('click');
}

// Download ZIP
export async function downloadZip() {
    const images = state.filteredImages.length ? state.filteredImages : state.images;
    if (!images.length) {
        showToast('warning', 'No Images', 'No images available for export');
        return;
    }

    const job = state.allJobs.find(j => j.id === state.currentJob);
    const model = (job?.model || 'images').replace(/[^\w.-]+/g, '_').slice(0, 60);

    if (state.currentJob) {
        const zipUrl = `${window.location.origin}/jobs/${encodeURIComponent(state.currentJob)}/zip`;
        try {
            showToast('info', 'Preparing ZIP', 'Generating server ZIP...');
            const response = await fetch(zipUrl);
            if (!response.ok) {
                const message = await response.text().catch(() => '');
                throw new Error(message || `HTTP ${response.status}`);
            }

            const blob = await response.blob();
            if (!blob || blob.size === 0) {
                throw new Error('Empty ZIP file');
            }

            const headerName = parseFilenameFromDisposition(response.headers.get('content-disposition'));
            const fallbackName = `${model || 'images'}_images.zip`;
            saveAs(blob, headerName || fallbackName);
            showToast('success', 'ZIP Ready', 'ZIP downloaded from server');
            playSound('download');
            return;
        } catch (error) {
            console.warn('Server ZIP download failed, falling back to browser ZIP:', error);
        }
    }

    if (typeof JSZip === 'undefined' || typeof saveAs === 'undefined') {
        showToast('error', 'ZIP Unavailable', 'ZIP dependencies are not loaded');
        return;
    }

    const zip = new JSZip();

    let successCount = 0;

    showToast('info', 'Preparing ZIP', `Downloading ${images.length} image${images.length !== 1 ? 's' : ''}...`);

    for (let index = 0; index < images.length; index++) {
        const src = toDisplayUrl(images[index]);
        if (!src) continue;

        try {
            const response = await fetch(src);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const arrayBuffer = await response.arrayBuffer();
            const urlPath = new URL(src, window.location.origin).pathname;
            const rawName = decodeURIComponent(urlPath.split('/').pop() || `image_${index + 1}.jpg`);
            const fileName = rawName.toLowerCase().endsWith('.jpg') || rawName.toLowerCase().endsWith('.jpeg')
                ? rawName
                : `${rawName.replace(/\.[a-z0-9]+$/i, '')}.jpg`;

            zip.file(fileName, arrayBuffer);
            successCount++;
        } catch (error) {
            console.warn(`Failed to include image in ZIP: ${src}`, error);
        }
    }

    if (successCount === 0) {
        showToast('error', 'ZIP Failed', 'Could not download images for ZIP export');
        return;
    }

    const blob = await zip.generateAsync({ type: 'blob' });
    saveAs(blob, `${model}_images.zip`);

    showToast('success', 'ZIP Ready', `${successCount} image${successCount !== 1 ? 's' : ''} downloaded`);
    playSound('download');
}

// Image Selection Functions
export function toggleImageSelection(src) {
    if (state.selectedImages.has(src)) {
        state.selectedImages.delete(src);
    } else {
        state.selectedImages.add(src);
    }
    updateSelectionUI();
    playSound('click');
}

export function toggleSelectAll() {
    const selectAllCheckbox = document.getElementById('select-all-images');
    if (selectAllCheckbox && selectAllCheckbox.checked) {
        // Select all visible images
        state.filteredImages.forEach(src => state.selectedImages.add(src));
    } else {
        // Deselect all
        state.selectedImages.clear();
    }
    renderGallery();
    updateSelectionUI();
    playSound('click');
}

export function updateSelectionUI() {
    const selectionControls = document.getElementById('selection-controls');
    const deleteBtn = document.getElementById('delete-selected-btn');
    const deleteCount = document.getElementById('delete-count');
    const selectAllCheckbox = document.getElementById('select-all-images');

    const selectedCount = state.selectedImages.size;

    // Show/hide selection controls
    if (selectionControls) {
        if (state.images.length > 0) {
            selectionControls.classList.remove('hidden');
            selectionControls.classList.add('flex');
        } else {
            selectionControls.classList.add('hidden');
            selectionControls.classList.remove('flex');
        }
    }

    // Update delete button
    if (deleteBtn) {
        deleteBtn.disabled = selectedCount === 0;
    }
    if (deleteCount) {
        deleteCount.textContent = `Delete (${selectedCount})`;
    }

    // Update select all checkbox state
    if (selectAllCheckbox) {
        const allSelected = state.filteredImages.length > 0 &&
            state.filteredImages.every(src => state.selectedImages.has(src));
        selectAllCheckbox.checked = allSelected;
        selectAllCheckbox.indeterminate = selectedCount > 0 && !allSelected;
    }
}

export async function deleteSelectedImages() {
    const selectedCount = state.selectedImages.size;
    if (selectedCount === 0) return;

    const { showConfirm } = await import('./ui.js');
    const confirmed = await showConfirm(
        '🗑️ Delete Images',
        `Are you sure you want to delete ${selectedCount} selected image${selectedCount > 1 ? 's' : ''}? This cannot be undone.`,
        'warning'
    );

    if (!confirmed) return;

    showToast('info', 'Deleting Images', `Removing ${selectedCount} images...`);

    // For now, just remove from frontend (backend deletion would require endpoint)
    const imagesToDelete = Array.from(state.selectedImages);
    imagesToDelete.forEach(src => {
        state.images = state.images.filter(img => img !== src);
        state.filteredImages = state.filteredImages.filter(img => img !== src);
    });

    state.selectedImages.clear();
    renderGallery();
    updateSelectionUI();

    showToast('success', 'Images Deleted', `Removed ${selectedCount} image${selectedCount > 1 ? 's' : ''} from view`);
    playSound('success');

    // Reload to refresh from server
    if (state.currentJob) {
        const job = state.allJobs.find(j => j.id === state.currentJob);
        if (job) {
            setTimeout(() => loadImages(state.currentJob, job.model || job.url), 1500);
        }
    }
}
