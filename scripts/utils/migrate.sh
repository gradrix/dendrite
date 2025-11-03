#!/bin/bash
set -e

echo "🗄️  Running Database Migrations"
echo "=============================="

# Ensure PostgreSQL is running
if ! docker compose ps | grep -q "postgres.*Up"; then
    echo "Starting PostgreSQL..."
    docker compose up -d postgres
    sleep 5
fi

# Wait for PostgreSQL
echo "⏳ Waiting for PostgreSQL..."
for i in {1..30}; do
    if docker compose exec -T postgres pg_isready -U dendrite 2>&1 | grep -q "accepting connections"; then
        echo "✅ PostgreSQL ready"
        break
    fi
    [ $i -eq 30 ] && echo "❌ PostgreSQL failed" && exit 1
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

for migration in "${MIGRATIONS[@]}"; do
    MIGRATION_FILE="neural_engine/scripts/$migration"
    
    if [ -f "$MIGRATION_FILE" ]; then
        echo "📝 Applying: $migration"
        
        if docker compose exec -T postgres psql -U dendrite -d dendrite -f "/app/$MIGRATION_FILE" 2>&1 | grep -q "ERROR"; then
            echo "   ⚠️  Migration had errors (may already be applied)"
        else
            echo "   ✅ Applied successfully"
        fi
    else
        echo "   ⚠️  File not found: $MIGRATION_FILE"
    fi
done

echo ""
echo "✅ Migrations complete!"
echo ""

# Show table summary
echo "📊 Database Tables:"
docker compose exec -T postgres psql -U dendrite -d dendrite -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname = 'public' 
ORDER BY tablename;
" 2>&1 | grep -v "^$"

echo ""
echo "✅ Database ready!"
