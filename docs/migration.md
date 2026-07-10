# Migration Guide (v1 → v2)

SkillLoop **0.2.0** upgrades the local SQLite store from schema **v1** to schema **v2**.
This is a one-time, automatic upgrade.

## What changed

- Added a `content_hash` column used to deduplicate and verify raw traces.
- Added new indexes to support bulk insert/query paths and a busy-timeout.
- The migration runs inside a transaction, so it is **atomic**: either it fully
  applies or the store is left unchanged. **No data loss** occurs on success or failure.

## Before you upgrade

1. Back up your state directory (contains the SQLite DB and any exported datasets):

   ```bash
   cp -R ~/.skillloop ~/.skillloop.bak-$(date +%Y%m%d)
   ```

2. Run the pre-flight diagnostic to confirm the environment is healthy:

   ```bash
   skillloop doctor
   # or
   python -m skillloop doctor
   ```

   `doctor` checks Python version, install integrity, and store reachability before
   you touch any data.

## During the upgrade

The v1 → v2 migration happens automatically the first time 0.2.0 opens the store. You
do not need to run a separate command. If you start from a fresh install there is
nothing to migrate.

## Installing the new version

```bash
pipx install git+https://github.com/lamenting-hawthorn/skillloop.git@v0.2.0
```

Or upgrade an existing install:

```bash
pipx upgrade skillloop
```

## Rolling back

If you need to revert, restore your pre-upgrade backup and reinstall the previous
version. The v2 store is not readable by v1, so the backup is the safe path.
