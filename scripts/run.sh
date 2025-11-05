#!/bin/bash
set -e

# Production Service Runner for Neural Engine
# Usage:
#   ./scripts/run.sh ask "Your goal here"              # Single goal execution
#   ./scripts/run.sh demo                              # Run end-to-end demo
#   ./scripts/run.sh serve                             # Start service mode
#   ./scripts/run.sh status                            # Check system health

COMMAND=${1:-help}
shift || true

echo "🧠 Neural Engine - Self-Improving AI System"
echo "=========================================="

# Ensure services are running
ensure_services() {
    echo "🐳 Ensuring services are running..."
    docker compose up -d redis postgres ollama 2>&1 | grep -v "orphan" || true
    
    # Wait for services
    echo "⏳ Waiting for services..."
    
    # Wait for Redis
    for i in {1..30}; do
        if docker compose exec -T redis redis-cli ping 2>&1 | grep -q PONG; then
            echo "✅ Redis ready"
            break
        fi
        [ $i -eq 30 ] && echo "❌ Redis failed" && exit 1
        sleep 1
    done
    
    # Wait for PostgreSQL
    for i in {1..30}; do
        if docker compose exec -T postgres pg_isready -U dendrite 2>&1 | grep -q "accepting connections"; then
            echo "✅ PostgreSQL ready"
            break
        fi
        [ $i -eq 30 ] && echo "❌ PostgreSQL failed" && exit 1
        sleep 1
    done
    
    # Wait for Ollama
    for i in {1..60}; do
        if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
            echo "✅ Ollama ready"
            break
        fi
        [ $i -eq 60 ] && echo "❌ Ollama failed" && exit 1
        sleep 1
    done
    
    echo "✅ All services ready"
    
    # Run database migrations (idempotent - safe to run multiple times)
    echo "🗄️  Running database migrations..."
    if ./scripts/utils/migrate.sh > /dev/null 2>&1; then
        echo "✅ Database migrations complete"
    else
        echo "⚠️  Migration warnings (may already be applied)"
    fi
}

case "$COMMAND" in
    ask)
        # Single goal execution with full visibility
        GOAL=""
        DEBUG_FLAG=""
        
        # Parse arguments (support --debug-llm flag)
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --debug-llm)
                    DEBUG_FLAG="--debug-llm"
                    shift
                    ;;
                *)
                    GOAL="$GOAL $1"
                    shift
                    ;;
            esac
        done
        
        GOAL=$(echo "$GOAL" | xargs)  # Trim whitespace
        
        if [ -z "$GOAL" ]; then
            echo "Usage: ./scripts/run.sh ask \"Your goal here\" [--debug-llm]"
            echo ""
            echo "Options:"
            echo "  --debug-llm    Show all LLM calls with prompts and responses"
            echo ""
            echo "Examples:"
            echo "  ./scripts/run.sh ask \"What is 2 plus 2?\""
            echo "  ./scripts/run.sh ask \"What is 2 plus 2?\" --debug-llm"
            exit 1
        fi
        
        ensure_services
        
        echo ""
        echo "🎯 Executing goal with full thinking visibility"
        if [ -n "$DEBUG_FLAG" ]; then
            echo "🔍 LLM Debug Mode: ENABLED"
        fi
        echo ""
        
        # Run with thinking visualizer
        docker compose run --rm tests python /app/run_goal.py "$GOAL" --verbose $DEBUG_FLAG
        ;;
    
    demo)
        # Run comprehensive end-to-end demo
        ensure_services
        
        echo ""
        echo "🎬 Running End-to-End Demo"
        echo "=========================="
        echo "This demo shows:"
        echo "  - Goal decomposition with learned patterns"
        echo "  - Neural pathway caching (System 1/System 2)"
        echo "  - Error recovery in action"
        echo "  - Tool dependency validation"
        echo "  - Complete thinking process visibility"
        echo ""
        
        docker compose run --rm tests python /app/neural_engine/demos/end_to_end_demo.py
        ;;
    
    serve)
        # Start continuous service mode
        ensure_services
        
        echo ""
        echo "🚀 Starting Neural Engine Service"
        echo "================================="
        echo ""
        echo "Service will:"
        echo "  - Process goals continuously"
        echo "  - Learn from executions"
        echo "  - Improve tools autonomously (every 5 minutes)"
        echo "  - Cache successful pathways"
        echo "  - Recover from errors automatically"
        echo ""
        echo "Press Ctrl+C to stop"
        echo ""
        
        # Run main service
        docker compose up app
        ;;
    
    status)
        # Check system health
        echo ""
        echo "🏥 System Health Check"
        echo "====================="
        echo ""
        
        # Check if services are running
        if docker compose ps | grep -q "redis.*Up"; then
            echo "✅ Redis: Running"
        else
            echo "❌ Redis: Not running"
        fi
        
        if docker compose ps | grep -q "postgres.*Up"; then
            echo "✅ PostgreSQL: Running"
            
            # Get database stats
            if docker compose exec -T postgres psql -U dendrite -d dendrite -c "SELECT COUNT(*) FROM tool_executions" >/dev/null 2>&1; then
                EXEC_COUNT=$(docker compose exec -T postgres psql -U dendrite -d dendrite -t -c "SELECT COUNT(*) FROM tool_executions" 2>/dev/null | tr -d ' ' | head -1)
                CACHE_COUNT=$(docker compose exec -T postgres psql -U dendrite -d dendrite -t -c "SELECT COUNT(*) FROM neural_pathways WHERE is_valid = true" 2>/dev/null | tr -d ' ' | head -1)
                PATTERN_COUNT=$(docker compose exec -T postgres psql -U dendrite -d dendrite -t -c "SELECT COUNT(*) FROM goal_decomposition_patterns WHERE success = true" 2>/dev/null | tr -d ' ' | head -1)
                
                echo "   📊 Executions: $EXEC_COUNT"
                echo "   💾 Cached pathways: $CACHE_COUNT"
                echo "   📚 Learned patterns: $PATTERN_COUNT"
            fi
        else
            echo "❌ PostgreSQL: Not running"
        fi
        
        if docker compose ps | grep -q "ollama.*Up"; then
            echo "✅ Ollama: Running"
            
            # Check model
            if curl -s http://localhost:11434/api/tags 2>/dev/null | grep -q "mistral"; then
                echo "   🤖 Mistral model: Available"
            else
                echo "   ⚠️  Mistral model: Not found"
            fi
        else
            echo "❌ Ollama: Not running"
        fi
        
        echo ""
        ;;
    
    *)
        echo ""
        echo "Usage: ./scripts/run.sh <command> [args]"
        echo ""
        echo "Commands:"
        echo "  ask \"goal\"     Execute a single goal with full visibility"
        echo "  demo           Run comprehensive end-to-end demo"
        echo "  serve          Start continuous service mode"
        echo "  status         Check system health"
        echo ""
        echo "Examples:"
        echo "  ./scripts/run.sh ask \"Say hello to the world\""
        echo "  ./scripts/run.sh demo"
        echo "  ./scripts/run.sh serve"
        echo "  ./scripts/run.sh status"
        echo ""
        ;;
esac

