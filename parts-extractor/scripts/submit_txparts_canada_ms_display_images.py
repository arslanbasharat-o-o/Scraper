from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd
import requests


APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = APP_ROOT / "output" / "txparts_canada_mobilesentrix_images"
DEFAULT_TX_TREE = APP_ROOT / "output" / "txparts_canada" / "categories.json"
DEFAULT_MS_TREE = APP_ROOT / "output" / "mobilesentrix_canada" / "categories.json"

APPLE_RE = re.compile(r"\b(apple|iphone|ipad|ipod|watch|apple\s*watch|macbook|airpods)\b", re.I)
SKIP_PARENT_RE = re.compile(r"\b(apple|tools|accessories|cases?)\b", re.I)
SERIES_ONLY_RE = re.compile(r"\b(series|cases?|chargers?|cables?|headphones?)\b$", re.I)
YEAR_RE = re.compile(r"\b(20\d{2})\b")
MODEL_NUMBER_RE = re.compile(r"\b(XT-?\d{3,5}(?:-\d{1,3})?|SM-[A-Z]\d{3,4}[A-Z]?|[A-Z]{1,4}\d{3,5}(?:-\d{1,3})?)\b", re.I)
NETWORK_RE = re.compile(r"\b(4G|5G)\b", re.I)
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid", "srsltid"}

DISPLAY_TITLE_FILTER = (
    "Display Assembly, LCD Assembly, OLED Assembly, AMOLED Assembly, Screen Assembly, "
    "LCD Screen, OLED Screen, AMOLED Screen, Touch Screen, Digitizer Assembly, "
    "Display LCD, Display OLED, Incell Assembly, Inner Display, Outer Display, "
    "Cover Display, Main Display, Flexible OLED, Foldable Display"
)

REPORT_COLUMNS = [
    "TX Brand",
    "TX Model",
    "Model Number",
    "TX URL",
    "MobileSentrix Model",
    "MobileSentrix URL",
    "Display Type",
    "Match Confidence",
    "Submission Status",
    "Images Found",
    "Error",
    "Job ID",
    "Folder Name",
    "TX Series",
    "Release Year",
    "Network",
    "Match Notes",
]


@dataclass
class ModelEntry:
    source: str
    brand: str
    series: str
    model: str
    url: str
    parent: str
    model_number: str = ""
    year: str = ""
    network: str = ""
    canonical: str = ""
    tokens: tuple[str, ...] = ()


