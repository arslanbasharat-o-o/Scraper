// server.js
const fs = require('fs');
const fsp = require('fs/promises');
const path = require('path');
const Module = require('module');

// This project lives in a folder named "node_modules", which breaks default Node resolution.
// Inject the nested dependency directory into NODE_PATH so plain "node server.js" works.
const localNodeModulesPath = path.join(__dirname, 'node_modules');
const nodePathEntries = (process.env.NODE_PATH || '').split(path.delimiter).filter(Boolean);
if (!nodePathEntries.includes(localNodeModulesPath)) {
  process.env.NODE_PATH = [localNodeModulesPath, ...nodePathEntries].join(path.delimiter);
  Module._initPaths();
}

const express = require('express');
const { Builder, By, until } = require('selenium-webdriver');
const chrome = require('selenium-webdriver/chrome');
const archiver = require('archiver');
const { execFile } = require('child_process');
const { promisify } = require('util');
const execFileAsync = promisify(execFile);

const app = express();
const PORT = Number.parseInt(process.env.PORT || '', 10) || 3001;

function envInt(name, fallback, min = 0, max = Number.MAX_SAFE_INTEGER) {
  const raw = process.env[name];
  const parsed = Number.parseInt(raw || '', 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, parsed));
}

const NAVIGATION_TIMEOUT_MS = envInt('NAVIGATION_TIMEOUT_MS', 40000, 5000, 180000);
const PRODUCT_DELAY_MIN_MS = envInt('PRODUCT_DELAY_MIN_MS', 50, 0, 5000);
const PRODUCT_DELAY_MAX_MS = Math.max(
  PRODUCT_DELAY_MIN_MS,
  envInt('PRODUCT_DELAY_MAX_MS', 120, PRODUCT_DELAY_MIN_MS, 10000)
);
const SELECTOR_TIMEOUT_MS = envInt('SELECTOR_TIMEOUT_MS', 15000, 3000, 120000);
const CHALLENGE_WAIT_MS = envInt('CHALLENGE_WAIT_MS', 25000, 5000, 180000);
const LOG_HISTORY_LIMIT = 200; // Reduced from 500 for lower memory usage
const SSE_HEARTBEAT_MS = 35000; // Reduced heartbeat frequency for less network traffic
const IMAGE_HTTP_TIMEOUT_MS = envInt('IMAGE_HTTP_TIMEOUT_MS', 20000, 3000, 120000);
const IMAGE_CONVERT_TIMEOUT_MS = envInt('IMAGE_CONVERT_TIMEOUT_MS', 25000, 3000, 120000);
const IMAGE_SELECTOR_TIMEOUT_MS = envInt('IMAGE_SELECTOR_TIMEOUT_MS', 8000, 2000, 60000);
const MAX_ACTIVE_SCRAPES = envInt('MAX_ACTIVE_SCRAPES', 3, 1, 10);
const MAX_RETRIES = envInt('IMAGE_EXTRACT_RETRIES', 0, 0, 5); // Single retry only
const EMPTY_RESULT_RETRIES = envInt('IMAGE_EMPTY_RETRIES', 0, 0, 3);
const PRODUCTS_PER_BROWSER = envInt('PRODUCTS_PER_BROWSER', 8, 4, 100); // Lower memory footprint
const DRIVER_RECOVERY_RETRIES = 1;
const IMAGE_DOWNLOAD_CONCURRENCY = envInt('IMAGE_DOWNLOAD_CONCURRENCY', 3, 1, 10); // Reduced for stability
const JOB_MAX_RUNTIME_MS = envInt('JOB_MAX_RUNTIME_MS', 45 * 60 * 1000, 5 * 60 * 1000, 24 * 60 * 60 * 1000);
const MEMORY_WARN_HEAP_PERCENT = envInt('MEMORY_WARN_HEAP_PERCENT', 90, 50, 99);
const MEMORY_WARN_MIN_HEAP_TOTAL_MB = envInt('MEMORY_WARN_MIN_HEAP_TOTAL_MB', 256, 16, 8192);
const MEMORY_WARN_MIN_HEAP_USED_MB = envInt('MEMORY_WARN_MIN_HEAP_USED_MB', 192, 16, 8192);
const MEMORY_WARN_COOLDOWN_MS = envInt('MEMORY_WARN_COOLDOWN_MS', 30 * 60 * 1000, 60 * 1000, 24 * 60 * 60 * 1000);

const DOWNLOAD_ROOT = path.join(__dirname, 'downloads');
const JOB_DB_PATH = path.join(DOWNLOAD_ROOT, 'jobs-db.json');
const PERSIST_JOBS_ENABLED = String(process.env.PERSIST_JOBS || 'false').toLowerCase() === 'true';
const PERSIST_INTERVAL_MS = 5000; // Only persist every 5 seconds max
const PYTHON_CANDIDATES = (() => {
  const candidates = [];
  const seen = new Set();
  const add = (command, argsPrefix = []) => {
    const cmd = String(command || '').trim();
    if (!cmd) return;
    const key = `${cmd}::${argsPrefix.join(' ')}`;
    if (seen.has(key)) return;
    seen.add(key);
    candidates.push({ command: cmd, argsPrefix });
  };

  // Explicit override for constrained environments.
  add(process.env.PYTHON_BIN || '');

  if (process.platform === 'win32') {
    add('python');
    add('py', ['-3']);
    add('py');
  } else {
    add('python3');
    add('python');
    // Common absolute paths for macOS/Linux when PATH is minimal.
    add('/usr/bin/python3');
    add('/usr/local/bin/python3');
    add('/opt/homebrew/bin/python3');
    add('/Library/Frameworks/Python.framework/Versions/Current/bin/python3');
    add('/Library/Frameworks/Python.framework/Versions/3.14/bin/python3');
    add('/Library/Frameworks/Python.framework/Versions/3.13/bin/python3');
    add('/Library/Frameworks/Python.framework/Versions/3.12/bin/python3');
    add('/Library/Frameworks/Python.framework/Versions/3.11/bin/python3');
  }

  return candidates;
})();
const PYTHON_CONVERT_SCRIPT_PATH = path.join(__dirname, 'convert_image.py');
const PYTHON_ZIP_SCRIPT_PATH = path.join(__dirname, 'create_zip.py');

const eventClients = new Set();
const logClients = new Set();
const jobs = new Map();
const stopRequestedJobIds = new Set();
const deletedJobIds = new Set();
const logHistory = [];
const scrapeQueue = [];
let activeScrapes = 0;
let lastPersistTime = 0;
let lastMemoryWarningAt = 0;
let cachedPythonRuntime; // undefined=not checked, null=unavailable, object=resolved
let pythonMissingLogged = false;
let pythonConvertScriptMissingLogged = false;

async function resolvePythonRuntime(jobId = null) {
  if (cachedPythonRuntime !== undefined) return cachedPythonRuntime;

  for (const candidate of PYTHON_CANDIDATES) {
    // Skip missing absolute paths quickly.
    if (path.isAbsolute(candidate.command) && !fs.existsSync(candidate.command)) {
      continue;
    }
    try {
      await execFileAsync(
        candidate.command,
        [...candidate.argsPrefix, '--version'],
        { timeout: 5000, maxBuffer: 1024 * 1024 }
      );
      cachedPythonRuntime = candidate;
      return cachedPythonRuntime;
    } catch {
      // try next candidate
    }
  }

  cachedPythonRuntime = null;
  if (!pythonMissingLogged) {
    const tried = PYTHON_CANDIDATES.map((item) => item.command).join(', ');
    writeLog(
      'warning',
      `No Python runtime found (${tried}). Image conversion disabled; original image URLs will be stored.`,
      'image',
      jobId
    );
    pythonMissingLogged = true;
  }
  return null;
}

app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET,POST,DELETE,OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type');
  
  // Set request timeout
  req.setTimeout(60000); // 60 second timeout
  
  // Add request size limits
  if (req.method === 'POST') {
    req.on('data', (chunk) => {
      if (req.headers['content-length'] > 1024 * 100) { // 100KB limit
        res.status(413).json({ success: false, error: 'Payload too large' });
        req.connection.destroy();
      }
    });
  }
  
  if (req.method === 'OPTIONS') {
    return res.sendStatus(204);
  }
  next();
});

app.use(express.static(path.join(__dirname, 'frontend')));
app.use('/downloads', express.static(DOWNLOAD_ROOT));

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'frontend/index.html'));
});

function nowIso() {
  return new Date().toISOString();
}

function createJobId() {
  return `${Date.now()}${Math.floor(Math.random() * 1000000)}`;
}

function monitorMemory() {
  if (global.gc) {
    global.gc();
  }
  
  const memUsage = process.memoryUsage();
  const heapUsedMB = Math.round(memUsage.heapUsed / 1024 / 1024);
  const heapTotalMB = Math.round(memUsage.heapTotal / 1024 / 1024);
  const externalMB = Math.round(memUsage.external / 1024 / 1024);
  
  const heapUsagePercent = heapTotalMB > 0 ? Math.round((heapUsedMB / heapTotalMB) * 100) : 0;

  // Avoid false positives on tiny heaps (e.g. 14MB/15MB) and rate-limit warnings.
  const largeEnoughToAlert =
    heapTotalMB >= MEMORY_WARN_MIN_HEAP_TOTAL_MB ||
    heapUsedMB >= MEMORY_WARN_MIN_HEAP_USED_MB;
  const shouldWarn = largeEnoughToAlert && heapUsagePercent >= MEMORY_WARN_HEAP_PERCENT;

  if (shouldWarn) {
    const now = Date.now();
    if (now - lastMemoryWarningAt >= MEMORY_WARN_COOLDOWN_MS) {
      lastMemoryWarningAt = now;
      writeLog('warning', `High memory usage: ${heapUsedMB}MB / ${heapTotalMB}MB (${heapUsagePercent}%)`, 'memory');
    }
  }
  
  return { heapUsedMB, heapTotalMB, externalMB, heapUsagePercent };
}

function sendSse(res, event, payload) {
  res.write(`event: ${event}\n`);
  res.write(`data: ${JSON.stringify(payload)}\n\n`);
}

function broadcast(clients, event, payload) {
  for (const client of clients) {
    try {
      sendSse(client, event, payload);
    } catch (err) {
      // ignore broken connections; close handler removes stale clients
    }
  }
}

