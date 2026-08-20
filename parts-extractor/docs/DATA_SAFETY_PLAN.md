# Data Safety Plan

## Protected Data

Production scrape history, items, automation jobs, run records, and checkpoints
live in `data/site_dbs/*.db`. Browser profiles, caches, logs, screenshots,
`error_logs/`, `.tmp/`, `test-tmp/`, and `output/` are diagnostic or generated
artifacts and are not the source of truth.

## Current Recovery Controls

1. Every automation run has a durable database record.
2. Progress stores completed target count, target URLs, item count, preview
   items, and resume metadata.
3. A pause, interruption, or failure keeps the same run ID resumable.
4. A failed run saves its usable partial history before it stops.
5. Resume atomically claims the existing run as `resuming`; it does not create a
   replacement job or reset completed work.
6. If the resume helper cannot launch, the run returns to `failed` with the
   checkpoint preserved.
7. Startup recovery converts abandoned `running` or `resuming` records into a
   recoverable interrupted state.

`AUTOMATION_CHECKPOINT_ITEM_LIMIT` is 100,000 items. A partial history is saved
only when the checkpoint contains the complete item payload it claims to hold.
If the count and payload disagree, the app refuses to create a misleading
partial history and leaves the run recoverable.

## Backup Procedure

Before deployment or database repair:

1. Confirm no run has status `running` or `resuming`.
2. Stop the Flask process so SQLite files are quiescent.
3. Copy the complete `data/site_dbs/` directory to a timestamped directory under
   `data/backups/`.
4. Run `PRAGMA quick_check` and `PRAGMA foreign_key_check` on both source and
   backup copies.
5. Record history counts, item counts, and the latest automation run.

Verified audit backup:
`data/backups/audit-baseline-20260724-142717/`

Verified predeployment backup, including later manual histories:
`data/backups/predeploy-20260724-182438/`

## Failed-Run Procedure

1. Do not delete the failed run or its history.
2. Read its error and completed-target count in Automation.
3. Fix the scraper or environment problem.
4. Press Resume on that same run.
5. Confirm the run changes through `resuming` to `running`.
6. Verify completed targets continue from the checkpoint.
7. After completion, verify the history item count and database integrity.

## Retention

- No automatic history deletion is enabled.
- Delete and cleanup APIs require a visible confirmation plus the destructive
  confirmation header.
- Keep at least one known-good backup before removing histories.
- Logs and browser diagnostics may be rotated after confirming they contain no
  unique incident evidence.
- Never treat a failed relationship or an old timestamp as permission to delete
  a business record.

## Recovery Objective

The controls reduce lost work to the progress since the latest durable
checkpoint. They cannot guarantee that a supplier, network, disk, or browser
will never fail. The operational promise is recoverability and preserved
history, not an impossible promise of zero failures.
