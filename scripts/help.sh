#!/bin/bash

cat << 'EOF'
🧠 Dendrite Neural Engine - Available Commands
═══════════════════════════════════════════════

SETUP & MANAGEMENT:
  ./scripts/setup.sh          First-time setup (pull models, verify)
  ./scripts/start.sh          Start all services
  ./scripts/stop.sh           Stop all services
  ./scripts/reset.sh          Reset everything (delete all data)
  ./scripts/health.sh         Check system health

DEVELOPMENT:
  ./scripts/dev.sh            Start in dev mode (hot reload + logs)
  ./scripts/run.sh "goal"     Execute a specific goal
  ./scripts/shell.sh          Open shell in app container
  ./scripts/logs.sh [service] View logs (all or specific service)

TESTING:
  ./scripts/test.sh           Run all tests (Docker)
  ./scripts/test-debug.sh     Run tests with VS Code debugger (F5 to attach)
  ./scripts/test-local.sh     Run tests locally (faster)
  ./scripts/test-unit.sh      Run only unit tests
  ./scripts/test-integration.sh  Run only integration tests
  ./scripts/test-watch.sh     Watch mode for TDD

EXAMPLES:
  ./scripts/run.sh "List my recent Strava activities"
  ./scripts/run.sh "How many kudos did I give this month?"
  ./scripts/logs.sh app
  ./scripts/shell.sh redis

For detailed documentation: cat scripts/README.md

EOF
