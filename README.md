# 🔮 1024 Prediction Market Multi-Agent Oracle

> **An Open-Source, AI-Powered Decentralized Oracle for 1024 Prediction Market Resolution**  
> **Powered by Google Gemini Deep Research API + Multi-Agent Cross-Verification**

## 🎯 What is This?

This is the **AI Oracle** for the **1024 Prediction Market**. Instead of relying on a centralized admin to determine market outcomes, this system uses multiple AI agents to independently research questions and reach consensus with full source traceability.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Gemini API](https://img.shields.io/badge/Gemini-Deep%20Research-4285F4.svg)](https://ai.google.dev/)

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
│         │   Gemini     │  │   Gemini     │  │   OpenAI     │               │
│         │  (50+ sources)│  │ (50+ sources)│  │ (50+ sources)│               │
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
| 🗳️ **Consensus** | 2/3+ supermajority required for valid results |
| 📦 **IPFS Storage** | All research stored on IPFS for transparency |
| ⛓️ **On-Chain** | Results submitted to Solana with IPFS proof |

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Google Gemini API Key ([Get one here](https://ai.google.dev/))
- (Optional) OpenAI API Key for additional agent

### Installation

```bash
# Clone the repository
git clone https://github.com/1024chain/1024-multi-deep-research-agent-oracle.git
cd 1024-multi-deep-research-agent-oracle

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Configure API keys
cp .env.example .env
# Edit .env with your API keys
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
    consensus_threshold=0.67,  # 2/3 majority
)

# Research a prediction market question
result = await oracle.resolve(
    question="Did Bitcoin reach $100,000 by December 31, 2025?",
    resolution_criteria="BTC/USD spot price must have reached or exceeded $100,000.00 on any major exchange (Coinbase, Binance, Kraken) at any point before midnight UTC on December 31, 2025.",
)

# Check result
print(f"Outcome: {result.outcome}")           # YES / NO / UNDETERMINED
print(f"Confidence: {result.confidence:.1%}") # 85.0%
print(f"Agreement: {result.agreement_ratio:.1%}")  # 100.0%
print(f"Total Sources: {len(result.sources)}")     # 156
print(f"IPFS Hash: {result.ipfs_hash}")       # Qm...

# View all sources
for source in result.sources[:10]:
    print(f"  - {source.title}")
    print(f"    URL: {source.url}")
    print(f"    Category: {source.category}")
```

### CLI Usage

```bash
# Resolve a question
oracle resolve \
    --question "Did SpaceX successfully land Starship on December 15, 2025?" \
    --criteria "Starship must complete controlled landing without RUD" \
    --agents 3

# Output:
# ✅ Consensus Reached: YES
# 📊 Agreement: 100% (3/3 agents)
# 🔍 Total Sources: 162
# 📄 IPFS Hash: QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco
# 
# Top Sources:
#   1. SpaceX Official - "Starship Flight 7 Success" (spacex.com)
#   2. Reuters - "SpaceX Starship lands successfully" (reuters.com)
#   3. NASA - "Artemis Program Update" (nasa.gov)
#   ...
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    1024 Multi-Agent Deep Research Oracle                     │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     Oracle Request                                     │  │
│  │  {                                                                    │  │
│  │    "market_id": 123,                                                  │  │
│  │    "question": "Did X happen?",                                       │  │
│  │    "resolution_criteria": "...",                                      │  │
│  │    "deadline": "2025-12-31T23:59:59Z"                                │  │
│  │  }                                                                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                      │                                       │
│                    ┌─────────────────┼─────────────────┐                    │
│                    ↓                 ↓                 ↓                    │
│  ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐   │
│  │  Gemini Agent A     │ │  Gemini Agent B     │ │  Gemini Agent C     │   │
│  │  ─────────────────  │ │  ─────────────────  │ │  ─────────────────  │   │
│  │  Model: gemini-2.0  │ │  Model: gemini-2.0  │ │  Model: gemini-2.0  │   │
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
│             │                       │                       │               │
│             └───────────────────────┼───────────────────────┘               │
│                                     ↓                                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                       Consensus Engine                                 │  │
│  │                                                                        │  │
│  │  1. Collect agent results                                             │  │
│  │  2. Validate source requirements (50+ each)                           │  │
│  │  3. Check cross-agent agreement                                       │  │
│  │  4. Calculate weighted confidence                                     │  │
│  │  5. Require 2/3+ supermajority                                        │  │
│  │  6. Merge & deduplicate sources                                       │  │
│  │                                                                        │  │
│  │  ✅ Consensus: YES (100% agreement, 155 unique sources)               │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                     │                                       │
│                                     ↓                                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                       IPFS Storage                                     │  │
│  │                                                                        │  │
│  │  Store complete research data:                                        │  │
│  │  - All agent results                                                  │  │
│  │  - All 155 sources with URLs                                          │  │
│  │  - Reasoning traces                                                   │  │
│  │  - Timestamps                                                         │  │
│  │                                                                        │  │
│  │  → IPFS Hash: QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                     │                                       │
│                                     ↓                                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                       Blockchain Submission                            │  │
│  │                                                                        │  │
│  │  Submit to Solana Prediction Market Program:                          │  │
│  │  - market_id: 123                                                     │  │
│  │  - outcome: YES (1)                                                   │  │
│  │  - confidence: 8500 (85.00%)                                          │  │
│  │  - ipfs_cid: "QmXoy..."                                               │  │
│  │  - agent_count: 3                                                     │  │
│  │  - source_count: 155                                                  │  │
│  │                                                                        │  │
│  │  → Transaction: 5abc...xyz                                            │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 🔧 Configuration

### Environment Variables

```bash
# .env
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key  # Optional, for OpenAI agent

# IPFS
IPFS_GATEWAY=https://w3s.link
WEB3_STORAGE_TOKEN=your_web3_storage_token

# Solana
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
ORACLE_KEYPAIR_PATH=./keys/oracle.json
```

### Oracle Configuration

```yaml
# config/oracle.yaml
oracle:
  # Minimum number of agents required
  min_agents: 3
  
  # Consensus threshold (0.67 = 2/3 majority)
  consensus_threshold: 0.67
  
  # Minimum confidence for valid result
  min_confidence: 0.5

agents:
  # Gemini Deep Research Agents
  - type: gemini
    model: gemini-2.0-flash-exp
    min_sources: 50
    search_depth: comprehensive
    
  - type: gemini
    model: gemini-2.0-flash-exp  
    min_sources: 50
    search_depth: focused
    
  - type: gemini
    model: gemini-2.0-flash-exp
    min_sources: 50
    search_depth: diverse

source_requirements:
  min_total: 50
  min_categories: 5
  categories:
    official: 5      # Government, company sites
    news: 15         # Reuters, AP, Bloomberg
    social: 10       # Twitter, Reddit
    domain: 10       # Domain-specific sources
    fact_check: 3    # Snopes, PolitiFact
```

## 📊 Source Categories

Each agent must collect sources from at least 5 categories:

| Category | Examples | Min Required |
|----------|----------|--------------|
| **Official** | .gov, company press releases, official announcements | 5 |
| **News** | Reuters, AP, Bloomberg, BBC, CNN | 15 |
| **Social** | Twitter/X (verified accounts), Reddit | 10 |
| **Domain-Specific** | ESPN (sports), CoinDesk (crypto), etc. | 10 |
| **Fact-Check** | Snopes, PolitiFact, FactCheck.org | 3 |

## 📦 IPFS Research Data Format

All research is stored on IPFS for full transparency:

```json
{
  "version": "1.0.0",
  "market_id": 123,
  "question": "Did Bitcoin reach $100,000 by December 31, 2025?",
  "resolution_criteria": "BTC/USD spot price >= $100,000 on major exchange",
  "research_timestamp": "2025-12-31T23:30:00Z",
  
  "agents": [
    {
      "agent_id": "gemini-agent-1",
      "model": "gemini-2.0-flash-exp",
      "strategy": "comprehensive",
      "outcome": "YES",
      "confidence": 0.85,
      "reasoning": "Based on comprehensive analysis of 52 sources...",
      "sources": [
        {
          "url": "https://www.coinbase.com/price/bitcoin",
          "title": "Bitcoin Price | BTC Price Index | Coinbase",
          "snippet": "Bitcoin reached $100,847.23 on December 15, 2025",
          "date": "2025-12-15",
          "category": "official",
          "relevance": 0.98,
          "credibility": 0.95
        },
        // ... 51 more sources
      ],
      "research_duration_seconds": 45.2
    },
    // ... 2 more agents
  ],
  
  "consensus": {
    "outcome": "YES",
    "confidence": 0.85,
    "agreement_ratio": 1.0,
    "total_unique_sources": 155,
    "source_overlap_ratio": 0.32
  },
  
  "merged_sources": [
    // All 155 unique sources
  ]
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

### Trust Assumptions

1. **Gemini API is honest** - Google's API returns genuine search results
2. **Sources are real** - URLs point to actual content
3. **Consensus is meaningful** - Multiple agents agreeing increases confidence

### Limitations

- Still relies on AI interpretation
- Source quality varies
- Novel events may have limited sources
- AI can be wrong

## 🗺️ Roadmap

- [x] **v0.1** - Core architecture design
- [ ] **v0.2** - Gemini Deep Research agent implementation
- [ ] **v0.3** - Consensus engine
- [ ] **v0.4** - IPFS storage integration
- [ ] **v0.5** - Solana program integration
- [ ] **v1.0** - Production release

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

```bash
# Development setup
git clone https://github.com/1024chain/1024-multi-deep-research-agent-oracle.git
cd 1024-multi-deep-research-agent-oracle
pip install -e ".[dev]"
pre-commit install

# Run tests
pytest tests/

# Run linter
ruff check .
```

## 📜 License

MIT License - See [LICENSE](./LICENSE) for details.

## 🔗 Links

- **Documentation**: [docs.1024oracle.xyz](https://docs.1024oracle.xyz)
- **GitHub**: [github.com/1024chain/1024-multi-deep-research-agent-oracle](https://github.com/1024chain/1024-multi-deep-research-agent-oracle)
- **Discord**: [discord.gg/1024chain](https://discord.gg/1024chain)
- **Twitter**: [@1024chain](https://twitter.com/1024chain)

---

**Built with ❤️ by the 1024 Team**

*Powered by Google Gemini Deep Research API*
