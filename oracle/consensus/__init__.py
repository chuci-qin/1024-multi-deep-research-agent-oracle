"""
Consensus Engine for Multi-Agent Oracle.

Calculates consensus from multiple agent results using
Byzantine Fault Tolerant voting.
"""

from oracle.consensus.engine import ConsensusEngine, ConsensusConfig

__all__ = [
    "ConsensusEngine",
    "ConsensusConfig",
]
