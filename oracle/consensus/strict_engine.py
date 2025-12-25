"""
Strict Consensus Engine

Enhanced consensus engine with strict verification, provable data generation,
and detailed disagreement analysis for on-chain oracle resolution.

Task ID: 2.5.1 - 2.5.13 from IMPLEMENTATION-TRACKER.md
"""

import hashlib
import json
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import structlog

from oracle.models import (
    AgentResult,
    ConsensusResult,
    ResearchSource,
    Outcome,
    SourceCategory,
)
from oracle.consensus.engine import ConsensusConfig, ConsensusEngine
from oracle.research.thinking_recorder import ThinkingRecorder
from oracle.research.website_tracker import WebsiteTracker
from oracle.research.reasoning_chain import ReasoningChain

logger = structlog.get_logger()


class StrictConsensusConfig(ConsensusConfig):
    """
    Extended configuration for strict consensus calculation.
    
    Task 2.5.1: Define StrictConsensusConfig.
    """
    
    # Enhanced threshold (default 2/3 supermajority)
    threshold: float = Field(default=0.67, ge=0.5, le=1.0)
    
    # Strict source requirements
    min_tier1_sources: int = Field(
        default=2,
        description="Minimum Tier 1 (official/wire) sources required"
    )
    min_tier2_sources: int = Field(
        default=3,
        description="Minimum Tier 2 (major news) sources required"
    )
    require_source_diversity: bool = Field(
        default=True,
        description="Require sources from multiple categories"
    )
    min_source_categories: int = Field(
        default=3,
        description="Minimum number of different source categories"
    )
    
    # Confidence requirements
    min_individual_confidence: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum confidence per agent for vote to count"
    )
    min_consensus_confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum weighted average confidence for consensus"
    )
    
    # Verification settings
    require_cross_verification: bool = Field(
        default=True,
        description="Require key facts to be verified across agents"
    )
    min_cross_verified_facts: int = Field(
        default=3,
        description="Minimum facts verified by multiple agents"
    )
    
    # Human review triggers
    max_confidence_spread: float = Field(
        default=0.3,
        description="Max confidence spread before requiring review"
    )


class VerificationResult(BaseModel):
    """Result of source and fact verification."""
    
    passed: bool = Field(..., description="Whether verification passed")
    tier1_sources: int = Field(default=0)
    tier2_sources: int = Field(default=0)
    total_sources: int = Field(default=0)
    unique_sources: int = Field(default=0)
    source_categories: list[str] = Field(default_factory=list)
    cross_verified_facts: int = Field(default=0)
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DisagreementAnalysis(BaseModel):
    """
    Detailed analysis of agent disagreements.
    
    Task 2.5.10-2.5.11: Implement disagreement analysis.
    """
    
    has_disagreement: bool = Field(default=False)
    outcome_distribution: dict[str, int] = Field(default_factory=dict)
    confidence_stats: dict = Field(default_factory=dict)
    source_overlap_by_outcome: dict[str, float] = Field(default_factory=dict)
    conflicting_evidence: list[dict] = Field(default_factory=list)
    contributing_factors: list[str] = Field(default_factory=list)
    resolution_recommendations: list[str] = Field(default_factory=list)
    requires_manual_review: bool = Field(default=False)
    review_reason: Optional[str] = Field(None)


class ProvableConsensusData(BaseModel):
    """
    Provable consensus data for on-chain verification.
    
    Task 2.5.12-2.5.13: Generate provable data.
    """
    
    # Consensus summary
    consensus_reached: bool
    outcome: str
    confidence: float
    agent_count: int
    agreement_ratio: float
    weighted_ratio: float
    
    # Verification results
    verification: VerificationResult
    
    # Disagreement analysis (if any)
    disagreement: Optional[DisagreementAnalysis] = None
    
    # Source summary
    total_sources: int
    unique_sources: int
    tier_distribution: dict[str, int] = Field(default_factory=dict)
    
    # Timestamps
    calculated_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    
    # Hash for verification
    data_hash: Optional[str] = Field(None)
    
    def calculate_hash(self) -> str:
        """Calculate SHA256 hash of the provable data."""
        # Exclude the hash field itself
        data = self.model_dump(exclude={"data_hash"})
        # Sort for deterministic output
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def model_post_init(self, __context) -> None:
        """Calculate hash after initialization."""
        if self.data_hash is None:
            self.data_hash = self.calculate_hash()


