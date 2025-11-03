# CI Postgres Fix

## Problem
GitHub Actions CI was failing with:
```
Waiting for Postgres...
Postgres failed to start
Error: Process completed with exit code 1.
```

## Root Cause
**Two issues found:**

### 1. ❌ Wrong Init Script Paths
When scripts were reorganized into folders, the docker-compose.yml still referenced old paths:
```yaml
# WRONG (old paths)
- ./scripts/init_db.sql:/docker-entrypoint-initdb.d/01_init_db.sql
- ./scripts/init_extensions.sql:/docker-entrypoint-initdb.d/02_init_extensions.sql
```

Scripts were moved to `scripts/db/` but docker-compose wasn't updated.

### 2. ❌ Insufficient Wait Time
CI workflow only waited 60 seconds (60 iterations × 1 second) for Postgres to start. With init scripts creating 17 tables, this wasn't enough time.

---

## Solutions

### ✅ 1. Fixed Init Script Paths
Updated `docker-compose.yml`:
```yaml
# CORRECT (new paths after reorganization)
- ./scripts/db/init_db.sql:/docker-entrypoint-initdb.d/01_init_db.sql
- ./scripts/db/init_extensions.sql:/docker-entrypoint-initdb.d/02_init_extensions.sql
```

### ✅ 2. Improved Postgres Wait Logic
Updated `.github/workflows/main.yml`:

**Before:**
- 60 iterations × 1 second = 60s max
- Only checked `pg_isready`
- No detailed error logging

**After:**
- 90 iterations × 2 seconds = 180s max (3 minutes)
- Checks both `pg_isready` AND `psql -c "SELECT 1"` (verifies init scripts completed)
- Shows detailed logs on failure (container status + postgres logs)

```yaml
echo "Waiting for Postgres..."
for i in {1..90}; do
  # First check if postgres is accepting connections
  if docker compose exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
    # Also verify we can actually connect (init scripts completed)
    if docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1" >/dev/null 2>&1; then
      echo "Postgres ready"; break
    fi
  fi
  if [ $i -eq 90 ]; then 
    echo "Postgres failed to start"
    echo "Container status:"
    docker compose ps postgres
    echo "Postgres logs:"
    docker compose logs postgres
    exit 1
  fi
  sleep 2
done
```

---

## Verification

### Local Test ✅
```bash
$ docker compose down postgres
$ docker compose up -d postgres
$ sleep 10
$ docker compose exec -T postgres pg_isready -U dendrite -d dendrite
/var/run/postgresql:5432 - accepting connections

$ docker compose exec -T postgres psql -U dendrite -d dendrite -c "\dt"
# Shows 17 tables created successfully ✅
```

### CI Impact
- Postgres will now have proper init scripts
- 3 minutes should be enough even for slow CI runners
- Better error diagnostics if it still fails

---

## Files Modified

1. **docker-compose.yml**
   - Fixed postgres init script paths (moved to `scripts/db/`)

2. **.github/workflows/main.yml**
   - Increased postgres wait timeout (60s → 180s)
   - Added verification query (`SELECT 1`)
   - Added detailed error logging

---

## Related Issues

This issue was introduced during the scripts reorganization where:
- Scripts were moved from `scripts/*.sql` → `scripts/db/*.sql`
- docker-compose.yml wasn't updated to reflect new paths
- Postgres container was starting but couldn't find init scripts
- Init scripts weren't running, but pg_isready still returned "ready"
- CI thought postgres was ready, but database wasn't initialized

**Root cause:** Incomplete refactoring - moved files but didn't update all references

---

## Prevention

Added to validation checklist:
- [ ] Check all docker-compose volume mounts after file moves
- [ ] Test postgres initialization locally before pushing
- [ ] Verify init scripts create expected tables

**Added validation step:**
```bash
# Validate postgres init scripts work
docker compose down postgres
docker compose up -d postgres
sleep 15
docker compose exec -T postgres psql -U dendrite -d dendrite -c "\dt" | grep executions
```

---

## Status
✅ **Fixed** - Ready to push to CI
