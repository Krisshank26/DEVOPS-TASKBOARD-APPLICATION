#!/usr/bin/env bash
set -euo pipefail

URL="${URL:-http://taskboard.local/api/tasks}"
REQUESTS="${REQUESTS:-500}"
FAILURES=0

for ((i = 1; i <= REQUESTS; i++)); do
  if ! curl --fail --silent --max-time 5 "$URL" >/dev/null; then
    FAILURES=$((FAILURES + 1))
  fi
done 

echo "Load Test Completed" 

echo "Requests: $REQUESTS"
echo "Failures: $FAILURES"

if [[ "$FAILURES" -ne 0 ]]; then
  echo "Load test failed."
  exit 1
fi

echo "Load test passed." 
