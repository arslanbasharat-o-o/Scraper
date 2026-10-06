# Production Server Update

Update the checkout and run its deployment checks:

```bash
git pull origin main && bash deploy.sh
```

On systemd hosts, `deploy.sh` installs and enables `scraper.service` if needed,
restarts it, and checks `/readyz`. Without systemd, the script prints the
Gunicorn command to start the app.

Useful endpoints:

- Dashboard: `http://<your-server-ip>:5000/`
- Readiness: `http://<your-server-ip>:5000/readyz`
- Liveness: `http://<your-server-ip>:5000/livez`
