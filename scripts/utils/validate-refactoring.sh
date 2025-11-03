#!/bin/bash
# Validation script to verify refactoring didn't break anything

set -e

echo "🔍 Validation Script - Checking Refactoring Changes"
echo "=================================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track failures
FAILURES=0

check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} File exists: $1"
        return 0
    else
        echo -e "${RED}✗${NC} File missing: $1"
        FAILURES=$((FAILURES + 1))
        return 1
    fi
}

check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓${NC} Directory exists: $1"
        return 0
    else
        echo -e "${RED}✗${NC} Directory missing: $1"
        FAILURES=$((FAILURES + 1))
        return 1
    fi
}

check_executable() {
    if [ -x "$1" ]; then
        echo -e "${GREEN}✓${NC} Executable: $1"
        return 0
    else
        echo -e "${YELLOW}⚠${NC}  Not executable (may be intentional): $1"
        return 0
    fi
}

echo "1. Checking Scripts Reorganization..."
echo "--------------------------------------"
check_dir "scripts/docker"
check_dir "scripts/testing"
check_dir "scripts/demos"
check_dir "scripts/db"
check_dir "scripts/utils"
check_file "scripts/run.sh"
check_file "scripts/docker/start.sh"
check_file "scripts/docker/stop.sh"
check_file "scripts/testing/test.sh"
check_executable "scripts/docker/start.sh"
echo ""

echo "2. Checking Documentation..."
echo "----------------------------"
check_file "README.md"
check_file "docs/GETTING_STARTED.md"
check_file "docs/ARCHITECTURE.md"
check_file "docs/API.md"
check_file "docs/STRAVA_AUTH_TESTING.md"
check_dir "docs/archive/phase-summaries"
check_dir "docs/archive/old-strategies"
echo ""

echo "3. Checking Dead Code Archive..."
echo "--------------------------------"
check_dir "neural_engine/core/archive_deprecated"
check_file "neural_engine/core/archive_deprecated/agentic_core_neuron.py"
check_file "neural_engine/core/archive_deprecated/classification_facts.py"
echo ""

echo "4. Checking Docker Configuration..."
echo "------------------------------------"
check_file "docker-compose.yml"
check_file ".github/workflows/main.yml"
echo ""

echo "5. Checking Test Files..."
echo "-------------------------"
check_file "neural_engine/tests/test_strava_auth_flow.py"
check_file "pytest.ini"
echo ""

echo "6. Testing Docker Compose Configuration..."
echo "--------------------------------------"
if docker compose config > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} docker-compose.yml is valid"
    
    # Check for profile definitions
    if grep -q "profiles:" docker-compose.yml; then
        echo -e "${GREEN}✓${NC} Profile definitions found in docker-compose.yml"
    else
        echo -e "${RED}✗${NC} No profile definitions in docker-compose.yml"
        FAILURES=$((FAILURES + 1))
    fi
    
    # Check for ollama-cpu service
    if grep -q "ollama-cpu:" docker-compose.yml; then
        echo -e "${GREEN}✓${NC} ollama-cpu service defined"
    else
        echo -e "${RED}✗${NC} ollama-cpu service missing"
        FAILURES=$((FAILURES + 1))
    fi
else
    echo -e "${RED}✗${NC} docker-compose.yml configuration error"
    FAILURES=$((FAILURES + 1))
fi
echo ""

echo "7. Checking for Broken Import References..."
echo "--------------------------------------------"
# Check if any code still references removed files
BROKEN_IMPORTS=0

if grep -r "from.*agentic_core_neuron" neural_engine/ --exclude-dir=archive_deprecated --exclude-dir=__pycache__ 2>/dev/null; then
    echo -e "${RED}✗${NC} Found imports of agentic_core_neuron"
    BROKEN_IMPORTS=$((BROKEN_IMPORTS + 1))
else
    echo -e "${GREEN}✓${NC} No imports of agentic_core_neuron"
fi

if grep -r "from.*classification_facts" neural_engine/ --exclude-dir=archive_deprecated --exclude-dir=__pycache__ 2>/dev/null; then
    echo -e "${RED}✗${NC} Found imports of classification_facts"
    BROKEN_IMPORTS=$((BROKEN_IMPORTS + 1))
else
    echo -e "${GREEN}✓${NC} No imports of classification_facts"
fi

if [ $BROKEN_IMPORTS -gt 0 ]; then
    FAILURES=$((FAILURES + BROKEN_IMPORTS))
fi
echo ""

echo "8. README File Size Check..."
echo "----------------------------"
OLD_README_SIZE=$(wc -l README.md.old 2>/dev/null | awk '{print $1}' || echo "N/A")
NEW_README_SIZE=$(wc -l README.md | awk '{print $1}')
echo "Old README: $OLD_README_SIZE lines"
echo "New README: $NEW_README_SIZE lines"
if [ "$OLD_README_SIZE" != "N/A" ] && [ "$NEW_README_SIZE" -lt "$OLD_README_SIZE" ]; then
    echo -e "${GREEN}✓${NC} README reduced in size (more concise)"
else
    echo -e "${YELLOW}⚠${NC}  README size check skipped"
fi
echo ""

echo "9. Checking Python Syntax..."
echo "----------------------------"
# Just check if file can be read by Python (syntax check without writing cache)
if python3 -c "import ast; ast.parse(open('neural_engine/tests/test_strava_auth_flow.py').read())" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} test_strava_auth_flow.py has valid syntax"
else
    echo -e "${RED}✗${NC} test_strava_auth_flow.py has syntax errors"
    FAILURES=$((FAILURES + 1))
fi
echo ""

echo "=================================================="
if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}✅ All validation checks passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Run full test suite: ./scripts/testing/test.sh"
    echo "  2. Test docker startup: ./scripts/docker/start.sh"
    echo "  3. Commit changes: git add -A && git commit -m 'Refactor complete'"
    exit 0
else
    echo -e "${RED}❌ $FAILURES validation check(s) failed${NC}"
    echo ""
    echo "Please review the failures above and fix before committing."
    exit 1
fi
