# 🔮 1024 Prediction Market Multi-Agent Oracle

> **An Open-Source, AI-Powered Decentralized Oracle for 1024 Prediction Market Resolution**  
> **Powered by Google Gemini Deep Research API + Multi-Agent Cross-Verification**

## 🎯 What is This?

This is the **AI Oracle** for the **1024 Prediction Market**. Instead of relying on a centralized admin to determine market outcomes, this system uses multiple AI agents to independently research questions and reach consensus with full source traceability.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Gemini API](https://img.shields.io/badge/Gemini-Deep%20Research-4285F4.svg)](https://ai.google.dev/)
[![Docker](https://img.shields.io/badge/docker-chuciqin1%2F1024--multi--deep--research--agent--oracle-2496ED.svg)](https://hub.docker.com/r/chuciqin1/1024-multi-deep-research-agent-oracle)

## 🌟 Why AI Oracle for Prediction Markets?

Traditional prediction market oracles face a critical trust problem:

| Approach | Problem |
|----------|---------|
| **Centralized Admin** | Single point of failure, can manipulate results |
| **Chainlink/Pyth** | Only for price data, not event outcomes |
| **UMA Optimistic** | Complex, requires token economics |

**Our Solution**: Use multiple AI Deep Research Agents to independently research event outcomes, cross-verify results, and reach consensus before submitting to the blockchain.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   "Did Bitcoin reach $100k by Dec 31, 2025?"                               │
│                                                                             │
│         ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│         │   Agent A    │  │   Agent B    │  │   Agent C    │               │
│         │   Gemini     │  │   Gemini     │  │   Gemini     │               │
│         │ (50+ sources)│  │ (50+ sources)│  │ (50+ sources)│               │
│         └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│                │                 │                 │                        │
│                │  YES (85%)      │  YES (82%)      │  YES (88%)            │
│                │                 │                 │                        │
│                └─────────────────┼─────────────────┘                        │
│                                  ↓                                          │
│                    ┌─────────────────────────┐                              │
│                    │    Consensus: YES       │                              │
│                    │    Agreement: 100%      │                              │
│                    │    Total Sources: 150+  │                              │
│                    │    IPFS: Qm...abc       │                              │
│                    └─────────────────────────┘                              │
│                                  ↓                                          │
│                         Submit to Blockchain                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🔍 **Deep Research** | Each agent collects **50+ sources** from diverse categories |
| 🔗 **Full Citations** | Every claim is backed by verifiable source URLs |
| 🤖 **Multi-Agent** | 3+ independent AI agents for cross-verification |
| 🗳️ **Strict Consensus** | Unanimous agreement (100%) or 2/3+ supermajority |
| 📦 **IPFS Storage** | All research stored on IPFS via Storacha for transparency |
| ⛓️ **On-Chain** | Results submitted to 1024Chain with IPFS proof + SHA256 hash |
| 🔄 **V2 API** | Enhanced endpoints with oracle config verification |
| 🛡️ **Challenge Period** | Users can challenge results with evidence |

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Google Gemini API Key ([Get one here](https://ai.google.dev/))

### Installation

```bash
# Clone the repository
git clone https://github.com/1024chain/1024-multi-deep-research-agent-oracle.git
cd 1024-multi-deep-research-agent-oracle

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies (uv will auto-create .venv)
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

<details>
<summary>Alternative: Using pip</summary>

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .
```
</details>

### Run the Oracle API Server

```bash
# Start the server
uv run uvicorn oracle.api.server:app --host 0.0.0.0 --port 8989

# Or use the shortcut
uv run oracle-server
```

### Basic Usage

```python
from oracle import MultiAgentOracle
from oracle.agents import GeminiDeepResearchAgent

# Initialize with 3 Gemini agents (different configurations)
oracle = MultiAgentOracle(
    agents=[
        GeminiDeepResearchAgent(
            agent_id="gemini-agent-1",
            min_sources=50,
            search_depth="comprehensive",
        ),
        GeminiDeepResearchAgent(
            agent_id="gemini-agent-2", 
            min_sources=50,
            search_depth="focused",
        ),
        GeminiDeepResearchAgent(
            agent_id="gemini-agent-3",
            min_sources=50,
            search_depth="diverse",
        ),
    ],
    consensus_threshold=1.0,  # Unanimous agreement
)

# Research a prediction market question
result = await oracle.resolve(
    question="Did Bitcoin reach $100,000 by December 31, 2025?",
    resolution_criteria="BTC/USD spot price must have reached or exceeded $100,000.00 on any major exchange (Coinbase, Binance, Kraken) at any point before midnight UTC on December 31, 2025.",
)

# Check result
print(f"Outcome: {result.outcome}")               # YES / NO / UNDETERMINED
print(f"Confidence: {result.confidence:.1%}")     # 85.0%
print(f"Agreement: {result.agreement_ratio:.1%}") # 100.0%
print(f"Total Sources: {len(result.sources)}")    # 156
print(f"IPFS CID: {result.research_data_cid}")    # bafyrei...
print(f"SHA256 Hash: {result.research_data_hash}")
```

## 🌐 API Endpoints

### V2 API (Recommended)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v2/resolve` | POST | Start async resolution with config verification |
| `/api/v2/resolve/sync` | POST | Synchronous resolution (blocking) |
| `/api/v2/result/{request_id}` | GET | Get resolution result |
| `/api/v2/strategies` | GET | List available research strategies |

### V2 Request Format

```json
{
  "market_id": "market_123",
  "question": "Did Bitcoin reach $100,000 by December 31, 2025?",
  "resolution_criteria": "BTC/USD spot price >= $100,000 on major exchange",
  "oracle_config_cid": "bafyreiabc...",
  "oracle_config_hash": "sha256:abc123..."
}
```

### V2 Response Format

```json
{
  "request_id": "req_abc123",
  "status": "completed",
  "result": {
    "outcome": "YES",
    "confidence": 0.85,
    "agreement_ratio": 1.0,
    "research_data_cid": "bafyrei...",
    "research_data_hash": "sha256:def456...",
    "requires_manual_review": false,
    "verification_status": "verified"
  }
}
```

## 🐳 Docker

### Quick Start with Docker

```bash
# Pull from Docker Hub
docker pull chuciqin1/1024-multi-deep-research-agent-oracle:latest

# Run with environment file (recommended)
docker run -d \
  --name oracle \
  -p 8989:8989 \
  --env-file .env \
  chuciqin1/1024-multi-deep-research-agent-oracle:latest

# Or run with inline environment variables
docker run -d \
  --name oracle \
  -p 8989:8989 \
  -e GEMINI_API_KEY=your_api_key \
  -e GEMINI_MODEL=gemini-3-flash-preview \
  -e MIN_AGENTS=3 \
  -e CONSENSUS_THRESHOLD=1.0 \
  chuciqin1/1024-multi-deep-research-agent-oracle:latest

# Check logs
docker logs -f oracle
```

### Build from Source

```bash
# Build the image
docker build -t 1024-multi-agent-oracle .

# Run locally
docker run -d \
  --name oracle \
  -p 8989:8989 \
  --env-file .env \
  1024-multi-agent-oracle
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  oracle:
    image: chuciqin1/1024-multi-deep-research-agent-oracle:latest
    ports:
      - "8989:8989"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - GEMINI_MODEL=gemini-3-flash-preview
      - MIN_AGENTS=3
      - CONSENSUS_THRESHOLD=1.0
      - REQUIRE_UNANIMOUS=true
      - MAX_CONSENSUS_ROUNDS=5
      - LOG_LEVEL=INFO
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8989/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## 🔧 Configuration

### Environment Variables

```bash
# =============================================================================
# AI Provider API Keys
# =============================================================================

# Google Gemini API (Required)
GEMINI_API_KEY=your_gemini_api_key

# Gemini Model - Available models:
# - gemini-3-flash-preview (latest, recommended)
# - gemini-2.5-flash
# - gemini-2.0-flash
GEMINI_MODEL=gemini-3-flash-preview

# OpenAI API (Optional)
# OPENAI_API_KEY=your_openai_api_key

# =============================================================================
# IPFS Storage - Storacha (formerly web3.storage)
# =============================================================================

# Storacha Space DID Key (for research data storage)
# Get yours at: https://console.storacha.network/
STORACHA_SPACE_DID=did:key:z6Mkv...

# IPFS Gateway URL
IPFS_GATEWAY=https://w3s.link

# =============================================================================
# Oracle Configuration
# =============================================================================

# Number of agents
MIN_AGENTS=3

# Consensus threshold (1.0 = unanimous, 0.67 = 2/3 majority)
CONSENSUS_THRESHOLD=1.0

# Require unanimous agreement
REQUIRE_UNANIMOUS=true

# Maximum consensus rounds before requiring manual review
MAX_CONSENSUS_ROUNDS=5

# Minimum sources per agent
MIN_SOURCES_PER_AGENT=50

# Research timeout in seconds
RESEARCH_TIMEOUT=300

# =============================================================================
# API Server Configuration
# =============================================================================

# API Server Host and Port
API_HOST=0.0.0.0
API_PORT=8989

# Log Level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# Enable debug mode
DEBUG=false
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    1024 Multi-Agent Deep Research Oracle                    │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     Oracle Request (V2)                               │  │
│  │  {                                                                    │  │
│  │    "market_id": "market_123",                                        │  │
│  │    "question": "Did X happen?",                                      │  │
│  │    "resolution_criteria": "...",                                     │  │
│  │    "oracle_config_cid": "bafyrei...",                               │  │
│  │    "oracle_config_hash": "sha256:..."                               │  │
│  │  }                                                                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                      │                                      │
│                    ┌─────────────────┼─────────────────┐                    │
│                    ↓                 ↓                 ↓                    │
│  ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐   │
│  │  Gemini Agent A     │ │  Gemini Agent B     │ │  Gemini Agent C     │   │
│  │  ─────────────────  │ │  ─────────────────  │ │  ─────────────────  │   │
│  │  Model: gemini-3-   │ │  Model: gemini-3-   │ │  Model: gemini-3-   │   │
│  │         flash       │ │         flash       │ │         flash       │   │
│  │  Strategy: Compre-  │ │  Strategy: Focused  │ │  Strategy: Diverse  │   │
│  │            hensive  │ │                     │ │                     │   │
│  │                     │ │                     │ │                     │   │
│  │  ┌───────────────┐  │ │  ┌───────────────┐  │ │  ┌───────────────┐  │   │
│  │  │ Google Search │  │ │  │ Google Search │  │ │  │ Google Search │  │   │
│  │  │ grounding     │  │ │  │ grounding     │  │ │  │ grounding     │  │   │
│  │  └───────────────┘  │ │  └───────────────┘  │ │  └───────────────┘  │   │
│  │                     │ │                     │ │                     │   │
│  │  Sources: 52        │ │  Sources: 48        │ │  Sources: 55        │   │
│  │  Result: YES        │ │  Result: YES        │ │  Result: YES        │   │
│  │  Confidence: 85%    │ │  Confidence: 82%    │ │  Confidence: 88%    │   │
│  └──────────┬──────────┘ └──────────┬──────────┘ └──────────┬──────────┘   │
│             │                       │                       │              │
│             └───────────────────────┼───────────────────────┘              │
│                                     ↓                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    Strict Consensus Engine                            │ │
│  │                                                                       │ │
│  │  1. Collect agent results                                            │ │
│  │  2. Validate source requirements (50+ each)                          │ │
│  │  3. Check cross-agent agreement                                      │ │
│  │  4. Require UNANIMOUS agreement (100%)                               │ │
│  │  5. Up to 5 consensus rounds if disagreement                         │ │
│  │  6. Flag for manual review if no consensus                           │ │
│  │                                                                       │ │
│  │  ✅ Consensus: YES (100% agreement, 155 unique sources)              │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                     │                                      │
│                                     ↓                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    IPFS Storage (Storacha)                            │ │
│  │                                                                       │ │
│  │  Store complete research data:                                       │ │
│  │  - All agent results with thinking traces                            │ │
│  │  - All 155 sources with URLs                                         │ │
│  │  - Reasoning and verification data                                   │ │
│  │  - Timestamps and metadata                                           │ │
│  │                                                                       │ │
│  │  → IPFS CID: bafyreiabc...                                          │ │
│  │  → SHA256 Hash: sha256:def456...                                    │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                     │                                      │
│                                     ↓                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    1024Chain Submission                               │ │
│  │                                                                       │ │
│  │  Submit to 1024 Prediction Market Program:                           │ │
│  │  - market_id: "market_123"                                           │ │
│  │  - outcome: YES (1)                                                  │ │
│  │  - confidence: 8500 (85.00%)                                         │ │
│  │  - research_data_cid: [59 bytes]                                     │ │
│  │  - research_data_hash: [32 bytes]                                    │ │
│  │  - agent_count: 3                                                    │ │
│  │  - source_count: 155                                                 │ │
│  │                                                                       │ │
│  │  → Challenge Period: 24-72 hours                                     │ │
│  │  → Users can challenge with evidence                                 │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 📊 Source Categories

Each agent must collect sources from diverse categories:

| Category | Examples | Purpose |
|----------|----------|---------|
| **Official** | .gov, company press releases | Primary verification |
| **News** | Reuters, AP, Bloomberg, BBC | Mainstream coverage |
| **Social** | Twitter/X (verified), Reddit | Real-time signals |
| **Domain-Specific** | ESPN (sports), CoinDesk (crypto) | Expert sources |
| **Fact-Check** | Snopes, PolitiFact | Verification |

## 📦 IPFS Research Data Format

All research is stored on IPFS for full transparency:

```json
{
  "version": "2.0.0",
  "market_id": "market_123",
  "question": "Did Bitcoin reach $100,000 by December 31, 2025?",
  "resolution_criteria": "BTC/USD spot price >= $100,000 on major exchange",
  "research_timestamp": "2025-12-31T23:30:00Z",
  "oracle_config_cid": "bafyrei...",
  "oracle_config_hash": "sha256:...",
  
  "agents": [
    {
      "agent_id": "gemini-agent-1",
      "model": "gemini-3-flash-preview",
      "strategy": "comprehensive",
      "outcome": "YES",
      "confidence": 0.85,
      "reasoning": "Based on comprehensive analysis of 52 sources...",
      "thinking_trace": "Step 1: Searched for Bitcoin price history...",
      "sources": [
        {
          "url": "https://www.coinbase.com/price/bitcoin",
          "title": "Bitcoin Price | BTC Price Index | Coinbase",
          "snippet": "Bitcoin reached $100,847.23 on December 15, 2025",
          "date": "2025-12-15",
          "category": "official",
          "relevance": 0.98
        }
      ],
      "research_duration_seconds": 45.2
    }
  ],
  
  "consensus": {
    "outcome": "YES",
    "confidence": 0.85,
    "agreement_ratio": 1.0,
    "unanimous": true,
    "rounds_required": 1,
    "total_unique_sources": 155
  },
  
  "verification": {
    "config_verified": true,
    "data_hash": "sha256:def456...",
    "requires_manual_review": false
  }
}
```

## 🔐 Security & Trust Model

### How is this more trustworthy than a single admin?

| Aspect | Single Admin | Multi-Agent Oracle |
|--------|--------------|-------------------|
| **Decision Maker** | 1 person | 3+ independent AI agents |
| **Verification** | Trust admin | Cross-verify with 150+ sources |
| **Transparency** | Hidden | All research on IPFS |
| **Manipulation** | Easy | Need to fool multiple agents |
| **Audit** | Difficult | Anyone can verify sources |
| **Challenge** | None | 24-72 hour challenge period |
| **Hash Verification** | None | SHA256 hash stored on-chain |

### Trust Assumptions

1. **Gemini API is honest** - Google's API returns genuine search results
2. **Sources are real** - URLs point to actual content
3. **Consensus is meaningful** - Multiple agents agreeing increases confidence
4. **IPFS is immutable** - CIDs are content-addressed

### Limitations

- Still relies on AI interpretation
- Source quality varies
- Novel events may have limited sources
- AI can be wrong (hence challenge period)

## 🗺️ Roadmap

- [x] **v0.1** - Core architecture design
- [x] **v0.2** - Gemini Deep Research agent implementation
- [x] **v0.3** - Strict Consensus engine with multi-round support
- [x] **v0.4** - IPFS storage integration (Storacha)
- [x] **v0.5** - V2 API with config verification
- [x] **v0.6** - Docker & CI/CD pipeline
- [ ] **v0.7** - Challenge & dispute resolution
- [ ] **v1.0** - Production release

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

```bash
# Development setup
git clone https://github.com/1024chain/1024-multi-deep-research-agent-oracle.git
cd 1024-multi-deep-research-agent-oracle
uv sync --all-extras  # Install with dev dependencies
uv run pre-commit install

# Run tests
uv run pytest tests/

# Run linter
uv run ruff check .

# Type checking
uv run mypy oracle/
```

## 📜 License

MIT License - See [LICENSE](./LICENSE) for details.

## 🔗 Links

- **1024Chain Explorer**: [testnet-scan.1024chain.com](https://testnet-scan.1024chain.com/)
- **Docker Hub**: [hub.docker.com/r/chuciqin1/1024-multi-deep-research-agent-oracle](https://hub.docker.com/r/chuciqin1/1024-multi-deep-research-agent-oracle)
- **GitHub**: [github.com/1024chain/1024-multi-deep-research-agent-oracle](https://github.com/1024chain/1024-multi-deep-research-agent-oracle)

---

**Built with ❤️ by the 1024 Team**

*Powered by Google Gemini Deep Research API*
