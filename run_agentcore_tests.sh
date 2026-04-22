#!/bin/bash
# Test runner for AgentCore Migration
# Runs tests in order: Repositories -> MCP Servers -> Lambda Functions

set -e  # Exit on error

echo "=========================================="
echo "AgentCore Migration Test Suite"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name=$1
    local test_command=$2
    
    echo -e "${YELLOW}Running: ${test_name}${NC}"
    echo "Command: ${test_command}"
    echo ""
    
    if eval "${test_command}"; then
        echo -e "${GREEN}✓ ${test_name} PASSED${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ ${test_name} FAILED${NC}"
        ((TESTS_FAILED++))
    fi
    echo ""
    echo "=========================================="
    echo ""
}

# 1. Test Portfolio Data Access Repositories
echo "PHASE 1: Testing Portfolio Data Access Repositories"
echo "=========================================="
echo ""

run_test "Article Repository Tests" \
    "pnpm nx test wealth_management_portal.portfolio_data_access -- tests/test_article_repository.py"

run_test "Theme Repository Tests" \
    "pnpm nx test wealth_management_portal.portfolio_data_access -- tests/test_theme_repository.py"

# 2. Test Portfolio Data MCP Server
echo "PHASE 2: Testing Portfolio Data MCP Server"
echo "=========================================="
echo ""

run_test "Portfolio Data MCP Tools Tests" \
    "pnpm nx test wealth_management_portal.portfolio_data_server -- tests/test_mcp_tools.py"

# 3. Test Web Crawler MCP Server
echo "PHASE 3: Testing Web Crawler MCP Server"
echo "=========================================="
echo ""

run_test "Web Crawler MCP Tools Tests" \
    "pnpm nx test wealth_management_portal.web_crawler -- tests/test_web_crawler_mcp_tools.py"

# 4. Test Lambda Functions
echo "PHASE 4: Testing Lambda Functions"
echo "=========================================="
echo ""

run_test "Scheduler Tools (Lambda Functions)" \
    "pnpm nx test wealth_management_portal.scheduler_tools"

# Summary
echo ""
echo "=========================================="
echo "TEST SUMMARY"
echo "=========================================="
echo -e "${GREEN}Tests Passed: ${TESTS_PASSED}${NC}"
echo -e "${RED}Tests Failed: ${TESTS_FAILED}${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed! Ready for deployment.${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please fix before deploying.${NC}"
    exit 1
fi
