# Production Server Update & Setup Guide

### The All-In-One Fix & Auto-Run (Recommended)
Run this single command. It will automatically detect any fake/snap Chrome symlinks, install official Google Chrome (`.deb`), verify DevTools remote debugging sockets, update dependencies, restart the scraper service, and verify health:

```bash
git pull origin main && sudo bash scripts/auto_fix.sh
```

> [!NOTE]
> `scripts/auto_fix.sh` automatically installs a Git `post-merge` hook. For **all future updates**, simply running `git pull origin main` will automatically run the heal, update, service restart, and readiness check without any extra commands!

---

### Routine Updates (After Hook is Installed)
For all future updates:

```bash
git pull origin main
```
*(The post-merge hook will automatically execute `scripts/auto_fix.sh`, restart the service, and verify health)*

---

### Accessing Dashboards
- **Server Logs Dashboard**: `http://<your-server-ip>:5000/logs`
- **Health / Readiness Check**: `http://<your-server-ip>:5000/readyz`
- **Automation Jobs**: `http://<your-server-ip>:5000/automation`
