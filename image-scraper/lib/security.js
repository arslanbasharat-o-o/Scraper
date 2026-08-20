'use strict';

const dns = require('node:dns/promises');
const net = require('node:net');
const path = require('node:path');

const SAFE_JOB_ID = /^[a-zA-Z0-9_-]{1,100}$/;

function isSafeJobId(value) {
  return SAFE_JOB_ID.test(String(value || ''));
}

function isPrivateAddress(address) {
  const value = String(address || '').trim().toLowerCase().split('%')[0];
  if (!value) return true;

  if (value.startsWith('::ffff:')) {
    return isPrivateAddress(value.slice(7));
  }

  if (net.isIP(value) === 4) {
    const [a, b] = value.split('.').map(Number);
    return (
      a === 0 ||
      a === 10 ||
      a === 127 ||
      (a === 100 && b >= 64 && b <= 127) ||
      (a === 169 && b === 254) ||
      (a === 172 && b >= 16 && b <= 31) ||
      (a === 192 && b === 168) ||
      (a === 198 && (b === 18 || b === 19)) ||
      a >= 224
    );
  }

  if (net.isIP(value) === 6) {
    return (
      value === '::' ||
      value === '::1' ||
      value.startsWith('fc') ||
      value.startsWith('fd') ||
      /^fe[89ab]/.test(value)
    );
  }

  return true;
}

function parseAllowedHosts(value, defaults = []) {
  const configured = String(value || '')
    .split(',')
    .map((host) => host.trim().toLowerCase().replace(/^\.+/, ''))
    .filter(Boolean);
  return configured.length ? configured : defaults;
}

function hostMatches(hostname, allowedHosts) {
  const normalized = String(hostname || '').toLowerCase().replace(/\.$/, '');
  return allowedHosts.some((allowed) => normalized === allowed || normalized.endsWith(`.${allowed}`));
}

async function validatePublicHttpUrl(rawUrl, options = {}) {
  let parsed;
  try {
    parsed = new URL(String(rawUrl || '').trim());
  } catch {
    throw new Error('A valid absolute URL is required.');
  }

  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error('Only HTTP and HTTPS URLs are allowed.');
  }
  if (parsed.username || parsed.password) {
    throw new Error('URLs containing credentials are not allowed.');
  }

  const allowedHosts = Array.isArray(options.allowedHosts) ? options.allowedHosts : [];
  if (allowedHosts.length && !hostMatches(parsed.hostname, allowedHosts)) {
    throw new Error(`Host is not allowed: ${parsed.hostname}`);
  }

  const lookup = options.lookup || dns.lookup;
  const addresses = await lookup(parsed.hostname, { all: true, verbatim: true });
  if (!addresses.length || addresses.some((entry) => isPrivateAddress(entry.address))) {
    throw new Error('Private, loopback, and link-local network addresses are not allowed.');
  }

  parsed.hash = '';
  return parsed.href;
}

async function fetchWithValidatedRedirects(rawUrl, fetchOptions = {}, validationOptions = {}) {
  const fetchImpl = validationOptions.fetchImpl || globalThis.fetch;
  const maxRedirects = Number.isInteger(validationOptions.maxRedirects)
    ? validationOptions.maxRedirects
    : 5;
  let currentUrl = rawUrl;

  if (typeof fetchImpl !== 'function') {
    throw new Error('A fetch implementation is required.');
  }

  for (let redirectCount = 0; redirectCount <= maxRedirects; redirectCount++) {
    const safeUrl = await validatePublicHttpUrl(currentUrl, validationOptions);
    const response = await fetchImpl(safeUrl, { ...fetchOptions, redirect: 'manual' });
    const location = response.headers?.get?.('location');

    if (response.status >= 300 && response.status < 400 && location) {
      if (redirectCount === maxRedirects) {
        response.body?.cancel?.().catch?.(() => {});
        throw new Error(`Too many redirects (maximum ${maxRedirects}).`);
      }
      response.body?.cancel?.().catch?.(() => {});
      currentUrl = new URL(location, safeUrl).href;
      continue;
    }

    return response;
  }

  throw new Error('Unable to fetch URL.');
}

function resolveWithinRoot(root, child) {
  const resolvedRoot = path.resolve(root);
  const resolvedChild = path.resolve(resolvedRoot, child);
  if (resolvedChild !== resolvedRoot && !resolvedChild.startsWith(`${resolvedRoot}${path.sep}`)) {
    throw new Error('Resolved path is outside the configured storage root.');
  }
  return resolvedChild;
}

module.exports = {
  fetchWithValidatedRedirects,
  hostMatches,
  isPrivateAddress,
  isSafeJobId,
  parseAllowedHosts,
  resolveWithinRoot,
  validatePublicHttpUrl
};
