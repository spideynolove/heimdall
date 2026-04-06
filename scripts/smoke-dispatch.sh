#!/usr/bin/env bash
set -euo pipefail

SESSION="ai-do-smoke"
TASK="Reply with only the word PONG and nothing else."

echo "=== ai-dispatch smoke test ==="
echo ""
echo "1. Checking prerequisites..."
tmux -V
claude --version

echo ""
echo "2. Dispatching task to session '$SESSION'..."
source .venv/bin/activate
result=$(python src/ai_dispatch.py run "$TASK" --session "$SESSION")
echo "Result: $result"

echo ""
echo "3. Verifying output contains PONG..."
if echo "$result" | grep -qi "pong"; then
    echo "PASS: got expected response"
else
    echo "FAIL: response did not contain PONG"
    echo "Raw result: $result"
    exit 1
fi

echo ""
echo "4. Verifying tmux session exists..."
tmux has-session -t "$SESSION" && echo "PASS: session '$SESSION' exists"

echo ""
echo "5. Cleanup..."
tmux kill-session -t "$SESSION" 2>/dev/null || true
echo "Session killed."

echo ""
echo "=== Smoke test PASSED ==="
