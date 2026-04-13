#!/usr/bin/env node

/**
 * XCellParts Scraper - Cross-platform Startup Script with Requirements Check
 * Usage: node start.js
 */

const fs = require('fs');
const path = require('path');
const { execSync, spawn } = require('child_process');
const os = require('os');

// ANSI color codes
const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
};

const log = {
  header: (msg) => console.log(`${colors.blue}${msg}${colors.reset}`),
  success: (msg) => console.log(`${colors.green}✓${colors.reset} ${msg}`),
  error: (msg) => console.log(`${colors.red}✗${colors.reset} ${msg}`),
  warn: (msg) => console.log(`${colors.yellow}⚠${colors.reset} ${msg}`),
  info: (msg) => console.log(`  ${msg}`),
  step: (num, total, msg) => console.log(`${colors.yellow}[${num}/${total}]${colors.reset} ${msg}`),
};

const APP_DIR = __dirname;
const LOCAL_NODE_MODULES_PATH = path.join(APP_DIR, 'node_modules');
const SPEED_DEFAULTS = {
  IMAGE_DOWNLOAD_CONCURRENCY: '6',
  PRODUCT_DELAY_MIN_MS: '40',
  PRODUCT_DELAY_MAX_MS: '120',
  IMAGE_SELECTOR_TIMEOUT_MS: '7000',
  IMAGE_EXTRACT_RETRIES: '1',
  IMAGE_EMPTY_RETRIES: '0'
};

/**
 * Execute shell command and return output
 */
function execCommand(cmd, silent = false) {
  try {
    const nodePathEntries = (process.env.NODE_PATH || '')
      .split(path.delimiter)
      .filter(Boolean);
    if (!nodePathEntries.includes(LOCAL_NODE_MODULES_PATH)) {
      nodePathEntries.unshift(LOCAL_NODE_MODULES_PATH);
    }

    return execSync(cmd, {
      encoding: 'utf-8',
      stdio: silent ? 'pipe' : 'inherit',
      env: {
        ...process.env,
        NODE_PATH: nodePathEntries.join(path.delimiter)
      }
    })
      .trim();
  } catch (error) {
    return null;
  }
}

/**
 * Check if a command exists in PATH
 */
function commandExists(cmd) {
  const isWindows = process.platform === 'win32';
  const command = isWindows ? `where ${cmd}` : `which ${cmd}`;
  return execCommand(command, true) !== null;
}

/**
 * Get version string from command
 */
function getVersion(cmd) {
  return execCommand(`${cmd} -v`, true) || execCommand(`${cmd} --version`, true);
}

/**
 * Check if directory exists
 */
function dirExists(dirPath) {
  try {
    return fs.statSync(dirPath).isDirectory();
  } catch {
    return false;
  }
}

/**
 * Check if file exists
 */
function fileExists(filePath) {
  return fs.existsSync(filePath);
}

/**
 * Main startup routine
 */
