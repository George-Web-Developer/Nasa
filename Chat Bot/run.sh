#!/usr/bin/env bash
set -e

echo "====================================================================="
echo " NASA Space Apps Challenge 2026 - Health Monitoring Software"
echo " Astronaut Psychological Check-in Assistant & HUD Widget"
echo "====================================================================="
echo ""

# 1. Detect Python
PYTHON_BIN="python3"
if ! command -v python3 &> /dev/null; then
    if command -v python &> /dev/null; then
        PYTHON_BIN="python"
    else
        echo "[ERROR] Python was not found in PATH! Please install Python 3.10+."
        exit 1
    fi
fi

echo "[1/5] Using Python: $PYTHON_BIN"

# 2. Virtual environment
if [ ! -d "venv" ]; then
    echo "[2/5] Creating virtual environment 'venv'..."
    $PYTHON_BIN -m venv venv
else
    echo "[2/5] Virtual environment 'venv' already exists."
fi

source venv/bin/activate

# 3. Environment file
if [ ! -f ".env" ]; then
    echo "[3/5] Copying .env.example to .env (MOCK_LLM=true enabled)..."
    cp .env.example .env
else
    echo "[3/5] .env file detected."
fi

# 4. Requirements
echo "[4/5] Installing dependencies..."
pip install --upgrade pip > /dev/null 2>&1 || true
pip install -r requirements.txt

# 5. Seed
echo "[5/5] Initializing database and demo data..."
python seed.py

echo ""
echo "====================================================================="
echo " SERVER READY!"
echo " Opening at: http://localhost:8000"
echo " - Demo Page:     http://localhost:8000/chatbot-demo.html"
echo " - Widget JS:     http://localhost:8000/widget.js"
echo " - API Docs:      http://localhost:8000/docs"
echo "====================================================================="
echo ""

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
