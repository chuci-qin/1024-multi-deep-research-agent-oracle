"""
Consensus Engine for Multi-Agent Oracle.

Calculates consensus from multiple agent results using
Byzantine Fault Tolerant voting.

Components:
- ConsensusEngine: Basic consensus calculation
- StrictConsensusEngine: Enhanced consensus with strict verification
"""

from oracle.consensus.engine import ConsensusConfig, ConsensusEngine
from oracle.consensus.strict_engine import (
    DisagreementAnalysis,
    ProvableConsensusData,
    StrictConsensusConfig,
    StrictConsensusEngine,
    VerificationResult,
)

__all__ = [
    # Basic consensus
    "ConsensusEngine",
    "ConsensusConfig",
    # Strict consensus
    "StrictConsensusEngine",
    "StrictConsensusConfig",
    "VerificationResult",
    "DisagreementAnalysis",
    "ProvableConsensusData",
]
