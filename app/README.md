# Parts Extractor

Parts Extractor is a Flask-based scraping workspace for mobile parts suppliers. It includes multi-site scraping, session history, comparison tools, per-site SQLite databases, a shared DB-backed watchlist, and an image conversion utility.

## Features

- Multi-site scraping for MobileSentrix, XCellParts, TXParts, and Parts4Cells
- Realtime pricing and display filters on the extractor page
- Session history with comparison between runs
- Separate SQLite databases per supplier under `data/site_dbs/`
- Shared DB-backed watchlist that can be reopened later
- CSV and XLSX export tools
- Built-in image converter page

## Requirements

- Python 3.12 or newer
- pip
- A modern browser

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/parts-extractor.git
cd parts-extractor
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the app:

```bash
python app.py
```

5. Open:

```text
http://127.0.0.1:5000
```

## Project Structure

```text
parts-extractor/
|-- app.py
|-- database.py
|-- requirements.txt
|-- scrapers/
|   |-- scraper_engine.py
|   |-- xcell_scraper_engine.py
|   |-- txparts_scraper_engine.py
|   `-- parts4cells_scraper_engine.py
|-- data/
|   `-- site_dbs/
|-- static/
|   |-- css/
|   `-- js/
`-- templates/
```

## Database Notes

- Site databases are created automatically in `data/site_dbs/`
- Current site DBs include `mobilesentrix.db`, `xcellparts.db`, `txparts.db`, and `parts4cells.db`
- The watchlist is stored in the database, not just the browser

## Docker

```bash
docker build -t parts-extractor .
docker run -e PORT=5000 -p 5000:5000 parts-extractor
```

## Usage

### Extractor

1. Paste one or more supported category or product URLs.
2. Adjust pricing or display filters if needed.
3. Click `Fetch Data`.
4. Review, export, compare, or save items to the watchlist.

### Watchlist

- Save items directly from results
- Reopen them later with `View Watchlist`
- Export them with `Watchlist CSV`
- Clear them with the built-in confirmation modal

### History

- Browse previous scrape sessions
- Inspect item details
- Compare current runs against previous baselines
- Export sessions to XLSX

### Images

- Convert remote or uploaded images between supported formats
- Download processed output directly from the app

## Troubleshooting

### Scraping Issues

- If a supplier changes markup, some pages may return partial or empty results.
- If a site blocks requests, retry later or test with a different URL.

### Database Issues

- If a DB is locked, close other processes using the same SQLite file.
- If data is corrupted, remove the affected file inside `data/site_dbs/` and restart the app.

## License

MIT
