"""
1024 Multi-Agent Deep Research Oracle

An open-source, AI-powered decentralized oracle for prediction markets.
Powered by Google Gemini Deep Research API.
"""

from oracle.core import MultiAgentOracle
from oracle.agents import GeminiDeepResearchAgent
from oracle.consensus import ConsensusEngine
from oracle.storage import IPFSStorage
from oracle.models import (
    OracleRequest,
    OracleResult,
    ConsensusResult,
    ResearchSource,
    AgentResult,
)

__version__ = "0.1.0"
__all__ = [
    "MultiAgentOracle",
    "GeminiDeepResearchAgent",
    "ConsensusEngine",
    "ConsensusResult",
    "IPFSStorage",
    "OracleRequest",
    "OracleResult",
    "ResearchSource",
    "AgentResult",
]