@dataclass
class MatchResult:
    tx: ModelEntry
    ms: ModelEntry | None
    confidence: str
    notes: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def normalize_url(raw_url: str) -> str:
    raw_url = clean_text(raw_url)
    if not raw_url:
        return ""
    parsed = urlparse(raw_url)
    path = parsed.path.rstrip("/") or "/"
    query = urlencode(
        sorted((k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in TRACKING_PARAMS),
        doseq=True,
    )
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", query, ""))


def normalize_brand(parent: str, sub: str, model: str) -> str:
    parent = clean_text(parent)
    sub = clean_text(sub)
    model = clean_text(model)
    if parent.lower() == "google":
        return "Google"
    if parent.lower() == "other brands":
        return sub
    if parent.lower() == "other parts":
        return sub
    if parent in {"Samsung", "Motorola"}:
        return parent
    for brand in ("OnePlus", "LG", "TCL", "Nokia", "ZTE", "Alcatel", "REVVL", "Asus", "Sony", "Huawei", "Honor", "Xiaomi"):
        if re.search(rf"\b{re.escape(brand)}\b", f"{sub} {model}", re.I):
            return brand
    return parent


def extract_year(value: str) -> str:
    matches = YEAR_RE.findall(value or "")
    return matches[-1] if matches else ""


def extract_model_number(value: str) -> str:
    parenthetical = " ".join(re.findall(r"\(([^)]*)\)", value or ""))
    matches = MODEL_NUMBER_RE.findall(parenthetical or value or "")
    if not matches:
        return ""
    return matches[0].upper().replace("XT-", "XT")


def extract_network(value: str) -> str:
    match = NETWORK_RE.search(value or "")
    return match.group(1).upper() if match else ""


def canonicalize_model(brand: str, model: str) -> tuple[str, tuple[str, ...]]:
    brand_l = clean_text(brand).lower()
    text = clean_text(model).lower()
    text = text.replace("+", " plus ")
    text = re.sub(r"[\"']", " ", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b20\d{2}\b", " ", text)
    text = re.sub(r"\bsm-[a-z]\d+[a-z]?\b", " ", text)
    text = re.sub(r"\bxt-?\d+(?:-\d+)?\b", " ", text)
    text = re.sub(r"\b[a-z]{1,4}\d{2,5}(?:-\d{1,3})?\b", lambda m: m.group(0), text)
    text = re.sub(r"\b(samsung|motorola|google|pixel|lg|huawei|alcatel|asus|sony|honor|xiaomi|zte|tcl|nokia|revvl)\b", " ", text)
    if brand_l == "samsung":
        text = re.sub(r"\bgalaxy\b", " ", text)
    if brand_l == "motorola":
        text = re.sub(r"\b(moto|motorola)\b", " ", text)
    if brand_l == "google":
        text = re.sub(r"\bpixel\b", " ", text)
    tokens = tuple(re.findall(r"[a-z]+|\d+", text))
    return " ".join(tokens), tokens


def make_entry(source: str, parent: str, sub: str, model: str, url: str) -> ModelEntry:
    brand = normalize_brand(parent, sub, model)
    value = f"{brand} {sub} {model}"
    model_number = extract_model_number(value)
    year = extract_year(value)
    network = extract_network(value)
    canonical, tokens = canonicalize_model(brand, model)
    return ModelEntry(
        source=source,
        brand=brand,
        series=clean_text(sub),
        model=clean_text(model),
        url=normalize_url(url),
        parent=clean_text(parent),
        model_number=model_number,
        year=year,
        network=network,
        canonical=canonical,
        tokens=tokens,
    )


def iter_tree_models(tree: list[dict[str, Any]], source: str) -> list[ModelEntry]:
    entries: list[ModelEntry] = []
    for parent in tree:
        parent_name = clean_text(parent.get("parent_name"))
        if source == "tx" and SKIP_PARENT_RE.search(parent_name):
            continue
        if APPLE_RE.search(parent_name):
            continue
        for sub in parent.get("sub_children") or []:
            sub_name = clean_text(sub.get("sub_child_name"))
            if APPLE_RE.search(sub_name):
                continue
            for child in sub.get("children") or []:
                model = clean_text(child.get("child_name"))
                url = clean_text(child.get("child_url"))
                if not model or not url or APPLE_RE.search(model):
                    continue
                if source == "tx" and SERIES_ONLY_RE.search(model):
                    continue
                entries.append(make_entry(source, parent_name, sub_name, model, url))
    return entries


def brand_matches(tx_brand: str, ms_brand: str) -> bool:
    left = clean_text(tx_brand).lower()
    right = clean_text(ms_brand).lower()
    aliases = {
        "google": {"google", "google pixel"},
        "asus": {"asus", "asus zenfone"},
        "revvl": {"revvl", "t-mobile", "t-mobile revvl"},
    }
    return left == right or right in aliases.get(left, set()) or left in aliases.get(right, set())


def compatible_details(tx: ModelEntry, ms: ModelEntry) -> bool:
    if tx.year and ms.year and tx.year != ms.year:
        return False
    if tx.network and ms.network and tx.network != ms.network:
        return False
    return True


def score_candidate(tx: ModelEntry, ms: ModelEntry) -> tuple[int, str]:
    if not brand_matches(tx.brand, ms.brand):
        return -1000, "brand differs"
    if not compatible_details(tx, ms):
        return -900, "year or network differs"
    if tx.model_number and ms.model_number and tx.model_number == ms.model_number:
        if tx.canonical == ms.canonical or set(tx.tokens).issubset(set(ms.tokens)) or set(ms.tokens).issubset(set(tx.tokens)):
            return 100, "model number and commercial model match"
        return 65, "model number matches, commercial model differs"
    if tx.model_number and ms.model_number and tx.model_number != ms.model_number:
        return -800, "model number conflicts"
    if tx.canonical and tx.canonical == ms.canonical:
        return 90, "commercial model matches"
    return 0, "no strict match"


def match_models(tx_entries: list[ModelEntry], ms_entries: list[ModelEntry]) -> list[MatchResult]:
    results: list[MatchResult] = []
    for tx in tx_entries:
        candidates = [(score_candidate(tx, ms), ms) for ms in ms_entries]
        candidates = [(score, note, ms) for (score, note), ms in candidates if score > 0]
        candidates.sort(key=lambda item: item[0], reverse=True)
        if not candidates:
            results.append(MatchResult(tx=tx, ms=None, confidence="Rejected", notes="No MobileSentrix model match"))
            continue
        best_score, note, best = candidates[0]
        tied = [item for item in candidates if item[0] == best_score]
        if len(tied) > 1 and best_score < 100:
            results.append(MatchResult(tx=tx, ms=best, confidence="Review", notes=f"Ambiguous match: {len(tied)} candidates"))
        elif best_score >= 100:
            results.append(MatchResult(tx=tx, ms=best, confidence="Exact", notes=note))
        elif best_score >= 90:
            results.append(MatchResult(tx=tx, ms=best, confidence="High", notes=note))
        else:
            results.append(MatchResult(tx=tx, ms=best, confidence="Review", notes=note))
    return results


def stable_job_id(url: str) -> str:
    digest = hashlib.sha1(normalize_url(url).encode("utf-8")).hexdigest()[:16]
    return f"txca-ms-display-{digest}"


def folder_name(match: MatchResult) -> str:
    parts = [match.tx.brand, match.tx.model_number or "", match.tx.model]
    value = " - ".join(part for part in parts if part)
    return re.sub(r'[<>:"/\\|?*\x00-\x1F]+', " ", value).strip()[:120] or "MobileSentrix Display"


def load_progress(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"submitted_urls": {}, "updated_at": ""}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"submitted_urls": {}, "updated_at": ""}


def save_progress(path: Path, progress: dict[str, Any]) -> None:
    progress["updated_at"] = utc_now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(progress, indent=2, ensure_ascii=False), encoding="utf-8")


