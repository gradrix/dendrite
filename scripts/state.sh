#!/bin/bash
# State Management CLI Tool
# Inspect and manage the agent's persistent state database

DB_FILE="state/agent_state.db"

if [ ! -f "$DB_FILE" ]; then
    echo "❌ State database not found: $DB_FILE"
    exit 1
fi

ACTION=$1
KEY=$2

case $ACTION in
    list)
        echo "📋 All state keys:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        sqlite3 "$DB_FILE" "SELECT key, updated_at FROM state ORDER BY updated_at DESC" | while IFS='|' read -r key date; do
            echo "  🔑 $key"
            echo "     ⏰ Last updated: $date"
        done
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ;;
    
    get)
        if [ -z "$KEY" ]; then
            echo "❌ Usage: $0 get <key>"
            exit 1
        fi
        echo "📖 Getting value for key: $KEY"
        VALUE=$(sqlite3 "$DB_FILE" "SELECT value FROM state WHERE key='$KEY'")
        if [ -z "$VALUE" ]; then
            echo "❌ Key not found: $KEY"
            exit 1
        fi
        echo "Value:"
        echo "$VALUE" | python3 -m json.tool 2>/dev/null || echo "$VALUE"
        ;;
    
    delete|rm)
        if [ -z "$KEY" ]; then
            echo "❌ Usage: $0 delete <key>"
            exit 1
        fi
        echo "🗑️  Deleting key: $KEY"
        sqlite3 "$DB_FILE" "DELETE FROM state WHERE key='$KEY'"
        echo "✅ Deleted"
        ;;
    
    clear)
        read -p "⚠️  Are you sure you want to delete ALL state data? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            sqlite3 "$DB_FILE" "DELETE FROM state"
            echo "✅ All state data cleared"
        else
            echo "❌ Cancelled"
        fi
        ;;
    
    count)
        COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM state")
        echo "📊 Total state keys: $COUNT"
        ;;
    
    search)
        if [ -z "$KEY" ]; then
            echo "❌ Usage: $0 search <pattern>"
            exit 1
        fi
        echo "🔍 Searching for keys matching: $KEY"
        sqlite3 "$DB_FILE" "SELECT key, updated_at FROM state WHERE key LIKE '%$KEY%' ORDER BY updated_at DESC" | while IFS='|' read -r key date; do
            echo "  🔑 $key (updated: $date)"
        done
        ;;
    
    help|--help|-h|"")
        echo "🛠️  State Management CLI"
        echo ""
        echo "Usage: $0 <command> [arguments]"
        echo ""
        echo "Commands:"
        echo "  list, ls          - List all state keys with timestamps"
        echo "  get <key>         - Get value for a specific key"
        echo "  delete <key>      - Delete a specific key"
        echo "  search <pattern>  - Search keys by pattern"
        echo "  count             - Show total number of keys"
        echo "  clear             - Delete ALL state data (requires confirmation)"
        echo "  help              - Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 list"
        echo "  $0 get kudos_givers"
        echo "  $0 search activity"
        echo "  $0 delete old_cache_key"
        ;;
    
    *)
        echo "❌ Unknown command: $ACTION"
        echo "Run '$0 help' for usage information"
        exit 1
        ;;
esac
