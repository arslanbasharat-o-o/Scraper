import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const book1Path = process.env.BOOK1_PATH || process.argv[2] || path.resolve("data/Book1.xlsx");
const exportPath = process.env.EXPORT_PATH || process.argv[3] || path.resolve("data/export-update-sku-.xlsx");
const outputDir = path.resolve(process.env.OUTPUT_DIR || "outputs/sku-match");
const outputPath = path.join(outputDir, "Book1-with-matching-webcodes-v5.xlsx");

function colToA1(colIndexZeroBased) {
  let col = colIndexZeroBased + 1;
  let label = "";
  while (col > 0) {
    const rem = (col - 1) % 26;
    label = String.fromCharCode(65 + rem) + label;
    col = Math.floor((col - 1) / 26);
  }
  return label;
}

function normalizeSku(value) {
  if (value == null) return "";
  return String(value)
    .trim()
    .toUpperCase()
    .replace(/\+/g, "PLUS")
    .replace(/[^A-Z0-9]/g, "");
}

function normalizeText(value) {
  if (value == null) return "";
  return String(value)
    .trim()
    .toUpperCase()
    .replace(/\bW\s*\/\s*F\b/g, " WF ")
    .replace(/\bWITH\s+FRAME\b/g, " WF ")
    .replace(/\+/g, " PLUS ")
    .replace(/\bPRO\s*MAX\b/g, " PROMAX ")
    .replace(/\bPM\b/g, " PROMAX ")
    .replace(/\b(\d+)\s*(XL|MM|GB)\b/g, "$1$2")
    .replace(/\b5\s*G\b/g, "5G")
    .replace(/\bIPAD\s*MINI\b/g, "IPADMINI")
    .replace(/\bIPHONE\b/g, "IPH")
    .replace(/\bGALAXY\b/g, "GAL")
    .replace(/\bSAMSUNG\b/g, "")
    .replace(/\bBACK\s*DOOR\b/g, "BACKDOOR")
    .replace(/\bBACK\s*COVER\b/g, "BACKDOOR")
    .replace(/\bBACK\s*GLASS\b/g, "BACKDOOR")
    .replace(/\bBATTERY\s*COVER\b/g, "BACKDOOR")
    .replace(/\bREAR\s*GLASS\b/g, "BACKDOOR")
    .replace(/\bCHARGING\s*PORT\b/g, "CHARGINGPORT")
    .replace(/\bHOME\s*BUTTON\b/g, "HOMEBUTTON")
    .replace(/\bFINGER\s*PRINT\b/g, "FINGERPRINT")
    .replace(/\bPOWER\s*VOLUME\b/g, "POWERVOLUME")
    .replace(/\bVOLUME\s*POWER\b/g, "POWERVOLUME")
    .replace(/\bSIM\s*TRAY\b/g, "SIMTRAY")
    .replace(/\bLOUD\s*SPEAKER\b/g, "LOUDSPEAKER")
    .replace(/\bEAR\s*PIECE\b/g, "EARPIECE")
    .replace(/\bFRONT\s*CAMERA\b/g, "FRONTCAMERA")
    .replace(/\bBACK\s*CAMERA\b/g, "BACKCAMERA")
    .replace(/\bREAR\s*CAMERA\b/g, "BACKCAMERA")
    .replace(/\bMAIN\s*BOARD\b/g, "MAINBOARD")
    .replace(/\bMOTHER\s*BOARD\b/g, "MAINBOARD")
    .replace(/\bFLEX\s*CABLE\b/g, "FLEX")
    .replace(/[^A-Z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const semanticStopwords = new Set([
  "A",
  "AN",
  "AND",
  "ASSEMBLY",
  "BY",
  "CELL",
  "COMPATIBLE",
  "FOR",
  "GEN",
  "HIGH",
  "IN",
  "INC",
  "LCD",
  "LOGO",
  "NEW",
  "NO",
  "OF",
  "OEM",
  "PART",
  "PARTS",
  "PHONE",
  "PLUS",
  "PREMIUM",
  "QUALITY",
  "REPAIR",
  "REPLACEMENT",
  "SCREEN",
  "THE",
  "TO",
]);

const protectedSemanticTokens = new Set([
  "PLUS",
  "PRO",
  "PROMAX",
  "MAX",
  "MINI",
  "ULTRA",
  "LCD",
  "SCREEN",
]);

const colorTokens = new Set([
  "BLACK",
  "BLUE",
  "GOLD",
  "GRAY",
  "GREEN",
  "GREY",
  "MIDNIGHT",
  "PINK",
  "PURPLE",
  "RED",
  "ROSE",
  "SILVER",
  "SPACE",
  "WHITE",
  "YELLOW",
]);

function semanticTokens(value) {
  return normalizeText(value)
    .split(" ")
    .filter(Boolean)
    .map((token) => (token === "GREY" ? "GRAY" : token))
    .filter((token) => !semanticStopwords.has(token) || protectedSemanticTokens.has(token));
}

function uniqueSemanticTokens(value) {
  return [...new Set(semanticTokens(value))];
}

function hasAllTokens(candidateSet, requiredTokens) {
  return requiredTokens.every((token) => candidateSet.has(token));
}

function productNameScore(entry, requiredTokens) {
  const overlap = requiredTokens.filter((token) => entry.tokenSet.has(token)).length;
  const extraPenalty = Math.max(0, entry.tokens.length - requiredTokens.length) * 0.02;
  const skuBonus = hasAllTokens(entry.skuTokenSet, requiredTokens) ? 0.2 : 0;
  return overlap - extraPenalty + skuBonus;
}

function tokenKey(value) {
  const normalized = normalizeText(value);
  if (!normalized) return "";
  return normalized.split(" ").filter(Boolean).sort().join("|");
}

function valueText(value) {
  if (value == null) return "";
  return String(value).trim();
}

function webCodeValue(value) {
  const text = valueText(value);
  if (!text) return "";
  if (/^\d+$/.test(text) && text.length <= 15) return Number(text);
  return text;
}

function detectSkuColumn(rows) {
  const maxCols = Math.max(...rows.map((row) => row.length));
  const headerRowsToTry = Math.min(10, rows.length);
  const scored = [];

  for (let headerRow = 0; headerRow < headerRowsToTry; headerRow += 1) {
    for (let col = 0; col < maxCols; col += 1) {
      const header = valueText(rows[headerRow]?.[col]).toLowerCase();
      let score = 0;
      if (header === "sku") score += 1000;
      if (header.includes("sku")) score += 500;
      if (header.includes("product code") || header.includes("item code")) score += 100;

      const samples = rows
        .slice(headerRow + 1, Math.min(rows.length, headerRow + 51))
        .map((row) => valueText(row[col]))
        .filter(Boolean);
      const skuLike = samples.filter((sample) => {
        const normalized = normalizeSku(sample);
        return normalized.length >= 4 && /[A-Z]/i.test(sample) && /\d/.test(sample);
      }).length;
      score += skuLike;

      if (score > 0) {
        scored.push({ headerRow, col, header, score, samples: samples.slice(0, 5) });
      }
    }
  }

  scored.sort((a, b) => b.score - a.score);
  return scored[0];
}

async function loadWorkbook(filePath) {
  const input = await FileBlob.load(filePath);
  return SpreadsheetFile.importXlsx(input);
}

async function main() {
  await fs.mkdir(outputDir, { recursive: true });

  const book1 = await loadWorkbook(book1Path);
  const exported = await loadWorkbook(exportPath);

  const book1Summary = await book1.inspect({
    kind: "workbook,sheet,table",
    maxChars: 6000,
    tableMaxRows: 8,
    tableMaxCols: 12,
    tableMaxCellChars: 80,
  });
  const exportSummary = await exported.inspect({
    kind: "workbook,sheet,table",
    maxChars: 6000,
    tableMaxRows: 8,
    tableMaxCols: 12,
    tableMaxCellChars: 80,
  });

  console.log("BOOK1_SUMMARY");
  console.log(book1Summary.ndjson);
  console.log("EXPORT_SUMMARY");
  console.log(exportSummary.ndjson);

  const book1Sheets = JSON.parse(`[${book1Summary.ndjson
    .split("\n")
    .filter((line) => line.includes('"kind":"sheet"'))
    .join(",")}]`);
  const exportSheets = JSON.parse(`[${exportSummary.ndjson
    .split("\n")
    .filter((line) => line.includes('"kind":"sheet"'))
    .join(",")}]`);

  const book1SheetName = book1Sheets[0].name;
  const exportSheetName = exportSheets[0].name;
  const book1Sheet = book1.worksheets.getItem(book1SheetName);
  const exportSheet = exported.worksheets.getItem(exportSheetName);

  const book1Used = book1Sheet.getUsedRange(true);
  const exportUsed = exportSheet.getUsedRange(true);
  const book1Values = book1Used.values;
  const exportValues = exportUsed.values;

  const book1Sku = detectSkuColumn(book1Values);
  const exportSku = detectSkuColumn(exportValues);

  const book1Keys = new Map();
  for (let r = 1; r < book1Values.length; r += 1) {
    const original = valueText(book1Values[r]?.[0]);
    const key = normalizeSku(original);
    if (!key) continue;
    if (!book1Keys.has(key)) book1Keys.set(key, []);
    book1Keys.get(key).push({ row: r + 1, original });
  }

  const exportHeaders = exportValues[0].map(valueText);
  const columnMatchSummaries = exportHeaders.map((header, col) => {
    const matches = [];
    for (let r = 1; r < exportValues.length; r += 1) {
      const original = valueText(exportValues[r]?.[col]);
      const key = normalizeSku(original);
      if (key && book1Keys.has(key)) {
        matches.push({
          book1: book1Keys.get(key)[0].original,
          export: original,
          exportRow: r + 1,
        });
      }
    }
    return {
      col: colToA1(col),
      header,
      matchCount: matches.length,
      examples: matches.slice(0, 10),
    };
  });

  console.log("DETECTED");
  console.log(JSON.stringify({ book1SheetName, exportSheetName, book1Sku, exportSku }, null, 2));
  console.log("COLUMN_MATCH_SUMMARIES");
  console.log(JSON.stringify(columnMatchSummaries, null, 2));

  const exportSkuCol = 2;
  const exportWebSkuCol = 3;
  const exportLookup = new Map();
  const duplicateExportKeys = new Map();
  for (let r = 1; r < exportValues.length; r += 1) {
    const sku = valueText(exportValues[r]?.[exportSkuCol]);
    const key = normalizeSku(sku);
    if (!key) continue;
    if (exportLookup.has(key)) {
      if (!duplicateExportKeys.has(key)) duplicateExportKeys.set(key, [exportLookup.get(key)]);
      duplicateExportKeys.get(key).push({
        sku,
        webSku: valueText(exportValues[r]?.[exportWebSkuCol]),
        productName: valueText(exportValues[r]?.[1]),
        row: r + 1,
      });
      continue;
    }
    exportLookup.set(key, {
      sku,
      webSku: valueText(exportValues[r]?.[exportWebSkuCol]),
      productName: valueText(exportValues[r]?.[1]),
      row: r + 1,
    });
  }

  const exportTokenLookup = new Map();
  const exportTokenDuplicates = new Map();
  for (let r = 1; r < exportValues.length; r += 1) {
    const sku = valueText(exportValues[r]?.[2]);
    const key = tokenKey(sku);
    if (!key) continue;
    if (exportTokenLookup.has(key)) {
      if (!exportTokenDuplicates.has(key)) exportTokenDuplicates.set(key, [exportTokenLookup.get(key)]);
      exportTokenDuplicates.get(key).push({
        sku,
        webSku: valueText(exportValues[r]?.[3]),
        productName: valueText(exportValues[r]?.[1]),
        row: r + 1,
      });
      continue;
    }
    exportTokenLookup.set(key, {
      sku,
      webSku: valueText(exportValues[r]?.[3]),
      productName: valueText(exportValues[r]?.[1]),
      row: r + 1,
    });
  }

  const hierarchyCandidates = [];
  for (let r = 1; r < book1Values.length; r += 1) {
    const original = valueText(book1Values[r]?.[0]);
    const exactKey = normalizeSku(original);
    const sortedKey = tokenKey(original);
    if (!sortedKey || exportLookup.has(exactKey) || exportTokenDuplicates.has(sortedKey)) continue;
    const match = exportTokenLookup.get(sortedKey);
    if (match) {
      hierarchyCandidates.push({
        book1Row: r + 1,
        book1: original,
        exportRow: match.row,
        export: match.sku,
      });
    }
  }

  console.log("HIERARCHY_CANDIDATES");
  console.log(JSON.stringify({
    count: hierarchyCandidates.length,
    examples: hierarchyCandidates.slice(0, 80),
    skippedDuplicateTokenKeys: exportTokenDuplicates.size,
  }, null, 2));

  const productNameEntries = [];
  const productNameTokenIndex = new Map();
  for (let r = 1; r < exportValues.length; r += 1) {
    const sku = valueText(exportValues[r]?.[2]);
    const productName = valueText(exportValues[r]?.[1]);
    const webSku = valueText(exportValues[r]?.[3]);
    const tokens = uniqueSemanticTokens(`${productName} ${sku}`);
    if (!sku || !productName || tokens.length === 0) continue;
    const entry = {
      sku,
      webSku,
      productName,
      row: r + 1,
      tokens,
      tokenSet: new Set(tokens),
      skuTokens: uniqueSemanticTokens(sku),
    };
    entry.skuTokenSet = new Set(entry.skuTokens);
    const index = productNameEntries.length;
    productNameEntries.push(entry);
    for (const token of tokens) {
      if (!productNameTokenIndex.has(token)) productNameTokenIndex.set(token, []);
      productNameTokenIndex.get(token).push(index);
    }
  }

  function findProductNameMatch(original) {
    const requiredTokens = uniqueSemanticTokens(original);
    if (requiredTokens.length < 3) return { match: null, reason: "too_few_tokens" };

    const tokenLists = requiredTokens
      .map((token) => ({ token, rows: productNameTokenIndex.get(token) ?? [] }))
      .filter((item) => item.rows.length > 0)
      .sort((a, b) => a.rows.length - b.rows.length);
    if (tokenLists.length !== requiredTokens.length) return { match: null, reason: "missing_required_token" };

    const candidates = [];
    for (const index of tokenLists[0].rows) {
      const entry = productNameEntries[index];
      if (hasAllTokens(entry.tokenSet, requiredTokens)) {
        candidates.push({
          entry,
          score: productNameScore(entry, requiredTokens),
        });
      }
    }

    if (candidates.length === 0) return { match: null, reason: "no_candidate" };

    const skuStrong = candidates.filter((candidate) => hasAllTokens(candidate.entry.skuTokenSet, requiredTokens));
    if (skuStrong.length === 1) return { match: skuStrong[0].entry, reason: "sku_strong" };
    if (candidates.length === 1) return { match: candidates[0].entry, reason: "unique_product_name" };

    candidates.sort((a, b) => b.score - a.score);
    if (candidates[0].score >= candidates[1].score + 0.5) {
      return { match: candidates[0].entry, reason: "clear_score" };
    }

    return {
      match: null,
      reason: "ambiguous",
      ambiguous: candidates.slice(0, 5).map((candidate) => ({
        webSku: candidate.entry.webSku,
        sku: candidate.entry.sku,
        productName: candidate.entry.productName,
        row: candidate.entry.row,
        score: Number(candidate.score.toFixed(2)),
      })),
    };
  }

  const productNameCandidates = [];
  const productNameAmbiguous = [];
  const sampleRowsToCheck = new Set(["iPh 15 Plus Backdoor Blue"]);
  const namedDiagnostics = [];
  for (let r = 1; r < book1Values.length; r += 1) {
    const original = valueText(book1Values[r]?.[0]);
    const exactKey = normalizeSku(original);
    const sortedKey = tokenKey(original);
    const alreadyMatched =
      exportLookup.has(exactKey) ||
      (sortedKey && !exportTokenDuplicates.has(sortedKey) && exportTokenLookup.has(sortedKey));
    if (alreadyMatched) continue;

    const result = findProductNameMatch(original);
    if (sampleRowsToCheck.has(original)) {
      namedDiagnostics.push({ book1Row: r + 1, book1: original, result });
    }
    if (result.match) {
      productNameCandidates.push({
        book1Row: r + 1,
        book1: original,
        exportRow: result.match.row,
        exportWebSku: result.match.webSku,
        exportSku: result.match.sku,
        exportName: result.match.productName,
        reason: result.reason,
      });
    } else if (result.reason === "ambiguous") {
      productNameAmbiguous.push({
        book1Row: r + 1,
        book1: original,
        candidates: result.ambiguous,
      });
    }
  }

  console.log("PRODUCT_NAME_CANDIDATES");
  console.log(JSON.stringify({
    count: productNameCandidates.length,
    examples: productNameCandidates.slice(0, 100),
    ambiguousCount: productNameAmbiguous.length,
    ambiguousExamples: productNameAmbiguous.slice(0, 20),
    namedDiagnostics,
  }, null, 2));

  const outputRows = [[
    "Matching Product Web SKU",
    "Matching Product SKU",
    book1Values[0]?.[0] ?? "Book1 SKU",
  ]];
  const reviewRows = [[
    "Book1 Row",
    book1Values[0]?.[0] ?? "Book1 SKU",
    "Candidate Product Web SKU",
    "Candidate Product SKU",
    "Candidate Product Name",
    "Export Row",
    "Score",
  ]];
  let matchedRows = 0;
  let exactMatchedRows = 0;
  let hierarchyMatchedRows = 0;
  let productNameMatchedRows = 0;
  let ambiguousRows = 0;
  for (let r = 1; r < book1Values.length; r += 1) {
    const original = valueText(book1Values[r]?.[0]);
    const exactKey = normalizeSku(original);
    const sortedKey = tokenKey(original);
    let match = exactKey ? exportLookup.get(exactKey) : null;
    if (match) {
      exactMatchedRows += 1;
    } else if (sortedKey && !exportTokenDuplicates.has(sortedKey)) {
      match = exportTokenLookup.get(sortedKey);
      if (match) hierarchyMatchedRows += 1;
    }
    if (!match) {
      const result = findProductNameMatch(original);
      if (result.match) {
        match = result.match;
        productNameMatchedRows += 1;
      } else if (result.reason === "ambiguous") {
        ambiguousRows += 1;
        for (const candidate of result.ambiguous ?? []) {
          reviewRows.push([
            r + 1,
            original,
            webCodeValue(candidate.webSku),
            candidate.sku ?? "",
            candidate.productName ?? "",
            candidate.row ?? "",
            candidate.score ?? "",
          ]);
        }
      }
    }
    if (match) matchedRows += 1;
    outputRows.push([webCodeValue(match?.webSku), match?.sku ?? "", original]);
  }

  const outputWorkbook = Workbook.create();
  const outputSheet = outputWorkbook.worksheets.add("Sheet1");
  outputSheet.getRangeByIndexes(0, 0, outputRows.length, 3).values = outputRows;
  outputSheet.getRange(`A2:A${outputRows.length}`).setNumberFormat("0");
  outputSheet.getRange(`B1:C${outputRows.length}`).setNumberFormat("@");

  outputSheet.getRange("A1:C1").format = {
    fill: "#1F4E79",
    font: { bold: true, color: "#FFFFFF" },
  };
  outputSheet.getRange(`A1:C${outputRows.length}`).format.autofitColumns();
  outputSheet.freezePanes.freezeRows(1);

  const reviewSheet = outputWorkbook.worksheets.add("Review Possible Matches");
  reviewSheet.getRangeByIndexes(0, 0, reviewRows.length, 7).values = reviewRows;
  reviewSheet.getRange(`C2:C${reviewRows.length}`).setNumberFormat("0");
  reviewSheet.getRange(`B1:B${reviewRows.length}`).setNumberFormat("@");
  reviewSheet.getRange(`D1:E${reviewRows.length}`).setNumberFormat("@");
  reviewSheet.getRange("A1:G1").format = {
    fill: "#7A3E00",
    font: { bold: true, color: "#FFFFFF" },
  };
  reviewSheet.getRange(`A1:G${reviewRows.length}`).format.autofitColumns();
  reviewSheet.freezePanes.freezeRows(1);

  const preview = await outputWorkbook.render({
    sheetName: "Sheet1",
    range: `A1:C${Math.min(outputRows.length, 40)}`,
    scale: 1,
    format: "png",
  });
  await fs.writeFile(path.join(outputDir, "Book1-with-matching-webcodes-v5-preview.png"), new Uint8Array(await preview.arrayBuffer()));
  const reviewPreview = await outputWorkbook.render({
    sheetName: "Review Possible Matches",
    range: `A1:G${Math.min(reviewRows.length, 25)}`,
    scale: 1,
    format: "png",
  });
  await fs.writeFile(path.join(outputDir, "Book1-with-matching-webcodes-v5-review-preview.png"), new Uint8Array(await reviewPreview.arrayBuffer()));

  const check = await outputWorkbook.inspect({
    kind: "table",
    sheetId: "Sheet1",
    range: `A1:C${Math.min(outputRows.length, 30)}`,
    include: "values,formulas",
    tableMaxRows: 30,
    tableMaxCols: 3,
  });
  const reviewCheck = await outputWorkbook.inspect({
    kind: "table",
    sheetId: "Review Possible Matches",
    range: `A1:G${Math.min(reviewRows.length, 15)}`,
    include: "values,formulas",
    tableMaxRows: 15,
    tableMaxCols: 7,
  });
  const errors = await outputWorkbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 300 },
    summary: "final formula error scan",
  });

  const xlsx = await SpreadsheetFile.exportXlsx(outputWorkbook);
  await xlsx.save(outputPath);

  console.log("OUTPUT_CHECK");
  console.log(check.ndjson);
  console.log("REVIEW_CHECK");
  console.log(reviewCheck.ndjson);
  console.log("ERROR_SCAN");
  console.log(errors.ndjson);
  console.log("OUTPUT_SUMMARY");
  console.log(JSON.stringify({
    outputPath,
    rowsIncludingHeader: outputRows.length,
    book1DataRows: outputRows.length - 1,
    matchedRows,
    exactMatchedRows,
    hierarchyMatchedRows,
    productNameMatchedRows,
    blankRows: outputRows.length - 1 - matchedRows,
    ambiguousRows,
    reviewCandidateRows: reviewRows.length - 1,
    duplicateExportKeys: duplicateExportKeys.size,
  }, null, 2));
}

await main();
