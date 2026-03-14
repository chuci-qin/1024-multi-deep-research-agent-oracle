"""
Consensus Engine for Multi-Agent Oracle.

Calculates consensus from multiple agent results using
Byzantine Fault Tolerant voting.

Components:
- ConsensusEngine: Basic consensus calculation (binary markets)
- StrictConsensusEngine: Enhanced consensus with strict verification (binary markets)
- MultiOutcomeConsensusEngine: Consensus for multi-outcome markets
"""

from oracle.consensus.engine import ConsensusConfig, ConsensusEngine
from oracle.consensus.multi_outcome_engine import (
    MultiOutcomeConsensusConfig,
    MultiOutcomeConsensusEngine,
)
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
    # Multi-outcome consensus
    "MultiOutcomeConsensusEngine",
    "MultiOutcomeConsensusConfig",
]
