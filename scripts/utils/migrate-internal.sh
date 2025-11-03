#!/bin/bash
# Migration script for running INSIDE a container
# Uses direct psql connection (no docker commands)
set -e

echo "🗄️  Running Database Migrations (Internal)"
echo "============================================="

# Database connection details from environment
PGHOST="${POSTGRES_HOST:-postgres}"
PGPORT="${POSTGRES_PORT:-5432}"
PGUSER="${POSTGRES_USER:-dendrite}"
PGDATABASE="${POSTGRES_DB:-dendrite}"
export PGPASSWORD="${POSTGRES_PASSWORD:-dendrite_pass}"

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL at $PGHOST:$PGPORT..."
for i in {1..30}; do
    if pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" 2>/dev/null; then
        echo "✅ PostgreSQL ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ PostgreSQL failed to become ready after 30 seconds"
        exit 1
    fi
    sleep 1
done

# Run migrations in order
MIGRATIONS=(
    "009_tool_lifecycle_management.sql"
    "010_testing_framework.sql"
    "011_deployment_monitoring.sql"
    "012_tool_versions.sql"
    "013_goal_decomposition_patterns.sql"
    "014_neural_pathway_cache.sql"
)

echo ""
echo "Running migrations..."
echo ""

MIGRATION_DIR="/app/neural_engine/scripts"
SUCCESS_COUNT=0
SKIP_COUNT=0

for migration in "${MIGRATIONS[@]}"; do
    MIGRATION_FILE="$MIGRATION_DIR/$migration"
    
    if [ -f "$MIGRATION_FILE" ]; then
        echo "📝 Applying: $migration"
        
        # Run migration and capture output
        if OUTPUT=$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -f "$MIGRATION_FILE" 2>&1); then
            # Check if output contains ERROR
            if echo "$OUTPUT" | grep -q "ERROR"; then
                # Check if it's a "already exists" error (acceptable)
                if echo "$OUTPUT" | grep -qE "(already exists|duplicate)"; then
                    echo "   ⚠️  Already applied (skipping)"
                    SKIP_COUNT=$((SKIP_COUNT + 1))
                else
                    echo "   ❌ Migration failed with errors:"
                    echo "$OUTPUT" | grep "ERROR"
                    exit 1
                fi
            else
                echo "   ✅ Applied successfully"
                SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
            fi
        else
            echo "   ❌ Failed to execute migration"
            echo "$OUTPUT"
            exit 1
        fi
    else
        echo "   ⚠️  File not found: $MIGRATION_FILE"
    fi
done

echo ""
echo "✅ Migrations complete! ($SUCCESS_COUNT applied, $SKIP_COUNT skipped)"
echo ""

# Show table summary
echo "📊 Database Tables:"
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname = 'public' 
ORDER BY tablename;
" 2>&1 | grep -v "^$" || true

echo ""
echo "✅ Database ready!"
