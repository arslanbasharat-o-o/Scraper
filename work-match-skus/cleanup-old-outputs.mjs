import fs from "node:fs/promises";
import path from "node:path";

const outputDir = path.resolve("outputs/sku-match");
const keep = new Set([
  "Book1-with-matching-webcodes-v5.xlsx",
  "Book1-with-matching-webcodes-v5.xlsx.inspect.ndjson",
  "Book1-with-matching-webcodes-v5-preview.png",
  "Book1-with-matching-webcodes-v5-review-preview.png",
]);

const entries = await fs.readdir(outputDir, { withFileTypes: true });
const deleted = [];
const kept = [];
const failed = [];

for (const entry of entries) {
  if (!entry.isFile()) continue;
  if (keep.has(entry.name)) {
    kept.push(entry.name);
    continue;
  }

  const target = path.resolve(outputDir, entry.name);
  if (!target.startsWith(outputDir + path.sep)) {
    failed.push({ name: entry.name, error: "Refused path outside output directory" });
    continue;
  }

  try {
    await fs.rm(target, { force: true });
    deleted.push(entry.name);
  } catch (error) {
    failed.push({ name: entry.name, error: error.message });
  }
}

console.log(JSON.stringify({ outputDir, deleted, kept, failed }, null, 2));
