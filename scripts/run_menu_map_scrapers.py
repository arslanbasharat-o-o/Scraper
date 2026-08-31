from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd


MODULES = {
    "xcellparts": "scrapers.menu_map.xcellparts",
    "parts4cells": "scrapers.menu_map.parts4cells",
    "phonelcdparts": "scrapers.menu_map.phonelcdparts",
    "mobilesentrix": "scrapers.menu_map.mobilesentrix",
    "mobilesentrix_canada": "scrapers.menu_map.mobilesentrix_canada",
    "txparts": "scrapers.menu_map.txparts",
    "txparts_canada": "scrapers.menu_map.txparts_canada",
    "gadgetfix": "scrapers.menu_map.gadgetfix",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--sites", nargs="*", choices=sorted(MODULES))
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--timeout", type=int, default=60000)
    parser.add_argument("--interaction-delay", type=int, default=600)
    parser.add_argument("--scroll-delay", type=int, default=250)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--validate-urls", action="store_true")
    parser.add_argument("--skip-url-validation", action="store_true")
    parser.add_argument("--save-parent-screenshots", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    return parser


def selected_sites(args: argparse.Namespace) -> list[str]:
    if args.all or not args.sites:
        return list(MODULES)
    return args.sites


def command_for(site: str, args: argparse.Namespace) -> list[str]:
    cmd = [sys.executable, "-m", MODULES[site], "--headless"]
    for flag in ("inspect_only", "validate_urls", "skip_url_validation", "save_parent_screenshots"):
        if getattr(args, flag):
            cmd.append("--" + flag.replace("_", "-"))
    for name in ("output_dir", "timeout", "interaction_delay", "scroll_delay", "max_retries", "log_level"):
        cmd.extend(["--" + name.replace("_", "-"), str(getattr(args, name))])
    return cmd


def merge_outputs(output_root: Path, sites: list[str]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    frames = []
    nested = []
    errors = []
    for site in sites:
        site_dir = output_root / site
        csv_path = site_dir / "categories.csv"
        json_path = site_dir / "categories.json"
        err_path = site_dir / "scraping_errors.json"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            frames.append((site, df))
        if json_path.exists():
            nested.extend(json.loads(json_path.read_text(encoding="utf-8")))
        if err_path.exists():
            errors.extend(json.loads(err_path.read_text(encoding="utf-8")))
    if not frames:
        return
    all_df = pd.concat([df for _, df in frames], ignore_index=True)
    all_df.to_csv(output_root / "all_websites_categories.csv", index=False, encoding="utf-8-sig")
    (output_root / "all_websites_categories.json").write_text(json.dumps(nested, indent=2, ensure_ascii=False), encoding="utf-8")
    duplicate_urls = all_df[all_df["normalized_url"].fillna("").duplicated(keep=False) & all_df["normalized_url"].fillna("").ne("")]
    summary = pd.DataFrame(
        [
            {"metric": "Sites merged", "value": len(frames)},
            {"metric": "Total rows", "value": len(all_df)},
            {"metric": "Unique URLs", "value": all_df["normalized_url"].dropna().nunique()},
            {"metric": "Duplicate URL rows", "value": len(duplicate_urls)},
            {"metric": "Errors", "value": len(errors)},
        ]
    )
    with pd.ExcelWriter(output_root / "all_websites_categories.xlsx", engine="openpyxl") as writer:
        all_df.to_excel(writer, sheet_name="All Websites", index=False)
        for site, df in frames:
            df.to_excel(writer, sheet_name={
                "xcellparts": "XCell Parts",
                "parts4cells": "Parts4Cells",
                "phonelcdparts": "Phone LCD Parts",
                "mobilesentrix": "MobileSentrix",
                "mobilesentrix_canada": "MobileSentrix CA",
                "txparts": "TXParts",
                "txparts_canada": "TXParts CA",
                "gadgetfix": "GadgetFix",
            }[site], index=False)
        duplicate_urls.to_excel(writer, sheet_name="Duplicate URLs", index=False)
        pd.DataFrame(errors).to_excel(writer, sheet_name="Errors", index=False)
        summary.to_excel(writer, sheet_name="Summary", index=False)


async def main() -> None:
    args = build_parser().parse_args()
    sites = selected_sites(args)
    statuses = []
    for site in sites:
        cmd = command_for(site, args)
        print(f"Running {site}: {' '.join(cmd)}")
        proc = subprocess.run(cmd, text=True)
        statuses.append({"site": site, "returncode": proc.returncode})
        if proc.returncode != 0:
            print(f"{site} failed with exit code {proc.returncode}; continuing.")
    if not args.inspect_only:
        merge_outputs(Path(args.output_dir), sites)
    print("Final execution summary:")
    for status in statuses:
        print(f"  {status['site']}: exit_code={status['returncode']}")


if __name__ == "__main__":
    asyncio.run(main())
