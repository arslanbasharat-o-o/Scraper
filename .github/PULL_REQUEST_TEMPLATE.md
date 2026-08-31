## Summary

Describe what changed and why.

## Scope

- [ ] Bug fix
- [ ] Feature
- [ ] Refactor
- [ ] Performance
- [ ] Documentation
- [ ] CI/CD

## Validation

List exact commands and results.

```bash
python -m py_compile app.py automation_service.py database.py scripts/resume_automation_run.py scrapers/*.py
pytest tests -q
```

## Checklist

- [ ] I reviewed the deployment impact.
- [ ] I updated docs for behavior, config, or API changes.
- [ ] I added or updated tests where applicable.
- [ ] CI passes.

## Deployment Notes

- [ ] No deployment impact
- [ ] Requires environment variable changes
- [ ] Requires database or runtime data maintenance
- [ ] Requires service restart

Details:
