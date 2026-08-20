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
const archiver = require('archiver');
const { execFile } = require('child_process');
const { promisify } = require('util');
const crypto = require('node:crypto');
const { envBoolean, retainJobs } = require('./lib/runtime-config');
const {
  fetchWithValidatedRedirects,
  isSafeJobId,
  parseAllowedHosts,
  resolveWithinRoot,
  validatePublicHttpUrl
} = require('./lib/security');
const execFileAsync = promisify(execFile);

const app = express();
const PORT = Number.parseInt(process.env.PORT || '', 10) || 3001;
const HOST = String(process.env.HOST || (process.env.NODE_ENV === 'production' ? '0.0.0.0' : '127.0.0.1')).trim();
const APP_ACCESS_TOKEN = String(process.env.APP_ACCESS_TOKEN || '').trim();
const CORS_ALLOWED_ORIGINS = new Set(
  String(process.env.CORS_ALLOWED_ORIGINS || '')
    .split(',')
    .map((value) => value.trim().replace(/\/+$/, ''))
    .filter(Boolean)
);
const SCRAPE_ALLOWED_HOSTS = parseAllowedHosts(
  process.env.SCRAPE_ALLOWED_HOSTS,
  ['mobilesentrix.com', 'mobilesentrix.ca', 'xcellparts.com']
);
const DESTRUCTIVE_CONFIRMATION = 'permanently-delete';

if (process.env.NODE_ENV === 'production' && !APP_ACCESS_TOKEN) {
  throw new Error('APP_ACCESS_TOKEN is required when NODE_ENV=production.');
}

app.set('trust proxy', true);

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
const CHALLENGE_WAIT_MS = envInt('CHALLENGE_WAIT_MS', 25000, 5000, 180000);
const LOG_HISTORY_LIMIT = 200; // Reduced from 500 for lower memory usage
const SSE_HEARTBEAT_MS = 35000; // Reduced heartbeat frequency for less network traffic
const IMAGE_HTTP_TIMEOUT_MS = envInt('IMAGE_HTTP_TIMEOUT_MS', 45000, 3000, 180000);
const IMAGE_CONVERT_TIMEOUT_MS = envInt('IMAGE_CONVERT_TIMEOUT_MS', 60000, 3000, 180000);
const MAX_ACTIVE_SCRAPES = envInt('MAX_ACTIVE_SCRAPES', 3, 1, 4);
const SCRAPE_TRANSIENT_RETRIES = envInt('SCRAPE_TRANSIENT_RETRIES', 1, 0, 3);
const IMAGE_DOWNLOAD_CONCURRENCY = envInt('IMAGE_DOWNLOAD_CONCURRENCY', 3, 1, 4);
const JOB_MAX_RUNTIME_MS = envInt('JOB_MAX_RUNTIME_MS', 45 * 60 * 1000, 5 * 60 * 1000, 24 * 60 * 60 * 1000);
const MEMORY_WARN_HEAP_PERCENT = envInt('MEMORY_WARN_HEAP_PERCENT', 90, 50, 99);
const MEMORY_WARN_MIN_HEAP_TOTAL_MB = envInt('MEMORY_WARN_MIN_HEAP_TOTAL_MB', 256, 16, 8192);
const MEMORY_WARN_MIN_HEAP_USED_MB = envInt('MEMORY_WARN_MIN_HEAP_USED_MB', 192, 16, 8192);
const MEMORY_WARN_COOLDOWN_MS = envInt('MEMORY_WARN_COOLDOWN_MS', 30 * 60 * 1000, 60 * 1000, 24 * 60 * 60 * 1000);

const DOWNLOAD_ROOT = path.join(__dirname, 'downloads');
const JOB_DB_PATH = path.join(DOWNLOAD_ROOT, 'jobs-db.json');
const PERSIST_JOBS_ENABLED = envBoolean(process.env.PERSIST_JOBS, true);
const PERSIST_JOB_LIMIT = envInt('PERSIST_JOB_LIMIT', 0, 0, 100000);
const IMAGE_CLEANUP_ENABLED = envBoolean(process.env.IMAGE_CLEANUP_ENABLED, false);
const IMAGE_MAX_AGE_HOURS = envInt('IMAGE_MAX_AGE_HOURS', 24 * 30, 24, 24 * 3650);
const AUTO_RESUME_RESTORED_JOBS = envBoolean(process.env.AUTO_RESUME_RESTORED_JOBS, false);
const USE_PYTHON_BULK_ZIP = envBoolean(process.env.USE_PYTHON_BULK_ZIP, false);
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
  add(path.join(__dirname, '..', 'parts-extractor', '.venv', 'Scripts', 'python.exe'));
  add(path.join(__dirname, '..', 'parts-extractor', '.venv', 'bin', 'python'));

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
const PYTHON_BULK_ZIP_SCRIPT_PATH = path.join(__dirname, 'create_bulk_zip.py');
const BOTASAURUS_WORKER_PATH = path.join(__dirname, 'botasaurus_worker.py');
const BOTASAURUS_TASK_ROOT = path.join(__dirname, '.tmp', 'botasaurus-tasks');
const BOTASAURUS_TIMEOUT_SECONDS = Math.ceil(NAVIGATION_TIMEOUT_MS / 1000);

const eventClients = new Set();
const logClients = new Set();
const jobs = new Map();
const stopRequestedJobIds = new Set();
const deletedJobIds = new Set();
const deletedImageIdsByJob = new Map();
const logHistory = [];
const scrapeQueue = [];
const activeScrapeJobIds = new Set();
let activeScrapes = 0;
let lastPersistTime = 0;
let lastMemoryWarningAt = 0;
let cachedPythonRuntime; // undefined=not checked, null=unavailable, object=resolved
let cachedBotasaurusRuntime;
let cachedBulkZipPythonRuntime;
let pythonMissingLogged = false;
let activeBulkZipBuild = null;
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
        [...candidate.argsPrefix, '-c', 'import PIL; print("ok")'],
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
      `No Pillow-capable Python runtime found (${tried}). Image conversion disabled; original image URLs will not be stored as product images.`,
      'image',
      jobId
    );
    pythonMissingLogged = true;
  }
  return null;
}

async function resolveBulkZipPythonRuntime() {
  if (cachedBulkZipPythonRuntime !== undefined) return cachedBulkZipPythonRuntime;

  const venvPathFragment = `${path.sep}parts-extractor${path.sep}.venv${path.sep}`;
  const candidates = [
    ...PYTHON_CANDIDATES.filter((candidate) => !String(candidate.command).includes(venvPathFragment)),
    ...PYTHON_CANDIDATES
  ];

  for (const candidate of candidates) {
    if (path.isAbsolute(candidate.command) && !fs.existsSync(candidate.command)) continue;
    try {
      await execFileAsync(
        candidate.command,
        [...candidate.argsPrefix, '-c', 'import json, zipfile; print("ok")'],
        { timeout: 5000, maxBuffer: 1024 * 1024 }
      );
      cachedBulkZipPythonRuntime = candidate;
      return candidate;
    } catch {
      // try next candidate
    }
  }

  cachedBulkZipPythonRuntime = null;
  return null;
}

async function resolveBotasaurusRuntime(jobId = null) {
  if (cachedBotasaurusRuntime !== undefined) return cachedBotasaurusRuntime;

  for (const candidate of PYTHON_CANDIDATES) {
    if (path.isAbsolute(candidate.command) && !fs.existsSync(candidate.command)) continue;
    try {
      await execFileAsync(
        candidate.command,
        [...candidate.argsPrefix, '-c', 'import botasaurus, bs4'],
        { timeout: 10000, maxBuffer: 1024 * 1024 }
      );
      cachedBotasaurusRuntime = candidate;
      return candidate;
    } catch {
      // Try the next configured Python runtime.
    }
  }

  cachedBotasaurusRuntime = null;
  writeLog(
    'error',
    'Botasaurus runtime is unavailable. Install the Python requirements before resuming.',
    'scrape',
    jobId
  );
  return null;
}

async function runBotasaurusTask(action, rawUrl, jobId) {
  if (!['category', 'images', 'title'].includes(action)) {
    throw new Error(`Unsupported Botasaurus action: ${action}`);
  }
  if (!fs.existsSync(BOTASAURUS_WORKER_PATH)) {
    throw new Error('Botasaurus worker script is missing.');
  }

  const safeUrl = await validatePublicHttpUrl(rawUrl, { allowedHosts: SCRAPE_ALLOWED_HOSTS });
  const runtime = await resolveBotasaurusRuntime(jobId);
  if (!runtime) {
    throw new Error('Botasaurus runtime is unavailable.');
  }

  const taskId = `${String(jobId)}_${action}_${crypto.randomUUID()}`;
  const taskDir = resolveWithinRoot(BOTASAURUS_TASK_ROOT, taskId);
  const outputPath = resolveWithinRoot(taskDir, 'result.json');
  const profilePath = resolveWithinRoot(taskDir, 'profile');
  await fsp.mkdir(profilePath, { recursive: true });

  try {
    await execFileAsync(
      runtime.command,
      [
        ...runtime.argsPrefix,
        BOTASAURUS_WORKER_PATH,
        action,
        safeUrl,
        outputPath,
        profilePath,
        String(BOTASAURUS_TIMEOUT_SECONDS)
      ],
      {
        timeout: NAVIGATION_TIMEOUT_MS + CHALLENGE_WAIT_MS + 30000,
        maxBuffer: 10 * 1024 * 1024,
        windowsHide: true,
        env: {
          ...process.env,
          BOTASAURUS_HEADLESS: 'true'
        }
      }
    );

    const payload = JSON.parse(await fsp.readFile(outputPath, 'utf8'));
    if (!payload?.success) {
      throw new Error(payload?.error || 'Botasaurus extraction failed.');
    }
    return payload;
  } catch (err) {
    if (fs.existsSync(outputPath)) {
      try {
        const payload = JSON.parse(await fsp.readFile(outputPath, 'utf8'));
        if (payload?.error) throw new Error(payload.error);
      } catch (payloadError) {
        if (payloadError?.message && payloadError.message !== err.message) {
          throw payloadError;
        }
      }
    }
    throw err;
  } finally {
    await fsp.rm(taskDir, { recursive: true, force: true, maxRetries: 3, retryDelay: 200 }).catch(() => {});
  }
}

