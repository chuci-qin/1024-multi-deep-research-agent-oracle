"""
Canonical JSON (JCS) and SHA256 Hashing

Implements RFC 8785 (JSON Canonicalization Scheme) for deterministic
JSON serialization, and SHA256 hashing for data integrity verification.

This ensures that:
1. The same data always produces the same JSON string
2. The hash can be recalculated by anyone with the data
3. On-chain stored hashes can verify IPFS data integrity

Task ID: 2.7.1 - 2.7.8 from IMPLEMENTATION-TRACKER.md
"""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional, Union
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger()


class CanonicalJSONEncoder(json.JSONEncoder):
    """
    JSON encoder following RFC 8785 (JCS) principles.
    
    Task 2.7.2: Implement canonical JSON encoding.
    
    Key requirements:
    1. Keys sorted lexicographically (by UTF-8 bytes)
    2. No whitespace between tokens
    3. Numbers in shortest possible representation
    4. Strings properly escaped
    5. Booleans and null lowercase
    """
    
    def default(self, obj: Any) -> Any:
        # Handle datetime
        if isinstance(obj, datetime):
            return obj.isoformat()
        
        # Handle Enum
        if isinstance(obj, Enum):
            return obj.value
        
        # Handle Decimal
        if isinstance(obj, Decimal):
            # Convert to float, then format
            return float(obj)
        
        # Handle Pydantic models
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        
        # Handle bytes
        if isinstance(obj, bytes):
            return obj.hex()
        
        # Handle sets
        if isinstance(obj, set):
            return sorted(list(obj))
        
        return super().default(obj)


