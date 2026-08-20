'use strict';

function envBoolean(value, fallback) {
  if (value == null || String(value).trim() === '') return Boolean(fallback);
  return ['1', 'true', 'yes', 'on'].includes(String(value).trim().toLowerCase());
}

function retainJobs(jobs, limit) {
  const records = Array.isArray(jobs) ? jobs : [];
  const normalizedLimit = Number.isFinite(Number(limit)) ? Math.max(0, Math.floor(Number(limit))) : 0;
  return normalizedLimit > 0 ? records.slice(0, normalizedLimit) : records;
}

module.exports = {
  envBoolean,
  retainJobs
};
