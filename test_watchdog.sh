#!/bin/bash
# test_watchdog.sh
# Comprehensive watchdog testing script

set -e

API_URL="http://localhost:5000"
SERVICE_NAME="efio-api"

echo "================================================"
echo "EFIO Watchdog Testing Suite"
echo "================================================"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

test_passed=0
test_failed=0

# Helper functions
pass_test() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
    ((test_passed++))
}

fail_test() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    ((test_failed++))
}

info() {
    echo -e "${YELLOW}ℹ️  INFO${NC}: $1"
}

echo ""
echo "Test 1: Service Running"
echo "-------------------------------------------"
if systemctl is-active --quiet $SERVICE_NAME; then
    pass_test "Service is running"
else
    fail_test "Service is not running"
    echo "   Start with: sudo systemctl start $SERVICE_NAME"
    exit 1
fi

echo ""
echo "Test 2: Basic Health Check"
echo "-------------------------------------------"
response=$(curl -s -w "\n%{http_code}" "$API_URL/api/health")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

if [ "$http_code" = "200" ]; then
    pass_test "Basic health endpoint returns 200"
    echo "   Response: $body"
else
    fail_test "Health check failed (HTTP $http_code)"
fi

echo ""
echo "Test 3: Watchdog Health Check"
echo "-------------------------------------------"
response=$(curl -s -w "\n%{http_code}" "$API_URL/api/health/watchdog")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

if [ "$http_code" = "200" ]; then
    pass_test "Watchdog health endpoint returns 200"
    
    # Parse JSON (requires jq)
    if command -v jq &> /dev/null; then
        status=$(echo "$body" | jq -r '.status')
        watchdog_status=$(echo "$body" | jq -r '.watchdog.status')
        
        info "Overall status: $status"
        info "Watchdog status: $watchdog_status"
        
        # Show component health
        echo ""
        echo "   Component Health:"
        echo "$body" | jq -r '.components | to_entries[] | "   - \(.key): \(.value.status)"'
    else
        info "Install jq for detailed JSON parsing: sudo apt-get install jq"
        echo "   Raw response: $body"
    fi
else
    fail_test "Watchdog health check failed (HTTP $http_code)"
    echo "   Response: $body"
fi

echo ""
echo "Test 4: Systemd Watchdog Configuration"
echo "-------------------------------------------"
watchdog_sec=$(systemctl show $SERVICE_NAME -p WatchdogUSec | cut -d= -f2)
if [ "$watchdog_sec" != "0" ]; then
    pass_test "Systemd watchdog configured ($watchdog_sec microseconds)"
else
    fail_test "Systemd watchdog not configured"
    info "Check /etc/systemd/system/$SERVICE_NAME.service"
fi

echo ""
echo "Test 5: Service Restart Capability"
echo "-------------------------------------------"
restart_setting=$(systemctl show $SERVICE_NAME -p Restart | cut -d= -f2)
if [ "$restart_setting" = "always" ]; then
    pass_test "Auto-restart enabled ($restart_setting)"
else
    fail_test "Auto-restart not properly configured ($restart_setting)"
fi

echo ""
echo "Test 6: Service Logs Check"
echo "-------------------------------------------"
recent_logs=$(journalctl -u $SERVICE_NAME --since "5 minutes ago" --no-pager | wc -l)
if [ "$recent_logs" -gt 0 ]; then
    pass_test "Service is logging ($recent_logs log lines in last 5 min)"
    
    # Check for watchdog messages
    watchdog_logs=$(journalctl -u $SERVICE_NAME --since "5 minutes ago" --no-pager | grep -i "watchdog" | wc -l)
    if [ "$watchdog_logs" -gt 0 ]; then
        info "Found $watchdog_logs watchdog-related log entries"
        echo ""
        echo "   Recent watchdog logs:"
        journalctl -u $SERVICE_NAME --since "5 minutes ago" --no-pager | grep -i "watchdog" | tail -n 3 | sed 's/^/   /'
    fi
else
    fail_test "No recent logs found"
fi

echo ""
echo "Test 7: Memory & CPU Limits"
echo "-------------------------------------------"
mem_limit=$(systemctl show $SERVICE_NAME -p MemoryLimit | cut -d= -f2)
cpu_quota=$(systemctl show $SERVICE_NAME -p CPUQuotaPerSecUSec | cut -d= -f2)

if [ "$mem_limit" != "infinity" ]; then
    pass_test "Memory limit configured ($mem_limit)"
else
    info "No memory limit set (might want to add one)"
fi

if [ "$cpu_quota" != "infinity" ]; then
    pass_test "CPU quota configured ($cpu_quota)"
else
    info "No CPU quota set (might want to add one)"
fi

echo ""
echo "Test 8: Detailed Health Report"
echo "-------------------------------------------"
echo "Fetching detailed health report..."
curl -s "$API_URL/api/health/detailed" | python3 -m json.tool 2>/dev/null || curl -s "$API_URL/api/health/detailed"

echo ""
echo "================================================"
echo "Test Summary"
echo "================================================"
echo -e "Passed: ${GREEN}$test_passed${NC}"
echo -e "Failed: ${RED}$test_failed${NC}"
echo ""

if [ $test_failed -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi

# Optional: Stress test
echo ""
echo "================================================"
echo "Optional: Stress Test"
echo "================================================"
read -p "Run watchdog stress test? (will simulate failures) (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🔥 Running stress test..."
    echo "   This will send kill signal to test auto-restart"
    echo ""
    
    # Get PID
    pid=$(systemctl show $SERVICE_NAME -p MainPID | cut -d= -f2)
    
    if [ "$pid" != "0" ]; then
        echo "   Current PID: $pid"
        echo "   Sending SIGTERM..."
        sudo kill -TERM $pid
        
        echo "   Waiting 5 seconds for restart..."
        sleep 5
        
        if systemctl is-active --quiet $SERVICE_NAME; then
            echo -e "   ${GREEN}✅ Service auto-restarted successfully!${NC}"
            
            new_pid=$(systemctl show $SERVICE_NAME -p MainPID | cut -d= -f2)
            echo "   New PID: $new_pid"
        else
            echo -e "   ${RED}❌ Service failed to restart${NC}"
        fi
    else
        echo "   Could not determine service PID"
    fi
fi

echo ""
echo "Testing complete."