#!/bin/bash
#
# 1024 Multi-Agent Oracle 启动脚本
#

set -e

cd "$(dirname "$0")"

echo "🔮 Starting 1024 Multi-Agent Oracle..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "   Please copy .env.example to .env and add your GEMINI_API_KEY"
    exit 1
fi

# Check if GEMINI_API_KEY is set
if grep -q "GEMINI_API_KEY=$" .env || grep -q "GEMINI_API_KEY=your" .env; then
    echo "⚠️  Warning: GEMINI_API_KEY is not set in .env"
    echo "   The Oracle will not be able to research questions without an API key."
    echo "   Get your key at: https://ai.google.dev/"
    echo ""
fi

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "❌ Virtual environment not found!"
    echo "   Please run: python3 -m venv venv && source venv/bin/activate && pip install -e ."
    exit 1
fi

# Load environment
export $(grep -v '^#' .env | grep -v '^$' | xargs)

# Start the server
echo "🚀 Oracle API starting on http://0.0.0.0:${API_PORT:-8090}"
echo ""
exec python -m uvicorn oracle.api.server:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8090}" \
    --reload