def to_canonical_json(data: Any) -> str:
    """
    Convert data to canonical JSON string.
    
    Task 2.7.3: Implement to_canonical_json() function.
    
    Args:
        data: Any JSON-serializable data
        
    Returns:
        Canonical JSON string (deterministic, sorted keys, no whitespace)
    """
    # If it's a Pydantic model, convert to dict first
    if isinstance(data, BaseModel):
        data = data.model_dump()
    
    # Serialize with sorted keys and no extra whitespace
    return json.dumps(
        data,
        cls=CanonicalJSONEncoder,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def calculate_sha256(data: Union[str, bytes]) -> str:
    """
    Calculate SHA256 hash of data.
    
    Task 2.7.4: Implement calculate_sha256() function.
    
    Args:
        data: String or bytes to hash
        
    Returns:
        Hexadecimal SHA256 hash string
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    
    return hashlib.sha256(data).hexdigest()


def calculate_data_hash(data: Any) -> tuple[str, str]:
    """
    Calculate canonical JSON and its SHA256 hash.
    
    Args:
        data: Any JSON-serializable data
        
    Returns:
        Tuple of (canonical_json, sha256_hash)
    """
    canonical = to_canonical_json(data)
    hash_value = calculate_sha256(canonical)
    return canonical, hash_value


class HashableData(BaseModel):
    """
    Base class for hashable data structures.
    
    Task 2.7.5: Create HashableData base class.
    """
    
    def to_canonical_json(self) -> str:
        """Convert to canonical JSON string."""
        return to_canonical_json(self.model_dump())
    
    def calculate_hash(self) -> str:
        """Calculate SHA256 hash of canonical JSON."""
        return calculate_sha256(self.to_canonical_json())
    
    def get_hash_data(self) -> tuple[str, str]:
        """Get both canonical JSON and hash."""
        canonical = self.to_canonical_json()
        hash_value = calculate_sha256(canonical)
        return canonical, hash_value


class OracleConfigData(HashableData):
    """
    Oracle configuration data structure for IPFS storage.
    
    Task 2.7.6: Define OracleConfigData.
    
    This is stored on IPFS and its hash is submitted on-chain.
    """
    
    version: str = Field(default="1.0.0")
    market_id: int
    question: str
    resolution_criteria: str
    
    # Deadline and timing
    deadline: Optional[str] = Field(None)
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    
    # Agent configuration
    agent_count: int
    agent_strategies: list[str]
    
    # Consensus configuration
    consensus_threshold: float
    min_sources_per_agent: int
    min_source_categories: int
    
    # Source requirements
    require_tier1_sources: bool = Field(default=True)
    min_tier1_count: int = Field(default=2)
    min_tier2_count: int = Field(default=3)
    
    # Additional metadata
    metadata: dict = Field(default_factory=dict)


class ResearchDataEntry(HashableData):
    """
    Individual agent research data entry.
    
    Task 2.7.7: Define ResearchDataEntry.
    """
    
    agent_id: str
    model: str
    strategy: str
    
    # Outcome
    outcome: str
    confidence: float
    reasoning: str
    
    # Sources
    sources: list[dict]
    source_count: int
    
    # Process records (optional)
    thinking_process: Optional[list[dict]] = Field(None)
    website_visits: Optional[list[dict]] = Field(None)
    reasoning_chain: Optional[list[dict]] = Field(None)
    
    # Timing
    research_duration_seconds: float
    timestamp: str


class OracleResearchData(HashableData):
    """
    Complete oracle research data structure for IPFS storage.
    
    Task 2.7.8: Define OracleResearchData.
    
    This is the main research data stored on IPFS.
    """
    
    version: str = Field(default="2.0.0")
    
    # Reference to config
    oracle_config_cid: Optional[str] = Field(None)
    oracle_config_hash: Optional[str] = Field(None)
    
    # Market identification
    market_id: int
    question: str
    resolution_criteria: str
    
    # Research timing
    research_started_at: str
    research_completed_at: str
    
    # Agent research entries
    agent_results: list[ResearchDataEntry]
    
    # Consensus result
    consensus: dict  # Serialized ConsensusResult
    
    # Merged sources (deduplicated)
    merged_sources: list[dict]
    
    # Provable consensus data
    provable_data: Optional[dict] = Field(None)
    
    # Summary statistics
    total_agents: int
    valid_agents: int
    total_sources: int
    unique_sources: int
    
    def model_post_init(self, __context) -> None:
        """Calculate derived fields after init."""
        if not self.total_agents:
            self.total_agents = len(self.agent_results)
        if not self.valid_agents:
            self.valid_agents = sum(
                1 for r in self.agent_results
                if r.source_count >= 3  # Basic validity check
            )


class VerifiedData(BaseModel):
    """
    Container for verified data with hash.
    
    Used to ensure data integrity when retrieving from IPFS.
    """
    
    data: Union[OracleConfigData, OracleResearchData]
    canonical_json: str
    sha256_hash: str
    verified: bool = Field(default=False)
    
    @classmethod
    def from_data(cls, data: Union[OracleConfigData, OracleResearchData]) -> "VerifiedData":
        """Create verified data container from data."""
        canonical, hash_value = data.get_hash_data()
        return cls(
            data=data,
            canonical_json=canonical,
            sha256_hash=hash_value,
            verified=True,
        )
    
    def verify(self) -> bool:
        """Verify that the hash matches the data."""
        canonical, hash_value = self.data.get_hash_data()
        self.verified = (hash_value == self.sha256_hash)
        return self.verified


def verify_ipfs_data(
    json_data: str,
    expected_hash: str,
) -> tuple[bool, Optional[dict], str]:
    """
    Verify IPFS data against expected hash.
    
    Args:
        json_data: JSON string from IPFS
        expected_hash: Expected SHA256 hash
        
    Returns:
        Tuple of (is_valid, parsed_data, actual_hash)
    """
    try:
        # Parse JSON
        parsed = json.loads(json_data)
        
        # Calculate canonical form and hash
        canonical = to_canonical_json(parsed)
        actual_hash = calculate_sha256(canonical)
        
        # Compare hashes
        is_valid = (actual_hash == expected_hash)
        
        if not is_valid:
            logger.warning(
                "Hash mismatch",
                expected=expected_hash,
                actual=actual_hash,
            )
        
        return is_valid, parsed, actual_hash
        
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        return False, None, ""

