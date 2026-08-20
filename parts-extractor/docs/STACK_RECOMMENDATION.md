# Stack Recommendation

Audit date: 2026-07-24

## Decision Context

The application has four operational screens, Flask/Jinja rendering, one Python
deployment, stable same-origin JSON endpoints, SQLite persistence, no user
authentication, moderate client interaction, and two polling status views.
There is no existing Node build or frontend deployment pipeline.

The highest risks are data safety, job recovery, request compatibility, and
keeping the LAN tool easy to operate. A broad SPA migration would add routing,
build, CORS/CSRF, deployment, and state synchronization work without removing a
current business limitation.

## Candidate Scores

Scores are 1 (poor) to 10 (strong) for this application.

| Option | Safety | Maintainability | Performance | Accessibility | Productivity | Python fit | Real-time | Testing | Deployment | Scale |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Modernized vanilla + optional TypeScript | 10 | 8 | 9 | 9 | 8 | 10 | 8 | 8 | 10 | 7 |
| Flask + HTMX + Alpine | 8 | 8 | 8 | 9 | 8 | 10 | 8 | 8 | 9 | 7 |
| React + TypeScript + Vite | 5 | 9 | 8 | 8 | 6 | 6 | 9 | 9 | 5 | 9 |
| Vue 3 + TypeScript + Vite | 6 | 9 | 8 | 8 | 7 | 7 | 9 | 9 | 5 | 9 |
| Separate frontend application | 3 | 8 | 7 | 8 | 4 | 4 | 9 | 9 | 2 | 10 |

## Recommendation

Use modernized vanilla JavaScript with Flask/Jinja, ES modules introduced
incrementally, the existing CSS token system, and optional TypeScript for
isolated API/data modules after a build step is justified.

Technical reasons:

- It preserves all routes, forms, cookies, downloads, and same-origin behavior.
- It keeps one deployment and no CORS boundary.
- Four screens do not require a framework router or global state library.
- Existing DOM behavior is already covered by Python contract tests and
  Botasaurus UI checks.
- Polling is sufficient for current one-way status updates.

## Secondary Alternative

HTMX plus small Alpine components is reasonable for future server-driven forms
or partial table refreshes. It should be introduced only for a specific screen
where it removes more JavaScript than it adds. Do not mix HTMX ownership with
existing DOM mutation on the same component.

## Not Recommended

A separate React or Vue SPA is not recommended now. React/Vue themselves are
capable, but separating this frontend would require mature versioned APIs,
authentication design, CSRF/CORS decisions, a Node production build, an
independent deployment, and duplicate routing/error handling.

## Migration Sequence

1. Preserve current Flask pages and API defaults.
2. Expand contract and browser regression coverage.
3. Standardize request/error/download behavior in one API module.
4. Pilot the module on Menu Map.
5. Migrate Automation list polling and leave run details on demand.
6. Migrate History, then Extractor.
7. Consider TypeScript/Vite only when multiple extracted modules benefit from
   static contract checking.

## Risks and Rollback

The primary migration risk is changing request timing or payload shape. New API
behavior must be opt-in through query parameters or isolated modules. The
rollback is to restore the prior page script reference and stop sending the
opt-in parameter; backend defaults remain unchanged. No database rollback is
required for frontend-only phases.
