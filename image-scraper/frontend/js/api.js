/* =============================================
   API.JS - Frontend adapter for Node /scrape backend
   ============================================= */

import { state, MAX_CONCURRENT } from './state.js';

const LOCAL_JOBS_KEY = 'node_scraper_jobs_v2';
const locallyDeletedJobIds = new Set();
const API_BASE = (() => {
    const explicit = String(window.__SCRAPER_API_BASE__ || '').trim();
    if (explicit) return explicit.replace(/\/+$/, '');
    if (window.location.protocol === 'file:') return 'http://localhost:3001';
    if (['localhost', '127.0.0.1'].includes(window.location.hostname) && window.location.port !== '3001') {
        return 'http://localhost:3001';
    }
    return '';
})();

function storageGetJobs() {
    try {
        const raw = localStorage.getItem(LOCAL_JOBS_KEY);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
        console.warn('Failed to load local jobs:', error);
        return [];
    }
}

function storageSetJobs(jobs) {
    try {
        localStorage.setItem(LOCAL_JOBS_KEY, JSON.stringify(jobs));
    } catch (error) {
        console.warn('Failed to save local jobs:', error);
    }
}

function normalizeId(id) {
    if (id == null) return '';
    return String(id);
}

function wasRemovedLocally(jobId) {
    const id = normalizeId(jobId);
    return locallyDeletedJobIds.has(id) || !getJob(id);
}

function upsertJob(job) {
    const normalized = normalizeStoredJob(job);
    const jobs = storageGetJobs();
    const index = jobs.findIndex((j) => normalizeId(j.id) === normalizeId(normalized.id));
    if (index >= 0) jobs[index] = normalized;
    else jobs.unshift(normalized);
    storageSetJobs(jobs);
    return normalized;
}

function removeJob(jobId) {
    const id = normalizeId(jobId);
    storageSetJobs(storageGetJobs().filter((job) => normalizeId(job.id) !== id));
}

function getJob(jobId) {
    const id = normalizeId(jobId);
    return storageGetJobs().find((job) => normalizeId(job.id) === id) || null;
}

function createJobId() {
    return `${Date.now()}${Math.floor(Math.random() * 1000000)}`;
}

function normalizeUrl(url) {
    if (url == null) return '';
    if (typeof url === 'object') return '';
    const value = String(url).trim();
    if (!value) return '';
    if (/^\[object\s+\w+\]$/i.test(value)) return '';
    if (value === 'undefined' || value === 'null') return '';
    try {
        return new URL(value, window.location.origin).href;
    } catch {
        return value;
    }
}

function toImageUrl(entry, jobId = '') {
    if (!entry) return '';

    if (typeof entry === 'string') {
        return normalizeUrl(entry);
    }

    if (typeof entry !== 'object') return '';

    // Prefer the local endpoint for converted images so the gallery can render
    // consistent PNG output without relying on third-party hotlink behavior.
    const imageId = normalizeId(entry.id);
    const isConverted = entry.converted === true || entry.converted === 1 || String(entry.converted).toLowerCase() === 'true';
    if (jobId && imageId && isConverted) {
        const endpoint = `${API_BASE}/jobs/${encodeURIComponent(jobId)}/images/${encodeURIComponent(imageId)}`;
        const fileName = String(entry.file_name || '').trim();
        return normalizeUrl(fileName ? `${endpoint}?download_name=${encodeURIComponent(fileName)}` : endpoint);
    }

    return normalizeUrl(
        entry.original_url ||
        entry.url ||
        entry.src ||
        entry.image ||
        entry.href ||
        ''
    );
}

function toImageRecord(entry, jobId = '') {
    const src = toImageUrl(entry, jobId);
    if (!src) return null;

    if (typeof entry === 'string') {
        return { id: '', src, original_url: src, file_name: '' };
    }

    return {
        id: normalizeId(entry?.id),
        src,
        original_url: normalizeUrl(entry?.original_url || entry?.url || src),
        file_name: String(entry?.file_name || '').trim(),
        product_name: String(entry?.product_name || '').trim(),
        product_index: Number.isFinite(Number(entry?.product_index)) ? Number(entry.product_index) : null
    };
}

function normalizeProduct(product, jobId = '') {
    const images = Array.isArray(product?.images)
        ? product.images.map((img) => toImageUrl(img, jobId)).filter(Boolean)
        : [];

    const sourceImages = Array.isArray(product?.source_images)
        ? product.source_images.map((img) => toImageUrl(img, jobId)).filter(Boolean)
        : [];

    return {
        name: String(product?.name || product?.title || '').trim(),
        price: String(product?.price || '').trim(),
        product_url: normalizeUrl(product?.product_url || product?.url || ''),
        img: normalizeUrl(product?.img || ''),
        images: Array.from(new Set(images)),
        source_images: Array.from(new Set(sourceImages))
    };
}

