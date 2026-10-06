# Parts Extractor

Parts Extractor is a production-oriented catalog scraper and dashboard for
eight supplier catalogs. It collects category and product details, maintains
SQLite-backed history, and supports resumable scheduled runs.

## Features

- Supplier scrapers for MobileSentrix (US and Canada), XCell Parts, TX Parts
  (US and Canada), Parts4Cells, Phone LCD Parts, and GadgetFix.
- Category discovery, product enrichment, price history, and duplicate-aware
  catalog comparison.
- Resumable automation with durable checkpoints.
- A bounded HTTP-first fetch pipeline using Scrapling and browser fallbacks.

## Production Deployment

The supported deployment target is Ubuntu/Linux with systemd. The deployment
script prepares the virtual environment, installs dependencies, creates a
secure `.env` from the 40 GB server template when needed, runs preflight checks,
and installs or restarts a single-worker `scraper.service`.

```bash
git clone https://github.com/arslanbasharat-o-o/Scraper.git
cd Scraper
bash deploy.sh
```

Review `.env` and configure supplier credentials and a proxy before running
production scrape jobs. See [DEPLOYMENT.md](DEPLOYMENT.md) for prerequisites,
updates, and server operations.

## Configuration

The 40 GB KVM example is [`.env.server-40gb.example`](.env.server-40gb.example).
Copy it to `.env` only when configuring manually; never commit real credentials
or secrets. See [SECURITY.md](SECURITY.md) before exposing the dashboard.

## Project Layout

```text
.
├── app.py
├── automation_service.py
├── database.py
├── deploy.sh
├── data/menu_map_seeds/   # checked-in supplier category baselines
├── docs/
├── scrapers/
├── scripts/               # deployment operations and diagnostics
├── static/
├── templates/
└── tests/
```

## Validation

```bash
python -m pip install -r requirements-dev.txt
python -m py_compile app.py automation_service.py database.py scrapers/*.py
pytest -q
```

## License

See [LICENSE](LICENSE).