async function main() {
  console.log('');
  log.header('================================================');
  log.header('   XCellParts Scraper - Requirements Check');
  log.header('================================================');
  console.log('');

  let passed = 0;
  let failed = 0;

  // 1. Check Node.js
  log.step(1, 5, 'Checking Node.js...');
  const nodeVersion = process.version;
  log.success(`Node.js installed (${nodeVersion})`);
  passed++;

  // 2. Check npm
  log.step(2, 5, 'Checking npm...');
  if (commandExists('npm')) {
    const npmVersion = getVersion('npm');
    log.success(`npm installed (${npmVersion})`);
    passed++;
  } else {
    log.error('npm not found!');
    log.info('npm should be bundled with Node.js. Please reinstall Node.js.');
    failed++;
  }

  // 3. Check and install Node packages
  log.step(3, 5, 'Checking Node.js dependencies...');
  const packageJsonPath = path.join(APP_DIR, 'package.json');
  if (!fileExists(packageJsonPath)) {
    log.error('package.json not found!');
    failed++;
  } else {
    const nodeModulesPath = path.join(APP_DIR, 'node_modules');
    const requiredPackages = ['express', 'selenium-webdriver', 'chromedriver', 'archiver'];

    if (!dirExists(nodeModulesPath)) {
      log.info('Installing npm packages...');
      try {
        execCommand('npm install', false);
        log.success('npm packages installed');
        passed++;
      } catch (error) {
        log.error('Failed to install npm packages');
        failed++;
      }
    } else {
      const missingPackages = requiredPackages.filter(
        (pkg) => !dirExists(path.join(nodeModulesPath, pkg))
      );

      if (missingPackages.length > 0) {
        log.info(`Missing packages: ${missingPackages.join(', ')}`);
        log.info('Installing npm packages...');
        try {
          execCommand('npm install', false);
          log.success('npm packages installed');
          passed++;
        } catch (error) {
          log.error('Failed to install npm packages');
          failed++;
        }
      } else {
        log.success('All npm packages found');
        passed++;
      }
    }
  }

  // 4. Check for Chrome/Chromium
  log.step(4, 5, 'Checking for Chrome/Chromium browser...');
  let chromeFound = false;
  const isWindows = process.platform === 'win32';
  const isMac = process.platform === 'darwin';
  const isLinux = process.platform === 'linux';

  if ([commandExists('google-chrome'), commandExists('chromium'), commandExists('chromium-browser')].includes(true)) {
    chromeFound = true;
    const cmd = commandExists('google-chrome') ? 'google-chrome' : 
                commandExists('chromium') ? 'chromium' : 'chromium-browser';
    const version = getVersion(cmd);
    log.success(`Chrome/Chromium found (${version})`);
    passed++;
  } else if (isWindows) {
    const chromePaths = [
      'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
      'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    ];
    chromeFound = chromePaths.some((p) => fileExists(p));
    if (chromeFound) {
      log.success('Google Chrome found (Windows)');
      passed++;
    }
  } else if (isMac) {
    const chromePaths = [
      '/Applications/Google Chrome.app',
      '/Applications/Chromium.app',
    ];
    chromeFound = chromePaths.some((p) => dirExists(p));
    if (chromeFound) {
      log.success('Chrome/Chromium found (macOS)');
      passed++;
    }
  }

  if (!chromeFound) {
    log.warn('Chrome/Chromium not found (optional but recommended)');
    log.info('WebDriver needs a Chrome-compatible browser for scraping');
    log.info('Install from: https://www.google.com/chrome/');
  }

  // 5. Check directories
  log.step(5, 5, 'Checking project directories...');

  const downloadDir = path.join(APP_DIR, 'downloads');
  if (!dirExists(downloadDir)) {
    log.info('Creating downloads directory...');
    try {
      fs.mkdirSync(downloadDir, { recursive: true });
      log.success('downloads directory created');
      passed++;
    } catch (error) {
      log.error('Failed to create downloads directory');
      failed++;
    }
  } else {
    log.success('downloads directory exists');
    passed++;
  }

  const frontendDir = path.join(APP_DIR, 'frontend');
  if (!dirExists(frontendDir)) {
    log.error('frontend directory not found!');
    log.info(`Expected: ${frontendDir}`);
    failed++;
  } else {
    log.success('frontend directory found');
    passed++;
  }

  // Summary
  console.log('');
  log.header('================================================');
  if (failed === 0) {
    log.success('All requirements satisfied!');
  } else {
    log.error(`${failed} requirement(s) failed`);
  }
  log.header('================================================');
  console.log('');

  // Start server if all checks passed
  if (failed === 0) {
    log.info('Starting server on port 3001...');
    log.info('  Frontend: http://localhost:3001');
    log.info('  API: http://localhost:3001');
    log.info('  Speed mode defaults enabled');
    console.log('');
    log.warn('Press Ctrl+C to stop the server');
    console.log('');

    // Start the server
    const serverPath = path.join(APP_DIR, 'server.js');
    const runtimeEnv = {
      ...process.env,
      NODE_PATH: [LOCAL_NODE_MODULES_PATH, process.env.NODE_PATH || ''].filter(Boolean).join(path.delimiter)
    };

    for (const [key, value] of Object.entries(SPEED_DEFAULTS)) {
      if (!runtimeEnv[key]) {
        runtimeEnv[key] = value;
      }
    }

    const server = spawn('node', [serverPath], {
      stdio: 'inherit',
      cwd: APP_DIR,
      env: runtimeEnv
    });

    process.on('SIGINT', () => {
      log.info('Shutting down server...');
      server.kill();
      process.exit(0);
    });

    server.on('error', (error) => {
      log.error(`Failed to start server: ${error.message}`);
      process.exit(1);
    });

    server.on('exit', (code, signal) => {
      if (signal) {
        log.error(`Server exited due to signal ${signal}`);
        process.exit(1);
        return;
      }
      if (code !== 0) {
        log.error(`Server exited with code ${code}`);
      }
      process.exit(code ?? 0);
    });
  } else {
    process.exit(1);
  }
}

// Run the startup routine
main().catch((error) => {
  log.error(`Unexpected error: ${error.message}`);
  process.exit(1);
});
