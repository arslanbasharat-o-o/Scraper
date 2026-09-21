# Server Update Guide

Whenever new updates are pushed to GitHub, run these 3 commands on the server:

```bash
# 1. Pull the latest updates
git pull origin main

# 2. Restart the scraper service
sudo systemctl restart scraper

# 3. Verify server readiness
curl -s http://localhost:5000/readyz
```

> **Note:** If you run the server manually in a terminal instead of systemctl:
> ```bash
> pkill -f "python.*app.py" && .venv/bin/python app.py &
> ```
> Visit `http://<your-server-ip>:5000/readyz` to confirm `{"status":"ready"}` or check live logs at `http://<your-server-ip>:5000/logs`.