function tokenMatches(candidate) {
  const value = Buffer.from(String(candidate || ''));
  const expected = Buffer.from(APP_ACCESS_TOKEN);
  return value.length === expected.length && crypto.timingSafeEqual(value, expected);
}

function requestToken(req) {
  const authorization = String(req.get('authorization') || '');
  if (/^Bearer\s+/i.test(authorization)) return authorization.replace(/^Bearer\s+/i, '').trim();
  if (/^Basic\s+/i.test(authorization)) {
    try {
      const decoded = Buffer.from(authorization.replace(/^Basic\s+/i, ''), 'base64').toString('utf8');
      return decoded.includes(':') ? decoded.slice(decoded.indexOf(':') + 1) : decoded;
    } catch {
      return '';
    }
  }
  return String(req.get('x-api-key') || '');
}

app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'SAMEORIGIN');
  res.setHeader('Referrer-Policy', 'same-origin');
  res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');

  if (APP_ACCESS_TOKEN && !tokenMatches(requestToken(req))) {
    res.setHeader('WWW-Authenticate', 'Basic realm="Scraper", charset="UTF-8"');
    return res.status(401).json({ success: false, error: 'Authentication required' });
  }

  const origin = String(req.get('origin') || '').replace(/\/+$/, '');
  const forwardedProto = String(req.get('x-forwarded-proto') || '').split(',', 1)[0].trim();
  const forwardedHost = String(req.get('x-forwarded-host') || '').split(',', 1)[0].trim();
  const publicProtocol = forwardedProto || req.protocol;
  const publicHost = forwardedHost || req.get('host');
  const sameOrigin =
    !origin ||
    origin === `${req.protocol}://${req.get('host')}` ||
    origin === `${publicProtocol}://${publicHost}`;
  if (!sameOrigin && !CORS_ALLOWED_ORIGINS.has(origin)) {
    return res.status(403).json({ success: false, error: 'Origin is not allowed' });
  }
  if (origin) {
    res.header('Access-Control-Allow-Origin', origin);
    res.header('Vary', 'Origin');
  }
  res.header('Access-Control-Allow-Methods', 'GET,POST,DELETE,OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Authorization, Content-Type, X-API-Key, X-Confirm-Destructive, X-Requested-With');
  req.setTimeout(60000);

  if (req.method === 'OPTIONS') {
    return res.sendStatus(204);
  }
  next();
});

app.use(express.json({ limit: '100kb' }));
app.use(express.urlencoded({ extended: false, limit: '100kb' }));

app.param('id', (req, res, next, value) => {
  if (!isSafeJobId(value)) {
    return res.status(400).json({ success: false, error: 'Invalid job id' });
  }
  next();
});

function requireDestructiveConfirmation(req, res, next) {
  if (String(req.get('x-confirm-destructive') || '') !== DESTRUCTIVE_CONFIRMATION) {
    return res.status(428).json({
      success: false,
      error: 'Explicit destructive-action confirmation is required.'
    });
  }
  next();
}

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