function flattenImages(products) {
    const imageSet = new Set();

    for (const product of products) {
        const list = Array.isArray(product?.images) && product.images.length
            ? product.images
            : (product?.img ? [product.img] : []);

        for (const src of list) {
            const url = normalizeUrl(src);
            if (url) imageSet.add(url);
        }
    }

    return Array.from(imageSet);
}

function inferModel(url, products) {
    try {
        const pathName = new URL(url).pathname;
        const slug = pathName.split('/').filter(Boolean).pop() || 'Category';
        const tokens = slug.replace(/\.[a-z0-9]+$/i, '').split(/[-_]+/).filter(Boolean);
        if (!tokens.length) return 'Scrape Result';

        return tokens
            .map((token) => {
                if (/^(lg|htc|zte|nokia|iphone|ipad)$/i.test(token)) return token.toUpperCase();
                if (/^thinq$/i.test(token)) return 'ThinQ';
                if (/^[a-z]*\d+[a-z0-9]*$/i.test(token)) return token.toUpperCase();
                return token.charAt(0).toUpperCase() + token.slice(1).toLowerCase();
            })
            .join(' ');
    } catch {
        return 'Scrape Result';
    }
}

function normalizeFolderName(value) {
    return String(value || '')
        .replace(/[\r\n\t]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 120);
}

async function requestJSON(url, options = {}, timeoutMs = 180000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                ...(options.headers || {})
            },
            signal: controller.signal
        });

        let payload = null;
        try {
            payload = await response.json();
        } catch {
            payload = null;
        }

        if (!response.ok) {
            const message = payload?.error || payload?.detail || `Request failed (${response.status})`;
            throw new Error(message);
        }

        return payload;
    } catch (error) {
        if (error?.name === 'AbortError') {
            throw new Error('Request timed out. Please try again.');
        }
        throw error;
    } finally {
        clearTimeout(timer);
    }
}

function normalizeStoredJob(job) {
    const id = normalizeId(job?.id);
    const products = Array.isArray(job?.products) ? job.products.map((product) => normalizeProduct(product, id)) : [];

    const status = String(job?.status || 'queued');
    const totalItems = Number.isFinite(Number(job?.total_items))
        ? Number(job.total_items)
        : (status === 'completed' ? products.length : 0);

    const processedItems = Number.isFinite(Number(job?.processed_items))
        ? Number(job.processed_items)
        : (status === 'completed' ? products.length : 0);

    const imageCount = Number.isFinite(Number(job?.images))
        ? Number(job.images)
        : flattenImages(products).length;

    return {
        id,
        url: String(job?.url || '').trim(),
        status,
        folder_name: normalizeFolderName(job?.folder_name || ''),
        download_folder: normalizeFolderName(job?.download_folder || ''),
        title_filter: String(job?.title_filter || ''),
        model: String(job?.model || job?.folder_name || inferModel(job?.url || '', products)),
        images: Math.max(0, imageCount),
        total_items: Math.max(0, totalItems),
        processed_items: Math.max(0, processedItems),
        error: job?.error || null,
        products,
        created_at: job?.created_at || new Date().toISOString(),
        updated_at: job?.updated_at || new Date().toISOString()
    };
}

function toUiJob(job) {
    const normalized = normalizeStoredJob(job);
    return {
        id: normalized.id,
        url: normalized.url,
        status: normalized.status,
        model: normalized.model,
        folder_name: normalized.folder_name,
        download_folder: normalized.download_folder,
        title_filter: normalized.title_filter,
        images: normalized.images,
        total_items: normalized.total_items,
        processed_items: normalized.processed_items,
        error: normalized.error
    };
}

function mergeServerJobs(serverJobs) {
    const existing = storageGetJobs();
    const existingById = new Map(existing.map((job) => [normalizeId(job.id), normalizeStoredJob(job)]));

    const merged = serverJobs
        .filter((serverJob) => !locallyDeletedJobIds.has(normalizeId(serverJob?.id)))
        .map((serverJob) => {
        const id = normalizeId(serverJob?.id);
        const current = existingById.get(id) || null;

        const nextRecord = normalizeStoredJob({
            ...current,
            ...serverJob,
            id,
            products: Array.isArray(serverJob?.products)
                ? serverJob.products
                : (current?.products || [])
        });

        existingById.delete(id);
        return nextRecord;
    });

    merged.sort((a, b) => {
        const aTime = new Date(a.updated_at || a.created_at || 0).getTime();
        const bTime = new Date(b.updated_at || b.created_at || 0).getTime();
        return bTime - aTime;
    });

    storageSetJobs(merged);
    return merged;
}

