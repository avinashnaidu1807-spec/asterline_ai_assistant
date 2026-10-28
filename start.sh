#!/usr/bin/env bash
# ==============================================================================
# Asterline Research Assistant - Single-Command Launch Script (Linux/macOS)
# ==============================================================================
set -e

echo "=================================================================="
echo " Asterline AI Research Assistant - Multi-Agent & Persistent Memory"
echo "=================================================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo ""
echo "[1/4] Verifying dependencies..."
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "Error: Python 3 is required but not installed." >&2
    exit 1
fi
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi
echo "  Python: $($PYTHON_CMD --version)"

if ! command -v npm &> /dev/null; then
    echo "Error: Node.js / npm is required but not installed." >&2
    exit 1
fi
echo "  Node.js: $(node --version)"

if [ ! -f "$BACKEND_DIR/.env" ] && [ -f "$BACKEND_DIR/.env.example" ]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    echo "  Created backend/.env from template"
fi

echo ""
echo "[2/4] Initializing Database & Vector Store..."
$PYTHON_CMD scripts/ingest_corpus.py || true

echo ""
echo "[3/4] Starting Backend API (FastAPI) on port 8000..."
(cd "$BACKEND_DIR" && $PYTHON_CMD -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!

echo ""
echo "[4/4] Starting Frontend Dev Server (Vite) on port 5173..."
(cd "$FRONTEND_DIR" && npm run dev -- --port 5173) &
FRONTEND_PID=$!

cleanup() {
    echo ""
    echo "Stopping servers..."
    kill "$BACKEND_PID" 2>/dev/null || true
    kill "$FRONTEND_PID" 2>/dev/null || true
    echo "Servers stopped."
}
trap cleanup EXIT INT TERM

echo ""
echo "=================================================================="
echo " Asterline Assistant is running!"
echo " - Web Interface: http://localhost:5173"
echo " - API Docs:      http://localhost:8000/docs"
echo " - Health Check:  http://localhost:8000/health"
echo "=================================================================="
echo "Press Ctrl+C to stop both servers."
echo ""

wait

