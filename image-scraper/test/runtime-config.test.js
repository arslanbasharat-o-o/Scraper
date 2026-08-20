'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { envBoolean, retainJobs } = require('../lib/runtime-config');

test('production data retention is enabled by default', () => {
  assert.equal(envBoolean(undefined, true), true);
  assert.equal(envBoolean('', true), true);
});

test('automatic image cleanup is disabled by default', () => {
  assert.equal(envBoolean(undefined, false), false);
  assert.equal(envBoolean('', false), false);
});

test('zero persistence limit retains every job', () => {
  const jobs = Array.from({ length: 150 }, (_, index) => ({ id: index + 1 }));

  assert.equal(retainJobs(jobs, 0).length, 150);
});

test('explicit positive persistence limit is honored', () => {
  const jobs = Array.from({ length: 10 }, (_, index) => ({ id: index + 1 }));

  assert.deepEqual(retainJobs(jobs, 3).map((job) => job.id), [1, 2, 3]);
});
