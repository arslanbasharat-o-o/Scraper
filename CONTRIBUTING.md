# Contributing

Thanks for contributing to this repository.

## Code of Conduct

Please read [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) before participating.

## Repository Layout

This repo contains two separate applications:

- [`image-scraper/`](image-scraper) - Node.js image scraper service plus its helper Python scripts
- [`parts-extractor/`](parts-extractor) - Flask-based product scraper and automation workspace

Repository-wide governance and GitHub automation remain at the root under [`.github/`](.github).

## Development Setup

Clone once at the repo root, then work inside the subproject you need.

### Image Scraper

```bash
cd image-scraper
npm install
python3 -m pip install -r requirements.txt
node -c server.js
python3 -m py_compile convert_image.py create_zip.py
```

### Parts Extractor

```bash
cd parts-extractor
python3 -m py_compile app.py automation_service.py database.py scrapers/*.py
pytest tests -q
```

## Branch and Commit Workflow

1. Create a branch from `main`.
2. Keep commits focused and use Conventional Commit prefixes.
3. Open a pull request with clear scope and test notes.

Commit prefixes:

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation updates
- `refactor:` non-functional code changes
- `perf:` performance improvements
- `test:` test updates
- `chore:` tooling or maintenance

## Required Checks Before PR

- Image Scraper: `cd image-scraper && npm ci && node -c server.js`
- Image Scraper Python helpers: `cd image-scraper && python3 -m py_compile convert_image.py create_zip.py`
- Parts Extractor syntax: `cd parts-extractor && python3 -m py_compile app.py automation_service.py database.py scrapers/*.py`
- Parts Extractor tests: `cd parts-extractor && pytest tests -q`
- Update docs when behavior, routes, or startup instructions change

## Pull Request Expectations

- Link related issue(s)
- Describe behavior change and risk
- Include screenshots for UI changes
- Note environment variables added or changed

## Templates and Workflow

- Use GitHub issue forms under [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE)
- Use [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) for pull requests
- CI runs from [`.github/workflows/ci.yml`](.github/workflows/ci.yml)
- Railway CD currently deploys the Image Scraper from [`.github/workflows/cd-railway.yml`](.github/workflows/cd-railway.yml)
- Release notes are auto-drafted via [`.github/workflows/release-drafter.yml`](.github/workflows/release-drafter.yml)
- Labels are managed in [`.github/labels.json`](.github/labels.json) and synced by [`.github/workflows/labels-sync.yml`](.github/workflows/labels-sync.yml)

## Questions

- Check existing [issues](https://github.com/arslanbasharat-o-o/Scraper/issues)
- Open a new issue with reproducible details
