"""
Data models for the Multi-Agent Oracle.

These models define the core data structures used throughout the oracle system.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Outcome(str, Enum):
    """Possible outcomes for a prediction market resolution."""
    YES = "YES"
    NO = "NO"
    UNDETERMINED = "UNDETERMINED"
    INVALID = "INVALID"


class SourceCategory(str, Enum):
    """Categories for research sources."""
    OFFICIAL = "official"           # .gov, company websites, press releases
    NEWS = "news"                   # Reuters, AP, Bloomberg, BBC
    SOCIAL = "social"               # Twitter/X, Reddit
    DOMAIN_SPECIFIC = "domain_specific"  # Industry-specific sources
    FACT_CHECK = "fact_check"       # Snopes, PolitiFact


class ResearchSource(BaseModel):
    """A single research source with metadata."""
    
    url: str = Field(..., description="Source URL")
    title: str = Field(..., description="Source title")
    snippet: str = Field(default="", description="Relevant content excerpt")
    date: Optional[str] = Field(None, description="Publication date")
    category: SourceCategory = Field(..., description="Source category")
    relevance_score: float = Field(default=0.8, ge=0.0, le=1.0)
    credibility_score: float = Field(default=0.8, ge=0.0, le=1.0)
    cited_by: list[str] = Field(default_factory=list, description="Agent IDs that cited this source")
    
    def __hash__(self):
        return hash(self.url)
    
    def __eq__(self, other):
        if isinstance(other, ResearchSource):
            return self.url == other.url
        return False


class AgentResult(BaseModel):
    """Result from a single research agent."""
    
    agent_id: str = Field(..., description="Unique agent identifier")
    model: str = Field(..., description="LLM model used")
    strategy: str = Field(default="comprehensive", description="Research strategy used")
    outcome: Outcome = Field(..., description="Agent's determined outcome")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    reasoning: str = Field(..., description="Detailed reasoning")
    sources: list[ResearchSource] = Field(default_factory=list)
    source_count: int = Field(default=0)
    research_duration_seconds: float = Field(default=0.0)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    error: Optional[str] = Field(None)
    
    @property
    def is_valid(self) -> bool:
        """Check if result meets minimum requirements."""
        return (
            len(self.sources) >= 50
            and self.error is None
            and self.outcome != Outcome.INVALID
        )
    
    @property
    def category_distribution(self) -> dict[str, int]:
        """Get distribution of sources by category."""
        dist: dict[str, int] = {}
        for source in self.sources:
            cat = source.category.value if isinstance(source.category, SourceCategory) else source.category
            dist[cat] = dist.get(cat, 0) + 1
        return dist
    
    def model_post_init(self, __context) -> None:
        self.source_count = len(self.sources)


class OracleRequest(BaseModel):
    """Request for oracle resolution."""
    
    request_id: str = Field(..., description="Unique request identifier")
    market_id: int = Field(..., description="Prediction market ID")
    question: str = Field(..., description="Question to resolve")
    resolution_criteria: str = Field(..., description="Criteria for resolution")
    deadline: Optional[str] = Field(None, description="Resolution deadline")
    callback_url: Optional[str] = Field(None, description="Webhook callback URL")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ConsensusResult(BaseModel):
    """Result of consensus calculation."""
    
    reached: bool = Field(..., description="Whether consensus was reached")
    outcome: Outcome = Field(..., description="Consensus outcome")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    agreement_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    weighted_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    total_sources: int = Field(default=0)
    unique_sources: int = Field(default=0)
    source_overlap: float = Field(default=0.0)
    agent_count: int = Field(default=0)
    requires_human_review: bool = Field(default=False)
    reason: Optional[str] = Field(None)


class OracleResult(BaseModel):
    """Complete oracle resolution result."""
    
    request_id: str
    market_id: int
    question: str
    resolution_criteria: str
    
    # Consensus result
    consensus: ConsensusResult
    
    # Individual agent results
    agent_results: list[AgentResult] = Field(default_factory=list)
    
    # Merged sources (deduplicated)
    merged_sources: list[ResearchSource] = Field(default_factory=list)
    
    # IPFS storage
    ipfs_cid: Optional[str] = Field(None, description="IPFS CID for full research data")
    
    # Timestamps
    research_started_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    research_completed_at: Optional[str] = Field(None)
    
    # Blockchain submission
    transaction_signature: Optional[str] = Field(None)
    
    @property
    def outcome(self) -> Outcome:
        return self.consensus.outcome
    
    @property
    def confidence(self) -> float:
        return self.consensus.confidence
    
    @property
    def source_count(self) -> int:
        return len(self.merged_sources)


class IPFSResearchData(BaseModel):
    """Complete research data stored on IPFS."""
    
    version: str = "1.0.0"
    market_id: int
    question: str
    resolution_criteria: str
    research_timestamp: str
    
    agents: list[AgentResult]
    consensus: ConsensusResult
    merged_sources: list[ResearchSource]
    
    def to_json(self) -> str:
        import json
        return json.dumps(self.model_dump(), indent=2, default=str)
