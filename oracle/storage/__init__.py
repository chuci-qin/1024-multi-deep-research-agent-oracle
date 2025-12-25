"""
Storage module for Multi-Agent Oracle.

Provides IPFS storage for research data transparency.

Components:
- IPFSStorage: IPFS storage client
- canonical: Canonical JSON and SHA256 hashing utilities
- builder: Research data builder
"""

from oracle.storage.ipfs import IPFSStorage, IPFSConfig
from oracle.storage.canonical import (
    # Functions
    to_canonical_json,
    calculate_sha256,
    calculate_data_hash,
    verify_ipfs_data,
    # Classes
    HashableData,
    OracleConfigData,
    OracleResearchData,
    ResearchDataEntry,
    VerifiedData,
    CanonicalJSONEncoder,
)
from oracle.storage.builder import OracleResearchDataBuilder

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
