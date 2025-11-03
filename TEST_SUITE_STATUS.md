# Test Suite Status & Answers

## Q1: Do Postgres Migrations Run Automatically?

**Answer: NO** - But now they do in the test suite! ✅

### What Happens:

1. **On Container Start:**
   - Postgres container starts
   - Only runs `init_db.sql` and `init_extensions.sql` from `/docker-entrypoint-initdb.d/`
   - These create the base tables (17 tables)
   - This happens ONCE when the container is first created

2. **Migrations (Additional Schema Changes):**
   - Located in `neural_engine/scripts/009_*.sql` through `014_*.sql`
   - These are ALTER TABLE statements that add columns, indexes, etc.
   - **NOT automatically run** - must be manually executed

### Solution Applied:

Updated `./scripts/testing/test.sh` to:
1. Start services (redis, postgres, ollama)
2. **Run `./scripts/utils/migrate.sh`** automatically
3. Then run pytest

Now migrations are applied every time you run the test suite! ✅

---

## Q2: Should We Run Full Test Suite?

**Answer: YES** - But there's a port conflict to fix first

### Current Status:

**✅ What Works:**
- Postgres init scripts fixed (now at `scripts/db/`)
- Migrations run automatically in test suite
- Services start correctly
- Test framework ready

**⚠️ Issue Found:**
- System ollama running on port 11434 (outside Docker)
- Conflicts with Docker ollama containers
- Need to stop system ollama before running tests

### Solution:

**Before running tests:**
```bash
# Check if system ollama is running
ps aux | grep ollama | grep -v grep

# If found, stop it
sudo systemctl stop ollama  # If it's a service
# OR
sudo kill

 <PID>  # If it's a standalone process
```

**Then run tests:**
```bash
./scripts/testing/test.sh
```

### Test Script Improvements:

1. **Auto-detects GPU vs CPU:**
   - Checks for `nvidia-smi` and `$CI` variable
   - Uses appropriate profile automatically
   - Stops conflicting ollama service

2. **Runs migrations:**
   - Applies all `009_*.sql` through `014_*.sql`
   - Idempotent (safe to run multiple times)
   - Shows table summary after completion

3. **Better service waiting:**
   - Postgres: Waits for initialization + query test
   - Redis: Ping test
   - Ollama: API availability test

---

## Files Modified:

1. **scripts/testing/test.sh**
   - Added auto GPU/CPU detection
   - Added postgres service wait
   - Added automatic migration execution
   - Improved ollama conflict handling

2. **docker-compose.yml**
   - Fixed postgres init script paths: `scripts/db/init_db.sql` ✅

3. **.github/workflows/main.yml**
   - Improved postgres wait (180s timeout)
   - Added verification query
   - Better error logging

---

## Next Steps:

### To Run Tests Now:

```bash
# 1. Stop system ollama
sudo systemctl stop ollama
# or find and kill the process:
# ps aux | grep ollama | grep -v grep
# sudo kill <PID>

# 2. Clean slate
cd /home/gradrix/repos/center
docker compose down

# 3. Run tests
./scripts/testing/test.sh

# Or run specific tests:
./scripts/testing/test.sh -k test_strava_auth
./scripts/testing/test.sh -k test_intent_classifier
```

### For CI:

CI should work perfectly now:
- Uses `--profile cpu` (no GPU needed)
- No system ollama conflict
- Migrations will run automatically
- Postgres init scripts at correct paths

---

## Summary:

| Item | Status | Notes |
|------|--------|-------|
| Postgres init scripts | ✅ Fixed | Now at `scripts/db/` |
| Migrations | ✅ Automated | Run in test.sh |
| Test script GPU/CPU | ✅ Fixed | Auto-detects |
| CI postgres wait | ✅ Fixed | 180s timeout + verification |
| Local tests | ⚠️ Blocked | System ollama conflict on port 11434 |

**Action Required:** Stop system ollama service to run local tests

**CI Status:** Should pass on next push ✅