export function applyJobUpdateFromServer(update) {
    if (!update || update.id == null) return null;

    const id = normalizeId(update.id);
    if (locallyDeletedJobIds.has(id)) {
        removeJob(id);
        return null;
    }
    const current = getJob(id);

    const merged = normalizeStoredJob({
        ...current,
        ...update,
        id,
        products: Array.isArray(update.products)
            ? update.products
            : (current?.products || [])
    });

    upsertJob(merged);
    return toUiJob(merged);
}

export async function fetchJobs() {
    try {
        const payload = await requestJSON(`${API_BASE}/jobs`, {}, 30000);
        if (payload?.success && Array.isArray(payload.jobs)) {
            return mergeServerJobs(payload.jobs).map(toUiJob).filter(Boolean);
        }
    } catch (error) {
        console.warn('Remote jobs unavailable, using local cache:', error.message);
    }

    return storageGetJobs().map(toUiJob).filter(Boolean);
}

export async function startScrapeAPI(url, options = {}) {
    const cleanUrl = String(url || '').trim();
    if (!cleanUrl) throw new Error('URL is required');
    const titleFilter = String(options.titleFilter || '').trim();
    const folderName = normalizeFolderName(options.folderName || '');

    const jobId = createJobId();

    const runningJob = upsertJob({
        id: jobId,
        url: cleanUrl,
        status: 'running',
        folder_name: folderName,
        download_folder: folderName,
        model: folderName || inferModel(cleanUrl, []),
        images: 0,
        total_items: 0,
        processed_items: 0,
        products: [],
        error: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
    });

    try {
        const params = new URLSearchParams({
            url: cleanUrl,
            job_id: jobId
        });
        if (titleFilter) params.set('title_filter', titleFilter);
        if (folderName) params.set('folder_name', folderName);
        const endpoint = `${API_BASE}/scrape?${params.toString()}`;
        const payload = await requestJSON(endpoint, { method: 'POST' }, 60000);

        if (!payload?.success) {
            throw new Error(payload?.error || 'Scrape failed');
        }

        const rawProducts = Array.isArray(payload.products)
            ? payload.products
            : (Array.isArray(payload.data) ? payload.data : []);

        const products = rawProducts.map(normalizeProduct);
        const acceptedStatus = ['queued', 'running'].includes(String(payload.status || '').toLowerCase());

        if (wasRemovedLocally(jobId)) {
            return { success: false, canceled: true };
        }

        if (acceptedStatus && products.length === 0) {
            upsertJob({
                ...runningJob,
                status: payload.status || 'queued',
                folder_name: payload.folder_name || folderName,
                download_folder: payload.download_folder || payload.folder_name || folderName,
                model: payload.folder_name || folderName || inferModel(cleanUrl, []),
                products: [],
                images: 0,
                total_items: 0,
                processed_items: 0,
                updated_at: new Date().toISOString(),
                error: null
            });

            return {
                success: true,
                queued: true,
                job_id: jobId,
                folder_name: payload.folder_name || folderName,
                download_folder: payload.download_folder || payload.folder_name || folderName,
                products: []
            };
        }

        upsertJob({
            ...runningJob,
            status: 'completed',
            folder_name: payload.folder_name || folderName,
            download_folder: payload.download_folder || payload.folder_name || folderName,
            model: payload.folder_name || folderName || inferModel(cleanUrl, products),
            products,
            images: flattenImages(products).length,
            total_items: products.length,
            processed_items: products.length,
            completed_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            error: null
        });

        return {
            success: true,
            job_id: jobId,
            folder_name: payload.folder_name || folderName,
            download_folder: payload.download_folder || payload.folder_name || folderName,
            products
        };
    } catch (error) {
        if (wasRemovedLocally(jobId)) {
            return { success: false, canceled: true };
        }

        upsertJob({
            ...runningJob,
            status: 'failed',
            error: error.message,
            updated_at: new Date().toISOString()
        });
        throw error;
    }
}

export async function startModelScrapeAPI() {
    throw new Error('Model scrape is not available on this backend. Use a category URL.');
}

