#!/bin/bash
#
# 1024 Multi-Agent Oracle 启动脚本
# 使用 uv 进行依赖管理
#

set -e

cd "$(dirname "$0")"

echo "🔮 Starting 1024 Multi-Agent Oracle..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "   Please copy .env.example to .env and configure Vertex AI credentials."
    exit 1
fi

# Check if Vertex AI credentials are configured
if ! grep -q "GOOGLE_APPLICATION_CREDENTIALS_JSON=" .env || grep -q 'GOOGLE_APPLICATION_CREDENTIALS_JSON={"type":"service_account","project_id":"..."' .env; then
    echo "⚠️  Warning: GOOGLE_APPLICATION_CREDENTIALS_JSON is not configured in .env"
    echo "   The Oracle requires Vertex AI. Set GOOGLE_APPLICATION_CREDENTIALS_JSON with your GCP service account JSON."
    echo ""
fi

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed!"
    echo "   Please install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Load environment
export $(grep -v '^#' .env | grep -v '^$' | xargs)

# Start the server using uv
echo "🚀 Oracle API starting on http://0.0.0.0:${API_PORT:-8090}"
echo ""
exec uv run uvicorn oracle.api.server:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8090}" \
    --reload


