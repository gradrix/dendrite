#!/bin/bash
set -e

echo "🔧 Dendrite Setup Script"
echo "========================"
echo ""
echo "This script will:"
echo "  1. Start Docker services"
echo "  2. Pull required LLM models"
echo "  3. Verify installation"
echo ""

# Start services
./scripts/start.sh

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "  • Run the neural engine: docker compose exec app python main.py --goal 'your goal here'"
echo "  • Run tests: ./scripts/test.sh"
echo "  • View logs: ./scripts/logs.sh"
echo "  • Open shell: ./scripts/shell.sh"
echo ""