export async function deleteJobAPI(jobId) {
    const id = normalizeId(jobId);
    await requestJSON(`${API_BASE}/jobs/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        headers: { 'X-Confirm-Destructive': 'permanently-delete' }
    }, 30000);
    locallyDeletedJobIds.add(id);
    removeJob(id);
    return { success: true };
}

export async function stopJobAPI(jobId) {
    const id = normalizeId(jobId);

    try {
        await requestJSON(`${API_BASE}/jobs/${encodeURIComponent(id)}/stop`, { method: 'POST' }, 30000);
    } catch (error) {
        console.warn('Failed to stop remote job:', error.message);
    }

    const current = getJob(id);
    if (current) {
        upsertJob({ ...current, status: 'failed', error: 'Stopped by user', updated_at: new Date().toISOString() });
    }

    return { success: true };
}

export async function pauseJobAPI(jobId) {
    const id = normalizeId(jobId);
    const payload = await requestJSON(`${API_BASE}/jobs/${encodeURIComponent(id)}/pause`, { method: 'POST' }, 30000);
    if (!payload?.success) {
        throw new Error(payload?.error || 'Pause failed');
    }

    const current = getJob(id);
    if (current) {
        upsertJob({ ...current, status: 'paused', updated_at: new Date().toISOString() });
    }

    return payload;
}

export async function resumeJobAPI(jobId) {
    const id = normalizeId(jobId);
    const payload = await requestJSON(`${API_BASE}/jobs/${encodeURIComponent(id)}/resume`, { method: 'POST' }, 30000);
    if (!payload?.success) {
        throw new Error(payload?.error || 'Resume failed');
    }

    const current = getJob(id);
    if (current) {
        upsertJob({ ...current, status: payload.status || 'queued', updated_at: new Date().toISOString() });
    }

    return payload;
}

export async function resetJobsAPI() {
    await requestJSON(`${API_BASE}/jobs/reset`, {
        method: 'POST',
        headers: { 'X-Confirm-Destructive': 'permanently-delete' }
    }, 60000);
    locallyDeletedJobIds.clear();
    storageSetJobs([]);
    return { success: true };
}

export async function fetchImagesAPI(jobId) {
    const records = await fetchImageRecordsAPI(jobId);
    if (records.length) {
        return records.map((record) => record.src);
    }

    return [];
}

export async function fetchImageRecordsAPI(jobId) {
    const id = normalizeId(jobId);
    let job = null;

    try {
        const payload = await requestJSON(`${API_BASE}/jobs/${encodeURIComponent(id)}/images`, {}, 60000);
        if (payload?.success && Array.isArray(payload.images)) {
            const seen = new Set();
            const records = [];
            for (const img of payload.images) {
                const record = toImageRecord(img, id);
                if (!record || seen.has(record.src)) continue;
                seen.add(record.src);
                records.push(record);
            }
            return records;
        }
    } catch (error) {
        console.warn('Could not fetch image list endpoint, falling back to full job payload:', error.message);
    }

    // Always try to refresh the selected job with full product payload first.
    // This prevents stale local cache from showing only a subset of images.
    try {
        const payload = await requestJSON(`${API_BASE}/jobs/${encodeURIComponent(id)}?full=1`, {}, 60000);
        if (payload?.success && payload.job) {
            applyJobUpdateFromServer(payload.job);
            job = getJob(id);
        }
    } catch (error) {
        console.warn('Could not fetch full job payload, using local cache:', error.message);
    }

    if (!job) {
        job = getJob(id);
    }

    if (!job || !Array.isArray(job.products)) return [];
    return flattenImages(job.products).map((src) => ({ id: '', src, original_url: src, file_name: '' }));
}

export async function deleteImageAPI(jobId, imageId) {
    const id = normalizeId(jobId);
    const imgId = normalizeId(imageId);
    if (!id || !imgId) {
        throw new Error('Image id is missing');
    }

    const payload = await requestJSON(
        `${API_BASE}/jobs/${encodeURIComponent(id)}/images/${encodeURIComponent(imgId)}`,
        {
            method: 'DELETE',
            headers: { 'X-Confirm-Destructive': 'permanently-delete' }
        },
        30000
    );

    if (!payload?.success) {
        throw new Error(payload?.error || 'Image delete failed');
    }

    return payload;
}

export async function pauseAllJobsAPI() {
    try {
        const payload = await requestJSON(`${API_BASE}/admin/api/pause-all`, { method: 'POST' }, 30000);
        if (payload?.success) {
            await fetchJobs();
            return payload;
        }
    } catch (error) {
        console.warn('Failed to pause jobs on backend, applying local fallback:', error.message);
    }

    const jobs = storageGetJobs().map((job) =>
        job.status === 'running' ? { ...job, status: 'paused', updated_at: new Date().toISOString() } : job
    );
    storageSetJobs(jobs);
    return { success: true, paused_count: jobs.filter((job) => job.status === 'paused').length };
}

export async function resumeAllJobsAPI() {
    try {
        const payload = await requestJSON(`${API_BASE}/admin/api/resume-all`, { method: 'POST' }, 30000);
        if (payload?.success) {
            await fetchJobs();
            return payload;
        }
    } catch (error) {
        console.warn('Failed to resume jobs on backend, applying local fallback:', error.message);
    }

    const jobs = storageGetJobs().map((job) =>
        job.status === 'paused' ? { ...job, status: 'running', updated_at: new Date().toISOString() } : job
    );
    storageSetJobs(jobs);
    return { success: true, resumed_count: jobs.filter((job) => job.status === 'running').length };
}

export function canStartNewJob() {
    const running = state.allJobs.filter((j) => j.status === 'running').length;
    return running < MAX_CONCURRENT;
}
