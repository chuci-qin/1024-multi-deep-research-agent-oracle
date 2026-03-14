"""
Multi-Outcome Consensus Engine

Calculates consensus from multiple agent results for multi-outcome
prediction markets (N outcomes + UNDETERMINED bin).

4/5 votes for same outcome → consensus.
No majority → UNDETERMINED + manual review flag.
"""

import os

import structlog
from pydantic import BaseModel, Field

from oracle.models import (
    MultiOutcome,
    MultiOutcomeAgentResult,
    MultiOutcomeConsensusResult,
    ResearchSource,
)

logger = structlog.get_logger()


def _default_min_agents() -> int:
    return int(os.getenv("MIN_VALID_AGENTS", os.getenv("MIN_AGENTS", "2")))


class MultiOutcomeConsensusConfig(BaseModel):
    """Configuration for multi-outcome consensus calculation."""

    min_agents: int = Field(
        default_factory=_default_min_agents, description="Minimum valid agents required for voting"
    )
    threshold: float = Field(default=0.80, ge=0.5, le=1.0, description="Default 4/5 = 0.80 for multi-outcome")
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    use_weighted_voting: bool = Field(default=True)
    min_sources_per_agent: int = Field(default=50)


class MultiOutcomeConsensusEngine:
    """
    Consensus engine for multi-outcome prediction markets.

    Uses N+1 bins: one per outcome label + UNDETERMINED.
    Requires threshold majority (default 4/5 = 80%) for consensus.
    """

    def __init__(self, config: MultiOutcomeConsensusConfig | None = None):
        self.config = config or MultiOutcomeConsensusConfig()
        logger.info(
            "Initialized multi-outcome consensus engine",
            threshold=self.config.threshold,
            min_agents=self.config.min_agents,
        )

    def calculate(
        self,
        results: list[MultiOutcomeAgentResult],
        outcome_labels: list[str],
    ) -> MultiOutcomeConsensusResult:
        """
        Calculate consensus from multi-outcome agent results.

        Creates N+1 vote bins (one per outcome + UNDETERMINED).
        """
        undetermined = MultiOutcome(outcome_index=-1, outcome_label="UNDETERMINED")

        if len(results) < self.config.min_agents:
            return MultiOutcomeConsensusResult(
                reached=False,
                winning_outcome=undetermined,
                reason=f"Need {self.config.min_agents}+ agents, got {len(results)}",
                agent_count=len(results),
                requires_human_review=True,
            )

        valid_results = [r for r in results if r.is_valid]

        if len(valid_results) < self.config.min_agents:
            return MultiOutcomeConsensusResult(
                reached=False,
                winning_outcome=undetermined,
                reason=f"Only {len(valid_results)} valid results, need {self.config.min_agents}",
                agent_count=len(results),
                requires_human_review=True,
            )

        # N+1 bins: each outcome label + "UNDETERMINED"
        bins: dict[str, list[MultiOutcomeAgentResult]] = {label: [] for label in outcome_labels}
        bins["UNDETERMINED"] = []
        weights: dict[str, float] = dict.fromkeys(outcome_labels, 0.0)
        weights["UNDETERMINED"] = 0.0

        for result in valid_results:
            label = result.outcome_label
            if label not in bins:
                # Unmapped label → UNDETERMINED
                label = "UNDETERMINED"
            bins[label].append(result)
            weights[label] += self._calculate_vote_weight(result)

        total_weight = sum(weights.values())
        total_votes = len(valid_results)

        # Vote distribution for response
        vote_distribution = {label: len(agents) for label, agents in bins.items() if agents}

        # Find winner
        winning_label = max(weights.keys(), key=lambda k: weights[k])
        winning_count = len(bins[winning_label])
        winning_ratio = winning_count / total_votes if total_votes > 0 else 0
        weighted_ratio = weights[winning_label] / total_weight if total_weight > 0 else 0

        logger.info(
            "Multi-outcome vote results",
            vote_distribution=vote_distribution,
            winning_label=winning_label,
            winning_ratio=f"{winning_ratio:.1%}",
        )

        effective_ratio = weighted_ratio if self.config.use_weighted_voting else winning_ratio

        if effective_ratio >= self.config.threshold and winning_label != "UNDETERMINED":
            winning_results = bins[winning_label]
            merged_sources = self._merge_sources(winning_results)
            avg_confidence = sum(r.confidence for r in winning_results) / len(winning_results)

            # Find the outcome index for the winning label
            try:
                winning_index = outcome_labels.index(winning_label)
            except ValueError:
                winning_index = -1

            return MultiOutcomeConsensusResult(
                reached=True,
                winning_outcome=MultiOutcome(
                    outcome_index=winning_index,
                    outcome_label=winning_label,
                ),
                confidence=avg_confidence,
                agreement_ratio=winning_ratio,
                weighted_ratio=weighted_ratio,
                vote_distribution=vote_distribution,
                total_sources=sum(len(r.sources) for r in winning_results),
                unique_sources=len(merged_sources),
                agent_count=len(valid_results),
                requires_human_review=False,
            )
        else:
            return MultiOutcomeConsensusResult(
                reached=False,
                winning_outcome=undetermined,
                confidence=0.0,
                agreement_ratio=winning_ratio,
                weighted_ratio=weighted_ratio,
                vote_distribution=vote_distribution,
                agent_count=len(valid_results),
                requires_human_review=True,
                reason=f"No supermajority: highest agreement is {winning_ratio:.1%} for '{winning_label}'",
            )

    def _calculate_vote_weight(self, result: MultiOutcomeAgentResult) -> float:
        confidence = result.confidence
        source_quality = self._calculate_source_quality(result.sources)
        source_count_factor = min(len(result.sources) / self.config.min_sources_per_agent, 1.0)
        return confidence * source_quality * source_count_factor

    def _calculate_source_quality(self, sources: list[ResearchSource]) -> float:
        if not sources:
            return 0.0
        avg_credibility = sum(s.credibility_score for s in sources) / len(sources)
        categories = {s.category for s in sources}
        diversity_bonus = min(len(categories) / 25, 0.2)
        return min(avg_credibility + diversity_bonus, 1.0)

    def _merge_sources(self, results: list[MultiOutcomeAgentResult]) -> list[ResearchSource]:
        seen_urls: set[str] = set()
        merged: list[ResearchSource] = []

        all_sources: list[tuple[ResearchSource, str]] = []
        for result in results:
            for source in result.sources:
                all_sources.append((source, result.agent_id))

        all_sources.sort(
            key=lambda x: x[0].relevance_score * x[0].credibility_score,
            reverse=True,
        )

        for source, agent_id in all_sources:
            if source.url not in seen_urls:
                new_source = source.model_copy()
                new_source.cited_by = [agent_id]
                merged.append(new_source)
                seen_urls.add(source.url)
            else:
                for existing in merged:
                    if existing.url == source.url:
                        if agent_id not in existing.cited_by:
                            existing.cited_by.append(agent_id)
                        break

        return merged
