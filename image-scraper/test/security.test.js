'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const {
  fetchWithValidatedRedirects,
  hostMatches,
  isPrivateAddress,
  isSafeJobId,
  resolveWithinRoot,
  validatePublicHttpUrl
} = require('../lib/security');

test('job identifiers reject traversal and separators', () => {
  assert.equal(isSafeJobId('job_2026-07-24'), true);
  assert.equal(isSafeJobId('../jobs-db.json'), false);
  assert.equal(isSafeJobId('job/child'), false);
});

test('private and loopback addresses are blocked', () => {
  for (const address of ['127.0.0.1', '10.0.0.2', '172.16.0.1', '192.168.1.10', '169.254.1.1', '::1', 'fd00::1']) {
    assert.equal(isPrivateAddress(address), true, address);
  }
  assert.equal(isPrivateAddress('8.8.8.8'), false);
  assert.equal(isPrivateAddress('2606:4700:4700::1111'), false);
});

test('supplier host matching includes subdomains but not suffix lookalikes', () => {
  const allowed = ['mobilesentrix.com', 'mobilesentrix.ca'];
  assert.equal(hostMatches('static.mobilesentrix.com', allowed), true);
  assert.equal(hostMatches('mobilesentrix.com.example.test', allowed), false);
});

test('public URL validation rejects DNS results on private networks', async () => {
  await assert.rejects(
    validatePublicHttpUrl('https://mobilesentrix.com/example', {
      allowedHosts: ['mobilesentrix.com'],
      lookup: async () => [{ address: '127.0.0.1', family: 4 }]
    }),
    /Private/
  );
});

test('public URL validation accepts an allowed public host', async () => {
  const value = await validatePublicHttpUrl('https://www.mobilesentrix.com/example#fragment', {
    allowedHosts: ['mobilesentrix.com'],
    lookup: async () => [{ address: '8.8.8.8', family: 4 }]
  });

  assert.equal(value, 'https://www.mobilesentrix.com/example');
});

test('storage path resolution rejects directory escape', () => {
  const root = path.resolve('downloads');
  assert.throws(() => resolveWithinRoot(root, '../outside'), /outside/);
  assert.equal(resolveWithinRoot(root, 'safe/job'), path.join(root, 'safe', 'job'));
});

test('validated fetch checks redirect destinations before requesting them', async () => {
  const fetched = [];
  const lookup = async (hostname) => [{
    address: hostname === 'internal.example' ? '127.0.0.1' : '8.8.8.8',
    family: 4
  }];
  const fetchImpl = async (url) => {
    fetched.push(url);
    return {
      status: 302,
      headers: { get: () => 'http://internal.example/secret' },
      body: { cancel: async () => {} }
    };
  };

  await assert.rejects(
    fetchWithValidatedRedirects('https://public.example/image.jpg', {}, { fetchImpl, lookup }),
    /Private/
  );
  assert.deepEqual(fetched, ['https://public.example/image.jpg']);
});

test('validated fetch follows public redirects', async () => {
  const fetched = [];
  const fetchImpl = async (url) => {
    fetched.push(url);
    if (fetched.length === 1) {
      return {
        status: 302,
        headers: { get: () => '/final.jpg' },
        body: { cancel: async () => {} }
      };
    }
    return { status: 200, headers: { get: () => null } };
  };

  const response = await fetchWithValidatedRedirects(
    'https://public.example/start',
    {},
    {
      fetchImpl,
      lookup: async () => [{ address: '8.8.8.8', family: 4 }]
    }
  );

  assert.equal(response.status, 200);
  assert.deepEqual(fetched, [
    'https://public.example/start',
    'https://public.example/final.jpg'
  ]);
});
