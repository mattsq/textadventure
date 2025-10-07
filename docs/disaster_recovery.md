# Disaster Recovery Procedures

This runbook explains how to restore the text adventure editor and runtime after
accidental scene mutations, data corruption, or infrastructure failures. Follow
these steps to prepare for incidents, triage active problems, and safely roll
back to a known-good dataset.

## Preparation Checklist

Before an incident occurs, ensure the following safeguards are in place:

- Configure `TEXTADVENTURE_AUTOMATIC_BACKUP_DIR` so every destructive scene
  mutation triggers a JSON snapshot written to disk. The service stores backups
  as `scene-backup-<timestamp>-<checksum>.json` making it easy to sort by
  version.
- Optionally mirror backups to cloud storage by configuring
  `TEXTADVENTURE_AUTOMATIC_BACKUP_S3_BUCKET` (plus the companion prefix, region,
  and endpoint variables when needed). This provides an off-host copy if the
  primary machine becomes unavailable.
- Set a reasonable `TEXTADVENTURE_AUTOMATIC_BACKUP_RETENTION` so the on-disk
  backup directory retains enough history for incident response while pruning
  stale snapshots automatically.
- Regularly verify that backups are produced by triggering a harmless edit in a
  staging environment and confirming the JSON file appears locally (and in S3
  when enabled).
- Document who has permission to apply imports or restore backups so that only
  trained operators can execute the steps below.

## Immediate Response

When corruption or accidental changes are detected:

1. **Freeze mutations.** Stop the CLI/editor instance or revoke write access to
   prevent new changes while the investigation is in progress.
2. **Capture forensic data.** Export the current dataset with
   `GET /api/scenes/export` (or grab the latest automatic backup) so you can
   analyse what changed after the incident.
3. **Notify stakeholders.** Inform editors or players about the downtime window
   to prevent conflicting edits.

## Identify a Restore Point

Automatic backups and manual exports share the same JSON payload structure. Use
these techniques to choose a target version:

- **Local backups:** Inspect the directory configured by
  `TEXTADVENTURE_AUTOMATIC_BACKUP_DIR`. The newest file is usually the fastest
  recovery option, but you can select an older snapshot if required.
- **Cloud backups:** List objects in the configured bucket/prefix (for example
  `aws s3 ls s3://<bucket>/<prefix>/`) and download the desired JSON file.
- **Manual exports:** If you captured forensic data in the previous step,
  consider rolling back to that payload after verifying the contents.

## Validate the Candidate Dataset

Before applying a rollback, preview the differences between the current scenes
and the backup using the rollback planning endpoint:

```bash
http POST :8000/api/scenes/rollback \
  scenes:=@scene-backup-20240630T184500Z.json \
  generated_at="2024-06-30T18:45:00Z"
```

The response reports the version metadata, a diff summary, and an import plan
with the `replace` strategy. Review the `summary` and `entries` arrays to ensure
the rollback will only revert the intended changes. Repeat this process with
additional backups until you are confident about the target dataset.

## Apply the Rollback

Once you have selected a backup:

1. **Create an extra safety snapshot.** Call `POST /api/scenes/export` to record
   the pre-rollback state or manually copy the current dataset file. This allows
   you to undo the rollback if needed.
2. **Import the backup using the replace strategy:**

   ```bash
   http POST :8000/api/scenes/import \
     scenes:=@scene-backup-20240630T184500Z.json \
     schema_version:=2
   ```

   The service automatically applies the `replace` plan when the uploaded data
   matches a previously validated snapshot. If you are applying the rollback via
   a custom script, call `SceneService.plan_rollback` first and then pass the
   same dataset to `SceneService.import_scenes(strategy=ImportStrategy.REPLACE)`.
3. **Confirm success.** Re-run `GET /api/scenes/export` or launch the CLI to
   spot-check critical scenes. Verify that analytics (reachability, quality,
   item flow) no longer report the original incident.

## Post-Recovery Follow-Up

- Re-enable editor or CLI access once the restored dataset is verified.
- Archive the incident artefacts (diff reports, exported datasets, relevant log
  files) in your team’s shared location for auditing.
- Create action items to address the root cause (for example, tightening review
  processes or adding automated validation before imports).
- Consider increasing backup frequency or retention if the rollback required
  digging far into history.

Keeping this runbook with your deployment notes shortens recovery time and
provides a repeatable process for future operators.
