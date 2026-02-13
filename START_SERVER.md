# 🚀 XCellParts Scraper - Server Startup Guide

## Quick Start

### Option 1: Cross-Platform (Recommended)
```bash
npm start
# or
node start.js
```

### Option 2: macOS / Linux
```bash
./start.sh
# or
bash start.sh
```

### Option 3: Windows
```cmd
start.bat
```

### Option 4: Direct Server
```bash
npm run server
# or
node server.js
```

---

## What the Startup Script Does

The startup script (`start.js`, `start.sh`, or `start.bat`) automatically checks for all requirements:

✅ **Node.js & npm** - Verifies installation  
✅ **npm dependencies** - Checks and installs: `express`, `selenium-webdriver`, `sharp`, `webdriver-manager`, `chromedriver`  
✅ **Chrome/Chromium** - Looks for browser (required for web scraping)  
✅ **Project directories** - Creates missing `downloads/` folder, verifies `frontend/` exists  

---

## Requirements

### Minimum
- **Node.js** v14+ ([Download](https://nodejs.org/))
- **npm** v6+ (bundled with Node.js)
- **4GB RAM** minimum

### Optional but Recommended
- **Google Chrome** or **Chromium** (for web scraping with Selenium)
  - [Chrome Download](https://www.google.com/chrome/)
  - [Chromium Download](https://www.chromium.org/getting-involved/download-chromium)

---

## Server Details

- **Port**: 3001
- **Frontend**: http://localhost:3001
- **API Base**: http://localhost:3001

### Main Endpoints
- `GET /` - Serve frontend UI
- `POST /scrape` - Start a scrape job
- `GET /jobs` - List all jobs
- `GET /logs` - Stream server logs (SSE)
- `GET /gallery/:jobId` - Get scraped images for job

---

## Troubleshooting

### "Cannot find module 'express'"
```bash
npm install
```

### "Chrome not found"
The scraper needs a Chrome-compatible browser. Install Google Chrome or Chromium.

### "Unable to obtain browser driver" / Selenium Manager error
Run startup with dependency checks (this also wires `NODE_PATH` correctly for this folder name):
```bash
npm start
```

If needed, reinstall explicitly:
```bash
NODE_PATH="$(pwd)/node_modules" npm install
```

### "Permission denied" (macOS/Linux)
```bash
chmod +x start.sh
./start.sh
```

### Port 3001 already in use
Kill the existing process:
```bash
# macOS/Linux
lsof -ti:3001 | xargs kill -9

# Windows
netstat -ano | findstr :3001
taskkill /PID <PID> /F
```

---

## npm Scripts

```bash
npm start              # Start with requirements check (cross-platform)
npm run start:linux    # Start on Linux/macOS
npm run start:windows  # Start on Windows
npm run server         # Direct server run (skips checks)
```

---

## Project Structure

```
/
├── server.js              # Main Node.js server
├── start.js               # Cross-platform startup script
├── start.sh               # macOS/Linux startup script
├── start.bat              # Windows startup script
├── package.json           # Node dependencies
├── requirements.txt       # Python packages (if needed)
├── downloads/             # Auto-created scrape folder
├── frontend/              # Web UI files
│   ├── index.html
│   ├── admin.html
│   ├── js/
│   └── css/
├── products.json          # Scraped product data
└── jobs-db.json          # Job history (auto-created)
```

---

## Environment Variables (Optional)

Create a `.env` file in the project root:

```env
PORT=3001
NODE_ENV=production
CHROME_HEADLESS=true
CHROME_BIN=/path/to/chrome
CHROMEDRIVER_PATH=/path/to/chromedriver
IMAGE_DOWNLOAD_CONCURRENCY=6
PRODUCT_DELAY_MIN_MS=40
PRODUCT_DELAY_MAX_MS=120
IMAGE_SELECTOR_TIMEOUT_MS=7000
IMAGE_EXTRACT_RETRIES=1
IMAGE_EMPTY_RETRIES=0
```

## System Requirements by OS

### macOS
- Node.js 14+
- Chrome/Chromium from App Store or brew
- 4GB RAM minimum

### Linux
- Node.js 14+
- Chrome or Chromium via package manager
- 4GB RAM minimum

### Windows
- Node.js 14+ LTS recommended
- Chrome from microsoft.com or installer
- 4GB RAM minimum

---

## Performance Tips

1. **Disable Headless Mode** (see terminal output)
2. **Increase Timeouts** if network is slow
3. **Reduce Concurrency** if memory issues occur
4. **Use SSD** for faster disk I/O

---

**Questions?** Check the console output for detailed error messages.
