"""
Storage module for Multi-Agent Oracle.

Provides IPFS storage for research data transparency.

Components:
- IPFSStorage: IPFS storage client
- canonical: Canonical JSON and SHA256 hashing utilities
- builder: Research data builder
"""

from oracle.storage.builder import OracleResearchDataBuilder
from oracle.storage.canonical import (
    CanonicalJSONEncoder,
    # Classes
    HashableData,
    OracleConfigData,
    OracleResearchData,
    ResearchDataEntry,
    VerifiedData,
    calculate_data_hash,
    calculate_sha256,
    # Functions
    to_canonical_json,
    verify_ipfs_data,
)
from oracle.storage.ipfs import IPFSConfig, IPFSStorage

__all__ = [
    # IPFS
    "IPFSStorage",
    "IPFSConfig",
    # Canonical JSON
    "to_canonical_json",
    "calculate_sha256",
    "calculate_data_hash",
    "verify_ipfs_data",
    "CanonicalJSONEncoder",
    # Data structures
    "HashableData",
    "OracleConfigData",
    "OracleResearchData",
    "ResearchDataEntry",
    "VerifiedData",
    # Builder
    "OracleResearchDataBuilder",
]
