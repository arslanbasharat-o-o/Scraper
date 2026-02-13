/* =============================================
   TOAST.JS - Toast notification system
   ============================================= */

import { playSound } from './sound.js';

const MAX_TOASTS = 4;
let toastCounter = 0;

function hasToastWithKey(container, key) {
    const toasts = container.querySelectorAll('.toast');
    for (const t of toasts) {
        if (t.dataset.dedupe === key) return t;
    }
    return null;
}

// Show toast notification
export function showToast(type, title, message, duration = 3000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    // Soft de-duplication: avoid spamming same toast repeatedly in short bursts
    const dedupeKey = `${type}|${title}|${message || ''}`;
    const existing = hasToastWithKey(container, dedupeKey);
    if (existing) {
        existing.classList.remove('animate-toastOut');
        existing.classList.add('animate-toastPulse');
        setTimeout(() => existing.classList.remove('animate-toastPulse'), 240);
        return existing;
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type} animate-toastIn relative overflow-hidden`;
    toast.dataset.dedupe = dedupeKey;
    toast.dataset.toastId = String(++toastCounter);

    const icons = {
        success: '<svg class="w-5 h-5 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>',
        error: '<svg class="w-5 h-5 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg>',
        warning: '<svg class="w-5 h-5 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 9v2m0 4h.01"/></svg>',
        info: '<svg class="w-5 h-5 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 16h-1v-4h-1m1-4h.01"/></svg>'
    };

    toast.innerHTML = `
        ${icons[type] || icons.info}
        <div class="flex-1 min-w-0">
            <p class="font-medium text-white text-sm leading-tight">${title}</p>
            ${message ? `<p class="text-xs text-white/70 mt-0.5 leading-tight">${message}</p>` : ''}
        </div>
        <button class="toast-close-btn p-1 hover:bg-white/20 rounded-md transition-all flex-shrink-0 ml-2">
            <svg class="w-4 h-4 text-white/60" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
        <div class="toast-progress" style="animation: shrink ${duration}ms linear forwards"></div>
    `;

    // Click handler for close button
    const closeBtn = toast.querySelector('.toast-close-btn');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => dismissToast(toast));
    }

    container.appendChild(toast);

    // Keep max visible toasts low for smoother UI
    while (container.children.length > MAX_TOASTS) {
        const first = container.firstElementChild;
        if (first) dismissToast(first);
        else break;
    }

    // Auto dismiss
    let timeoutId = setTimeout(() => dismissToast(toast), duration);

    // Store timeout ID for cleanup
    toast.dataset.timeoutId = String(timeoutId);

    // Pause auto-dismiss on hover for better UX
    toast.addEventListener('mouseenter', () => {
        if (toast.dataset.timeoutId) {
            clearTimeout(Number(toast.dataset.timeoutId));
            toast.dataset.timeoutId = '';
        }
    });
    toast.addEventListener('mouseleave', () => {
        if (!toast.dataset.timeoutId) {
            timeoutId = setTimeout(() => dismissToast(toast), 1200);
            toast.dataset.timeoutId = String(timeoutId);
        }
    });

    // Play appropriate sound
    if (type === 'success') playSound('success');
    else if (type === 'error') playSound('error');
    else if (type === 'warning') playSound('warning');
    else playSound('info');

    return toast;
}

// Dismiss toast with animation
export function dismissToast(toast) {
    if (!toast || !toast.parentElement) return;

    // Clear timeout if exists
    if (toast.dataset.timeoutId) {
        clearTimeout(parseInt(toast.dataset.timeoutId));
    }

    toast.classList.remove('animate-toastIn', 'animate-toastPulse');
    toast.classList.add('animate-toastOut');

    setTimeout(() => {
        if (toast.parentElement) {
            toast.remove();
        }
    }, 220);
}

// Clear all toasts
export function clearAllToasts() {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toasts = container.querySelectorAll('.toast');
    toasts.forEach(toast => dismissToast(toast));
}
