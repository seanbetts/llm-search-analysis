# Backup and Restore Guide

Complete guide for backing up and restoring the SQLite database in the LLM Search Analysis application.

## Quick Reference

```bash
# Create a backup
./scripts/backup-database.sh

# Restore from a backup
./scripts/restore-database.sh ./backups/llm_search_20250102_143000.db

# Verify Docker setup
./scripts/verify-docker-setup.sh
```

---

## Why Backup?

SQLite databases should be backed up regularly to protect against:

- **Data loss** - Accidental deletion, corruption, or hardware failure
- **Migration errors** - Testing schema changes safely
- **Development mistakes** - Reverting to a known-good state
- **Version upgrades** - Preserving data before major updates

---

## Backup Strategy

###Recommended Backup Schedule

| Frequency | When | Method |
|-----------|------|--------|
| **Before deployment** | Before any Docker rebuild or code update | Manual backup script |
| **Daily** | End of day if actively using | Automated cron job |
| **Weekly** | Sunday night | Automated cron job |
| **Before major changes** | Schema migrations, bulk imports | Manual backup script |

### Retention Policy

The backup script automatically:
- ✅ Keeps the **10 most recent** backups
- ✅ Deletes older backups automatically
- ✅ Names backups with timestamps for easy identification

**Customize retention:**
```bash
# Edit scripts/backup-database.sh
# Change this line to keep more/fewer backups:
OLD_BACKUPS=$(ls -1t "$BACKUP_DIR"/*.db 2>/dev/null | tail -n +11)  # Keep 10
```

---

## Manual Backup

### Create a Backup

```bash
# Run from project root
./scripts/backup-database.sh

# Or specify custom backup directory
./scripts/backup-database.sh /path/to/backups
```

**Output:**
```
🗄️  SQLite Database Backup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Database Info:
   File: backend/data/llm_search.db
   Size: 4.8M
   Interactions: 72

💾 Creating backup...
🔍 Verifying backup integrity...
✅ Backup created successfully

📁 Backup Details:
   File: ./backups/llm_search_20250102_143000.db
   Size: 4.8M
   Created: Thu Jan 2 14:30:00 2025
```

### What the Backup Script Does

1. **Validates** source database exists
2. **Creates** timestamped backup using SQLite's `.backup` command (hot backup)
3. **Verifies** backup integrity with `PRAGMA integrity_check`
4. **Displays** backup details and statistics
5. **Cleans up** old backups (keeps 10 most recent)

### Backup File Format

```
./backups/llm_search_YYYYMMDD_HHMMSS.db
```

**Example:**
```
llm_search_20250102_143000.db
           ^^^^^^^^  ^^^^^^
           Date      Time
```

---

## Restore from Backup

### Restore Process

```bash
# 1. List available backups
ls -lht ./backups/*.db

# 2. Restore from specific backup
./scripts/restore-database.sh ./backups/llm_search_20250102_143000.db
```

**Interactive Restore:**
```
♻️  SQLite Database Restore
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 Verifying backup integrity...
✅ Backup file is valid

📊 Backup Info:
   File: ./backups/llm_search_20250102_143000.db
   Size: 4.8M
   Date: Jan 2 14:30
   Interactions: 72

⚠️  Current Database (will be replaced):
   File: backend/data/llm_search.db
   Size: 4.9M
   Interactions: 75

⚠️  WARNING: This will replace the current database!

A backup of the current database will be created first.

Continue with restore? (yes/no):
```

**Force Restore (no prompts):**
```bash
./scripts/restore-database.sh ./backups/llm_search_20250102_143000.db --force
```

### What the Restore Script Does

1. **Validates** backup file exists and is not corrupted
2. **Backs up** current database (safety measure)
3. **Prompts** for confirmation (unless `--force`)
4. **Stops** Docker containers (if running)
5. **Replaces** current database with backup
6. **Verifies** restored database integrity
7. **Restarts** Docker containers (if they were stopped)

### Safety Features

- ✅ **Automatic backup** of current database before restore
- ✅ **Integrity check** on both backup and restored database
- ✅ **Interactive confirmation** (can be skipped with `--force`)
- ✅ **Rollback** if restore fails (restores pre-restore backup)
- ✅ **Docker handling** (stops containers during restore, restarts after)

---

## Automated Backups

### Daily Backup (Cron Job)

Add to your crontab:

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * cd /path/to/llm-search-analysis && ./scripts/backup-database.sh >> /var/log/llm-backup.log 2>&1
```

### Weekly Backup (Cron Job)

```bash
# Add weekly backup every Sunday at 3 AM
0 3 * * 0 cd /path/to/llm-search-analysis && ./scripts/backup-database.sh /path/to/weekly-backups >> /var/log/llm-backup-weekly.log 2>&1
```

### Backup Before Docker Operations

```bash
# In your deployment script
#!/bin/bash
echo "Creating backup before deployment..."
./scripts/backup-database.sh

echo "Rebuilding containers..."
docker-compose down
docker-compose up -d --build

echo "Verifying deployment..."
./scripts/verify-docker-setup.sh
```

---

## Troubleshooting

### Backup Script Issues

#### "Database file not found"

**Problem:** Running script from wrong directory.

**Solution:**
```bash
# Must run from project root
cd /path/to/llm-search-analysis
./scripts/backup-database.sh
```

#### "Backup integrity check failed"

**Problem:** Source database is corrupted.

**Solution:**
```bash
# Check database integrity
sqlite3 backend/data/llm_search.db "PRAGMA integrity_check;"

