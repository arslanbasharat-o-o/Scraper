# Production Server Update & Setup Guide

### Option A: First-Time Setup (Install Chrome & Configure Environment)
Run this once to pull the new version, automatically install official Google Chrome (`.deb`), and check system health:

```bash
# 1. Pull latest code from GitHub
git pull origin main

# 2. Install official Google Chrome & configure virtualenv
bash scripts/setup_server.sh

# 3. Restart scraper service & verify health
sudo systemctl restart scraper && curl -s http://localhost:5000/readyz
```

---

### Option B: Routine Updates (Chrome Already Installed)
For all future updates where Chrome is already installed on the VPS:

```bash
# 1. Pull the latest updates
git pull origin main

# 2. Restart the scraper service
sudo systemctl restart scraper

# 3. Verify server readiness
curl -s http://localhost:5000/readyz
```

---

### Accessing Dashboards
- **Server Logs Dashboard**: `http://<your-server-ip>:5000/logs`
- **Health / Readiness Check**: `http://<your-server-ip>:5000/readyz`
- **Automation Jobs**: `http://<your-server-ip>:5000/automation`