function sanitizeDisplayName(value) {
  return String(value || '')
    .replace(/[\r\n\t]+/g, ' ')
    .replace(/[<>:"/\\|?*\x00-\x1F]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 120);
}

function normalizeSearchText(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function compactSearchText(value) {
  return normalizeSearchText(value).replace(/\s+/g, '');
}

function parseTitleFilterTerms(rawFilter) {
  const rawTerms = String(rawFilter || '')
    .split(/[\n,;|]+/)
    .map((term) => normalizeSearchText(term))
    .filter(Boolean);

  const terms = new Set(rawTerms);

  // MobileSentrix display products are not always titled "Display Assembly".
  // Expand that intent to common equivalent title wording used by parts suppliers.
  if (rawTerms.some((term) => /\bdisplay\b/.test(term) && /\bassembly\b/.test(term))) {
    [
      'display assembly',
      'screen assembly',
      'oled assembly',
      'lcd assembly',
      'soft oled assembly',
      'hard oled assembly',
      'soft assembly',
      'hard assembly',
      'incell assembly',
      'touch screen assembly',
      'digitizer assembly',
      'display lcd',
      'lcd screen',
      'oled screen',
    ].forEach((term) => terms.add(normalizeSearchText(term)));
  }

  return Array.from(terms);
}

function titleMatchesFilter(value, rawFilter) {
  const terms = parseTitleFilterTerms(rawFilter);
  if (!terms.length) return true;

  const haystack = normalizeSearchText(value);
  if (!haystack) return false;
  const compactHaystack = compactSearchText(value);

  return terms.some((term) => {
    const words = term.split(' ').filter(Boolean);
    if (!words.length) return false;
    if (words.every((word) => haystack.includes(word))) return true;
    const compactTerm = compactSearchText(term);
    return compactTerm.length > 1 && compactHaystack.includes(compactTerm);
  });
}

function productMatchesTitleFilter(product, rawFilter) {
  if (!rawFilter) return true;
  const haystack = [
    product?.name,
    product?.title,
    product?.product_url,
    product?.url,
  ].filter(Boolean).join(' ');
  if (!titleMatchesFilter(haystack, rawFilter)) return false;

  const normalizedHaystack = normalizeSearchText(haystack);
  const filterTerms = parseTitleFilterTerms(rawFilter).join(' ');
  const isDisplayFilter = /\b(display|screen|lcd|oled|amoled|digitizer|incell)\b/.test(filterTerms);
  if (!isDisplayFilter) return true;

  // A broad display filter can accidentally match parts like "LCD flex cable".
  // Keep complete screens/assemblies, but reject clearly separate components.
  return !/\b(screen protector|tempered glass|battery|charging port|charge port|camera|back glass|back cover|housing|speaker|microphone|sim tray|adhesive|sticker|repair tool|tool kit|case|flex cable|lcd flex|connector|board|motherboard|fingerprint|home button|earpiece|vibrator|antenna)\b/.test(normalizedHaystack);
}


function summarizeJob(job, includeProducts = false) {
  const summary = {
    id: String(job.id),
    url: String(job.url || ''),
    status: String(job.status || 'queued'),
    model: String(job.model || ''),
    folder_name: String(job.folder_name || ''),
    download_folder: String(job.download_folder || ''),
    title_filter: String(job.title_filter || ''),
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

function getDeletedImageIds(jobId) {
  const id = String(jobId);
  if (!deletedImageIdsByJob.has(id)) {
    deletedImageIdsByJob.set(id, new Set());
  }
  return deletedImageIdsByJob.get(id);
}

function filterDeletedImagesForJob(jobId, products = []) {
  if (!Array.isArray(products)) return [];
  const deletedIds = deletedImageIdsByJob.get(String(jobId));
  if (!deletedIds || deletedIds.size === 0) return products;

  return products.map((product) => {
    if (!product || !Array.isArray(product.images)) return product;
    return {
      ...product,
      images: product.images.filter((image) => !deletedIds.has(String(image?.id || '')))
    };
  });
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
      folder_name: '',
      download_folder: '',
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
let persistTimer = null;

function schedulePersistJobsDb({ immediate = false } = {}) {
  // Skip persistence if disabled
  if (!PERSIST_JOBS_ENABLED) return;

  const now = Date.now();
  const elapsed = now - lastPersistTime;
  if (!immediate && elapsed < PERSIST_INTERVAL_MS) {
    if (!persistTimer) {
      persistTimer = setTimeout(() => {
        persistTimer = null;
        schedulePersistJobsDb({ immediate: true });
      }, PERSIST_INTERVAL_MS - elapsed);
    }
    return;
  }
  if (persistTimer) {
    clearTimeout(persistTimer);
    persistTimer = null;
  }
  lastPersistTime = Date.now();

  persistPromise = persistPromise
    .then(async () => {
      try {
        await fsp.mkdir(DOWNLOAD_ROOT, { recursive: true });
        const sortedJobs = Array.from(jobs.values())
          .filter(job => !deletedJobIds.has(String(job.id)))
          .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
        const allJobs = retainJobs(sortedJobs, PERSIST_JOB_LIMIT)
          .map((job) => summarizeJob(job, true));

        const payload = {
          updated_at: nowIso(),
          jobs: allJobs
        };

        const tempPath = `${JOB_DB_PATH}.tmp`;
        const backupPath = `${JOB_DB_PATH}.bak`;
        if (fs.existsSync(JOB_DB_PATH)) {
          await fsp.copyFile(JOB_DB_PATH, backupPath).catch(() => {});
        }
        await fsp.writeFile(tempPath, JSON.stringify(payload, null, 2), 'utf8');
        await fsp.rename(tempPath, JOB_DB_PATH);
      } catch (err) {
        writeLog('error', `Failed to persist jobs DB: ${err.message}`, 'db');
      }
    });
}

function summarizeManifestJob(manifest, folderName) {
  const products = Array.isArray(manifest?.products) ? manifest.products : [];
  const imageCount = products.reduce(
    (sum, product) => sum + (Array.isArray(product?.images) ? product.images.length : 0),
    0
  );
  const totalItems = Number.isFinite(Number(manifest?.total_items))
    ? Number(manifest.total_items)
    : products.length;
  const processedItems = Number.isFinite(Number(manifest?.processed_items))
    ? Number(manifest.processed_items)
    : String(manifest?.status || '') === 'completed'
      ? totalItems
      : products.filter((product) => Array.isArray(product?.images) || Array.isArray(product?.source_images)).length;

  return {
    id: String(manifest?.job_id || folderName),
    url: String(manifest?.url || ''),
    status: String(manifest?.status || 'completed'),
    model: sanitizeDisplayName(manifest?.folder_name || manifest?.download_folder || folderName),
    folder_name: sanitizeDisplayName(manifest?.folder_name || manifest?.download_folder || folderName),
    download_folder: sanitizeDownloadFolderName(manifest?.download_folder || folderName, folderName),
    title_filter: String(manifest?.title_filter || ''),
    images: imageCount,
    total_items: totalItems,
    processed_items: processedItems,
    error: manifest?.error || null,
    products,
    stop_requested: false,
    pause_requested: false,
    created_at: manifest?.created_at || nowIso(),
    updated_at: manifest?.updated_at || manifest?.completed_at || nowIso()
  };
}

async function loadJobsFromManifests(reason = '') {
  const entries = await fsp.readdir(DOWNLOAD_ROOT, { withFileTypes: true }).catch(() => []);
  let restored = 0;
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const manifestPath = path.join(DOWNLOAD_ROOT, entry.name, 'manifest.json');
    if (!fs.existsSync(manifestPath)) continue;
    try {
      const manifest = JSON.parse(await fsp.readFile(manifestPath, 'utf8'));
      const job = summarizeManifestJob(manifest, entry.name);
      if (!job.id) continue;
      jobs.set(String(job.id), job);
      restored++;
    } catch (err) {
      writeLog('warning', `Could not restore manifest ${entry.name}: ${err.message}`, 'startup');
    }
  }
  if (restored > 0) {
    writeLog(
      'warning',
      `Rebuilt ${restored} job(s) from manifests${reason ? ` after ${reason}` : ''}`,
      'startup'
    );
    schedulePersistJobsDb({ immediate: true });
  }
  return restored;
}

async function loadPersistedJobs() {
  try {
    await fsp.mkdir(DOWNLOAD_ROOT, { recursive: true });
    if (!fs.existsSync(JOB_DB_PATH)) {
      await loadJobsFromManifests('missing jobs DB');
      return;
    }

    const raw = (await fsp.readFile(JOB_DB_PATH, 'utf8')).replace(/^\uFEFF/, '');
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed.jobs)) {
      await loadJobsFromManifests('invalid jobs DB shape');
      return;
    }

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
    await loadJobsFromManifests('jobs DB parse failure').catch((fallbackErr) => {
      writeLog('error', `Manifest restore fallback failed: ${fallbackErr.message}`, 'startup');
    });
  }
}

function recoverRestoredActiveJobs() {
  const restoredActiveJobs = Array.from(jobs.values()).filter((job) => {
    const status = String(job?.status || '');
    return ['queued', 'running'].includes(status) && job?.url;
  });

  for (const job of restoredActiveJobs) {
    const jobId = String(job.id);
    const folderName = sanitizeDisplayName(job.folder_name || job.model || '');
    const titleFilter = String(job.title_filter || '').trim();
    const downloadFolder = getJobDownloadFolderName(jobId, folderName || inferModelFromUrl(job.url));

    job.stop_requested = false;
    job.pause_requested = !AUTO_RESUME_RESTORED_JOBS;
    updateJob(jobId, {
      status: AUTO_RESUME_RESTORED_JOBS ? 'queued' : 'paused',
      error: AUTO_RESUME_RESTORED_JOBS ? null : 'Recovered after restart; waiting for manual resume.',
      pause_requested: !AUTO_RESUME_RESTORED_JOBS,
      folder_name: folderName,
      download_folder: downloadFolder,
      model: folderName || job.model || inferModelFromUrl(job.url)
    });
    if (AUTO_RESUME_RESTORED_JOBS) {
      writeLog('info', `Resuming restored job for ${job.url}`, 'queue', jobId);
      runScrapeJobInBackground({ jobId, url: job.url, folderName, titleFilter, downloadFolder });
    } else {
      writeLog('warning', `Recovered job is paused and ready for manual resume: ${job.url}`, 'queue', jobId);
    }
  }

  if (restoredActiveJobs.length > 0) {
    const action = AUTO_RESUME_RESTORED_JOBS ? 're-queued' : 'paused';
    writeLog('info', `${action} ${restoredActiveJobs.length} restored active job(s)`, 'startup');
    schedulePersistJobsDb({ immediate: true });
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
  const nextPatch = { ...patch };
  if (Array.isArray(nextPatch.products)) {
    nextPatch.products = filterDeletedImagesForJob(id, nextPatch.products);
    nextPatch.images = nextPatch.products.reduce(
      (sum, product) => sum + (Array.isArray(product?.images) ? product.images.length : 0),
      0
    );
  }
  Object.assign(job, nextPatch);
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
      const id = String(jobId);
      const queuedJob = jobs.get(id);
      if (queuedJob?.pause_requested || queuedJob?.status === 'paused') {
        updateJob(id, { status: 'paused' });
        scrapeQueue.push(start);
        setTimeout(processNextQueuedScrape, 2000);
        return;
      }

      activeScrapes++;
      activeScrapeJobIds.add(id);
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
        activeScrapeJobIds.delete(id);
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

function isTransientScrapeError(error) {
  const message = String(error?.message || error || '').toLowerCase();
  if (!message) return false;

  return [
    'timeout',
    'timed out',
    'navigation',
    'net::',
    'connection',
    'econnreset',
    'econnrefused',
    'etimedout',
    'socket hang up',
    'protocol error',
    'target closed',
    'browser disconnected',
    'page crashed',
    'temporarily unavailable',
    'too many requests',
    'http 429',
    'http 500',
    'http 502',
    'http 503',
    'http 504'
  ].some((needle) => message.includes(needle));
}

function withTimeout(promise, timeoutMs, label = 'Operation') {
  let timer = null;
  const timeoutPromise = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs}ms`)), timeoutMs);
    timer.unref?.();
  });

  return Promise.race([promise, timeoutPromise]).finally(() => {
    if (timer) clearTimeout(timer);
  });
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

function sanitizeDownloadFolderName(value, fallback = 'Scrape Job') {
  const cleaned = sanitizeDisplayName(value)
    .replace(/[. ]+$/g, '')
    .slice(0, 100);
  return cleaned || fallback;
}

function getJobDownloadFolderName(jobId, preferredName = '') {
  const id = String(jobId);
  const job = jobs.get(id);
  if (job?.download_folder) {
    return sanitizeDownloadFolderName(job.download_folder, `job_${sanitizeSegment(id, 'job')}`);
  }

  const name = sanitizeDownloadFolderName(
    preferredName || job?.folder_name || job?.model || `job_${id}`,
    `job_${sanitizeSegment(id, 'job')}`
  );
  return name;
}

function getJobDownloadDir(jobId, preferredName = '') {
  return path.join(DOWNLOAD_ROOT, getJobDownloadFolderName(jobId, preferredName));
}

function ensureJobDownloadMetadata(jobId, preferredName = '') {
  const id = String(jobId);
  const folder = getJobDownloadFolderName(id, preferredName);
  const job = jobs.get(id);
  if (job) {
    job.download_folder = folder;
    job.download_url = `/downloads/${encodeURIComponent(folder)}`;
  }
  return {
    folder,
    dir: path.join(DOWNLOAD_ROOT, folder),
    url: `/downloads/${encodeURIComponent(folder)}`
  };
}

function extensionFromUrl(value, fallback = '.jpg') {
  try {
    const pathname = new URL(value).pathname;
    const ext = path.extname(pathname).toLowerCase();
    if (/^\.(jpg|jpeg|png|webp|bmp|tiff|heic)$/.test(ext)) return ext;
  } catch {}
  return fallback;
}

function imageDedupeKey(value, baseUrl = '') {
  const absolute = toAbsoluteUrl(value, baseUrl || value);
  if (!absolute) return '';

  try {
    const parsed = new URL(absolute);
    parsed.hash = '';

    // MobileSentrix commonly exposes the same asset with cache/version query
    // variants. Keep the first real URL for download, but dedupe by asset path.
    if (parsed.pathname.match(/\.(jpg|jpeg|png|webp|bmp|tiff|heic)$/i)) {
      parsed.pathname = normalizeWordpressImageSizePath(parsed.pathname);
      parsed.search = '';
    } else {
      for (const key of ['v', 'ver', 'version', 'cache', 'ts', 'timestamp', 'width', 'height', 'w', 'h', 'q', 'quality']) {
        parsed.searchParams.delete(key);
      }
    }

    parsed.hostname = parsed.hostname.toLowerCase();
    return parsed.href;
  } catch {
    return absolute.split('#')[0].replace(/[?&](v|ver|version|cache|ts|timestamp|width|height|w|h|q|quality)=[^&]+/gi, '');
  }
}

function normalizeWordpressImageSizePath(pathname) {
  return String(pathname || '').replace(/-\d{2,5}x\d{2,5}(?=\.(?:jpe?g|png|webp)$)/i, '');
}

function normalizeProductImageSourceUrl(value) {
  const absolute = toAbsoluteUrl(value, value);
  if (!absolute) return '';

  try {
    const parsed = new URL(absolute);
    const pathname = parsed.pathname;
    const lowerPath = pathname.toLowerCase();

    if (!/\.(jpg|jpeg|png|webp|bmp|tiff|heic)$/i.test(lowerPath)) return '';
    const isMobileSentrixCatalogImage = lowerPath.includes('/catalog/product/');
    const isXcellUploadImage =
      parsed.hostname.toLowerCase().endsWith('xcellparts.com') &&
      lowerPath.includes('/wp-content/uploads/');
    if (!isMobileSentrixCatalogImage && !isXcellUploadImage) return '';
    if (lowerPath.includes('/thumbnail/')) return '';
    if (/\/(?:cache|placeholder|badge|badges|logo|logos|icon|icons)\//i.test(lowerPath)) return '';

    parsed.pathname = isXcellUploadImage
      ? normalizeWordpressImageSizePath(pathname)
      : pathname.replace(/\/catalog\/product\/small_image\//i, '/catalog/product/image/');
    parsed.hash = '';
    for (const key of ['width', 'height', 'w', 'h', 'q', 'quality', 'cache', 'ts', 'timestamp']) {
      parsed.searchParams.delete(key);
    }
    return parsed.href;
  } catch {
    return '';
  }
}

function buildExistingJobImageKeys(jobId) {
  const keys = new Set();
  const job = jobs.get(String(jobId));
  if (!job || !Array.isArray(job.products)) return keys;

  for (const product of job.products) {
    if (!product || !Array.isArray(product.images)) continue;
    for (const image of product.images) {
      const key = image?.source_dedupe_key || imageDedupeKey(image?.original_url || image?.url || '');
      if (key) keys.add(key);
    }
  }

  return keys;
}

function extractCatalogImageUrlsFromHtml(html, baseUrl = '') {
  if (!html || typeof html !== 'string') return [];

  const normalizedHtml = html
    .replace(/\\\//g, '/')
    .replace(/&quot;/g, '"')
    .replace(/&#x2F;/gi, '/')
    .replace(/&amp;/g, '&');

  const needle = '/catalog/product/image/';
  const separators = new Set(['"', "'", ' ', '\n', '\r', '\t', '<', '>', '(', ')', ',', ';']);
  const found = new Set();
  const galleryContextPattern = /(MagicZoom|MagicToolbox|MagicZoomPlusImage|product-img-box|product\.media|more-views|gallery|fotorama|og:image|image_src)/i;
  const nonProductAssetPattern = /(logo|brandmark|flag|country|canada|united[-_ ]?states|usa|all[-_ ]?colors|placeholder|favicon|apple-touch-icon|banner|sprite|icon)/i;

  let index = normalizedHtml.indexOf(needle);
  while (index !== -1) {
    let start = index;
    while (start > 0 && !separators.has(normalizedHtml[start - 1])) {
      start--;
    }

    let end = index + needle.length;
    while (end < normalizedHtml.length && !separators.has(normalizedHtml[end])) {
      end++;
    }

    let candidate = normalizedHtml.slice(start, end).trim();
    if (candidate) {
      const context = normalizedHtml.slice(Math.max(0, start - 500), Math.min(normalizedHtml.length, end + 500));
      const absolute = toAbsoluteUrl(candidate, baseUrl || 'https://www.mobilesentrix.com');
      if (
        absolute
        && absolute.includes('/catalog/product/image/')
        && galleryContextPattern.test(context)
        && !nonProductAssetPattern.test(`${absolute} ${context}`)
      ) {
        found.add(absolute);
      }
    }

    index = normalizedHtml.indexOf(needle, index + needle.length);
  }

  return Array.from(found);
}

async function extractImagesFromProductHtml(productUrl, jobId) {
  const normalizedUrl = toAbsoluteUrl(productUrl, productUrl);
  if (!normalizedUrl) return [];

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), IMAGE_HTTP_TIMEOUT_MS);

  try {
    const response = await fetchWithValidatedRedirects(normalizedUrl, {
      method: 'GET',
      signal: controller.signal,
      headers: {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'User-Agent':
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36'
      }
    }, {
      allowedHosts: SCRAPE_ALLOWED_HOSTS
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const html = await response.text();
    const urls = extractCatalogImageUrlsFromHtml(html, normalizedUrl);
    if (urls.length) {
      writeLog('info', `Recovered ${urls.length} image link(s) from direct HTML fetch: ${normalizedUrl}`, 'scrape', jobId);
    }
    return urls;
  } catch (err) {
    writeLog('warning', `Direct HTML image fallback failed for ${normalizedUrl}: ${err.message}`, 'scrape', jobId);
    return [];
  } finally {
    clearTimeout(timeout);
  }
}


function isSingleProductUrl(url) {
  if (!url || typeof url !== 'string') return false;

  try {
    const urlObj = new URL(url);
    const hostname = urlObj.hostname.toLowerCase();
    const pathname = urlObj.pathname.toLowerCase();
    const search = urlObj.search.toLowerCase();

    // MobileSentrix category/model trees must be scanned as categories.
    if (hostname.includes('mobilesentrix.') && pathname.includes('/replacement-parts/')) {
      return false;
    }
    if (/(^|\/)[a-z0-9-]+-series(\/|$)/i.test(pathname)) {
      return false;
    }
    if (/(category|collection|catalog|shop|browse|search|results|list|page)\//i.test(pathname)) {
      return false;
    }

    // Explicit single product patterns
    if (pathname.includes('/product/')) return true;
    if (/\/(p|item|sku|product-|view|details|product-detail|pd)\//i.test(pathname)) return true;
    if (/\/(products?|items?)\/(apple|samsung|iphone|galaxy|ipad|airpods|watch)-/i.test(pathname)) return true;

    // Product ID parameters
    if (search.includes('product_id=') || search.includes('?id=') || search.includes('?sku=') || search.includes('?item_id=')) {
      return true;
    }

    // Single numeric ID in pathname (e.g., /products/12345)
    if (/\/(products?|items?|listings?|offers?|deals?)\/\d+/.test(pathname)) {
      return true;
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


async function fetchImageBuffer(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), IMAGE_HTTP_TIMEOUT_MS);
  const parsed = (() => {
    try {
      return new URL(url);
    } catch {
      return null;
    }
  })();
  const hostname = parsed?.hostname || 'www.mobilesentrix.ca';
  const refererHost = hostname.startsWith('static.mobilesentrix.')
    ? hostname.replace('static.', 'www.')
    : hostname;

  try {
    const response = await fetchWithValidatedRedirects(url, {
      method: 'GET',
      signal: controller.signal,
      headers: {
        'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': `https://${refererHost}/`,
        'User-Agent':
          'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36'
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

function isExpectedImageAccessError(reason) {
  return /HTTP(?: error)?\s+(403|404|410|429)\b/i.test(String(reason || ''));
}

function isExpectedImageSkip(reason) {
  return (
    isExpectedImageAccessError(reason) ||
    /^Skipped non-product image:/i.test(String(reason || '')) ||
    /Python (script|runtime) not available/i.test(String(reason || ''))
  );
}

function formatPythonConversionError(err) {
  if (err?.killed || err?.signal) {
    return `Python conversion timed out or was killed after ${Math.round(IMAGE_CONVERT_TIMEOUT_MS / 1000)}s`;
  }
  if (/maxBuffer/i.test(String(err?.message || ''))) {
    return 'Python conversion output exceeded Node buffer';
  }
  return err?.message || 'Unknown Python conversion error';
}

async function convertImageToPythonPng(imageUrl, jobId, quality = 85) {
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
    const safeImageUrl = await validatePublicHttpUrl(imageUrl);
    const timeout = IMAGE_CONVERT_TIMEOUT_MS;

    // Execute Python script with timeout
    const { stdout } = await execFileAsync(
      pythonRuntime.command,
      [...pythonRuntime.argsPrefix, PYTHON_CONVERT_SCRIPT_PATH, safeImageUrl, String(quality), String(IMAGE_HTTP_TIMEOUT_MS / 1000)],
      { timeout, maxBuffer: 50 * 1024 * 1024 }
    );

    // Parse JSON response from Python
    const result = JSON.parse(stdout);

    if (!result.success) {
      const level = isExpectedImageAccessError(result.error) ? 'info' : 'warning';
      writeLog(level, `Python conversion skipped for ${imageUrl}: ${result.error}`, 'image', jobId);
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
      data: result.data,
      format: result.format || 'png',
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
      writeLog('warning', `Python image conversion error for ${imageUrl}: ${formatPythonConversionError(err)}`, 'image', jobId);
    }

    // Fallback: return URL for later processing
    return {
      success: true,
      data: null,
      url: imageUrl,
      converted: false,
      reason: `Python error: ${formatPythonConversionError(err)}`
    };
  }
}

async function saveImageFileForJob({ jobId, productName, productIndex, imageIndex, sourceUrl, converted }) {
  const folderMeta = ensureJobDownloadMetadata(jobId);
  await fsp.mkdir(folderMeta.dir, { recursive: true });

  const productPart = sanitizeSegment(productName, `product_${productIndex + 1}`).slice(0, 72).replace(/_+$/g, '');
  const imagePart = String(imageIndex + 1).padStart(3, '0');

  let buffer = null;
  let ext = '.jpg';
  let convertedOnDisk = false;

  if (converted?.data) {
    buffer = Buffer.from(converted.data, 'base64');
    ext = `.${String(converted.format || 'png').replace(/^\./, '')}`;
    convertedOnDisk = true;
  } else if (isExpectedImageSkip(converted?.reason)) {
    return {
      saved_to_disk: false,
      disk_converted: false,
      skipped_save: true,
      skip_reason: converted.reason,
      size: 0
    };
  } else {
    buffer = await fetchImageBuffer(sourceUrl);
    ext = extensionFromUrl(sourceUrl, '.jpg');
  }

  const fileName = `${String(productIndex + 1).padStart(2, '0')}_${productPart}_image_${imagePart}${ext}`;
  const filePath = path.join(folderMeta.dir, fileName);
  await fsp.writeFile(filePath, buffer);

  return {
    file_name: fileName,
    file_path: filePath,
    download_folder: folderMeta.folder,
    download_url: `${folderMeta.url}/${encodeURIComponent(fileName)}`,
    saved_to_disk: true,
    disk_converted: convertedOnDisk,
    size: buffer.length
  };
}

async function storeProductImagesInDb({ jobId, productName, productIndex, sourceImages }) {
  if (!Array.isArray(sourceImages) || sourceImages.length === 0) {
    return [];
  }

  const existingJobKeys = buildExistingJobImageKeys(jobId);
  const seenKeys = new Set(existingJobKeys);
  const uniqueSources = [];
  let duplicateCount = 0;
  let filteredCount = 0;

  for (const rawSourceUrl of sourceImages.filter(Boolean)) {
    const sourceUrl = normalizeProductImageSourceUrl(rawSourceUrl);
    if (!sourceUrl) {
      filteredCount++;
      continue;
    }
    const key = imageDedupeKey(sourceUrl);
    if (!key) continue;
    if (seenKeys.has(key)) {
      duplicateCount++;
      continue;
    }
    seenKeys.add(key);
    uniqueSources.push({ sourceUrl, sourceKey: key });
  }

  if (duplicateCount > 0) {
    writeLog(
      'info',
      `Skipped ${duplicateCount} duplicate image URL${duplicateCount !== 1 ? 's' : ''} for ${productName || `product ${productIndex + 1}`}`,
      'image',
      jobId
    );
  }

  if (filteredCount > 0) {
    writeLog(
      'info',
      `Skipped ${filteredCount} non-product image URL${filteredCount !== 1 ? 's' : ''} for ${productName || `product ${productIndex + 1}`}`,
      'image',
      jobId
    );
  }

  if (!uniqueSources.length) {
    return [];
  }

  // Convert images using Python concurrently for speed
  const conversions = await mapWithConcurrency(uniqueSources, IMAGE_DOWNLOAD_CONCURRENCY, async ({ sourceUrl, sourceKey }, index) => {
    try {
      const converted = await convertImageToPythonPng(sourceUrl, jobId);
      let fileMeta = {};
      try {
        fileMeta = await saveImageFileForJob({
          jobId,
          productName,
          productIndex,
          imageIndex: index,
          sourceUrl,
          converted
        });
      } catch (saveErr) {
        writeLog('warning', `Could not save image file for ${sourceUrl}: ${saveErr.message}`, 'image', jobId);
      }

      const keepInlineData = !fileMeta.saved_to_disk && converted.data;

      return {
        id: `${jobId}_${productIndex}_${index}`,
        url: sourceUrl,
        original_url: sourceUrl,
        source_dedupe_key: sourceKey,
        index: index + 1,
        product_index: productIndex,
        product_name: productName,
        created_at: nowIso(),
        image_data: keepInlineData ? converted.data : null,
        image_format: converted.format || (converted.converted ? 'png' : null),
        jpg_data: keepInlineData && converted.format === 'jpeg' ? converted.data : null,
        converted: converted.converted,
        size: converted.size || null,
        quality: converted.quality || null,
        error: converted.reason || null,
        ...fileMeta
      };
    } catch (err) {
      // Fallback: create image object without conversion
      return {
        id: `${jobId}_${productIndex}_${index}`,
        url: sourceUrl,
        original_url: sourceUrl,
        source_dedupe_key: imageDedupeKey(sourceUrl),
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

  return conversions.filter((image) => !image?.skipped_save);
}

function stripInlineImageDataFromProducts(products = []) {
  if (!Array.isArray(products)) return [];

  return products.map((product) => ({
    ...product,
    images: Array.isArray(product?.images)
      ? product.images.map((image) => ({
          ...image,
          image_data: undefined,
          jpg_data: undefined
        }))
      : []
  }));
}

async function writeJobManifest(jobId, payload) {
  const jobDir = getJobDownloadDir(jobId, payload?.folder_name || payload?.model || '');
  await fsp.mkdir(jobDir, { recursive: true });
  const manifestPath = path.join(jobDir, 'manifest.json');
  const tempPath = `${manifestPath}.tmp`;
  const backupPath = `${manifestPath}.bak`;
  const products = filterDeletedImagesForJob(jobId, payload?.products);
  if (fs.existsSync(manifestPath)) {
    await fsp.copyFile(manifestPath, backupPath).catch(() => {});
  }
  await fsp.writeFile(
    tempPath,
    JSON.stringify({ ...payload, products: stripInlineImageDataFromProducts(products) }, null, 2),
    'utf8'
  );
  await fsp.rename(tempPath, manifestPath);
}

async function waitWhileJobPaused(jobId) {
  const id = String(jobId);
  while (jobs.get(id)?.pause_requested) {
    writeLog('info', 'Job paused; waiting for resume...', 'scrape', id);
    await sleep(2000);
    const job = jobs.get(id);
    if (deletedJobIds.has(id) || stopRequestedJobIds.has(id) || job?.stop_requested) {
      throw new Error('Stopped by user');
    }
  }
}

function assertJobCanContinue(jobId) {
  const id = String(jobId);
  const job = jobs.get(id);
  if (deletedJobIds.has(id) || stopRequestedJobIds.has(id) || job?.stop_requested) {
    throw new Error('Stopped by user');
  }
}

async function checkpointImageJob(jobId, details) {
  const products = Array.isArray(details.products) ? details.products : [];
  updateJob(jobId, {
    processed_items: products.length,
    total_items: details.totalItems,
    images: details.imageCount,
    products
  });
  await writeJobManifest(jobId, {
    job_id: jobId,
    url: details.url,
    folder_name: details.folderName,
    download_folder: details.downloadFolder,
    status: 'running',
    created_at: jobs.get(String(jobId))?.created_at || nowIso(),
    updated_at: nowIso(),
    products
  });
}

async function scrapeWithBotasaurus(url, jobId, options = {}) {
  const titleFilter = String(options.titleFilter || '').trim();
  const folderName = sanitizeDisplayName(options.folderName || '');
  const downloadMeta = ensureJobDownloadMetadata(jobId, folderName || inferModelFromUrl(url));
  const existingProducts = Array.isArray(jobs.get(String(jobId))?.products)
    ? jobs.get(String(jobId)).products
    : [];
  const singleProduct = isSingleProductUrl(url);

  writeLog('info', 'Browser engine: headless Botasaurus', 'scrape', jobId);

  let products;
  if (singleProduct) {
    products = [{
      name: inferModelFromUrl(url),
      price: '',
      product_url: url,
      img: '',
      images: [],
      source_images: []
    }];
  } else {
    const categoryResult = await runBotasaurusTask('category', url, jobId);
    products = Array.isArray(categoryResult.products) ? categoryResult.products : [];
  }

  if (titleFilter) {
    products = products.filter((product) => productMatchesTitleFilter(product, titleFilter));
  }

  const checkpointByUrl = new Map(
    existingProducts
      .filter((product) => product?.product_url)
      .map((product) => [String(product.product_url), product])
  );
  let restoredCount = 0;
  for (const product of products) {
    const checkpoint = checkpointByUrl.get(String(product.product_url || ''));
    if (!checkpoint) continue;
    Object.assign(product, checkpoint, { checkpoint_complete: true });
    restoredCount++;
  }

  updateJob(jobId, {
    status: 'running',
    folder_name: folderName,
    download_folder: downloadMeta.folder,
    model: folderName || inferModelFromUrl(url),
    total_items: products.length,
    processed_items: restoredCount,
    images: existingProducts.reduce(
      (sum, product) => sum + (Array.isArray(product?.images) ? product.images.length : 0),
      0
    ),
    error: null,
    products: existingProducts
  });

  writeLog('info', `Found ${products.length} product(s)`, 'scrape', jobId);
  if (restoredCount) {
    writeLog('info', `Reusing ${restoredCount} durable product checkpoint(s)`, 'scrape', jobId);
  }

  let downloadedCount = 0;
  for (let index = 0; index < products.length; index++) {
    assertJobCanContinue(jobId);
    await waitWhileJobPaused(jobId);

    const product = products[index];
    if (product.checkpoint_complete) {
      delete product.checkpoint_complete;
      downloadedCount += Array.isArray(product.images) ? product.images.length : 0;
      await checkpointImageJob(jobId, {
        url,
        folderName,
        downloadFolder: downloadMeta.folder,
        products: products.slice(0, index + 1),
        totalItems: products.length,
        imageCount: downloadedCount
      });
      continue;
    }

    writeLog(
      'info',
      `Processing ${index + 1}/${products.length}: ${product.name || product.product_url}`,
      'scrape',
      jobId
    );
    await sleep(randomInt(PRODUCT_DELAY_MIN_MS, PRODUCT_DELAY_MAX_MS));

    let sourceImages = [];
    try {
      const imageResult = await runBotasaurusTask('images', product.product_url, jobId);
      sourceImages = Array.isArray(imageResult.images) ? imageResult.images : [];
    } catch (err) {
      writeLog(
        'warning',
        `Botasaurus image extraction failed for ${product.product_url}: ${err.message}`,
        'scrape',
        jobId
      );
    }

    if (!sourceImages.length) {
      sourceImages = await extractImagesFromProductHtml(product.product_url, jobId);
    }

    if (!sourceImages.length && product.img) {
      const fallbackImage = toAbsoluteUrl(product.img, product.product_url || url);
      if (fallbackImage && !fallbackImage.startsWith('data:') && !/\.(gif|svg)(\?|$)/i.test(fallbackImage)) {
        sourceImages = [fallbackImage];
      }
    }

    product.source_images = sourceImages;
    try {
      product.images = await storeProductImagesInDb({
        jobId,
        productName: product.name,
        productIndex: index,
        sourceImages
      });
    } catch (err) {
      product.images = [];
      product.error = err.message;
      writeLog('error', `Image storage failed for ${product.product_url}: ${err.message}`, 'image', jobId);
    }

    downloadedCount += product.images.length;
    await checkpointImageJob(jobId, {
      url,
      folderName,
      downloadFolder: downloadMeta.folder,
      products: products.slice(0, index + 1),
      totalItems: products.length,
      imageCount: downloadedCount
    });
    writeLog(
      'success',
      `Checkpointed ${product.images.length} image(s) for ${product.name || product.product_url}`,
      'image',
      jobId
    );
  }

  return products;
}

async function scrape(url, jobId, options = {}) {
  return scrapeWithBotasaurus(url, jobId, options);
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

app.get('/jobs/bulk/zip', async (req, res) => {
  const rootFolderName = sanitizeDownloadFolderName(req.query.folder || 'Bulk Jobs', 'Bulk Jobs');
  const includeFailed = String(req.query.include_failed || 'true').toLowerCase() !== 'false';
  const includeRunning = String(req.query.include_running || 'true').toLowerCase() !== 'false';
  const folderEntries = [];
  const seenFolders = new Set();

  for (const job of Array.from(jobs.values()).sort((a, b) => {
    return new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime();
  })) {
    const jobId = String(job.id || '');
    if (!jobId || deletedJobIds.has(jobId)) continue;

    const status = String(job.status || '');
    if (status === 'failed' && !includeFailed) continue;
    if (['running', 'queued', 'paused'].includes(status) && !includeRunning) continue;

    const folderName = getJobDownloadFolderName(jobId, job.folder_name || job.model || jobId);
    if (seenFolders.has(folderName)) continue;

    const dirPath = path.join(DOWNLOAD_ROOT, folderName);
    try {
      const stat = await fsp.stat(dirPath);
      if (!stat.isDirectory()) continue;
    } catch {
      continue;
    }

    const imageCount = Number(job.images || 0);
    if (imageCount <= 0) continue;
    seenFolders.add(folderName);
    folderEntries.push({ folderName, dirPath });
  }

  if (!folderEntries.length) {
    return res.status(404).json({ success: false, error: 'No downloaded bulk job folders found' });
  }

  const archiveName = `${sanitizeSegment(rootFolderName, 'bulk_jobs')}.zip`;
  const cacheDir = path.join(DOWNLOAD_ROOT, '.bulk-cache');
  const tempZipPath = path.join(cacheDir, archiveName);
  const tempBuildPath = `${tempZipPath}.building`;
  const folderListPath = path.join(cacheDir, `${path.basename(archiveName, '.zip')}.folders.json`);
  const latestFolderMtime = Math.max(
    ...folderEntries.map((entry) => {
      try {
        return fs.statSync(entry.dirPath).mtimeMs;
      } catch {
        return 0;
      }
    })
  );

  const collectManifestFilesForBulkZip = async () => {
    const filesToArchive = [];
    const seenArchivePaths = new Set();

    for (const entry of folderEntries) {
      const manifestPath = path.join(entry.dirPath, 'manifest.json');
      let manifest = null;
      try {
        manifest = JSON.parse(await fsp.readFile(manifestPath, 'utf8'));
      } catch {
        manifest = null;
      }

      const products = Array.isArray(manifest?.products) ? manifest.products : [];
      for (const product of products) {
        const images = Array.isArray(product?.images) ? product.images : [];
        for (const image of images) {
          const rawFileName = String(image?.file_name || '').trim();
          const candidatePath = image?.file_path
            ? path.resolve(String(image.file_path))
            : path.resolve(entry.dirPath, rawFileName);
          if (!candidatePath || !candidatePath.startsWith(`${path.resolve(entry.dirPath)}${path.sep}`)) {
            continue;
          }
          try {
            const stat = await fsp.stat(candidatePath);
            if (!stat.isFile() || stat.size <= 0) continue;
            const relative = path.relative(entry.dirPath, candidatePath).split(path.sep).join('/');
            const archivePath = `${rootFolderName}/${entry.folderName}/${relative}`;
            if (seenArchivePaths.has(archivePath)) continue;
            seenArchivePaths.add(archivePath);
            filesToArchive.push({ filePath: candidatePath, archivePath, size: stat.size });
          } catch {
            // Skip manifest records whose image file is no longer on disk.
          }
        }
      }
    }

    return filesToArchive;
  };

  const useCachedBulkZip = ['1', 'true'].includes(String(req.query.cache || '').toLowerCase());
  if (!useCachedBulkZip) {
    try {
      const filesToArchive = await collectManifestFilesForBulkZip();
      if (!filesToArchive.length) {
        return res.status(404).json({ success: false, error: 'No saved image files found for bulk ZIP' });
      }

      const totalBytes = filesToArchive.reduce((sum, file) => sum + file.size, 0);
      if (req.query.prepare === '1' || req.query.prepare === 'true') {
        return res.json({
          success: true,
          ready: true,
          streaming: true,
          filename: archiveName,
          folders: folderEntries.length,
          file_count: filesToArchive.length,
          size: totalBytes,
          size_mb: Math.round((totalBytes / (1024 * 1024)) * 100) / 100,
          url: `/jobs/bulk/zip?folder=${encodeURIComponent(rootFolderName)}`
        });
      }

      res.setHeader('Content-Type', 'application/zip');
      res.setHeader('Content-Disposition', `attachment; filename="${archiveName}"`);
      writeLog('info', `Streaming Bulk ZIP with ${filesToArchive.length} image file(s)`, 'jobs');

      await new Promise((resolve, reject) => {
        const archive = archiver('zip', { store: true });
        let queuedCount = 0;
        let completed = false;

        const fail = (err) => {
          if (completed) return;
          completed = true;
          reject(err);
        };

        res.on('finish', () => {
          completed = true;
          resolve();
        });
        res.on('close', () => {
          if (!completed) {
            archive.abort();
            fail(new Error('Bulk ZIP client disconnected'));
          }
        });
        archive.on('error', fail);
        archive.on('warning', (err) => {
          writeLog('warning', `Bulk ZIP warning: ${err.message}`, 'jobs');
        });

        archive.pipe(res);
        for (const file of filesToArchive) {
          archive.file(file.filePath, { name: file.archivePath });
          queuedCount++;
          if (queuedCount % 1000 === 0) {
            writeLog('info', `Queued ${queuedCount}/${filesToArchive.length} image file(s) for streamed Bulk ZIP`, 'jobs');
          }
        }
        Promise.resolve(archive.finalize()).catch(fail);
      });
      writeLog('info', `Bulk ZIP stream completed with ${folderEntries.length} folder(s)`, 'jobs');
      return;
    } catch (err) {
      writeLog('error', `Bulk ZIP stream failed: ${err.message}`, 'jobs');
      if (!res.headersSent) {
        return res.status(500).json({ success: false, error: `Bulk ZIP stream failed: ${err.message}` });
      }
      return;
    }
  }

  const hasFreshZip = async () => {
    try {
      const zipStat = await fsp.stat(tempZipPath);
      return zipStat.mtimeMs >= latestFolderMtime && zipStat.size > 0;
    } catch {
      return false;
    }
  };

  const buildBulkZip = async () => {
    await fsp.mkdir(cacheDir, { recursive: true });
    await fsp.rm(tempBuildPath, { force: true }).catch(() => {});
    writeLog('info', `Building Bulk ZIP with ${folderEntries.length} folder(s)`, 'jobs');

    const buildWithNode = async () => {
      const filesToArchive = [];
      const seenArchivePaths = new Set();

      for (const entry of folderEntries) {
        const manifestPath = path.join(entry.dirPath, 'manifest.json');
        let manifest = null;
        try {
          manifest = JSON.parse(await fsp.readFile(manifestPath, 'utf8'));
        } catch {
          manifest = null;
        }

        const products = Array.isArray(manifest?.products) ? manifest.products : [];
        for (const product of products) {
          const images = Array.isArray(product?.images) ? product.images : [];
          for (const image of images) {
            const candidatePath = image?.file_path
              ? path.resolve(String(image.file_path))
              : path.resolve(entry.dirPath, String(image?.file_name || ''));
            if (!candidatePath || !candidatePath.startsWith(`${path.resolve(entry.dirPath)}${path.sep}`)) {
              continue;
            }
            try {
              const stat = await fsp.stat(candidatePath);
              if (!stat.isFile() || stat.size <= 0) continue;
            } catch {
              continue;
            }

            const relative = path.relative(entry.dirPath, candidatePath).split(path.sep).join('/');
            const archivePath = `${rootFolderName}/${entry.folderName}/${relative}`;
            if (seenArchivePaths.has(archivePath)) continue;
            seenArchivePaths.add(archivePath);
            filesToArchive.push({ filePath: candidatePath, archivePath });
          }
        }
      }

      if (!filesToArchive.length) {
        throw new Error('No manifest-listed image files found for bulk ZIP');
      }

      writeLog('info', `Adding ${filesToArchive.length} image file(s) to Bulk ZIP`, 'jobs');
      await new Promise((resolve, reject) => {
        const output = fs.createWriteStream(tempBuildPath);
        const archive = archiver('zip', { store: true });
        let queuedCount = 0;
        output.on('close', resolve);
        output.on('error', reject);
        archive.on('error', reject);
        archive.pipe(output);
        for (const file of filesToArchive) {
          archive.file(file.filePath, { name: file.archivePath });
          queuedCount++;
          if (queuedCount % 500 === 0) {
            writeLog('info', `Queued ${queuedCount}/${filesToArchive.length} image file(s) for Bulk ZIP`, 'jobs');
          }
        }
        archive.finalize().catch(reject);
      });
      await fsp.rename(tempBuildPath, tempZipPath);
      const zipStat = await fsp.stat(tempZipPath);
      writeLog('info', `Bulk ZIP built with Node fallback (${Math.round((zipStat.size / (1024 * 1024)) * 100) / 100}MB)`, 'jobs');
    };

    const pythonRuntime = USE_PYTHON_BULK_ZIP ? await resolveBulkZipPythonRuntime() : null;
    if (USE_PYTHON_BULK_ZIP && fs.existsSync(PYTHON_BULK_ZIP_SCRIPT_PATH) && pythonRuntime) {
      try {
        await fsp.writeFile(
          folderListPath,
          JSON.stringify(folderEntries.map((entry) => entry.folderName)),
          'utf8'
        );
        const { stdout } = await execFileAsync(
          pythonRuntime.command,
          [
            ...pythonRuntime.argsPrefix,
            PYTHON_BULK_ZIP_SCRIPT_PATH,
            DOWNLOAD_ROOT,
            tempBuildPath,
            rootFolderName,
            '--folders-json',
            folderListPath
          ],
          { timeout: 2 * 60 * 60 * 1000, maxBuffer: 20 * 1024 * 1024 }
        );
        const result = JSON.parse(stdout);
        if (!result.success) {
          throw new Error(result.error || 'Python bulk ZIP failed');
        }
        await fsp.rename(tempBuildPath, tempZipPath);
        writeLog('info', `Bulk ZIP built (${result.file_count} file(s), ${result.size_mb}MB)`, 'jobs');
        return;
      } catch (err) {
        await fsp.rm(tempBuildPath, { force: true }).catch(() => {});
        writeLog('warning', `Python bulk ZIP failed, using Node fallback: ${err.message}`, 'jobs');
      }
    }

    await buildWithNode();
  };

  const startBulkZipBuild = () => {
    const buildPromise = buildBulkZip();
    activeBulkZipBuild = { path: tempZipPath, promise: buildPromise, startedAt: Date.now() };
    buildPromise
      .catch((err) => {
        writeLog('error', `Bulk ZIP failed: ${err.message}`, 'jobs');
        fsp.rm(tempBuildPath, { force: true }).catch(() => {});
      })
      .finally(() => {
        if (activeBulkZipBuild?.promise === buildPromise) {
          activeBulkZipBuild = null;
        }
      });
    return buildPromise;
  };

  if (req.query.prepare === '1' || req.query.prepare === 'true') {
    if (!(await hasFreshZip())) {
      if (!activeBulkZipBuild) {
        startBulkZipBuild();
      }
      return res.status(202).json({
        success: true,
        preparing: true,
        filename: archiveName,
        folders: folderEntries.length,
        message: 'Bulk ZIP is being prepared'
      });
    }
  }

  try {
    while (!(await hasFreshZip())) {
      if (activeBulkZipBuild) {
        writeLog('info', 'Bulk ZIP is already building; waiting for active build', 'jobs');
        await activeBulkZipBuild.promise;
        continue;
      }

      await startBulkZipBuild();
    }
  } catch (err) {
    writeLog('error', `Bulk ZIP failed: ${err.message}`, 'jobs');
    await fsp.rm(tempBuildPath, { force: true }).catch(() => {});
    if (!res.headersSent) {
      return res.status(500).json({ success: false, error: `Bulk ZIP failed: ${err.message}` });
    }
    return;
  }

  const zipStat = await fsp.stat(tempZipPath);
  if (req.query.prepare === '1' || req.query.prepare === 'true') {
    return res.json({
      success: true,
      filename: archiveName,
      folders: folderEntries.length,
      size: zipStat.size,
      size_mb: Math.round((zipStat.size / (1024 * 1024)) * 100) / 100,
      url: `/jobs/bulk/zip?folder=${encodeURIComponent(rootFolderName)}`
    });
  }

  res.setHeader('Content-Type', 'application/zip');
  res.setHeader('Content-Disposition', `attachment; filename="${archiveName}"`);
  res.setHeader('Content-Length', zipStat.size);
  res.on('finish', () => {
    writeLog('info', `Bulk ZIP download completed with ${folderEntries.length} folder(s)`, 'jobs');
  });
  fs.createReadStream(tempZipPath).pipe(res);
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
  const folderName = getJobDownloadFolderName(jobId, job?.folder_name || job?.model || `job_${safeJobId}`);
  const jobDir = path.join(DOWNLOAD_ROOT, folderName);

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

  const baseName = sanitizeSegment(folderName || job?.model || `job_${safeJobId}`, `job_${safeJobId}`).slice(0, 80) || `job_${safeJobId}`;
  const filename = `${baseName}.zip`;
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
      archive.directory(jobDir, folderName);

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
      archive.directory(jobDir, folderName);
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
            folder_name: job.folder_name || '',
            download_folder: job.download_folder || '',
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

  if (foundImage.file_path && fs.existsSync(foundImage.file_path)) {
    const ext = path.extname(foundImage.file_path).toLowerCase();
    const contentType = ext === '.png'
      ? 'image/png'
      : ext === '.webp'
        ? 'image/webp'
        : 'image/jpeg';
    res.setHeader('Content-Type', contentType);
    if (foundImage.file_name) {
      res.setHeader('Content-Disposition', `inline; filename="${String(foundImage.file_name).replace(/"/g, '')}"`);
    }
    res.setHeader('Cache-Control', 'public, max-age=86400');
    return fs.createReadStream(foundImage.file_path).pipe(res);
  }

  // If converted image data is stored, serve it directly.
  const encodedImageData = foundImage.image_data || foundImage.jpg_data;
  if (encodedImageData && foundImage.converted) {
    try {
      const imageBuffer = Buffer.from(encodedImageData, 'base64');
      const format = String(foundImage.image_format || (foundImage.jpg_data ? 'jpeg' : 'png')).toLowerCase();
      const contentType = format === 'png' ? 'image/png' : 'image/jpeg';
      res.setHeader('Content-Type', contentType);
      if (foundImage.file_name) {
        res.setHeader('Content-Disposition', `inline; filename="${String(foundImage.file_name).replace(/"/g, '')}"`);
      }
      res.setHeader('Content-Length', imageBuffer.length);
      res.setHeader('Cache-Control', 'public, max-age=86400');
      return res.send(imageBuffer);
    } catch (err) {
      writeLog('warning', `Failed to decode converted image data for image ${imageId}: ${err.message}`, 'image', jobId);
    }
  }

  // If no converted data, return metadata and redirect to original URL
  res.json({
    success: true,
    image: {
      ...foundImage,
      image_data: undefined,
      jpg_data: undefined
    },
    converted: foundImage.converted,
    original_url: foundImage.original_url
  });
});

app.delete('/jobs/:id/images/:imageId', requireDestructiveConfirmation, async (req, res) => {
  const jobId = String(req.params.id);
  const imageId = String(req.params.imageId);

  if (deletedJobIds.has(jobId)) {
    return res.status(404).json({ success: false, error: 'Job not found' });
  }

  const job = jobs.get(jobId);
  if (!job) {
    return res.status(404).json({ success: false, error: 'Job not found' });
  }

  let removedImage = null;
  let removed = false;

  if (Array.isArray(job.products)) {
    for (const product of job.products) {
      if (!product || !Array.isArray(product.images)) continue;
      const before = product.images.length;
      product.images = product.images.filter((image) => {
        const matches = String(image?.id || '') === imageId;
        if (matches) removedImage = image;
        return !matches;
      });
      if (product.images.length !== before) {
        removed = true;
        break;
      }
    }
  }

  if (!removed) {
    return res.status(404).json({ success: false, error: 'Image not found' });
  }

  getDeletedImageIds(jobId).add(imageId);

  if (removedImage?.file_path) {
    try {
      const resolvedFile = resolveWithinRoot(DOWNLOAD_ROOT, String(removedImage.file_path));
      if (resolvedFile !== path.resolve(DOWNLOAD_ROOT) && fs.existsSync(resolvedFile)) {
        await fsp.unlink(resolvedFile);
      }
    } catch (err) {
      writeLog('warning', `Failed to delete image file ${imageId}: ${err.message}`, 'image', jobId);
    }
  }

  job.images = Array.isArray(job.products)
    ? job.products.reduce((sum, product) => sum + (Array.isArray(product?.images) ? product.images.length : 0), 0)
    : 0;
  job.updated_at = nowIso();

  try {
    await writeJobManifest(jobId, {
      job_id: jobId,
      url: job.url,
      folder_name: job.folder_name || '',
      download_folder: job.download_folder || '',
      status: job.status || 'completed',
      created_at: job.created_at || nowIso(),
      updated_at: job.updated_at,
      products: job.products || []
    });
  } catch (err) {
    writeLog('warning', `Failed to update manifest after image delete: ${err.message}`, 'image', jobId);
  }

  emitJobUpdate(jobId);
  schedulePersistJobsDb({ immediate: true });
  writeLog('info', `Deleted image ${imageId}`, 'image', jobId);

  res.json({ success: true, job_id: jobId, image_id: imageId, images: job.images });
});

app.delete('/jobs/:id', requireDestructiveConfirmation, async (req, res) => {
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
    const downloadDir = resolveWithinRoot(
      DOWNLOAD_ROOT,
      job?.download_folder
        ? sanitizeDownloadFolderName(job.download_folder, jobId)
        : jobId
    );
    await fsp.rm(downloadDir, { recursive: true, force: true });
    const legacyDownloadDir = resolveWithinRoot(DOWNLOAD_ROOT, jobId);
    if (downloadDir !== legacyDownloadDir) {
      await fsp.rm(legacyDownloadDir, { recursive: true, force: true });
    }
  } catch (err) {
    writeLog('warning', `Failed to delete files for job ${jobId}: ${err.message}`, 'jobs', jobId);
  }

  schedulePersistJobsDb();
  res.json({ success: true });
});

app.post('/jobs/reset', requireDestructiveConfirmation, async (req, res) => {
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

app.post('/jobs/:id/pause', (req, res) => {
  const jobId = String(req.params.id);
  const job = jobs.get(jobId);
  if (!job) {
    return res.status(404).json({ success: false, error: 'Job not found' });
  }

  const status = String(job.status || '');
  if (!['running', 'queued', 'paused'].includes(status)) {
    return res.status(409).json({ success: false, error: `Cannot pause ${status || 'unknown'} job` });
  }

  job.pause_requested = true;
  updateJob(jobId, { status: 'paused', pause_requested: true });
  writeLog('info', 'Paused job', 'jobs', jobId);
  res.json({ success: true, job_id: jobId, status: 'paused' });
});

app.post('/jobs/:id/resume', async (req, res) => {
  const jobId = String(req.params.id);
  const job = jobs.get(jobId);
  if (!job) {
    return res.status(404).json({ success: false, error: 'Job not found' });
  }

  if (!['paused', 'failed'].includes(String(job.status || ''))) {
    return res.status(409).json({ success: false, error: 'Only paused or failed jobs can be resumed' });
  }

  let safeUrl;
  try {
    safeUrl = await validatePublicHttpUrl(job.url, { allowedHosts: SCRAPE_ALLOWED_HOSTS });
  } catch (err) {
    return res.status(400).json({ success: false, error: `Saved job URL is invalid: ${err.message}` });
  }

  const isAttachedToWorker = activeScrapeJobIds.has(jobId);
  const nextStatus = isAttachedToWorker ? 'running' : 'queued';
  updateJob(jobId, {
    status: nextStatus,
    pause_requested: false,
    stop_requested: false,
    error: null
  });
  writeLog('info', 'Resumed job', 'jobs', jobId);
  if (isAttachedToWorker) {
    processNextQueuedScrape();
  } else {
    const folderName = sanitizeDisplayName(job.folder_name || job.model || '');
    const titleFilter = String(job.title_filter || '').trim();
    const downloadFolder = getJobDownloadFolderName(jobId, folderName || inferModelFromUrl(safeUrl));
    runScrapeJobInBackground({
      jobId,
      url: safeUrl,
      folderName,
      titleFilter,
      downloadFolder
    });
  }
  res.json({ success: true, job_id: jobId, status: nextStatus });
});

function runScrapeJobInBackground({ jobId, url, folderName, titleFilter, downloadFolder }) {
  executeWithScrapeSlot(jobId, async () => {
    updateJob(jobId, { status: 'running', error: null });
    writeLog('info', `Scrape started for ${url}`, 'scrape', jobId);

    let lastError = null;
    for (let attempt = 0; attempt <= SCRAPE_TRANSIENT_RETRIES; attempt++) {
      try {
        if (attempt > 0) {
          updateJob(jobId, { status: 'running', error: null });
          writeLog('info', `Retrying scrape (${attempt}/${SCRAPE_TRANSIENT_RETRIES})`, 'scrape', jobId);
        }
        return await scrape(url, jobId, { titleFilter, folderName });
      } catch (err) {
        lastError = err;
        const canRetry = attempt < SCRAPE_TRANSIENT_RETRIES && isTransientScrapeError(err);
        if (!canRetry) throw err;

        const delayMs = 2000 * (attempt + 1);
        writeLog(
          'info',
          `Transient scrape error; retrying in ${Math.round(delayMs / 1000)}s: ${err.message}`,
          'scrape',
          jobId
        );
        await sleep(delayMs);
      }
    }

    throw lastError || new Error('Scrape failed');
  })
    .then(async (products) => {
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
        folder_name: folderName,
        download_folder: downloadFolder,
        model: folderName || currentJob?.model || inferModelFromUrl(url),
        products,
        processed_items: products.length,
        total_items: products.length,
        images: products.reduce((sum, product) => sum + (Array.isArray(product.images) ? product.images.length : 0), 0)
      });

      if (!deletedJobIds.has(jobId)) {
        await writeJobManifest(jobId, {
          job_id: jobId,
          url,
          folder_name: folderName,
          download_folder: downloadFolder,
          status,
          created_at: currentJob?.created_at || nowIso(),
          completed_at: nowIso(),
          products
        });
      }

      if (stopped) {
        writeLog('warning', 'Scrape stopped before completion', 'scrape', jobId);
        return;
      }

      writeLog('success', `Scrape completed. ${products.length} products processed.`, 'scrape', jobId);
    })
    .catch((err) => {
      const stopped =
        deletedJobIds.has(jobId) ||
        stopRequestedJobIds.has(jobId) ||
        /stopped by user/i.test(String(err?.message || ''));
      if (stopped) {
        updateJob(jobId, { status: 'failed', error: 'Stopped by user' });
        const stoppedJob = jobs.get(jobId);
        if (stoppedJob) {
          writeJobManifest(jobId, {
            job_id: jobId,
            url,
            folder_name: folderName,
            download_folder: downloadFolder,
            status: 'failed',
            created_at: stoppedJob.created_at || nowIso(),
            updated_at: nowIso(),
            error: 'Stopped by user',
            products: stoppedJob.products || []
          }).catch((manifestErr) => {
            writeLog('error', `Failed to save stopped-job manifest: ${manifestErr.message}`, 'db', jobId);
          });
        }
        writeLog('warning', 'Scrape stopped before completion', 'scrape', jobId);
        return;
      }

      updateJob(jobId, { status: 'failed', error: err.message });
      const failedJob = jobs.get(jobId);
      if (failedJob) {
        writeJobManifest(jobId, {
          job_id: jobId,
          url,
          folder_name: folderName,
          download_folder: downloadFolder,
          status: 'failed',
          created_at: failedJob.created_at || nowIso(),
          updated_at: nowIso(),
          error: err.message,
          products: failedJob.products || []
        }).catch((manifestErr) => {
          writeLog('error', `Failed to save failed-job manifest: ${manifestErr.message}`, 'db', jobId);
        });
      }
      writeLog('error', `Scrape failed: ${err.message}`, 'scrape', jobId);
    })
    .finally(() => {
      stopRequestedJobIds.delete(jobId);
      deletedJobIds.delete(jobId);
    });
}

async function handleScrape(req, res) {
  const { url } = req.query;
  const providedJobId = req.query.job_id;
  const titleFilter = String(req.query.title_filter || req.query.filter || '').trim();
  const folderName = sanitizeDisplayName(req.query.folder_name || req.query.folder || req.query.label || req.query.name || '');

  if (!url) {
    return res.status(400).json({ success: false, error: 'URL parameter is required' });
  }

  let safeUrl;
  try {
    safeUrl = await validatePublicHttpUrl(url, { allowedHosts: SCRAPE_ALLOWED_HOSTS });
  } catch (err) {
    return res.status(400).json({ success: false, error: err.message });
  }

  const jobId = String(providedJobId || createJobId());
  if (!isSafeJobId(jobId)) {
    return res.status(400).json({ success: false, error: 'Invalid job id' });
  }
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
      folder_name: existingJob.folder_name || '',
      download_folder: existingJob.download_folder || '',
      products: [],
      data: []
    });
  }

  // If a completed job is replayed with the same id+url, return cached result instead of rerunning.
  if (
    existingJob &&
    existingStatus === 'completed' &&
    String(existingJob.url || '').trim() === safeUrl &&
    Array.isArray(existingJob.products)
  ) {
    writeLog('info', 'Duplicate completed scrape request served from cache', 'queue', jobId);
    return res.json({
      success: true,
      duplicate: true,
      job_id: jobId,
      status: 'completed',
      folder_name: existingJob.folder_name || '',
      download_folder: existingJob.download_folder || '',
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
  const downloadFolder = getJobDownloadFolderName(jobId, folderName || inferModelFromUrl(safeUrl));

  updateJob(jobId, {
    id: jobId,
    url: safeUrl,
    status: 'queued',
    folder_name: folderName,
    download_folder: downloadFolder,
    model: folderName || inferModelFromUrl(safeUrl),
    title_filter: titleFilter,
    images: 0,
    total_items: 0,
    processed_items: 0,
    error: null,
    products: [],
    stop_requested: false,
    pause_requested: false,
    created_at: jobs.get(jobId)?.created_at || nowIso()
  });

  writeLog(
    'info',
    `Scrape accepted for ${safeUrl}${folderName ? ` (folder: ${folderName})` : ''}${titleFilter ? ` (filter: ${titleFilter})` : ''}`,
    'scrape',
    jobId
  );

  runScrapeJobInBackground({ jobId, url: safeUrl, folderName, titleFilter, downloadFolder });

  return res.status(202).json({
    success: true,
    job_id: jobId,
    status: 'queued',
    folder_name: folderName,
    download_folder: downloadFolder,
    products: [],
    data: []
  });
}

app.get('/scrape', handleScrape);
app.post('/scrape', handleScrape);

// Admin API endpoints
app.post('/admin/api/pause-all', (req, res) => {
  let pausedCount = 0;
  for (const job of jobs.values()) {
    if (job.status === 'running' || job.status === 'queued') {
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

app.post('/admin/api/resume-all', async (req, res) => {
  let resumedCount = 0;
  const errors = [];
  for (const job of jobs.values()) {
    if (job.status === 'paused') {
      const jobId = String(job.id);
      try {
        const safeUrl = await validatePublicHttpUrl(job.url, { allowedHosts: SCRAPE_ALLOWED_HOSTS });
        const folderName = sanitizeDisplayName(job.folder_name || job.model || '');
        const titleFilter = String(job.title_filter || '').trim();
        const downloadFolder = getJobDownloadFolderName(jobId, folderName || inferModelFromUrl(safeUrl));

        job.pause_requested = false;
        job.stop_requested = false;
        if (activeScrapeJobIds.has(jobId)) {
          updateJob(jobId, { status: 'running', pause_requested: false, stop_requested: false, error: null });
        } else {
          updateJob(jobId, { status: 'queued', pause_requested: false, stop_requested: false, error: null });
          runScrapeJobInBackground({ jobId, url: safeUrl, folderName, titleFilter, downloadFolder });
        }
        resumedCount++;
      } catch (err) {
        errors.push({ job_id: jobId, error: err.message });
      }
    }
  }
  writeLog('info', `Resumed ${resumedCount} job(s)`, 'admin');
  schedulePersistJobsDb();
  res.json({ success: errors.length === 0, resumed_count: resumedCount, errors });
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

app.post('/admin/api/reset-user', requireDestructiveConfirmation, (req, res) => {
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
    const job = jobs.get(jobId);
    const downloadDir = resolveWithinRoot(
      DOWNLOAD_ROOT,
      job?.download_folder
        ? sanitizeDownloadFolderName(job.download_folder, jobId)
        : jobId
    );
    jobs.delete(jobId);
    fsp.rm(downloadDir, { recursive: true, force: true }).catch(() => {});
    const legacyDownloadDir = resolveWithinRoot(DOWNLOAD_ROOT, jobId);
    if (downloadDir !== legacyDownloadDir) {
      fsp.rm(legacyDownloadDir, { recursive: true, force: true }).catch(() => {});
    }
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
  recoverRestoredActiveJobs();
  app.listen(PORT, HOST, () => {
    const mem = monitorMemory();
    writeLog('info', `Scraper API running at http://${HOST}:${PORT}`, 'startup');
    writeLog('info', `Memory: ${mem.heapUsedMB}MB / ${mem.heapTotalMB}MB (${mem.heapUsagePercent}%)`, 'startup');
    writeLog('info', `Concurrency: ${MAX_ACTIVE_SCRAPES} active job(s), max runtime: ${Math.round(JOB_MAX_RUNTIME_MS / 60000)} minute(s)`, 'startup');
    writeLog('info', `Job persistence: ${PERSIST_JOBS_ENABLED ? 'ENABLED' : 'DISABLED (in-memory only)'}`, 'startup');
  });

  if (IMAGE_CLEANUP_ENABLED) {
    const cleanupIntervalMs = 30 * 60 * 1000;
    setInterval(async () => {
      monitorMemory();
      writeLog('info', 'Starting scheduled image cleanup...', 'cleanup');
      await cleanupOldImages(IMAGE_MAX_AGE_HOURS);
    }, cleanupIntervalMs);

    cleanupOldImages(IMAGE_MAX_AGE_HOURS).catch((err) => {
      writeLog('warning', `Initial cleanup on startup failed: ${err.message}`, 'cleanup');
    });
    writeLog(
      'warning',
      `Image cleanup enabled: runs every ${cleanupIntervalMs / 60000} minutes and removes data older than ${IMAGE_MAX_AGE_HOURS} hours`,
      'startup'
    );
  } else {
    writeLog('info', 'Automatic image cleanup is disabled; saved job data will be retained.', 'startup');
  }

  // Memory monitoring every 10 minutes
  const MEMORY_CHECK_INTERVAL_MS = 10 * 60 * 1000;
  setInterval(() => {
    monitorMemory();
  }, MEMORY_CHECK_INTERVAL_MS);

});