def fetch_existing_jobs(base_url: str, timeout: int = 15) -> dict[str, dict[str, Any]]:
    response = requests.get(f"{base_url.rstrip('/')}/jobs", timeout=timeout)
    response.raise_for_status()
    data = response.json()
    jobs = data.get("jobs") if isinstance(data, dict) else []
    return {normalize_url(job.get("url", "")): job for job in jobs or [] if job.get("url")}


def submit_to_scraper(base_url: str, match: MatchResult, timeout: int = 30) -> dict[str, Any]:
    assert match.ms is not None
    params = {
        "url": match.ms.url,
        "job_id": stable_job_id(match.ms.url),
        "folder_name": folder_name(match),
        "title_filter": DISPLAY_TITLE_FILTER,
    }
    response = requests.post(f"{base_url.rstrip('/')}/scrape", params=params, timeout=timeout)
    payload: dict[str, Any]
    try:
        payload = response.json()
    except ValueError:
        payload = {"success": False, "error": response.text[:500]}
    if response.status_code >= 400 or not payload.get("success"):
        raise RuntimeError(payload.get("error") or f"HTTP {response.status_code}")
    return payload


def report_row(match: MatchResult, status: str, images_found: int = 0, error: str = "", job_id: str = "") -> dict[str, Any]:
    tx = match.tx
    ms = match.ms
    return {
        "TX Brand": tx.brand,
        "TX Model": tx.model,
        "Model Number": tx.model_number,
        "TX URL": tx.url,
        "MobileSentrix Model": ms.model if ms else "",
        "MobileSentrix URL": ms.url if ms else "",
        "Display Type": "Display",
        "Match Confidence": match.confidence,
        "Submission Status": status,
        "Images Found": images_found,
        "Error": error,
        "Job ID": job_id,
        "Folder Name": folder_name(match) if ms else "",
        "TX Series": tx.series,
        "Release Year": tx.year,
        "Network": tx.network,
        "Match Notes": match.notes,
    }


