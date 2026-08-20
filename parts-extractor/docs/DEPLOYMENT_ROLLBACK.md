# Deployment and Rollback

## Safe Deployment

1. Confirm `/api/automation/runs?limit=50` contains no `running` or `resuming`
   run.
2. Disable or pause scheduled jobs that must not start during deployment.
3. Verify the latest timestamped copy under `data/backups/`.
4. Run the full test suite and syntax checks.
5. Stop only the process that owns the Parts Extractor port.
6. Start the app from the project directory with headless browser defaults:

```powershell
$env:OPEN_BROWSER = "0"
$env:FLASK_DEBUG = "0"
$env:PORT = "5000"
.\start.bat
```

7. Verify:

```text
http://127.0.0.1:5000/api/health
http://127.0.0.1:5000/api/statistics
http://<LAN-IP>:5000/
```

8. Confirm run 21 is still completed with 13,385 items and no run started
   automatically.

Do not expose port 5000 directly to the internet. The app has no login system.

## Application Rollback

1. Pause schedules and stop the server.
2. Restore the previous application files or Git revision.
3. Do not replace databases unless a database regression is confirmed.
4. Restart and verify health, statistics, histories, and automation status.

The database changes in this audit are additive and backward compatible. Older
application code may not understand `resuming`, so code rollback should occur
only while no run is in that state.

## Database Rollback

Database restore is a last resort:

1. Stop Flask and all resume helper processes.
2. Copy the current `data/site_dbs/` to a new incident backup.
3. Select the exact timestamped backup to restore.
4. Compare history and item counts so post-backup business records are not
   silently discarded.
5. Restore only the affected database file.
6. Run `PRAGMA quick_check` and `PRAGMA foreign_key_check`.
7. Restart and verify the affected history and automation run.

Verified baseline:
`data/backups/audit-baseline-20260724-142717/`

That backup predates several valid manual histories created later on July 24.
Restoring it wholesale would discard those later records. Recover individual
records or merge additively when possible.

Preferred current rollback backup:
`data/backups/predeploy-20260724-182438/`

## Post-Deployment Checks

- `/api/health` returns `healthy` and `browser_engine: botasaurus`.
- Local and LAN URLs respond.
- No visible browser windows open during scraping.
- No run changes from paused/disabled without an explicit action or due schedule.
- Resume claims the same run ID.
- History and item totals do not unexpectedly fall.

## Current Network State

- Local URL: `http://127.0.0.1:5000/`
- Wi-Fi URL: `http://192.168.1.3:5000/`
- Binding: `0.0.0.0:5000`
- Wi-Fi profile: Private
- HTTP and TCP checks on the Wi-Fi address: passed

Adding a Windows Firewall rule requires an elevated administrator terminal. If
another device is blocked, run this once as Administrator:

```powershell
New-NetFirewallRule `
  -DisplayName "Parts Extractor - TCP 5000 (Private LAN)" `
  -Description "Allow Parts Extractor from devices on the local private subnet only." `
  -Enabled True `
  -Direction Inbound `
  -Action Allow `
  -Profile Private `
  -Protocol TCP `
  -LocalPort 5000 `
  -RemoteAddress LocalSubnet
```

Do not create a Public-profile or internet-wide rule because the app has no
authentication.
