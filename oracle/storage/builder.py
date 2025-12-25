"""
Oracle Research Data Builder

Builds complete research data structures from agent results,
consensus calculations, and research process recordings.

Task ID: 2.8.1 - 2.8.8 from IMPLEMENTATION-TRACKER.md
"""

from datetime import datetime

import structlog

from oracle.consensus.strict_engine import ProvableConsensusData
from oracle.models import (
    AgentResult,
    ConsensusResult,
    ResearchSource,
)
from oracle.research.reasoning_chain import ReasoningChain
from oracle.research.thinking_recorder import ThinkingRecorder
from oracle.research.website_tracker import WebsiteTracker
from oracle.storage.canonical import (
    OracleConfigData,
    OracleResearchData,
    ResearchDataEntry,
)

logger = structlog.get_logger()


class OracleResearchDataBuilder:
    """
    Builder for constructing complete oracle research data.

    Task 2.8.1-2.8.8: Implement OracleResearchDataBuilder.

    This class collects all research data and builds the final
    data structure for IPFS storage.
    """

    def __init__(
        self,
        market_id: int,
        question: str,
        resolution_criteria: str,
        deadline: str | None = None,
    ):
        """
        Initialize the builder.

        Task 2.8.2: Constructor.

        Args:
            market_id: Prediction market ID
            question: Question to resolve
            resolution_criteria: Criteria for resolution
            deadline: Optional deadline
        """
        self.market_id = market_id
        self.question = question
        self.resolution_criteria = resolution_criteria
        self.deadline = deadline

        # Timing
        self.research_started_at: str | None = None
        self.research_completed_at: str | None = None

        # Agent results
        self._agent_results: list[AgentResult] = []
        self._thinking_recorders: dict[str, ThinkingRecorder] = {}
        self._website_trackers: dict[str, WebsiteTracker] = {}
        self._reasoning_chains: dict[str, ReasoningChain] = {}

        # Consensus
        self._consensus: ConsensusResult | None = None
        self._provable_data: ProvableConsensusData | None = None

        # Config
        self._oracle_config: OracleConfigData | None = None
        self._oracle_config_cid: str | None = None
        self._oracle_config_hash: str | None = None

        # Merged sources
        self._merged_sources: list[ResearchSource] = []

        logger.debug(
            "Created OracleResearchDataBuilder",
            market_id=market_id,
        )

    def start_research(self) -> "OracleResearchDataBuilder":
        """
        Mark research start time.

        Task 2.8.3: Implement start_research().
        """
        self.research_started_at = datetime.utcnow().isoformat()
        logger.info(
            "Research started",
            market_id=self.market_id,
            started_at=self.research_started_at,
        )
        return self

    def add_agent_result(
        self,
        result: AgentResult,
        thinking_recorder: ThinkingRecorder | None = None,
        website_tracker: WebsiteTracker | None = None,
        reasoning_chain: ReasoningChain | None = None,
    ) -> "OracleResearchDataBuilder":
        """
        Add an agent's research result.

        Task 2.8.4: Implement add_agent_result().

        Args:
            result: Agent research result
            thinking_recorder: Optional thinking process recorder
            website_tracker: Optional website visit tracker
            reasoning_chain: Optional reasoning chain
        """
        self._agent_results.append(result)

        agent_id = result.agent_id

        if thinking_recorder:
            self._thinking_recorders[agent_id] = thinking_recorder

        if website_tracker:
            self._website_trackers[agent_id] = website_tracker

        if reasoning_chain:
            self._reasoning_chains[agent_id] = reasoning_chain

        logger.debug(
            "Added agent result",
            agent_id=agent_id,
            outcome=result.outcome.value,
            sources=len(result.sources),
        )

        return self

    def set_consensus(
        self,
        consensus: ConsensusResult,
        provable_data: ProvableConsensusData | None = None,
    ) -> "OracleResearchDataBuilder":
        """
        Set the consensus result.

        Task 2.8.5: Implement set_consensus().

        Args:
            consensus: Consensus calculation result
            provable_data: Optional provable consensus data
        """
        self._consensus = consensus
        self._provable_data = provable_data

        logger.debug(
            "Set consensus",
            reached=consensus.reached,
            outcome=consensus.outcome.value,
            confidence=consensus.confidence,
        )

        return self

    def set_merged_sources(
        self,
        sources: list[ResearchSource],
    ) -> "OracleResearchDataBuilder":
        """
        Set the merged (deduplicated) sources.

        Task 2.8.6: Implement set_merged_sources().
        """
        self._merged_sources = sources
        logger.debug(f"Set {len(sources)} merged sources")
        return self

    def set_oracle_config(
        self,
        config: OracleConfigData,
        cid: str | None = None,
    ) -> "OracleResearchDataBuilder":
        """
        Set the oracle configuration.

        Args:
            config: Oracle configuration data
            cid: Optional IPFS CID if already stored
        """
        self._oracle_config = config
        self._oracle_config_cid = cid

        # Calculate hash
        _, hash_value = config.get_hash_data()
        self._oracle_config_hash = hash_value

        return self

    def complete_research(self) -> "OracleResearchDataBuilder":
        """
        Mark research as complete.

        Task 2.8.7: Implement complete_research().
        """
        self.research_completed_at = datetime.utcnow().isoformat()
        logger.info(
            "Research completed",
            market_id=self.market_id,
            completed_at=self.research_completed_at,
            agent_count=len(self._agent_results),
        )
        return self

    def build(self) -> OracleResearchData:
        """
        Build the final OracleResearchData structure.

        Task 2.8.8: Implement build() method.

        Returns:
            Complete OracleResearchData ready for IPFS storage
        """
        if not self.research_started_at:
            self.research_started_at = datetime.utcnow().isoformat()

        if not self.research_completed_at:
            self.research_completed_at = datetime.utcnow().isoformat()

        # Build agent result entries
        agent_entries: list[ResearchDataEntry] = []

        for result in self._agent_results:
            agent_id = result.agent_id

            # Get optional recorders
            thinking = self._thinking_recorders.get(agent_id)
            websites = self._website_trackers.get(agent_id)
            reasoning = self._reasoning_chains.get(agent_id)

            entry = ResearchDataEntry(
                agent_id=agent_id,
                model=result.model,
                strategy=result.strategy,
                outcome=result.outcome.value,
                confidence=result.confidence,
                reasoning=result.reasoning,
                sources=[s.model_dump() for s in result.sources],
                source_count=len(result.sources),
                thinking_process=([s.model_dump() for s in thinking.steps] if thinking else None),
                website_visits=([v.model_dump() for v in websites.visits] if websites else None),
                reasoning_chain=([s.model_dump() for s in reasoning.steps] if reasoning else None),
                research_duration_seconds=result.research_duration_seconds,
                timestamp=result.timestamp,
            )
            agent_entries.append(entry)

        # Build consensus dict
        consensus_dict = (
            self._consensus.model_dump()
            if self._consensus
            else {"reached": False, "outcome": "UNDETERMINED"}
        )

        # Build merged sources list
        merged_sources_list = [s.model_dump() for s in self._merged_sources]

        # Build provable data dict
        provable_dict = self._provable_data.model_dump() if self._provable_data else None

        # Calculate stats
        total_sources = sum(len(r.sources) for r in self._agent_results)
        unique_urls = set()
        for r in self._agent_results:
            for s in r.sources:
                unique_urls.add(s.url)

        # Build final structure
        research_data = OracleResearchData(
            oracle_config_cid=self._oracle_config_cid,
            oracle_config_hash=self._oracle_config_hash,
            market_id=self.market_id,
            question=self.question,
            resolution_criteria=self.resolution_criteria,
            research_started_at=self.research_started_at,
            research_completed_at=self.research_completed_at,
            agent_results=agent_entries,
            consensus=consensus_dict,
            merged_sources=merged_sources_list,
            provable_data=provable_dict,
            total_agents=len(self._agent_results),
            valid_agents=sum(1 for r in self._agent_results if r.is_valid),
            total_sources=total_sources,
            unique_sources=len(unique_urls),
        )

        logger.info(
            "Built OracleResearchData",
            market_id=self.market_id,
            agents=research_data.total_agents,
            sources=research_data.unique_sources,
            hash=research_data.calculate_hash()[:16] + "...",
        )

        return research_data

    def build_config(
        self,
        agent_count: int,
        agent_strategies: list[str],
        consensus_threshold: float = 0.67,
        min_sources_per_agent: int = 50,
        min_source_categories: int = 5,
    ) -> OracleConfigData:
        """
        Build oracle configuration data.

        Args:
            agent_count: Number of agents
            agent_strategies: List of strategy names
            consensus_threshold: Consensus threshold
            min_sources_per_agent: Min sources per agent
            min_source_categories: Min source categories

        Returns:
            OracleConfigData
        """
        config = OracleConfigData(
            market_id=self.market_id,
            question=self.question,
            resolution_criteria=self.resolution_criteria,
            deadline=self.deadline,
            agent_count=agent_count,
            agent_strategies=agent_strategies,
            consensus_threshold=consensus_threshold,
            min_sources_per_agent=min_sources_per_agent,
            min_source_categories=min_source_categories,
        )

        self._oracle_config = config
        _, self._oracle_config_hash = config.get_hash_data()

        return config

    @property
    def agent_count(self) -> int:
        """Get current agent count."""
        return len(self._agent_results)

    @property
    def has_consensus(self) -> bool:
        """Check if consensus has been set."""
        return self._consensus is not None

    @property
    def is_complete(self) -> bool:
        """Check if research is complete."""
        return (
            self.research_completed_at is not None
            and len(self._agent_results) > 0
            and self._consensus is not None
        )
