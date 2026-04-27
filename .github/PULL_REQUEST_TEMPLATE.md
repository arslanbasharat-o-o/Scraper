## Summary

Describe what changed and why.

## Touched Areas

- [ ] `image-scraper`
- [ ] `parts-extractor`
- [ ] `.github` / CI / repo metadata

## Scope

- [ ] Bug fix
- [ ] Feature
- [ ] Refactor
- [ ] Performance
- [ ] Documentation
- [ ] CI/CD

## Linked Issues

Closes #

## Validation

List exact commands and results. Delete anything that does not apply.

```bash
# image-scraper
cd image-scraper
node -c server.js
python3 -m py_compile convert_image.py create_zip.py

# parts-extractor
cd ../parts-extractor
python3 -m py_compile app.py automation_service.py database.py scrapers/*.py
pytest tests -q

# repo metadata / workflows
git diff -- .github
```

## Notes

- Include screenshots for UI changes.
- Call out any path moves or startup command changes.
- Mention deployment impact if Railway, Docker, or GitHub Actions behavior changed.

## Checklist

- [ ] I ran local validation for touched areas.
- [ ] I updated docs for behavior/config/API changes.
- [ ] I reviewed for breaking changes.
- [ ] I added or updated tests where applicable.
- [ ] CI passes.

## Deployment Notes

- [ ] No deployment impact
- [ ] Requires environment variable changes
- [ ] Requires migration or manual follow-up

Details (if any):