function writeLog(level, message, source = 'server', jobId = null) {
  const entry = {
    time: nowIso(),
    level,
    source,
    message,
    job_id: jobId ? String(jobId) : null
  };

  logHistory.push(entry);
  if (logHistory.length > LOG_HISTORY_LIMIT) {
    logHistory.splice(0, logHistory.length - LOG_HISTORY_LIMIT);
  }

  console.log(`[${entry.time}] [${level.toUpperCase()}] [${source}] ${message}`);
  broadcast(logClients, 'log', entry);

  return entry;
}

function setupSseHeaders(res) {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache, no-transform');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders?.();
}

function inferModelFromUrl(url) {
  if (!url) return 'Scrape Job';
  try {
    const slug = new URL(url).pathname.split('/').filter(Boolean).pop() || 'category';
    const tokens = slug.replace(/\.[a-z0-9]+$/i, '').split(/[-_]+/).filter(Boolean);
    if (!tokens.length) return 'Scrape Job';

    return tokens
      .map((token) => {
        if (/^(lg|htc|zte|nokia|iphone|ipad)$/i.test(token)) return token.toUpperCase();
        if (/^thinq$/i.test(token)) return 'ThinQ';
        if (/^[a-z]*\d+[a-z0-9]*$/i.test(token)) return token.toUpperCase();
        return token.charAt(0).toUpperCase() + token.slice(1).toLowerCase();
      })
      .join(' ');
  } catch {
    return 'Scrape Job';
  }
}

function summarizeJob(job, includeProducts = false) {
  const summary = {
    id: String(job.id),
    url: String(job.url || ''),
    status: String(job.status || 'queued'),
    model: String(job.model || ''),
    images: Number.isFinite(Number(job.images)) ? Number(job.images) : 0,
    total_items: Number.isFinite(Number(job.total_items)) ? Number(job.total_items) : 0,
    processed_items: Number.isFinite(Number(job.processed_items)) ? Number(job.processed_items) : 0,
    error: job.error || null,
    created_at: job.created_at || nowIso(),
    updated_at: job.updated_at || nowIso()
  };

  if (includeProducts) {
    summary.products = Array.isArray(job.products) ? job.products : [];
  }

  return summary;
}

function getOrCreateJob(jobId, url = '') {
  const id = String(jobId);
  if (deletedJobIds.has(id)) return null;
  if (!jobs.has(id)) {
    const created = nowIso();
    jobs.set(id, {
      id,
      url,
      status: 'queued',
      model: inferModelFromUrl(url),
      images: 0,
      total_items: 0,
      processed_items: 0,
      error: null,
      products: [],
      stop_requested: false,
      pause_requested: false,
      created_at: created,
      updated_at: created
    });
  }
  return jobs.get(id);
}

let persistPromise = Promise.resolve();

function schedulePersistJobsDb() {
  // Skip persistence if disabled
  if (!PERSIST_JOBS_ENABLED) return;
  
  // Debounce persistence - only write if 5+ seconds since last write
  const now = Date.now();
  if (now - lastPersistTime < PERSIST_INTERVAL_MS) {
    return;
  }
  lastPersistTime = now;

  persistPromise = persistPromise
    .then(async () => {
      try {
        await fsp.mkdir(DOWNLOAD_ROOT, { recursive: true });
        const allJobs = Array.from(jobs.values())
          .filter(job => job.status === 'completed' || job.status === 'failed') // Only persist terminal states
          .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
          .slice(0, 100) // Keep only last 100 jobs
          .map((job) => summarizeJob(job, true));

        const payload = {
          updated_at: nowIso(),
          jobs: allJobs
        };

        await fsp.writeFile(JOB_DB_PATH, JSON.stringify(payload, null, 2), 'utf8');
      } catch (err) {
        writeLog('error', `Failed to persist jobs DB: ${err.message}`, 'db');
      }
    });
}

async function loadPersistedJobs() {
  try {
    await fsp.mkdir(DOWNLOAD_ROOT, { recursive: true });
    if (!fs.existsSync(JOB_DB_PATH)) return;

    const raw = await fsp.readFile(JOB_DB_PATH, 'utf8');
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed.jobs)) return;

    for (const job of parsed.jobs) {
      if (!job || job.id == null) continue;
      jobs.set(String(job.id), {
        ...job,
        id: String(job.id),
        stop_requested: false,
        pause_requested: false,
        products: Array.isArray(job.products) ? job.products : []
      });
    }

    if (parsed.jobs.length > 0) {
      writeLog('info', `Restored ${parsed.jobs.length} persisted job(s)`, 'startup');
    }
  } catch (err) {
    writeLog('warning', `Could not load persisted jobs: ${err.message}`, 'startup');
  }
}

function emitJobUpdate(jobId) {
  const job = jobs.get(String(jobId));
  if (!job) return;
  broadcast(eventClients, 'job_update', summarizeJob(job, false));
}

function updateJob(jobId, patch = {}, { emit = true, persist = true } = {}) {
  const id = String(jobId);
  if (deletedJobIds.has(id)) return null;

  const job = getOrCreateJob(id, patch.url || '');
  if (!job) return null;
  Object.assign(job, patch);
  job.id = String(job.id || id);
  job.updated_at = nowIso();

  if (!job.model) {
    job.model = inferModelFromUrl(job.url);
  }

  if (emit) {
    emitJobUpdate(job.id);
  }

  if (persist) {
    schedulePersistJobsDb();
  }

  return job;
}

function isActiveJobStatus(status) {
  return ['queued', 'running', 'paused'].includes(String(status || ''));
}

function processNextQueuedScrape() {
  if (activeScrapes >= MAX_ACTIVE_SCRAPES) return;
  const next = scrapeQueue.shift();
  if (typeof next === 'function') {
    next();
  }
}

