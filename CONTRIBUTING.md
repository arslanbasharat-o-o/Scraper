# Contributing

Thanks for contributing to this project.

## Code of Conduct

Please read [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) before participating.

## Development Setup

```bash
git clone https://github.com/YOUR_USERNAME/Scraper.git
cd Scraper
npm install
node -c server.js
python3 -m py_compile convert_image.py create_zip.py
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
- `chore:` tooling/maintenance

## Required Checks Before PR

- `node -c server.js`
- `python3 -m py_compile convert_image.py create_zip.py`
- Basic smoke run: `npm run server`
- Update docs when behavior or APIs change

## Pull Request Expectations

- Link related issue(s)
- Describe behavior change and risk
- Include screenshots for UI changes
- Note environment variables added/changed

## Templates and Workflow

- Use GitHub issue forms under `.github/ISSUE_TEMPLATE/`
- Use `.github/PULL_REQUEST_TEMPLATE.md` for all pull requests
- CI runs from `.github/workflows/ci.yml`
- CD to Railway runs from `.github/workflows/cd-railway.yml` when required secrets are set
- Release notes are auto-drafted via `.github/workflows/release-drafter.yml`
- Label definitions are managed in `.github/labels.json` and synced by `.github/workflows/labels-sync.yml`

## Repository Structure

```text
.
├── .github/
│   ├── ISSUE_TEMPLATE/
│   ├── workflows/
│   ├── CODEOWNERS
│   ├── labels.json
│   ├── release-drafter.yml
│   ├── dependabot.yml
│   └── PULL_REQUEST_TEMPLATE.md
├── docs/
│   ├── API_REFERENCE.md
│   ├── README.md
│   ├── DEPLOYMENT_RAILWAY.md
│   ├── QUICK_START.md
│   ├── START_SERVER.md
│   ├── OPTIMIZATION.md
│   ├── PYTHON_SETUP.md
│   └── PYTHON_CONVERSION.md
├── frontend/
├── downloads/
├── server.js
├── convert_image.py
├── create_zip.py
├── Dockerfile
├── railway.toml
├── .env.example
├── .editorconfig
├── .gitattributes
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
└── SECURITY.md
```

## Documentation Map

- Project overview: [`README.md`](README.md)
- Deployment: [`docs/DEPLOYMENT_RAILWAY.md`](docs/DEPLOYMENT_RAILWAY.md)
- Operations and tuning: [`docs/OPTIMIZATION.md`](docs/OPTIMIZATION.md)
- Python integration: [`docs/PYTHON_SETUP.md`](docs/PYTHON_SETUP.md)

## Questions

- Check existing [issues](https://github.com/arslanbasharat-o-o/Scraper/issues)
- Open a new issue with reproducible details
