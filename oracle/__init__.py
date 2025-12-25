"""
1024 Multi-Agent Deep Research Oracle

An open-source, AI-powered decentralized oracle for prediction markets.
Powered by Google Gemini Deep Research API.

Components:
- MultiAgentOracle: Main oracle orchestrator
- GeminiDeepResearchAgent: Gemini-powered research agent
- StrictConsensusEngine: Enhanced consensus with verification
- IPFSStorage: IPFS storage for research data
- Research module: Thinking/Website/Reasoning recorders

Version: 0.2.0 (Phase 2 LLM Oracle Core)
"""

from oracle.core import MultiAgentOracle
from oracle.agents import GeminiDeepResearchAgent, StrategyFactory, StrategyProfile
from oracle.consensus import ConsensusEngine, StrictConsensusEngine
from oracle.storage import (
    IPFSStorage,
    OracleResearchDataBuilder,
    OracleConfigData,
    OracleResearchData,
)
from oracle.models import (
    OracleRequest,
    OracleResult,
    ConsensusResult,
    ResearchSource,
    AgentResult,
)

# Import research module
from oracle.research import (
    ThinkingRecorder,
    WebsiteTracker,
    ReasoningChain,
)

__version__ = "0.2.0"
__all__ = [
    # Core
    "MultiAgentOracle",
    # Agents
    "GeminiDeepResearchAgent",
    "StrategyFactory",
    "StrategyProfile",
    # Consensus
    "ConsensusEngine",
    "StrictConsensusEngine",
    "ConsensusResult",
    # Storage
    "IPFSStorage",
    "OracleResearchDataBuilder",
    "OracleConfigData",
    "OracleResearchData",
    # Models
    "OracleRequest",
    "OracleResult",
    "ResearchSource",
    "AgentResult",
    # Research recorders
    "ThinkingRecorder",
    "WebsiteTracker",
    "ReasoningChain",
]
