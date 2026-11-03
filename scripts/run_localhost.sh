#!/usr/bin/env bash
# ==============================================================================
# Department Club App - Localhost Startup Script
# ==============================================================================
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "=== Starting Department Club Platform in Localhost ==="

# 1. Stop existing instances on ports 5000 and 8080 if running
echo "[1/4] Checking and clearing ports 5000 and 8080..."
fuser -k 5000/tcp 2>/dev/null || true
fuser -k 8080/tcp 2>/dev/null || true

# 2. Check Flutter web build exists, build if missing
if [ ! -f "frontend/build/web/index.html" ]; then
    echo "[2/4] Frontend build missing. Compiling Flutter Web..."
    cd frontend && /home/kingsley-judewin/flutter/bin/flutter build web && cd "$PROJECT_DIR"
else
    echo "[2/4] Frontend web bundle found."
fi

# 3. Start Flask Backend Server in background
echo "[3/4] Starting Flask Backend on http://127.0.0.1:5000..."
nohup .venv/bin/python wsgi.py > instance/backend.log 2>&1 < /dev/null &
BACKEND_PID=$!
echo "      Backend started (PID: $BACKEND_PID, logs: instance/backend.log)"

# Wait for backend health check
sleep 2
for i in {1..10}; do
    if curl -s http://127.0.0.1:5000/health | grep -q "healthy"; then
        echo "      Backend is healthy and connected to database!"
        break
    fi
    sleep 1
done

# 4. Start Frontend Web Server in background
echo "[4/4] Starting Frontend Web Server on http://localhost:8080..."
nohup .venv/bin/python -m http.server 8080 --directory frontend/build/web --bind 0.0.0.0 > instance/frontend.log 2>&1 < /dev/null &
FRONTEND_PID=$!
echo "      Frontend started (PID: $FRONTEND_PID, logs: instance/frontend.log)"

echo ""
echo "=========================================================="
echo " Application is running successfully!"
echo "   Frontend Web Client: http://localhost:8080"
echo "   Backend REST API:    http://127.0.0.1:5000"
echo "   API Health Check:    http://127.0.0.1:5000/health"
echo "   Swagger Docs:        http://127.0.0.1:5000/api/v1/docs/"
echo "=========================================================="
echo ""
echo "To view logs:"
echo "   tail -f instance/backend.log"
echo "   tail -f instance/frontend.log"
echo ""
echo "To stop both servers:"
echo "   fuser -k 5000/tcp 8080/tcp"
echo "=========================================================="
