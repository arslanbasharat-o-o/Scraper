# Scraper Workspace

This repository contains two separate applications:

- [`image-scraper/`](image-scraper) - the Node.js image scraping service with Selenium, ZIP export, and Railway deployment files
- [`parts-extractor/`](parts-extractor) - the Flask-based product and category scraping workspace with automation, history, watchlist, and image tools

## Quick Start

### Image Scraper

```bash
cd image-scraper
npm install
python3 -m pip install -r requirements.txt
npm start
```

Default URL: `http://localhost:3001`

### Parts Extractor

```bash
cd parts-extractor
start.bat
```

Default URL: `http://127.0.0.1:5000`

## Repository Structure

```text
.
├── .github/
├── image-scraper/
│   ├── docs/
│   ├── frontend/
│   ├── server.js
│   ├── start.bat
│   └── README.md
├── parts-extractor/
│   ├── scrapers/
│   ├── static/
│   ├── templates/
│   ├── app.py
│   ├── start.bat
│   └── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── SECURITY.md
└── LICENSE
```

## Notes

- GitHub repository metadata, policies, and workflows stay at the root.
- Railway deployment is currently configured for [`image-scraper/`](image-scraper).
- Each subproject keeps its own runtime files, docs, and startup commands inside its folder.