# If corrupted, restore from previous backup
./scripts/restore-database.sh ./backups/llm_search_YYYYMMDD_HHMMSS.db
```

### Restore Script Issues

#### "Backup file is corrupted"

**Problem:** Backup file cannot be validated.

**Solution:**
```bash
# Try a different backup
ls -lht ./backups/*.db
./scripts/restore-database.sh ./backups/llm_search_OLDER_DATE.db
```

#### "Docker containers still running"

**Problem:** Containers should be stopped during restore.

**Solution:**
```bash
# Manual restore process
docker-compose down
./scripts/restore-database.sh ./backups/llm_search_20250102_143000.db --force
docker-compose up -d
```

### Database Locked Errors

**Problem:** Database is locked during backup.

**Solution:**
```bash
# Stop containers first
docker-compose down

# Create backup
./scripts/backup-database.sh

# Restart containers
docker-compose up -d
```

---

## Backup Best Practices

### ✅ DO

- **Backup before deployment** - Always backup before rebuilding containers
- **Test restores periodically** - Verify backups work (quarterly)
- **Store backups off-machine** - Copy to cloud storage or external drive
- **Backup before schema changes** - Migrations can fail
- **Automate backups** - Use cron for daily/weekly backups
- **Monitor backup size** - Ensure backups are growing as expected

### ❌ DON'T

- **Don't backup while containers running** - Can cause inconsistencies (stop containers first)
- **Don't store only one backup** - Keep multiple historical backups
- **Don't ignore backup failures** - Check logs if automated backups fail
- **Don't skip integrity checks** - Always verify backup is valid
- **Don't delete old backups manually** - Let script manage retention

---

## Manual Backup Methods

If scripts aren't available, you can backup manually:

### Using SQLite Command

```bash
# Stop containers
docker-compose down

# Hot backup (safe while app running)
sqlite3 backend/data/llm_search.db ".backup './backups/manual_backup.db'"

# Restart containers
docker-compose up -d
```

### Using File Copy

```bash
# WARNING: Only use when containers are stopped!
docker-compose down

# Copy file
cp backend/data/llm_search.db ./backups/manual_backup_$(date +%Y%m%d).db

# Restart
docker-compose up -d
```

### Verify Manual Backup

```bash
# Check integrity
sqlite3 ./backups/manual_backup.db "PRAGMA integrity_check;"
# Should output: ok

# Check data
sqlite3 ./backups/manual_backup.db "SELECT COUNT(*) FROM responses;"
```

---

## Disaster Recovery

### Full Recovery Procedure

If database is completely lost:

1. **Stop application**
   ```bash
   docker-compose down
   ```

2. **Restore from most recent backup**
   ```bash
   ./scripts/restore-database.sh ./backups/llm_search_LATEST.db --force
   ```

3. **Verify restoration**
   ```bash
   sqlite3 backend/data/llm_search.db "PRAGMA integrity_check;"
   sqlite3 backend/data/llm_search.db "SELECT COUNT(*) FROM responses;"
   ```

4. **Start application**
   ```bash
   docker-compose up -d
   ```

5. **Verify application**
   ```bash
   ./scripts/verify-docker-setup.sh
   ```

### Point-in-Time Recovery

To recover to a specific point in time:

```bash
# List backups with timestamps
ls -lht ./backups/*.db

# Find backup closest to desired time
# Example: Restore to Jan 2, 14:30
./scripts/restore-database.sh ./backups/llm_search_20250102_143000.db
```

---

## Backup Storage

### Local Storage

Backups are stored in `./backups/` by default:

```
llm-search-analysis/
├── backups/
│   ├── llm_search_20250102_143000.db (4.8M)
│   ├── llm_search_20250102_020000.db (4.7M)
│   ├── llm_search_20250101_143000.db (4.6M)
│   └── ...
├── backend/
│   └── data/
│       └── llm_search.db (current database)
└── scripts/
    ├── backup-database.sh
    └── restore-database.sh
```

### Cloud Storage (Recommended)

Copy backups to cloud storage for disaster recovery:

```bash
# AWS S3
aws s3 cp ./backups/ s3://my-bucket/llm-backups/ --recursive

# Google Cloud Storage
gsutil -m cp -r ./backups/ gs://my-bucket/llm-backups/

# Rsync to remote server
rsync -avz ./backups/ user@backup-server:/backups/llm-search/
```

### Automated Cloud Upload

```bash
# Add to cron after backup
0 2 * * * cd /path/to/llm-search-analysis && ./scripts/backup-database.sh && aws s3 sync ./backups/ s3://my-bucket/llm-backups/
```

---

## Migration to PostgreSQL

When ready to migrate from SQLite to PostgreSQL, backups are still valuable:

```bash
# 1. Final SQLite backup
./scripts/backup-database.sh

# 2. Export to SQL
sqlite3 backend/data/llm_search.db .dump > llm_search_export.sql

# 3. Import to PostgreSQL
psql -U postgres -d llm_search < llm_search_export.sql

# 4. Keep SQLite backup for rollback
mv backend/data/llm_search.db backend/data/llm_search_sqlite_backup.db
```

---

## Related Documentation

- **Environment Variables:** [ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md)
- **Docker Setup Verification:** Run `./scripts/verify-docker-setup.sh`
- **Deployment Guide:** [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
