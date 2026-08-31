# Contributing

Thank you for improving Parts Extractor.

## Development Setup

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pytest
```

## Local Checks

Run these before opening a pull request:

```bash
python -m py_compile app.py automation_service.py database.py scripts/resume_automation_run.py scrapers/*.py
pytest tests -q
```

## Branch and Commit Workflow

1. Create a branch from `main`.
2. Keep commits focused.
3. Include test notes with every pull request.

Recommended commit prefixes:

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation update
- `perf:` performance improvement
- `test:` test update
- `chore:` maintenance

## Pull Requests

Pull requests should include:

- A short summary of the change.
- Any behavior or deployment risk.
- Screenshots for UI changes.
- Environment variables added or changed.
- Tests run locally.