def write_reports(rows: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "processing_report.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    pd.DataFrame(rows, columns=REPORT_COLUMNS).to_excel(output_dir / "processing_report.xlsx", index=False)
    review_rows = [row for row in rows if row["Submission Status"] in {"Review Required", "No MobileSentrix Match"}]
    pd.DataFrame(review_rows, columns=REPORT_COLUMNS).to_csv(output_dir / "manual_review_report.csv", index=False, encoding="utf-8-sig")


def run(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    progress_path = output_dir / "progress.json"
    if args.reset_progress and progress_path.exists():
        progress_path.unlink()
    progress = load_progress(progress_path)
    tx_entries = iter_tree_models(load_json(Path(args.tx_tree)), "tx")
    ms_entries = iter_tree_models(load_json(Path(args.ms_tree)), "ms")
    matches = match_models(tx_entries, ms_entries)

    existing_jobs: dict[str, dict[str, Any]] = {}
    if args.submit:
        try:
            health = requests.get(f"{args.image_scraper_url.rstrip('/')}/health", timeout=10)
            health.raise_for_status()
            existing_jobs = fetch_existing_jobs(args.image_scraper_url)
        except Exception as exc:
            raise SystemExit(f"Image scraper is not reachable at {args.image_scraper_url}: {exc}") from exc

    rows: list[dict[str, Any]] = []
    submitted = 0
    seen_urls = set(progress.get("submitted_urls", {}).keys())

    for match in matches:
        if match.confidence == "Rejected":
            rows.append(report_row(match, "No MobileSentrix Match"))
            continue
        if match.confidence == "Review":
            rows.append(report_row(match, "Review Required"))
            continue
        if not match.ms:
            rows.append(report_row(match, "No MobileSentrix Match"))
            continue

        url_key = normalize_url(match.ms.url)
        job_id = stable_job_id(match.ms.url)
        existing = existing_jobs.get(url_key)
        if url_key in seen_urls:
            metadata = progress.get("submitted_urls", {}).get(url_key, {})
            rows.append(report_row(match, "Duplicate Skipped", int(metadata.get("images_found") or 0), job_id=metadata.get("job_id") or job_id))
            continue
        if existing and str(existing.get("status", "")).lower() in {"queued", "running", "completed", "paused"}:
            rows.append(report_row(match, "Duplicate Skipped", int(existing.get("images") or 0), job_id=str(existing.get("id") or job_id)))
            progress.setdefault("submitted_urls", {})[url_key] = {
                "job_id": str(existing.get("id") or job_id),
                "status": existing.get("status"),
                "images_found": int(existing.get("images") or 0),
                "url": match.ms.url,
                "metadata": asdict(match.tx),
            }
            save_progress(progress_path, progress)
            continue
        if not args.submit:
            rows.append(report_row(match, "Submitted" if args.dry_run_status_submitted else "Dry Run", job_id=job_id))
            continue
        if args.max_submit and submitted >= args.max_submit:
            rows.append(report_row(match, "Review Required", error="Not submitted because --max-submit limit was reached", job_id=job_id))
            continue

        try:
            payload = submit_to_scraper(args.image_scraper_url, match)
            submitted += 1
            job_id = str(payload.get("job_id") or job_id)
            status = "Duplicate Skipped" if payload.get("duplicate") else "Submitted"
            rows.append(report_row(match, status, job_id=job_id))
            progress.setdefault("submitted_urls", {})[url_key] = {
                "job_id": job_id,
                "status": payload.get("status") or status,
                "images_found": 0,
                "url": match.ms.url,
                "metadata": asdict(match.tx),
                "submitted_at": utc_now(),
            }
            save_progress(progress_path, progress)
            time.sleep(max(0.0, float(args.delay)))
        except Exception as exc:
            rows.append(report_row(match, "Scraper Error", error=str(exc), job_id=job_id))

    write_reports(rows, output_dir)
    summary = {
        "tx_models": len(tx_entries),
        "ms_models": len(ms_entries),
        "rows": len(rows),
        "exact": sum(1 for row in rows if row["Match Confidence"] == "Exact"),
        "high": sum(1 for row in rows if row["Match Confidence"] == "High"),
        "review": sum(1 for row in rows if row["Submission Status"] == "Review Required"),
        "no_match": sum(1 for row in rows if row["Submission Status"] == "No MobileSentrix Match"),
        "submitted_this_run": submitted,
        "output_dir": str(output_dir),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Match TXParts Canada Android menu models to MobileSentrix Canada and queue display image scrapes.")
    parser.add_argument("--tx-tree", default=str(DEFAULT_TX_TREE))
    parser.add_argument("--ms-tree", default=str(DEFAULT_MS_TREE))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--image-scraper-url", default="http://localhost:3001")
    parser.add_argument("--submit", action="store_true", help="Queue accepted Exact/High matches in the local image scraper.")
    parser.add_argument("--max-submit", type=int, default=0, help="Optional cap for new submissions in this run.")
    parser.add_argument("--delay", type=float, default=0.15, help="Delay between image-scraper submissions.")
    parser.add_argument("--reset-progress", action="store_true", help="Delete the local submission progress file before processing.")
    parser.add_argument("--dry-run-status-submitted", action="store_true", help="Label dry-run accepted matches as Submitted in the report.")
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