class StrictConsensusEngine(ConsensusEngine):
    """
    Strict Consensus Engine with enhanced verification.
    
    Task 2.5.2-2.5.9: Implement StrictConsensusEngine.
    
    Features:
    - Strict source quality requirements
    - Cross-agent fact verification
    - Detailed disagreement analysis
    - Provable consensus data generation
    - Integration with research recorders
    """
    
    def __init__(self, config: Optional[StrictConsensusConfig] = None):
        self.strict_config = config or StrictConsensusConfig()
        super().__init__(config=self.strict_config)
        
        logger.info(
            "Initialized strict consensus engine",
            threshold=self.strict_config.threshold,
            min_tier1=self.strict_config.min_tier1_sources,
            min_tier2=self.strict_config.min_tier2_sources,
        )
    
    def calculate_strict(
        self,
        results: list[AgentResult],
        thinking_recorders: Optional[list[ThinkingRecorder]] = None,
        website_trackers: Optional[list[WebsiteTracker]] = None,
        reasoning_chains: Optional[list[ReasoningChain]] = None,
    ) -> tuple[ConsensusResult, ProvableConsensusData]:
        """
        Calculate strict consensus with full verification.
        
        Task 2.5.3-2.5.4: Main calculation method.
        
        Args:
            results: Agent research results
            thinking_recorders: Optional thinking process records
            website_trackers: Optional website visit trackers
            reasoning_chains: Optional reasoning chain records
            
        Returns:
            Tuple of (ConsensusResult, ProvableConsensusData)
        """
        logger.info(f"Calculating strict consensus from {len(results)} agents")
        
        # Step 1: Verify source requirements
        verification = self._verify_sources(results)
        
        # Step 2: Filter by confidence threshold
        qualified_results = [
            r for r in results
            if r.is_valid and r.confidence >= self.strict_config.min_individual_confidence
        ]
        
        logger.info(
            f"Qualified results: {len(qualified_results)}/{len(results)}",
            verification_passed=verification.passed,
        )
        
        # Step 3: Calculate base consensus
        if len(qualified_results) < self.strict_config.min_agents:
            consensus = ConsensusResult(
                reached=False,
                outcome=Outcome.UNDETERMINED,
                reason=f"Only {len(qualified_results)} qualified results, need {self.strict_config.min_agents}",
                agent_count=len(results),
                requires_human_review=True,
            )
        else:
            consensus = super().calculate(qualified_results)
        
        # Step 4: Additional verification checks
        if consensus.reached:
            # Check if confidence meets minimum
            if consensus.confidence < self.strict_config.min_consensus_confidence:
                consensus.reached = False
                consensus.requires_human_review = True
                consensus.reason = f"Confidence {consensus.confidence:.1%} below minimum {self.strict_config.min_consensus_confidence:.1%}"
            
            # Check verification requirements
            if not verification.passed:
                consensus.requires_human_review = True
                # Don't invalidate consensus, but flag for review
        
        # Step 5: Analyze disagreement
        disagreement = self._analyze_disagreement_detailed(results)
        
        # Step 6: Generate provable data
        provable_data = self._generate_provable_data(
            results=results,
            consensus=consensus,
            verification=verification,
            disagreement=disagreement if disagreement.has_disagreement else None,
        )
        
        logger.info(
            "Strict consensus calculated",
            reached=consensus.reached,
            outcome=consensus.outcome.value,
            confidence=consensus.confidence,
            verification_passed=verification.passed,
            has_disagreement=disagreement.has_disagreement,
        )
        
        return consensus, provable_data
    
    def _verify_sources(self, results: list[AgentResult]) -> VerificationResult:
        """
        Verify source requirements.
        
        Task 2.5.5-2.5.6: Implement source verification.
        """
        issues: list[str] = []
        warnings: list[str] = []
        
        # Collect all sources
        all_sources: list[ResearchSource] = []
        seen_urls: set[str] = set()
        
        for result in results:
            for source in result.sources:
                all_sources.append(source)
                seen_urls.add(source.url)
        
        unique_count = len(seen_urls)
        
        # Count by tier (based on category)
        tier1_categories = {SourceCategory.OFFICIAL}
        tier2_categories = {SourceCategory.NEWS}
        
        tier1_count = sum(
            1 for s in all_sources
            if s.category in tier1_categories or s.credibility_score >= 0.9
        )
        tier2_count = sum(
            1 for s in all_sources
            if s.category in tier2_categories or 0.7 <= s.credibility_score < 0.9
        )
        
        # Get unique categories
        categories = list(set(s.category.value for s in all_sources))
        
        # Check requirements
        passed = True
        
        if tier1_count < self.strict_config.min_tier1_sources:
            issues.append(
                f"Insufficient Tier 1 sources: {tier1_count}/{self.strict_config.min_tier1_sources}"
            )
            passed = False
        
        if tier2_count < self.strict_config.min_tier2_sources:
            issues.append(
                f"Insufficient Tier 2 sources: {tier2_count}/{self.strict_config.min_tier2_sources}"
            )
            passed = False
        
        if self.strict_config.require_source_diversity:
            if len(categories) < self.strict_config.min_source_categories:
                warnings.append(
                    f"Limited source diversity: {len(categories)}/{self.strict_config.min_source_categories} categories"
                )
        
        # Cross-verification check (simplified)
        # Count sources cited by multiple agents
        url_citation_count: dict[str, int] = {}
        for result in results:
            for source in result.sources:
                url_citation_count[source.url] = url_citation_count.get(source.url, 0) + 1
        
        cross_verified = sum(1 for count in url_citation_count.values() if count >= 2)
        
        if self.strict_config.require_cross_verification:
            if cross_verified < self.strict_config.min_cross_verified_facts:
                warnings.append(
                    f"Limited cross-verification: {cross_verified}/{self.strict_config.min_cross_verified_facts} facts"
                )
        
        return VerificationResult(
            passed=passed,
            tier1_sources=tier1_count,
            tier2_sources=tier2_count,
            total_sources=len(all_sources),
            unique_sources=unique_count,
            source_categories=categories,
            cross_verified_facts=cross_verified,
            issues=issues,
            warnings=warnings,
        )
    
    def _analyze_disagreement_detailed(
        self,
        results: list[AgentResult],
    ) -> DisagreementAnalysis:
        """
        Perform detailed disagreement analysis.
        
        Task 2.5.10-2.5.11: Implement analyze_disagreement_detailed().
        """
        # Basic analysis from parent
        basic_analysis = self.analyze_disagreement(results)
        
        # Count outcomes
        outcome_dist: dict[str, int] = {}
        for result in results:
            key = result.outcome.value
            outcome_dist[key] = outcome_dist.get(key, 0) + 1
        
        # Check for disagreement
        has_disagreement = len(outcome_dist) > 1
        
        # Confidence statistics
        confidences = [r.confidence for r in results if r.is_valid]
        conf_stats = {
            "min": min(confidences) if confidences else 0.0,
            "max": max(confidences) if confidences else 0.0,
            "mean": sum(confidences) / len(confidences) if confidences else 0.0,
            "spread": (max(confidences) - min(confidences)) if confidences else 0.0,
        }
        
        # Source overlap by outcome
        source_overlap_by_outcome: dict[str, float] = {}
        for outcome_value in outcome_dist.keys():
            outcome = Outcome(outcome_value)
            outcome_results = [r for r in results if r.outcome == outcome]
            if len(outcome_results) >= 2:
                source_overlap_by_outcome[outcome_value] = self._calculate_source_overlap(
                    outcome_results
                )
        
        # Identify conflicting evidence
        conflicting_evidence: list[dict] = []
        if has_disagreement:
            # Find sources supporting different outcomes
            sources_by_outcome: dict[str, list[str]] = {}
            for result in results:
                key = result.outcome.value
                if key not in sources_by_outcome:
                    sources_by_outcome[key] = []
                sources_by_outcome[key].extend([s.url for s in result.sources])
            
            # Find overlapping sources between different outcomes
            outcomes = list(sources_by_outcome.keys())
            for i in range(len(outcomes)):
                for j in range(i + 1, len(outcomes)):
                    set_a = set(sources_by_outcome[outcomes[i]])
                    set_b = set(sources_by_outcome[outcomes[j]])
                    overlap = set_a & set_b
                    if overlap:
                        conflicting_evidence.append({
                            "outcomes": [outcomes[i], outcomes[j]],
                            "shared_sources": list(overlap)[:5],  # Limit
                            "interpretation_conflict": True,
                        })
        
        # Contributing factors
        factors: list[str] = []
        if conf_stats["spread"] > self.strict_config.max_confidence_spread:
            factors.append("High confidence spread among agents")
        if len(conflicting_evidence) > 0:
            factors.append("Same sources interpreted differently")
        if len(outcome_dist) >= 3:
            factors.append("Three-way split in outcomes")
        
        # Recommendations
        recommendations: list[str] = []
        if conf_stats["spread"] > self.strict_config.max_confidence_spread:
            recommendations.append("Consider human review due to confidence variance")
        if len(outcome_dist) > 2:
            recommendations.append("Resolution criteria may need clarification")
        if not has_disagreement and conf_stats["mean"] < 0.7:
            recommendations.append("Low overall confidence - verify with additional sources")
        
        # Determine if manual review required
        requires_review = (
            conf_stats["spread"] > self.strict_config.max_confidence_spread
            or len(conflicting_evidence) > 2
        )
        
        review_reason = None
        if requires_review:
            if conf_stats["spread"] > self.strict_config.max_confidence_spread:
                review_reason = "High confidence variance"
            elif len(conflicting_evidence) > 2:
                review_reason = "Significant evidence conflicts"
        
        return DisagreementAnalysis(
            has_disagreement=has_disagreement,
            outcome_distribution=outcome_dist,
            confidence_stats=conf_stats,
            source_overlap_by_outcome=source_overlap_by_outcome,
            conflicting_evidence=conflicting_evidence,
            contributing_factors=factors,
            resolution_recommendations=recommendations,
            requires_manual_review=requires_review,
            review_reason=review_reason,
        )
    
    def _generate_provable_data(
        self,
        results: list[AgentResult],
        consensus: ConsensusResult,
        verification: VerificationResult,
        disagreement: Optional[DisagreementAnalysis] = None,
    ) -> ProvableConsensusData:
        """
        Generate provable consensus data for on-chain submission.
        
        Task 2.5.12-2.5.13: Implement generate_provable_data().
        """
        # Tier distribution
        tier_dist: dict[str, int] = {}
        for result in results:
            for source in result.sources:
                if source.credibility_score >= 0.9:
                    tier = "tier_1"
                elif source.credibility_score >= 0.7:
                    tier = "tier_2"
                elif source.credibility_score >= 0.5:
                    tier = "tier_3"
                else:
                    tier = "tier_4_5"
                tier_dist[tier] = tier_dist.get(tier, 0) + 1
        
        return ProvableConsensusData(
            consensus_reached=consensus.reached,
            outcome=consensus.outcome.value,
            confidence=consensus.confidence,
            agent_count=consensus.agent_count,
            agreement_ratio=consensus.agreement_ratio,
            weighted_ratio=consensus.weighted_ratio,
            verification=verification,
            disagreement=disagreement,
            total_sources=consensus.total_sources,
            unique_sources=consensus.unique_sources,
            tier_distribution=tier_dist,
        )
    
    def get_consensus_summary(
        self,
        consensus: ConsensusResult,
        provable_data: ProvableConsensusData,
    ) -> str:
        """Generate human-readable consensus summary."""
        lines = [
            "# Consensus Summary",
            "",
            f"**Consensus Reached:** {'Yes' if consensus.reached else 'No'}",
            f"**Outcome:** {consensus.outcome.value}",
            f"**Confidence:** {consensus.confidence:.1%}",
            f"**Agent Agreement:** {consensus.agreement_ratio:.1%}",
            f"**Weighted Agreement:** {consensus.weighted_ratio:.1%}",
            "",
            "## Source Verification",
            f"- Tier 1 Sources: {provable_data.verification.tier1_sources}",
            f"- Tier 2 Sources: {provable_data.verification.tier2_sources}",
            f"- Total Unique Sources: {provable_data.verification.unique_sources}",
            f"- Verification Passed: {'Yes' if provable_data.verification.passed else 'No'}",
        ]
        
        if provable_data.verification.issues:
            lines.append("")
            lines.append("### Issues")
            for issue in provable_data.verification.issues:
                lines.append(f"- ⚠️ {issue}")
        
        if provable_data.verification.warnings:
            lines.append("")
            lines.append("### Warnings")
            for warning in provable_data.verification.warnings:
                lines.append(f"- ℹ️ {warning}")
        
        if provable_data.disagreement and provable_data.disagreement.has_disagreement:
            da = provable_data.disagreement
            lines.extend([
                "",
                "## Disagreement Analysis",
                f"- Outcome Distribution: {da.outcome_distribution}",
                f"- Requires Manual Review: {'Yes' if da.requires_manual_review else 'No'}",
            ])
            
            if da.contributing_factors:
                lines.append("- Contributing Factors:")
                for factor in da.contributing_factors:
                    lines.append(f"  - {factor}")
        
        lines.extend([
            "",
            "---",
            f"*Data Hash: {provable_data.data_hash}*",
        ])
        
        return "\n".join(lines)