function executeWithScrapeSlot(jobId, runTask) {
  return new Promise((resolve, reject) => {
    const start = async () => {
      activeScrapes++;
      const id = String(jobId);
      let runtimeTimer = null;
      let didTimeout = false;

      const timeoutPromise = new Promise((_, timeoutReject) => {
        runtimeTimer = setTimeout(() => {
          didTimeout = true;
          stopRequestedJobIds.add(id);
          const liveJob = jobs.get(id);
          if (liveJob) {
            liveJob.stop_requested = true;
            liveJob.pause_requested = false;
          }
          const minutes = Math.round(JOB_MAX_RUNTIME_MS / 60000);
          writeLog('warning', `Job exceeded max runtime (${minutes}m); stopping`, 'scrape', id);
          timeoutReject(new Error(`Job timed out after ${minutes} minutes`));
        }, JOB_MAX_RUNTIME_MS);
      });

      try {
        const currentJob = jobs.get(id);
        if (deletedJobIds.has(id) || stopRequestedJobIds.has(id) || currentJob?.stop_requested) {
          throw new Error('Stopped by user');
        }

        const taskPromise = Promise.resolve().then(() => runTask());
        const result = await Promise.race([taskPromise, timeoutPromise]);
        resolve(result);
      } catch (error) {
        reject(error);
      } finally {
        if (runtimeTimer) {
          clearTimeout(runtimeTimer);
          runtimeTimer = null;
        }
        if (didTimeout) {
          updateJob(id, { status: 'failed', error: `Job timed out after ${Math.round(JOB_MAX_RUNTIME_MS / 60000)} minutes` });
        }
        activeScrapes = Math.max(0, activeScrapes - 1);
        processNextQueuedScrape();
      }
    };

    if (activeScrapes < MAX_ACTIVE_SCRAPES) {
      start();
    } else {
      scrapeQueue.push(start);
      updateJob(jobId, { status: 'queued' });
      writeLog('info', `Scrape queued (position ${scrapeQueue.length})`, 'queue', jobId);
    }
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

async function mapWithConcurrency(items, limit, worker) {
  const safeItems = Array.isArray(items) ? items : [];
  if (!safeItems.length) return [];

  const results = new Array(safeItems.length);
  let nextIndex = 0;

  const runner = async () => {
    while (true) {
      const index = nextIndex++;
      if (index >= safeItems.length) break;
      results[index] = await worker(safeItems[index], index);
    }
  };

  const runnerCount = Math.max(1, Math.min(limit, safeItems.length));
  await Promise.all(Array.from({ length: runnerCount }, () => runner()));
  return results;
}

async function clearDirectoryContents(dirPath) {
  await fsp.mkdir(dirPath, { recursive: true });
  const entries = await fsp.readdir(dirPath, { withFileTypes: true });

  for (const entry of entries) {
    const targetPath = path.join(dirPath, entry.name);
    let removed = false;
    let lastError = null;

    for (let attempt = 0; attempt < 3 && !removed; attempt++) {
      try {
        await fsp.rm(targetPath, {
          recursive: true,
          force: true,
          maxRetries: 2,
          retryDelay: 120
        });
        removed = true;
      } catch (err) {
        lastError = err;
        if (err?.code !== 'EBUSY' || attempt === 2) {
          break;
        }
        await sleep(120 * (attempt + 1));
      }
    }

    if (!removed && lastError && lastError.code !== 'ENOENT') {
      throw lastError;
    }
  }
}

async function directoryHasFiles(dirPath) {
  const entries = await fsp.readdir(dirPath, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name);
    if (entry.isFile()) return true;
    if (entry.isDirectory()) {
      const childHasFiles = await directoryHasFiles(fullPath);
      if (childHasFiles) return true;
    }
  }
  return false;
}

function toAbsoluteUrl(value, baseUrl) {
  if (!value) return '';
  try {
    return new URL(value, baseUrl).href;
  } catch {
    return '';
  }
}

function sanitizeSegment(value, fallback = 'item') {
  const normalized = String(value || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .toLowerCase();

  return normalized || fallback;
}

function extractCatalogImageUrlsFromHtml(html, baseUrl = '') {
  if (!html || typeof html !== 'string') return [];

  const needle = '/catalog/product/image/';
  const separators = new Set(['"', "'", ' ', '\n', '\r', '\t', '<', '>', '(', ')']);
  const found = new Set();

  let index = html.indexOf(needle);
  while (index !== -1) {
    let start = index;
    while (start > 0 && !separators.has(html[start - 1])) {
      start--;
    }

    let end = index + needle.length;
    while (end < html.length && !separators.has(html[end])) {
      end++;
    }

    let candidate = html.slice(start, end).trim();
    if (candidate) {
      candidate = candidate.split('&amp;').join('&');
      const absolute = toAbsoluteUrl(candidate, baseUrl || 'https://www.mobilesentrix.com');
      if (absolute && absolute.includes('/catalog/product/image/')) {
        found.add(absolute);
      }
    }

    index = html.indexOf(needle, index + needle.length);
  }

  return Array.from(found);
}

async function waitForChallengeToClear(driver, timeoutMs = CHALLENGE_WAIT_MS) {
  const startedAt = Date.now();

  while (Date.now() - startedAt < timeoutMs) {
    let title = '';
    try {
      title = (await driver.getTitle()) || '';
    } catch {}

    const lowerTitle = title.toLowerCase();
    const isChallengeTitle =
      lowerTitle.includes('just a moment') ||
      lowerTitle.includes('attention required') ||
      lowerTitle.includes('checking your browser');

    if (!isChallengeTitle) return true;
    await driver.sleep(1000);
  }

  return false;
}

function resolveChromeDriverPath() {
  const binaryName = process.platform === 'win32' ? 'chromedriver.exe' : 'chromedriver';
  const candidates = [
    process.env.CHROMEDRIVER_PATH,
    '/usr/bin/chromedriver',
    (() => {
      try {
        const chromedriver = require('chromedriver');
        return chromedriver?.path || '';
      } catch {
        return '';
      }
    })(),
    path.join(__dirname, '.tmp/chromedriver/chromedriver-mac-x64/chromedriver'),
    path.join(__dirname, '.tmp/chromedriver/chromedriver-mac-arm64/chromedriver'),
    path.join(__dirname, 'chromedriver'),
    path.join(__dirname, 'node_modules/chromedriver/lib/chromedriver', binaryName),
    path.join(__dirname, 'node_modules/.bin', binaryName)
  ].filter(Boolean);

  for (const candidate of candidates) {
    try {
      const resolved = path.resolve(candidate);
      if (fs.existsSync(resolved) && fs.statSync(resolved).isFile()) {
        return resolved;
      }
    } catch {}
  }

  return null;
}

function isDriverSessionError(error) {
  const message = String(error?.message || error || '').toLowerCase();
  return (
    message.includes('invalid session id') ||
    message.includes('session deleted') ||
    message.includes('not connected to devtools') ||
    message.includes('disconnected') ||
    message.includes('no such window')
  );
}

function isSingleProductUrl(url) {
  if (!url || typeof url !== 'string') return false;
  
  try {
    const urlObj = new URL(url);
    const hostname = urlObj.hostname.toLowerCase();
    const pathname = urlObj.pathname.toLowerCase();
    const search = urlObj.search.toLowerCase();
    
    // Explicit single product patterns
    if (pathname.includes('/product/')) return true;
    if (/\/(p|item|sku|product-|view|details|product-detail|pd)\//i.test(pathname)) return true;
    if (/\/(apple|samsung|iphone|galaxy|ipad|airpods|watch)\//i.test(pathname)) return true;
    
    // Product ID parameters
    if (search.includes('product_id=') || search.includes('?id=') || search.includes('?sku=') || search.includes('?item_id=')) {
      return true;
    }
    
    // Single numeric ID in pathname (e.g., /products/12345)
    if (/\/(products?|items?|listings?|offers?|deals?)\/\d+/.test(pathname)) {
      return true;
    }

    // MobileSentrix category trees (e.g. /replacement-parts/.../g-series/...)
    // often end with slug-like segments that can look like product URLs.
    if (hostname.includes('mobilesentrix.') && pathname.includes('/replacement-parts/')) {
      return false;
    }
    if (/(^|\/)[a-z0-9-]+-series(\/|$)/i.test(pathname)) {
      return false;
    }
    
    // Exclude obvious category/collection URLs
    if (/(category|collection|catalog|shop|browse|search|results|list|page)\//i.test(pathname)) {
      return false;
    }
    
    // Check for typical product name patterns (with model/SKU after)
    if (/[a-z0-9]+-[a-z0-9]+-[a-z0-9]+/i.test(pathname) && !search.includes('category')) {
      return true;
    }
    
    return false;
  } catch {
    return false;
  }
}

async function cleanupOldImages(maxAgeHours = 24) {
  try {
    const now = Date.now();
    const maxAgeMs = maxAgeHours * 60 * 60 * 1000;
    let deletedCount = 0;

    // Clean up old images from database (in-memory jobs storage)
    for (const job of jobs.values()) {
      if (!Array.isArray(job.products)) continue;

      for (const product of job.products) {
        if (!Array.isArray(product.images)) continue;

        const beforeCount = product.images.length;
        product.images = product.images.filter((image) => {
          if (!image.created_at) return true; // Keep images without timestamp
          
          const imageAge = now - new Date(image.created_at).getTime();
          if (imageAge > maxAgeMs) {
            deletedCount++;
            writeLog('info', `Deleted old image from database: ${image.id} (age: ${Math.round(imageAge / 3600000)} hours)`, 'cleanup');
            return false; // Remove this image
          }
          return true; // Keep this image
        });

        const afterCount = product.images.length;
        if (beforeCount !== afterCount) {
          schedulePersistJobsDb();
        }
      }
    }

    // Also clean up any remaining old files in filesystem (manifest.json files, etc.)
    if (fs.existsSync(DOWNLOAD_ROOT)) {
      try {
        const entries = await fsp.readdir(DOWNLOAD_ROOT, { withFileTypes: true });
        for (const entry of entries) {
          if (entry.isDirectory()) {
            const dirPath = path.join(DOWNLOAD_ROOT, entry.name);
            try {
              const stats = await fsp.stat(dirPath);
              const dirAge = now - stats.mtimeMs;
              
              if (dirAge > maxAgeMs) {
                await fsp.rm(dirPath, { recursive: true, force: true });
                deletedCount++;
                writeLog('info', `Deleted old job directory: ${entry.name} (age: ${Math.round(dirAge / 3600000)} hours)`, 'cleanup');
              }
            } catch (err) {
              writeLog('warning', `Could not cleanup directory ${entry.name}: ${err.message}`, 'cleanup');
            }
          }
        }
      } catch (err) {
        writeLog('warning', `Error scanning download directory: ${err.message}`, 'cleanup');
      }
    }

    if (deletedCount > 0) {
      writeLog('info', `Cleanup completed: Removed ${deletedCount} old image(s) from database and filesystem`, 'cleanup');
    }
  } catch (err) {
    writeLog('error', `Image cleanup failed: ${err.message}`, 'cleanup');
  }
}

function createChromeOptions(profileDir) {
  const options = new chrome.Options();
  options.setPageLoadStrategy('eager');
  options.excludeSwitches('enable-automation');

  const headlessEnabled = String(process.env.CHROME_HEADLESS || 'true').toLowerCase() !== 'false';
  if (headlessEnabled) {
    options.addArguments('--headless=new');
  }

  if (process.env.CHROME_BIN) {
    options.setChromeBinaryPath(process.env.CHROME_BIN);
  }

  options.addArguments(
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--disable-extensions',
    '--disable-plugins',
    '--disable-default-apps',
    '--disable-preconnect',
    '--disable-component-extensions-with-background-pages',
    '--disable-background-networking',
    '--disable-features=TranslateUI,BlinkGenPropertyTrees',
    '--window-size=1366,768',  // Smaller window to save memory
    '--disable-blink-features=AutomationControlled',
    '--disable-sync',
    '--disable-translate',
    '--disable-client-side-phishing-detection',
    '--mute-audio',
    '--single-process=false',
    '--memory-pressure-off',
    '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36'
  );

  if (profileDir) {
    options.addArguments(`--user-data-dir=${profileDir}`);
  }

  return options;
}

async function createDriverInstance(chromeDriverPath, profileDir) {
  const options = createChromeOptions(profileDir);
  const builder = new Builder().forBrowser('chrome').setChromeOptions(options);
  builder.setChromeService(new chrome.ServiceBuilder(chromeDriverPath));

  const driver = await builder.build();
  await driver.manage().setTimeouts({
    pageLoad: NAVIGATION_TIMEOUT_MS,
    script: NAVIGATION_TIMEOUT_MS
  });

  return driver;
}

async function openProductTab(driver, categoryTabHandle, jobId) {
  try {
    await driver.switchTo().newWindow('tab');
    return await driver.getWindowHandle();
  } catch (tabErr) {
    writeLog('warning', `Could not open product tab, using category tab: ${tabErr.message}`, 'scrape', jobId);
    if (categoryTabHandle) return categoryTabHandle;
    return await driver.getWindowHandle();
  }
}

async function autoScrollUntilStable(driver, maxRounds = 25, waitMs = 1200) {
  let prevCount = 0;
  let stableRounds = 0;

  for (let round = 0; round < maxRounds; round++) {
    await driver.executeScript('window.scrollTo(0, document.body.scrollHeight);');
    await driver.sleep(waitMs);

    let count = 0;
    try {
      count = await driver.executeScript('return document.querySelectorAll("li.item").length;');
    } catch {
      count = 0;
    }

    if (count === prevCount) {
      stableRounds++;
      if (stableRounds >= 5) break;
    } else {
      stableRounds = 0;
      prevCount = count;
    }
  }
}

async function extractCategoryProducts(driver, categoryUrl) {
  const rawProducts = await driver.executeScript(() => {
    const attrs = ['src', 'data-src', 'srcset', 'data-lazy', 'data-original'];
    const extractFirstImage = (val) => {
      if (!val) return '';
      const first = String(val).split(',')[0].trim();
      return first.split(' ')[0].trim();
    };

    // Try primary selector first
    let items = document.querySelectorAll('li.item');
    
    // Fallback selectors if primary doesn't match
    if (!items.length) {
      items = document.querySelectorAll('[data-product-id]');
    }
    if (!items.length) {
      items = document.querySelectorAll('div.product-item');
    }
    if (!items.length) {
      items = document.querySelectorAll('article.product');
    }
    if (!items.length) {
      items = document.querySelectorAll('div.product');
    }

    return Array.from(items).map((item) => {
      const name = (item.querySelector('h2.product-name')?.textContent || item.querySelector('h2')?.textContent || item.querySelector('[data-name]')?.textContent || '').trim();
      const priceNode = item.querySelector('span.regular-price') || item.querySelector('.price') || item.querySelector('[data-price]');
      const price = (priceNode?.textContent || '').trim();

      let img = '';
      const imgEl = item.querySelector('img.small-img') || item.querySelector('img[data-src]') || item.querySelector('img');
      if (imgEl) {
        for (const attr of attrs) {
          const val = imgEl.getAttribute(attr);
          if (val && String(val).trim()) {
            img = extractFirstImage(val);
            if (img) break;
          }
        }
      }

      const productUrl = 
        item.querySelector('a.product-image.figure')?.getAttribute('href') || 
        item.querySelector('a[href*="/product"]')?.getAttribute('href') ||
        item.querySelector('a[data-url]')?.getAttribute('data-url') ||
        '';

      return {
        name,
        price,
        img,
        product_url: productUrl
      };
    });
  });

  return rawProducts.map((product) => ({
    name: String(product.name || '').trim(),
    price: String(product.price || '').trim(),
    product_url: toAbsoluteUrl(product.product_url, categoryUrl),
    img: toAbsoluteUrl(product.img, categoryUrl) || String(product.img || '').trim(),
    images: [],
    source_images: []
  }));
}

async function extractImagesWithDriver(driver, productUrl, productTabHandle, jobId) {
  if (!productUrl) return [];

  const normalizedUrl = toAbsoluteUrl(productUrl, productUrl);
  if (!normalizedUrl) {
    writeLog('error', `Invalid product URL: ${productUrl}`, 'scrape', jobId);
    return [];
  }

  await sleep(randomInt(PRODUCT_DELAY_MIN_MS, PRODUCT_DELAY_MAX_MS));

  const imageSet = new Set();

  try {
    await driver.switchTo().window(productTabHandle);
    try {
      await driver.get(normalizedUrl);
    } catch (navigationErr) {
      if (isDriverSessionError(navigationErr)) {
        throw navigationErr;
      }

      const navMessage = String(navigationErr?.message || '');
      if (/timed out receiving message from renderer|timeout/i.test(navMessage)) {
        writeLog(
          'warning',
          `Product navigation timed out, attempting extraction from partial DOM: ${normalizedUrl}`,
          'scrape',
          jobId
        );
      } else {
        throw navigationErr;
      }
    }

    const challengeCleared = await waitForChallengeToClear(driver, CHALLENGE_WAIT_MS);
    if (!challengeCleared) {
      writeLog('warning', `Challenge page did not clear: ${normalizedUrl}`, 'scrape', jobId);
      return [];
    }

    const collectCandidateUrls = async () =>
      driver.executeScript(async () => {
        const out = [];
        const seen = new Set();

        const push = (value) => {
          if (!value) return;
          const trimmed = String(value).trim();
          // Accept common image formats, reject GIFs and data URIs
          if (trimmed && !seen.has(trimmed) && (trimmed.match(/^https?:\/\/|^\//) && !trimmed.match(/\.(gif|svg)$/i) && !trimmed.startsWith('data:'))) {
            out.push(trimmed);
            seen.add(trimmed);
          }
        };

        // Trigger lazy loading by scrolling
        window.scrollTo(0, 0);
        await new Promise(r => setTimeout(r, 800));
        
        let scrollHeight = document.documentElement.scrollHeight;
        for (let i = 0; i < 5; i++) {
          window.scrollBy(0, scrollHeight / 5);
          await new Promise(r => setTimeout(r, 300));
        }
        window.scrollTo(0, 0);
        await new Promise(r => setTimeout(r, 500));

        // 1. MagicZoom/MagicScroll (internal catalog system)
        for (const selector of ['div.MagicScroll a.mz-thumb[href]', 'div.MagicToolboxContainer a.MagicZoom[href]', 'a.MagicZoom[href]', 'a[id^="MagicZoomPlusImage"][href]', 'a[href*="/catalog/product/image/"]']) {
          for (const node of document.querySelectorAll(selector)) {
            push(node.getAttribute('href') || node.href);
          }
        }

        // 2. Generic product image galleries (Slick, Swiper, etc.)
        if (out.length < 20) {
          for (const selector of ['.gallery img[src]', '.product-gallery img[src]', '.product-images img[src]', '.product-image-container img[src]', '.images img[src]', '.photos img[src]', '.fotorama__img', '.slick-slide img', '.swiper-slide img', '.product-photo img', '.product-pic img']) {
            for (const node of document.querySelectorAll(selector)) {
              push(node.src || node.getAttribute('data-src') || node.getAttribute('data-zoom-image') || node.getAttribute('data-original'));
            }
          }
        }

        // 3. Picture elements and srcset images
        if (out.length < 20) {
          for (const picture of document.querySelectorAll('picture')) {
            for (const source of picture.querySelectorAll('source[srcset]')) {
              const srcset = source.getAttribute('srcset');
              if (srcset) {
                push(srcset.split(',')[0]?.trim()?.split(' ')[0]);
              }
            }
            const img = picture.querySelector('img');
            if (img) {
              push(img.src);
              push(img.getAttribute('data-src'));
              push(img.getAttribute('data-zoom-image'));
            }
          }
        }

        // 4. All img tags with all possible attributes
        if (out.length < 30) {
          for (const img of document.querySelectorAll('img:not([src*="logo"]):not([src*="icon"]):not([src*="svg"])')) {
            push(img.src);
            push(img.getAttribute('data-src'));
            push(img.getAttribute('data-zoom-image'));
            push(img.getAttribute('data-image'));
            push(img.getAttribute('data-original'));
            push(img.getAttribute('data-large'));
            push(img.getAttribute('data-original-src'));
            push(img.getAttribute('data-img-url'));
            push(img.getAttribute('data-full'));
            push(img.getAttribute('x-src'));
            // Check srcset
            const srcset = img.getAttribute('srcset');
            if (srcset) {
              push(srcset.split(',')[0]?.trim()?.split(' ')[0]);
            }
          }
        }

        // 5. Background images on divs/sections
        if (out.length < 20) {
          for (const el of document.querySelectorAll('[style*="background-image"], [class*="gallery"], [class*="image"], [class*="photo"], [class*="product"]')) {
            const style = window.getComputedStyle(el);
            const bgImg = style.backgroundImage;
            if (bgImg && bgImg.includes('url')) {
              const match = bgImg.match(/url\(['"]?([^'")]+)['"]?\)/);
              if (match) push(match[1]);
            }
          }
        }

        // 6. Structured data (JSON-LD, microdata)
        if (out.length < 20) {
          const collectImageValue = (value) => {
            if (!value) return;
            if (typeof value === 'string') {
              push(value);
              return;
            }
            if (Array.isArray(value)) {
              for (const item of value) {
                collectImageValue(item);
              }
              return;
            }
            if (typeof value === 'object') {
              push(value.url);
              push(value.contentUrl);
              push(value.image);
              if (value.images) {
                collectImageValue(value.images);
              }
            }
          };

          for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
            try {
              const payload = JSON.parse(script.textContent || '{}');
              const nodes = Array.isArray(payload) ? payload : [payload];
              for (const node of nodes) {
                if (node && typeof node === 'object') {
                  collectImageValue(node.image);
                  if (node.offers) collectImageValue(node.offers);
                }
              }
            } catch {}
          }

          // Schema.org microdata
          for (const img of document.querySelectorAll('[itemtype*="schema.org/Product"] img[src], [itemtype*="schema.org/Product"] [itemprop="image"]')) {
            push(img.src || img.getAttribute('content') || img.getAttribute('data-src'));
          }
        }

        // 7. Meta tags and link elements
        push(document.querySelector('meta[property="og:image"]')?.getAttribute('content'));
        push(document.querySelector('meta[name="twitter:image"]')?.getAttribute('content'));
        push(document.querySelector('meta[name="thumbnail"]')?.getAttribute('content'));
        push(document.querySelector('meta[property="og:image:url"]')?.getAttribute('content'));
        push(document.querySelector('link[rel="image_src"]')?.getAttribute('href'));
        push(document.querySelector('link[rel="apple-touch-icon"]')?.getAttribute('href'));

        // 8. Data attributes on parent containers
        if (out.length < 30) {
          for (const el of document.querySelectorAll('[data-image], [data-images], [data-src], [data-zoom-image], [data-product-img], [data-img], [data-image-url]')) {
            push(el.getAttribute('data-image'));
            push(el.getAttribute('data-images'));
            push(el.getAttribute('data-src'));
            push(el.getAttribute('data-zoom-image'));
            push(el.getAttribute('data-product-img'));
            push(el.getAttribute('data-img'));
            push(el.getAttribute('data-image-url'));
          }
        }

        // 9. Video thumbnails (in case of video product images)
        for (const video of document.querySelectorAll('video, [data-video], [data-video-poster]')) {
          push(video.getAttribute('poster'));
          push(video.getAttribute('data-video-poster'));
          push(video.getAttribute('data-thumbnail'));
        }

        // 10. Links to images (common on some sites)
        if (out.length < 30) {
          for (const a of document.querySelectorAll('a[href*=".jpg"], a[href*=".jpeg"], a[href*=".png"], a[href*=".webp"]')) {
            push(a.getAttribute('href'));
            push(a.getAttribute('data-src'));
            push(a.getAttribute('data-image'));
          }
        }

        return Array.from(new Set(out)).filter(url => url && (url.match(/^https?:\/\/|^\//) && !url.match(/\.(gif|svg)$/i)));
      });

    let hrefs = [];
    try {
      const initial = await collectCandidateUrls();
      hrefs = Array.isArray(initial) ? initial : [];
      if (hrefs.length) {
        writeLog('debug', `Image extraction found ${hrefs.length} candidate URL(s) for: ${normalizedUrl}`, 'scrape', jobId);
      }
    } catch (err) {
      writeLog('error', `Image collection failed: ${err.message}`, 'scrape', jobId);
      hrefs = [];
    }

    if (!hrefs.length) {
      hrefs = await driver.wait(
        async () => {
          const values = await collectCandidateUrls();
          return Array.isArray(values) && values.length ? values : false;
        },
        IMAGE_SELECTOR_TIMEOUT_MS
      ).catch(async () => {
        try {
          const values = await collectCandidateUrls();
          return Array.isArray(values) ? values : [];
        } catch {
          return [];
        }
      });
      if (hrefs.length) {
        writeLog('info', `Image extraction recovered ${hrefs.length} URL(s) after wait: ${normalizedUrl}`, 'scrape', jobId);
      }
    }

    let effectiveHrefs = Array.isArray(hrefs) ? hrefs : [];
    if (!effectiveHrefs.length) {
      try {
        const html = await driver.getPageSource();
        const fromSource = extractCatalogImageUrlsFromHtml(html, normalizedUrl);
        if (fromSource.length) {
          writeLog(
            'info',
            `Recovered ${fromSource.length} image link(s) from page source fallback: ${normalizedUrl}`,
            'scrape',
            jobId
          );
          effectiveHrefs = fromSource;
        }
      } catch {
        // ignore source fallback errors
      }
    }

    if (!effectiveHrefs.length) {
      writeLog('warning', `No full-resolution image links found after all methods: ${normalizedUrl}`, 'scrape', jobId);
      return [];
    }

    const preFilterCount = effectiveHrefs.length;
    for (const href of effectiveHrefs) {
      const absoluteHref = toAbsoluteUrl(href, normalizedUrl);
      if (!absoluteHref) continue;
      
      // Skip thumbnails and small images
      if (absoluteHref.includes('/small_image/') || absoluteHref.includes('/thumbnail/')) continue;
      if (absoluteHref.match(/\.(gif|svg)$/i)) continue;
      
      // For single product URLs, be inclusive - accept any URL that looks like an image
      const hasImageExtension = absoluteHref.match(/\.(jpg|jpeg|png|webp|bmp|tiff|heic)$/i);
      const hasImageParam = absoluteHref.match(/[?&](image|img|photo|picture|src|url|file|content)\=/i);
      const hasImagePath = absoluteHref.match(/\/(image|img|photo|picture|asset|media|cdn|static|content|media)\//i);
      const isImageUrl = absoluteHref.match(/^https?:\/\/.*\.(jpg|jpeg|png|webp|bmp|tiff|heic)/i);
      
      // Accept catalog images OR any image-like URL
      if (absoluteHref.includes('/catalog/product/image/') || hasImageExtension || hasImageParam || hasImagePath || isImageUrl) {
        imageSet.add(absoluteHref);
      }
    }

    if (imageSet.size < preFilterCount) {
      writeLog('debug', `Image filter: ${preFilterCount} candidates → ${imageSet.size} kept for: ${normalizedUrl}`, 'scrape', jobId);
    }
  } catch (err) {
    if (isDriverSessionError(err)) {
      throw err;
    }
    writeLog('error', `Product page failed: ${normalizedUrl} (${err.message})`, 'scrape', jobId);
    return [];
  }

  return Array.from(imageSet);
}

async function fetchImageBuffer(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), IMAGE_HTTP_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      method: 'GET',
      redirect: 'follow',
      signal: controller.signal,
      headers: {
        'User-Agent':
          'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36'
      }
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const buffer = Buffer.from(await response.arrayBuffer());
    if (!buffer.length) {
      throw new Error('Empty image payload');
    }

    return buffer;
  } finally {
    clearTimeout(timeout);
  }
}

async function convertImageToPythonJpg(imageUrl, jobId, quality = 85) {
  // Check if Python script exists
  if (!fs.existsSync(PYTHON_CONVERT_SCRIPT_PATH)) {
    if (!pythonConvertScriptMissingLogged) {
      writeLog('warning', 'Python image conversion script not found, storing source URLs only', 'image', jobId);
      pythonConvertScriptMissingLogged = true;
    }
    return {
      success: true,
      data: null,
      url: imageUrl,
      converted: false,
      reason: 'Python script not available'
    };
  }

  const pythonRuntime = await resolvePythonRuntime(jobId);
  if (!pythonRuntime) {
    return {
      success: true,
      data: null,
      url: imageUrl,
      converted: false,
      reason: 'Python runtime not available'
    };
  }

  try {
    const timeout = IMAGE_CONVERT_TIMEOUT_MS;
    
    // Execute Python script with timeout
    const { stdout } = await execFileAsync(
      pythonRuntime.command,
      [...pythonRuntime.argsPrefix, PYTHON_CONVERT_SCRIPT_PATH, imageUrl, String(quality), String(IMAGE_HTTP_TIMEOUT_MS / 1000)],
      { timeout, maxBuffer: 50 * 1024 * 1024 }
    );

    // Parse JSON response from Python
    const result = JSON.parse(stdout);
    
    if (!result.success) {
      writeLog('warning', `Python conversion failed for ${imageUrl}: ${result.error}`, 'image', jobId);
      return {
        success: true,
        data: null,
        url: imageUrl,
        converted: false,
        reason: result.error
      };
    }

    return {
      success: true,
      data: result.data,              // base64 encoded JPG
      url: imageUrl,
      converted: true,
      size: result.size,
      quality: result.quality
    };
  } catch (err) {
    if (err && err.code === 'ENOENT') {
      cachedPythonRuntime = null;
      if (!pythonMissingLogged) {
        writeLog('warning', `Python runtime not available (${err.message}); storing source URLs only`, 'image', jobId);
        pythonMissingLogged = true;
      }
    } else {
      writeLog('warning', `Python image conversion error for ${imageUrl}: ${err.message}`, 'image', jobId);
    }
    
    // Fallback: return URL for later processing
    return {
      success: true,
      data: null,
      url: imageUrl,
      converted: false,
      reason: `Python error: ${err.message}`
    };
  }
}

async function storeProductImagesInDb({ jobId, productName, productIndex, sourceImages }) {
  if (!Array.isArray(sourceImages) || sourceImages.length === 0) {
    return [];
  }

  const uniqueSources = Array.from(new Set(sourceImages.filter(Boolean)));
  if (!uniqueSources.length) {
    return [];
  }

  // Convert images using Python concurrently for speed
  const conversions = await mapWithConcurrency(uniqueSources, IMAGE_DOWNLOAD_CONCURRENCY, async (sourceUrl, index) => {
    try {
      const converted = await convertImageToPythonJpg(sourceUrl, jobId);
      return {
        id: `${jobId}_${productIndex}_${index}`,
        url: sourceUrl,
        original_url: sourceUrl,
        index: index + 1,
        product_index: productIndex,
        product_name: productName,
        created_at: nowIso(),
        jpg_data: converted.data,        // base64 encoded JPG or null
        converted: converted.converted,
        size: converted.size || null,
        quality: converted.quality || null,
        error: converted.reason || null
      };
    } catch (err) {
      // Fallback: create image object without conversion
      return {
        id: `${jobId}_${productIndex}_${index}`,
        url: sourceUrl,
        original_url: sourceUrl,
        index: index + 1,
        product_index: productIndex,
        product_name: productName,
        created_at: nowIso(),
        jpg_data: null,
        converted: false,
        error: err.message
      };
    }
  });

  return conversions;
}

async function writeJobManifest(jobId, payload) {
  const jobDir = path.join(DOWNLOAD_ROOT, String(jobId));
  await fsp.mkdir(jobDir, { recursive: true });
  const manifestPath = path.join(jobDir, 'manifest.json');
  await fsp.writeFile(manifestPath, JSON.stringify(payload, null, 2), 'utf8');
}

async function scrape(url, jobId) {
  const chromeDriverPath = resolveChromeDriverPath();
  if (!chromeDriverPath) {
    const suggestedNodePath = path.join(__dirname, 'node_modules');
    throw new Error(
      'ChromeDriver binary not found. Run `npm start` or install dependencies with ' +
      `\`NODE_PATH=${suggestedNodePath} npm install\`.`
    );
  }
  writeLog('info', `Using ChromeDriver at ${chromeDriverPath}`, 'scrape', jobId);
  writeLog(
    'info',
    `Speed profile: delay ${PRODUCT_DELAY_MIN_MS}-${PRODUCT_DELAY_MAX_MS}ms, image-concurrency ${IMAGE_DOWNLOAD_CONCURRENCY}, retries ${MAX_RETRIES}, empty-retries ${EMPTY_RESULT_RETRIES}`,
    'scrape',
    jobId
  );

  const profileRoot = path.join(__dirname, '.tmp', 'chrome-profile');
  await fsp.mkdir(profileRoot, { recursive: true });

  const profileDirs = [];
  const createProfileDir = async (tag) => {
    const safeTag = sanitizeSegment(tag, 'profile');
    const profileDir = path.join(profileRoot, `${String(jobId)}_${Date.now()}_${safeTag}`);
    await fsp.mkdir(profileDir, { recursive: true });
    profileDirs.push(profileDir);
    return profileDir;
  };

  let driver = null;
  let products = [];
  let categoryTabHandle = null;
  let productTabHandle = null;

  const restartDriver = async (tag, { createProductTab = true } = {}) => {
    if (driver) {
      try {
        await driver.quit();
      } catch (err) {
        writeLog('warning', `Browser quit error: ${err.message}`, 'scrape', jobId);
      }
      driver = null;
    }

    const profileDir = await createProfileDir(tag);
    try {
      driver = await createDriverInstance(chromeDriverPath, profileDir);
    } catch (err) {
      writeLog(
        'warning',
        `Driver startup with profile failed (${err.message}); retrying with default Chrome profile`,
        'scrape',
        jobId
      );
      driver = await createDriverInstance(chromeDriverPath, null);
    }

    categoryTabHandle = await driver.getWindowHandle();
    productTabHandle = createProductTab
      ? await openProductTab(driver, categoryTabHandle, jobId)
      : categoryTabHandle;
  };

  try {
    await restartDriver('initial', { createProductTab: false });

    const isSingleProduct = isSingleProductUrl(url);

    if (isSingleProduct) {
      // Handle single product URL - extract images directly from this product
      writeLog('info', `Detected single product URL: ${url}`, 'scrape', jobId);

      const singleProduct = {
        name: inferModelFromUrl(url),
        price: '',
        product_url: url,
        img: '',
        images: [],
        source_images: []
      };

      products = [singleProduct];

      updateJob(jobId, {
        status: 'running',
        model: inferModelFromUrl(url),
        total_items: 1,
        processed_items: 0,
        images: 0,
        error: null,
        products: []
      });

      writeLog('info', `Processing single product: ${url}`, 'scrape', jobId);

      productTabHandle = await openProductTab(driver, categoryTabHandle, jobId);

      let sourceImages = [];
      let retries = 0;
      let emptyRetries = 0;
      let recoveryRetries = 0;

      while (sourceImages.length === 0) {
        try {
          sourceImages = await extractImagesWithDriver(driver, url, productTabHandle, jobId);

          if (!sourceImages.length && emptyRetries < EMPTY_RESULT_RETRIES) {
            emptyRetries++;
            writeLog(
              'warning',
              `No images extracted (retry ${emptyRetries}/${EMPTY_RESULT_RETRIES}), retrying...`,
              'scrape',
              jobId
            );
            await sleep(700);
            continue;
          }
          break;
        } catch (err) {
          const sessionLost = isDriverSessionError(err);

          if (sessionLost && recoveryRetries < DRIVER_RECOVERY_RETRIES) {
            recoveryRetries++;
            writeLog(
              'warning',
              `Browser session dropped; restarting browser and retrying`,
              'scrape',
              jobId
            );
            await restartDriver(`recover_single_product`, { createProductTab: true });
            continue;
          }

          if (!sessionLost && retries < MAX_RETRIES) {
            retries++;
            writeLog(
              'warning',
              `Image extraction failed (retry ${retries}/${MAX_RETRIES}): ${err.message}`,
              'scrape',
              jobId
            );
            await sleep(1200);
            continue;
          }

          writeLog('warning', `Image extraction failed: ${err.message}`, 'scrape', jobId);
          break;
        }
      }

      singleProduct.source_images = sourceImages;

      let storedImages = [];
      try {
        storedImages = await storeProductImagesInDb({
          jobId,
          productName: singleProduct.name,
          productIndex: 0,
          sourceImages
        });
      } catch (err) {
        writeLog('error', `Image storage failed for ${url}: ${err.message}`, 'image', jobId);
      }

      singleProduct.images = storedImages;

      const convertedCount = storedImages.filter(img => img.converted).length;
      const failedCount = storedImages.filter(img => img.error).length;

      updateJob(jobId, {
        processed_items: 1,
        total_items: 1,
        images: storedImages.length,
        products: [singleProduct]
      });

      writeLog(
        'success',
        `Stored ${storedImages.length} image(s) in database for single product (${convertedCount} converted, ${failedCount} not converted)`,
        'image',
        jobId
      );

      return products;
    }

    // Handle category URL - extract all products from category
    writeLog('info', `Loading category: ${url}`, 'scrape', jobId);
    await driver.switchTo().window(categoryTabHandle);
    await driver.get(url);

    // First try immediate selector match, then scroll to load more items
    let elementsFound = false;
    try {
      await driver.wait(until.elementsLocated(By.css('li.item')), SELECTOR_TIMEOUT_MS / 3);
      elementsFound = true;
    } catch (selectorErr) {
      writeLog('warning', `Initial elements not found quickly, scrolling to load items...`, 'scrape', jobId);
    }

    // Scroll page to trigger lazy loading and stabilize product list
    await autoScrollUntilStable(driver);

    // If initial wait failed, try one more time after scrolling
    if (!elementsFound) {
      try {
        await driver.wait(until.elementsLocated(By.css('li.item')), SELECTOR_TIMEOUT_MS / 3);
      } catch (retryErr) {
        writeLog('warning', `Product list still not found after scrolling, attempting extraction anyway...`, 'scrape', jobId);
      }
    }

    products = await extractCategoryProducts(driver, url);

    const initialModel = inferModelFromUrl(url);

    updateJob(jobId, {
      status: 'running',
      model: initialModel,
      total_items: products.length,
      processed_items: 0,
      images: 0,
      error: null,
      products: []
    });

    writeLog('info', `Found ${products.length} products`, 'scrape', jobId);

    productTabHandle = await openProductTab(driver, categoryTabHandle, jobId);

    let downloadedCount = 0;

    for (let index = 0; index < products.length; index++) {
      const product = products[index];
      const jobIdStr = String(jobId);
      const liveJob = jobs.get(jobIdStr);
      if (deletedJobIds.has(jobIdStr) || stopRequestedJobIds.has(jobIdStr) || liveJob?.stop_requested) {
        writeLog('warning', 'Stop requested by user; ending scrape loop.', 'scrape', jobId);
        break;
      }

      // Check for pause requests
      while (true) {
        const pausedJob = jobs.get(jobIdStr);
        if (!pausedJob?.pause_requested) break;
        writeLog('info', 'Job paused; waiting for resume...', 'scrape', jobId);
        await sleep(2000);
        const updatedJob = jobs.get(jobIdStr);
        if (deletedJobIds.has(jobIdStr) || stopRequestedJobIds.has(jobIdStr) || updatedJob?.stop_requested) {
          writeLog('warning', 'Stop requested while paused; ending scrape loop.', 'scrape', jobId);
          throw new Error('Stopped by user');
        }
      }

      // Restart browser periodically to prevent memory leaks
      if (index > 0 && index % PRODUCTS_PER_BROWSER === 0) {
        writeLog('info', `Restarting browser after ${PRODUCTS_PER_BROWSER} products for memory cleanup`, 'scrape', jobId);
        await restartDriver(`rotation_${index}`, { createProductTab: true });
        await sleep(500);
      }

      writeLog(
        'info',
        `Processing ${index + 1}/${products.length}: ${product.name || product.product_url}`,
        'scrape',
        jobId
      );

      let sourceImages = [];
      let retries = 0;
      let emptyRetries = 0;
      let recoveryRetries = 0;

      while (sourceImages.length === 0) {
        try {
          sourceImages = await extractImagesWithDriver(driver, product.product_url, productTabHandle, jobId);

          if (!sourceImages.length && emptyRetries < EMPTY_RESULT_RETRIES) {
            emptyRetries++;
            writeLog(
              'warning',
              `No images extracted (retry ${emptyRetries}/${EMPTY_RESULT_RETRIES}), retrying...`,
              'scrape',
              jobId
            );
            await sleep(700);
            continue;
          }

          break;
        } catch (err) {
          const sessionLost = isDriverSessionError(err);

          if (sessionLost && recoveryRetries < DRIVER_RECOVERY_RETRIES) {
            recoveryRetries++;
            writeLog(
              'warning',
              `Browser session dropped while scraping ${product.product_url}; restarting browser and retrying`,
              'scrape',
              jobId
            );
            await restartDriver(`recover_${index}_${recoveryRetries}`, { createProductTab: true });
            continue;
          }

          if (!sessionLost && retries < MAX_RETRIES) {
            retries++;
            writeLog(
              'warning',
              `Image extraction failed (retry ${retries}/${MAX_RETRIES}): ${err.message}`,
              'scrape',
              jobId
            );
            await sleep(1200);
            continue;
          }

          writeLog('warning', `Image extraction failed: ${err.message}`, 'scrape', jobId);
          break;
        }
      }

      if (!sourceImages.length && product.img) {
        const fallbackImage = toAbsoluteUrl(product.img, product.product_url || url);
        const looksLikeImage = fallbackImage && !fallbackImage.startsWith('data:') && !/\.(gif|svg)(\?|$)/i.test(fallbackImage);
        if (looksLikeImage) {
          sourceImages = [fallbackImage];
          writeLog('info', `Using listing image fallback for ${product.product_url}`, 'scrape', jobId);
        }
      }

      product.source_images = sourceImages;

      let storedImages = [];
      try {
        storedImages = await storeProductImagesInDb({
          jobId,
          productName: product.name,
          productIndex: index,
          sourceImages
        });
      } catch (err) {
        writeLog('error', `Image storage failed for ${product.product_url}: ${err.message}`, 'image', jobId);
      }

      product.images = storedImages;
      downloadedCount += storedImages.length;
      
      const convertedCount = storedImages.filter(img => img.converted).length;
      const failedCount = storedImages.filter(img => img.error).length;

      updateJob(jobId, {
        processed_items: index + 1,
        total_items: products.length,
        images: downloadedCount,
        products: products.slice(0, index + 1)
      });

      writeLog(
        'success',
        `Stored ${storedImages.length} image(s) in database for ${product.name || product.product_url} (${convertedCount} Python-converted, ${failedCount} not converted)`,
        'image',
        jobId
      );
    }

    return products;
  } finally {
    if (driver) {
      try {
        await driver.quit();
      } catch (err) {
        writeLog('warning', `Browser quit error: ${err.message}`, 'scrape', jobId);
      }
    }
    await Promise.all(profileDirs.map((dir) => fsp.rm(dir, { recursive: true, force: true }).catch(() => {})));
    writeLog('info', 'Browser session closed', 'scrape', jobId);
  }
}

app.get('/events', (req, res) => {
  setupSseHeaders(res);
  eventClients.add(res);

  sendSse(res, 'ready', { time: nowIso() });
  for (const job of jobs.values()) {
    sendSse(res, 'job_update', summarizeJob(job, false));
  }

  const heartbeat = setInterval(() => {
    try {
      sendSse(res, 'ping', { time: nowIso() });
    } catch {
      // no-op
    }
  }, SSE_HEARTBEAT_MS);

  req.on('close', () => {
    clearInterval(heartbeat);
    eventClients.delete(res);
  });
});

app.get('/logs', (req, res) => {
  const limitRaw = Number(req.query.limit);
  const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(limitRaw, LOG_HISTORY_LIMIT)) : 100;
  res.json({ success: true, logs: logHistory.slice(-limit) });
});

app.get('/logs/stream', (req, res) => {
  setupSseHeaders(res);
  logClients.add(res);

  const initial = logHistory.slice(-80);
  for (const entry of initial) {
    sendSse(res, 'log', entry);
  }

  const heartbeat = setInterval(() => {
    try {
      sendSse(res, 'ping', { time: nowIso() });
    } catch {
      // no-op
    }
  }, SSE_HEARTBEAT_MS);

  req.on('close', () => {
    clearInterval(heartbeat);
    logClients.delete(res);
  });
});

app.get('/jobs', (req, res) => {
  const list = Array.from(jobs.values())
    .filter((job) => !deletedJobIds.has(String(job.id)))
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .map((job) => summarizeJob(job, false));

  res.json({ success: true, jobs: list });
});

app.get('/jobs/:id', (req, res) => {
  const jobId = String(req.params.id);
  if (deletedJobIds.has(jobId)) {
    return res.status(404).json({ success: false, error: 'Job not found' });
  }

  const job = jobs.get(jobId);
  if (!job) {
    return res.status(404).json({ success: false, error: 'Job not found' });
  }

  const includeProducts = req.query.full === '1' || req.query.full === 'true';
  res.json({ success: true, job: summarizeJob(job, includeProducts) });
});

app.get('/jobs/:id/zip', async (req, res) => {
  const jobId = String(req.params.id);
  if (deletedJobIds.has(jobId)) {
    return res.status(404).json({ success: false, error: 'Job not found' });
  }

  const safeJobId = jobId.replace(/[^a-zA-Z0-9_-]/g, '');
  if (!safeJobId) {
    return res.status(400).json({ success: false, error: 'Invalid job id' });
  }

  const job = jobs.get(jobId);
  const jobDir = path.join(DOWNLOAD_ROOT, safeJobId);

  try {
    const stat = await fsp.stat(jobDir);
    if (!stat.isDirectory()) {
      return res.status(404).json({ success: false, error: 'No files found for this job' });
    }
  } catch {
    return res.status(404).json({ success: false, error: 'No files found for this job' });
  }

  const hasFiles = await directoryHasFiles(jobDir).catch(() => false);
  if (!hasFiles) {
    return res.status(404).json({ success: false, error: 'No files found for this job' });
  }

  const baseName = sanitizeSegment(job?.model || `job_${safeJobId}`, `job_${safeJobId}`).slice(0, 80) || `job_${safeJobId}`;
  const filename = `${baseName}_${safeJobId}.zip`;
  const tempZipPath = path.join(DOWNLOAD_ROOT, `${safeJobId}_temp.zip`);

  try {
    // Use Python for fast ZIP compression when available
    const pythonRuntime = await resolvePythonRuntime(jobId);
    let usedPythonZip = false;

    if (fs.existsSync(PYTHON_ZIP_SCRIPT_PATH) && pythonRuntime) {
      // Python ZIP creation (faster)
      try {
        const { stdout } = await execFileAsync(
          pythonRuntime.command,
          [...pythonRuntime.argsPrefix, PYTHON_ZIP_SCRIPT_PATH, jobDir, tempZipPath, '9'],
          { timeout: 300000, maxBuffer: 100 * 1024 * 1024 }
        );

        const result = JSON.parse(stdout);
        if (!result.success) {
          writeLog('warning', `Python ZIP creation failed, falling back to Node archiver: ${result.error}`, 'jobs', jobId);
        } else {
          // Stream the ZIP file
          const fileStream = fs.createReadStream(tempZipPath);
          const zipSize = result.size;

          res.setHeader('Content-Type', 'application/zip');
          res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
          res.setHeader('Content-Length', zipSize);

          fileStream.on('error', (err) => {
            writeLog('error', `ZIP stream error for job ${jobId}: ${err.message}`, 'jobs', jobId);
            if (!res.headersSent) {
              res.status(500).json({ success: false, error: 'Stream error' });
            }
          });

          res.on('finish', () => {
            // Clean up temp ZIP after download
            fsp.unlink(tempZipPath).catch(() => {});
            writeLog('info', `ZIP download completed for job ${jobId} (${result.size_mb}MB)`, 'jobs', jobId);
          });

          fileStream.pipe(res);
          usedPythonZip = true;
        }
      } catch (err) {
        if (err && err.code === 'ENOENT') {
          cachedPythonRuntime = null;
          if (!pythonMissingLogged) {
            writeLog('warning', `Python runtime unavailable (${err.message}), using Node.js archiver`, 'jobs', jobId);
            pythonMissingLogged = true;
          }
        } else {
          writeLog('warning', `Python ZIP creation failed, using Node.js archiver: ${err.message}`, 'jobs', jobId);
        }
      }
    }

    if (!usedPythonZip) {
      // Fallback to Node.js archiver if Python script/runtime is not available
      if (!fs.existsSync(PYTHON_ZIP_SCRIPT_PATH)) {
        writeLog('warning', 'Python ZIP script not found, using Node.js archiver (slower)', 'jobs', jobId);
      } else if (!pythonRuntime) {
        writeLog('warning', 'Python runtime unavailable, using Node.js archiver (slower)', 'jobs', jobId);
      }
      
      res.setHeader('Content-Type', 'application/zip');
      res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);

      const archive = archiver('zip', { zlib: { level: 9 } });
      archive.on('warning', (err) => {
        if (err?.code === 'ENOENT') {
          writeLog('warning', `ZIP warning for job ${jobId}: ${err.message}`, 'jobs', jobId);
          return;
        }
      });

      archive.on('error', (err) => {
        writeLog('error', `ZIP build failed for job ${jobId}: ${err.message}`, 'jobs', jobId);
        if (!res.headersSent) {
          res.status(500).json({ success: false, error: 'Could not build ZIP' });
          return;
        }
        res.destroy(err);
      });

      archive.pipe(res);
      archive.directory(jobDir, safeJobId);
      
      try {
        await archive.finalize();
        writeLog('info', `ZIP download generated for job ${jobId}`, 'jobs', jobId);
      } catch (err) {
        writeLog('error', `ZIP finalize failed for job ${jobId}: ${err.message}`, 'jobs', jobId);
      }
    }
  } catch (err) {
    writeLog('error', `ZIP creation error for job ${jobId}: ${err.message}`, 'jobs', jobId);
    
    // Fallback to Node.js archiver
    try {
      res.setHeader('Content-Type', 'application/zip');
      res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);

      const archive = archiver('zip', { zlib: { level: 9 } });
      archive.on('error', (err) => {
        if (!res.headersSent) {
          res.status(500).json({ success: false, error: 'Could not build ZIP' });
        }
      });

      archive.pipe(res);
      archive.directory(jobDir, safeJobId);
      await archive.finalize();
    } catch (fallbackErr) {
      if (!res.headersSent) {
        res.status(500).json({ success: false, error: 'ZIP creation failed' });
      }
    }
  }
});

app.get('/jobs/:id/images', (req, res) => {
  const jobId = String(req.params.id);
  if (deletedJobIds.has(jobId)) {
    return res.status(404).json({ success: false, error: 'Job not found' });
  }

  const job = jobs.get(jobId);
  if (!job) {
    return res.status(404).json({ success: false, error: 'Job not found' });
  }

  // Collect all images from all products in the database
  const allImages = [];
  if (Array.isArray(job.products)) {
    for (let productIndex = 0; productIndex < job.products.length; productIndex++) {
      const product = job.products[productIndex];
      if (product && Array.isArray(product.images)) {
        for (const image of product.images) {
          allImages.push({
            product_index: productIndex,
            product_name: product.name,
            product_url: product.product_url,
            ...image
          });
        }
      }
    }
  }

  const productId = req.query.product_id;
  let filteredImages = allImages;

  if (productId != null) {
    const prodIdx = Number(productId);
    if (!Number.isNaN(prodIdx)) {
      filteredImages = allImages.filter((img) => img.product_index === prodIdx);
    }
  }

  res.json({
    success: true,
    job_id: jobId,
    total_images: filteredImages.length,
    images: filteredImages
  });
});

app.get('/jobs/:id/images/:imageId', (req, res) => {
  const jobId = String(req.params.id);
  const imageId = String(req.params.imageId);

  if (deletedJobIds.has(jobId)) {
    return res.status(404).json({ success: false, error: 'Job not found' });
  }

  const job = jobs.get(jobId);
  if (!job) {
    return res.status(404).json({ success: false, error: 'Job not found' });
  }

  // Find the requested image
  let foundImage = null;
  if (Array.isArray(job.products)) {
    for (const product of job.products) {
      if (product && Array.isArray(product.images)) {
        const img = product.images.find(i => i.id === imageId);
        if (img) {
          foundImage = img;
          break;
        }
      }
    }
  }

  if (!foundImage) {
    return res.status(404).json({ success: false, error: 'Image not found' });
  }

  // If JPG data is stored, serve it directly
  if (foundImage.jpg_data && foundImage.converted) {
    try {
      const jpgBuffer = Buffer.from(foundImage.jpg_data, 'base64');
      res.setHeader('Content-Type', 'image/jpeg');
      res.setHeader('Content-Length', jpgBuffer.length);
      res.setHeader('Cache-Control', 'public, max-age=86400');
      return res.send(jpgBuffer);
    } catch (err) {
      writeLog('warning', `Failed to decode JPG data for image ${imageId}: ${err.message}`, 'image', jobId);
    }
  }

  // If no JPG data, return metadata and redirect to original URL
  res.json({
    success: true,
    image: {
      ...foundImage,
      jpg_data: undefined  // Don't send the base64 data in JSON response
    },
    converted: foundImage.converted,
    original_url: foundImage.original_url
  });
});

app.delete('/jobs/:id', async (req, res) => {
  const jobId = String(req.params.id);
  const job = jobs.get(jobId);
  const isActive = job && ['running', 'queued', 'paused'].includes(String(job.status || ''));

  if (isActive) {
    deletedJobIds.add(jobId);
    stopRequestedJobIds.add(jobId);
    job.stop_requested = true;
    job.pause_requested = false;
  } else {
    deletedJobIds.delete(jobId);
    stopRequestedJobIds.delete(jobId);
  }

  jobs.delete(jobId);

  try {
    await fsp.rm(path.join(DOWNLOAD_ROOT, jobId), { recursive: true, force: true });
  } catch (err) {
    writeLog('warning', `Failed to delete files for job ${jobId}: ${err.message}`, 'jobs', jobId);
  }

  schedulePersistJobsDb();
  res.json({ success: true });
});

app.post('/jobs/reset', async (req, res) => {
  const activeJobIds = Array.from(jobs.values())
    .filter((job) => ['running', 'queued', 'paused'].includes(String(job.status || '')))
    .map((job) => String(job.id));

  // Reset should stop active/queued work before clearing visible jobs.
  stopRequestedJobIds.clear();
  deletedJobIds.clear();
  for (const jobId of activeJobIds) {
    stopRequestedJobIds.add(jobId);
    deletedJobIds.add(jobId);
    const job = jobs.get(jobId);
    if (job) {
      job.stop_requested = true;
      job.pause_requested = false;
    }
  }

  jobs.clear();

  try {
    await clearDirectoryContents(DOWNLOAD_ROOT);
  } catch (err) {
    writeLog('warning', `Failed to reset downloads directory: ${err.message}`, 'jobs');
  }

  schedulePersistJobsDb();
  if (activeJobIds.length > 0) {
    writeLog('warning', `Reset requested; stopping ${activeJobIds.length} active job(s)`, 'jobs');
  }
  writeLog('info', 'All jobs reset by user', 'jobs');
  res.json({ success: true });
});

app.post('/jobs/:id/stop', (req, res) => {
  const jobId = String(req.params.id);
  const job = jobs.get(jobId);
  if (!job) {
    return res.status(404).json({ success: false, error: 'Job not found' });
  }

  stopRequestedJobIds.add(jobId);
  job.stop_requested = true;
  job.pause_requested = false;
  updateJob(jobId, { status: 'failed', error: 'Stopped by user' });
  writeLog('warning', 'Stop requested for running job', 'jobs', jobId);
  res.json({ success: true });
});

async function handleScrape(req, res) {
  const { url } = req.query;
  const providedJobId = req.query.job_id;

  if (!url) {
    return res.status(400).json({ success: false, error: 'URL parameter is required' });
  }

  const jobId = String(providedJobId || createJobId());
  const existingJob = jobs.get(jobId);
  const existingStatus = String(existingJob?.status || '');

  // Idempotency guard: the same job id should not start/queue multiple concurrent runs.
  if (existingJob && isActiveJobStatus(existingStatus)) {
    writeLog('warning', `Duplicate scrape request ignored; job is already ${existingStatus}`, 'queue', jobId);
    return res.status(202).json({
      success: true,
      duplicate: true,
      job_id: jobId,
      status: existingStatus,
      products: [],
      data: []
    });
  }

  // If a completed job is replayed with the same id+url, return cached result instead of rerunning.
  if (
    existingJob &&
    existingStatus === 'completed' &&
    String(existingJob.url || '').trim() === String(url || '').trim() &&
    Array.isArray(existingJob.products)
  ) {
    writeLog('info', 'Duplicate completed scrape request served from cache', 'queue', jobId);
    return res.json({
      success: true,
      duplicate: true,
      job_id: jobId,
      status: 'completed',
      products: existingJob.products,
      data: existingJob.products
    });
  }

  if (deletedJobIds.has(jobId) || stopRequestedJobIds.has(jobId)) {
    return res
      .status(409)
      .json({ success: false, job_id: jobId, error: 'Job is stopping. Retry with a new job id.' });
  }

  deletedJobIds.delete(jobId);
  stopRequestedJobIds.delete(jobId);

  updateJob(jobId, {
    id: jobId,
    url,
    status: 'queued',
    model: inferModelFromUrl(url),
    images: 0,
    total_items: 0,
    processed_items: 0,
    error: null,
    products: [],
    stop_requested: false,
    pause_requested: false,
    created_at: jobs.get(jobId)?.created_at || nowIso()
  });

  writeLog('info', `Scrape accepted for ${url}`, 'scrape', jobId);

  try {
    const products = await executeWithScrapeSlot(jobId, async () => {
      updateJob(jobId, { status: 'running', error: null });
      writeLog('info', `Scrape started for ${url}`, 'scrape', jobId);
      return scrape(url, jobId);
    });
    const currentJob = jobs.get(jobId);
    const stopped =
      deletedJobIds.has(jobId) ||
      stopRequestedJobIds.has(jobId) ||
      Boolean(currentJob?.stop_requested);

    const status = stopped ? 'failed' : 'completed';
    const error = stopped ? 'Stopped by user' : null;

    updateJob(jobId, {
      status,
      error,
      products,
      processed_items: products.length,
      total_items: products.length,
      images: products.reduce((sum, product) => sum + (Array.isArray(product.images) ? product.images.length : 0), 0)
    });

    if (!deletedJobIds.has(jobId)) {
      await writeJobManifest(jobId, {
        job_id: jobId,
        url,
        status,
        created_at: currentJob?.created_at || nowIso(),
        completed_at: nowIso(),
        products
      });
    }

    if (stopped) {
      writeLog('warning', 'Scrape stopped before completion', 'scrape', jobId);
      return res.status(409).json({ success: false, job_id: jobId, error: 'Stopped by user', products, data: products });
    }

    writeLog('success', `Scrape completed. ${products.length} products processed.`, 'scrape', jobId);
    return res.json({ success: true, job_id: jobId, products, data: products });
  } catch (err) {
    const stopped =
      deletedJobIds.has(jobId) ||
      stopRequestedJobIds.has(jobId) ||
      /stopped by user/i.test(String(err?.message || ''));
    if (stopped) {
      updateJob(jobId, { status: 'failed', error: 'Stopped by user' });
      writeLog('warning', 'Scrape stopped before completion', 'scrape', jobId);
      return res.status(409).json({ success: false, job_id: jobId, error: 'Stopped by user', products: [], data: [] });
    }

    updateJob(jobId, { status: 'failed', error: err.message });
    writeLog('error', `Scrape failed: ${err.message}`, 'scrape', jobId);
    return res.status(500).json({ success: false, job_id: jobId, error: err.message });
  } finally {
    stopRequestedJobIds.delete(jobId);
    deletedJobIds.delete(jobId);
  }
}

app.get('/scrape', handleScrape);
app.post('/scrape', handleScrape);

// Admin API endpoints
app.post('/admin/api/pause-all', (req, res) => {
  let pausedCount = 0;
  for (const job of jobs.values()) {
    if (job.status === 'running') {
      job.pause_requested = true;
      job.status = 'paused';
      pausedCount++;
      emitJobUpdate(job.id);
    }
  }
  writeLog('info', `Paused ${pausedCount} job(s)`, 'admin');
  schedulePersistJobsDb();
  res.json({ success: true, paused_count: pausedCount });
});

app.post('/admin/api/resume-all', (req, res) => {
  let resumedCount = 0;
  for (const job of jobs.values()) {
    if (job.status === 'paused') {
      job.pause_requested = false;
      job.status = 'running';
      resumedCount++;
      emitJobUpdate(job.id);
    }
  }
  writeLog('info', `Resumed ${resumedCount} job(s)`, 'admin');
  schedulePersistJobsDb();
  res.json({ success: true, resumed_count: resumedCount });
});

app.get('/health', (req, res) => {
  const mem = monitorMemory();
  const uptime = Math.floor(process.uptime());
  
  res.json({
    success: true,
    status: 'healthy',
    timestamp: nowIso(),
    uptime_seconds: uptime,
    memory: {
      heap_used_mb: mem.heapUsedMB,
      heap_total_mb: mem.heapTotalMB,
      external_mb: mem.externalMB,
      heap_usage_percent: mem.heapUsagePercent
    },
    jobs: {
      total: jobs.size,
      active_scrapes: activeScrapes,
      queue_size: scrapeQueue.length
    }
  });
});

app.get('/admin/api/overview', (req, res) => {
  let running = 0;
  let queued = 0;
  let completed = 0;
  let failed = 0;
  let paused = 0;
  let totalImages = 0;

  for (const job of jobs.values()) {
    switch (job.status) {
      case 'running':
        running++;
        break;
      case 'queued':
        queued++;
        break;
      case 'completed':
        completed++;
        break;
      case 'failed':
        failed++;
        break;
      case 'paused':
        paused++;
        break;
    }
    totalImages += Number(job.images) || 0;
  }

  res.json({
    success: true,
    stats: {
      running,
      queued,
      completed,
      failed,
      paused,
      total_images: totalImages,
      total_jobs: jobs.size
    }
  });
});

app.get('/admin/api/seo', (req, res) => {
  const seoData = {
    title: 'XCell Parts Scraper',
    description: 'Web scraper for product information',
    keywords: 'scraper, products'
  };
  res.json({ success: true, seo: seoData });
});

app.post('/admin/api/seo', (req, res) => {
  // SEO data update endpoint - currently just echoes back
  const seoData = req.body || {};
  res.json({ success: true, seo: seoData });
});

app.post('/admin/api/reset-user', (req, res) => {
  const userId = req.query.user_id;
  if (!userId) {
    return res.status(400).json({ success: false, error: 'user_id is required' });
  }

  let deletedCount = 0;
  const jobsToDelete = [];

  for (const [jobId, job] of jobs.entries()) {
    if (String(job.user_id || '') === String(userId)) {
      jobsToDelete.push(jobId);
      deletedCount++;
    }
  }

  for (const jobId of jobsToDelete) {
    jobs.delete(jobId);
    fsp.rm(path.join(DOWNLOAD_ROOT, jobId), { recursive: true, force: true }).catch(() => {});
  }

  writeLog('info', `Reset ${deletedCount} job(s) for user ${userId}`, 'admin');
  schedulePersistJobsDb();
  res.json({ success: true, deleted_count: deletedCount });
});

app.post('/admin/api/jobs/:id/stop', (req, res) => {
  const jobId = String(req.params.id);
  const job = jobs.get(jobId);
  if (!job) {
    return res.status(404).json({ success: false, error: 'Job not found' });
  }

  job.stop_requested = true;
  updateJob(jobId, { status: 'failed', error: 'Stopped by user' });
  writeLog('warning', 'Stop requested for job via admin API', 'admin', jobId);
  res.json({ success: true });
});

loadPersistedJobs().finally(() => {
  app.listen(PORT, () => {
    const mem = monitorMemory();
    writeLog('info', `Scraper API running at http://localhost:${PORT}`, 'startup');
    writeLog('info', `Memory: ${mem.heapUsedMB}MB / ${mem.heapTotalMB}MB (${mem.heapUsagePercent}%)`, 'startup');
    writeLog('info', `Concurrency: ${MAX_ACTIVE_SCRAPES} active job(s), max runtime: ${Math.round(JOB_MAX_RUNTIME_MS / 60000)} minute(s)`, 'startup');
    writeLog('info', `Job persistence: ${PERSIST_JOBS_ENABLED ? 'ENABLED' : 'DISABLED (in-memory only)'}`, 'startup');
  });

  // Schedule image cleanup task to run every 30 minutes
  const CLEANUP_INTERVAL_MS = 30 * 60 * 1000; // 30 minutes
  const IMAGE_MAX_AGE_HOURS = 24; // Delete images older than 24 hours

  setInterval(async () => {
    monitorMemory();
    writeLog('info', 'Starting scheduled image cleanup...', 'cleanup');
    await cleanupOldImages(IMAGE_MAX_AGE_HOURS);
  }, CLEANUP_INTERVAL_MS);

  // Memory monitoring every 10 minutes
  const MEMORY_CHECK_INTERVAL_MS = 10 * 60 * 1000;
  setInterval(() => {
    monitorMemory();
  }, MEMORY_CHECK_INTERVAL_MS);

  // Run initial cleanup on startup
  cleanupOldImages(IMAGE_MAX_AGE_HOURS).catch((err) => {
    writeLog('warning', `Initial cleanup on startup failed: ${err.message}`, 'cleanup');
  });

  writeLog('info', `Image cleanup scheduled to run every ${CLEANUP_INTERVAL_MS / 60000} minutes (deleting images older than ${IMAGE_MAX_AGE_HOURS} hours)`, 'startup');
});
