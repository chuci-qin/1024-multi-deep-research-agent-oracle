"""
Multi-Agent Oracle - Core Implementation

The main oracle class that orchestrates multiple agents,
calculates consensus, and stores results.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import structlog

from oracle.agents import BaseAgent, GeminiDeepResearchAgent, SearchStrategy
from oracle.consensus import ConsensusEngine, ConsensusConfig
from oracle.storage import IPFSStorage, IPFSConfig
from oracle.models import (
    AgentResult,
    OracleRequest,
    OracleResult,
    ConsensusResult,
    Outcome,
)

logger = structlog.get_logger()


class OracleConfig(BaseModel):
    """Configuration for the Multi-Agent Oracle."""
    
    # Agent settings
    num_agents: int = Field(default=3, ge=1, le=10)
    agent_timeout_seconds: int = Field(default=300)
    
    # Consensus settings
    consensus_threshold: float = Field(default=0.67, ge=0.5, le=1.0)
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Storage settings
    enable_ipfs: bool = Field(default=True)
    
    # Blockchain settings
    auto_submit: bool = Field(default=False)


class MultiAgentOracle:
    """
    Multi-Agent Deep Research Oracle.
    
    Orchestrates multiple AI agents to research prediction market
    questions, calculates consensus, and stores results on IPFS.
    
    Usage:
        oracle = MultiAgentOracle()
        result = await oracle.resolve(
            question="Did X happen?",
            resolution_criteria="...",
        )
    """
    
    def __init__(
        self,
        agents: Optional[list[BaseAgent]] = None,
        config: Optional[OracleConfig] = None,
        consensus_engine: Optional[ConsensusEngine] = None,
        ipfs_storage: Optional[IPFSStorage] = None,
    ):
        self.config = config or OracleConfig()
        
        # Initialize agents
        if agents:
            self.agents = agents
        else:
            self.agents = self._create_default_agents()
        
        # Initialize consensus engine
        self.consensus_engine = consensus_engine or ConsensusEngine(
            ConsensusConfig(
                threshold=self.config.consensus_threshold,
                min_agents=min(self.config.num_agents, 3),
            )
        )
        
        # Initialize IPFS storage
        if self.config.enable_ipfs:
            self.ipfs_storage = ipfs_storage or IPFSStorage()
        else:
            self.ipfs_storage = None
        
        logger.info(
            "Initialized Multi-Agent Oracle",
            num_agents=len(self.agents),
            consensus_threshold=self.config.consensus_threshold,
            ipfs_enabled=self.config.enable_ipfs,
        )
    
    def _create_default_agents(self) -> list[BaseAgent]:
        """Create default set of Gemini agents with different strategies."""
        import os
        
        strategies = [
            SearchStrategy.COMPREHENSIVE,
            SearchStrategy.FOCUSED,
            SearchStrategy.DIVERSE,
        ]
        
        # Get model from environment (default: gemini-1.5-flash for stability)
        model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        
        # Get number of agents from environment
        num_agents = int(os.getenv("MIN_AGENTS", str(self.config.num_agents)))
        
        agents = []
        for i, strategy in enumerate(strategies[:num_agents]):
            agent = GeminiDeepResearchAgent(
                agent_id=f"gemini-agent-{i+1}",
                strategy=strategy,
                model=model,
            )
            agents.append(agent)
        
        return agents
    
    async def resolve(
        self,
        question: str,
        resolution_criteria: str,
        market_id: Optional[int] = None,
        deadline: Optional[str] = None,
        callback_url: Optional[str] = None,
    ) -> OracleResult:
        """
        Resolve a prediction market question.
        
        Args:
            question: The question to resolve
            resolution_criteria: Criteria for determining the outcome
            market_id: Optional market ID for blockchain submission
            deadline: Optional deadline for the question
            callback_url: Optional webhook URL for async notification
            
        Returns:
            OracleResult with consensus, sources, and IPFS hash
        """
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        market_id = market_id or 0
        started_at = datetime.utcnow().isoformat()
        
        logger.info(
            "Starting resolution",
            request_id=request_id,
            question=question[:100],
            num_agents=len(self.agents),
        )
        
        # Create request
        request = OracleRequest(
            request_id=request_id,
            market_id=market_id,
            question=question,
            resolution_criteria=resolution_criteria,
            deadline=deadline,
            callback_url=callback_url,
        )
        
        # Run all agents in parallel
        agent_results = await self._run_agents(question, resolution_criteria, deadline)
        
        # Calculate consensus
        consensus = self.consensus_engine.calculate(agent_results)
        
        # Merge sources from agreeing agents
        if consensus.reached:
            agreeing_results = [
                r for r in agent_results 
                if r.outcome == consensus.outcome
            ]
            merged_sources = self.consensus_engine._merge_sources(agreeing_results)
        else:
            merged_sources = []
        
        # Store on IPFS
        ipfs_cid = None
        if self.ipfs_storage and (consensus.reached or len(agent_results) > 0):
            try:
                ipfs_cid = await self.ipfs_storage.store_research(
                    market_id=market_id,
                    question=question,
                    resolution_criteria=resolution_criteria,
                    agent_results=agent_results,
                    consensus=consensus,
                    merged_sources=merged_sources,
                )
            except Exception as e:
                logger.error(f"IPFS storage failed: {e}")
        
        # Build result
        result = OracleResult(
            request_id=request_id,
            market_id=market_id,
            question=question,
            resolution_criteria=resolution_criteria,
            consensus=consensus,
            agent_results=agent_results,
            merged_sources=merged_sources,
            ipfs_cid=ipfs_cid,
            research_started_at=started_at,
            research_completed_at=datetime.utcnow().isoformat(),
        )
        
        logger.info(
            "Resolution completed",
            request_id=request_id,
            outcome=consensus.outcome.value,
            consensus_reached=consensus.reached,
            confidence=f"{consensus.confidence:.1%}",
            source_count=len(merged_sources),
            ipfs_cid=ipfs_cid,
        )
        
        return result
    
    async def _run_agents(
        self,
        question: str,
        resolution_criteria: str,
        deadline: Optional[str] = None,
    ) -> list[AgentResult]:
        """Run all agents in parallel and collect results."""
        
        async def run_agent(agent: BaseAgent) -> AgentResult:
            try:
                return await asyncio.wait_for(
                    agent.research(question, resolution_criteria, deadline),
                    timeout=self.config.agent_timeout_seconds,
                )
            except asyncio.TimeoutError:
                logger.warning(f"Agent {agent.agent_id} timed out")
                return AgentResult(
                    agent_id=agent.agent_id,
                    model=agent.model_name,
                    outcome=Outcome.INVALID,
                    confidence=0.0,
                    reasoning="Research timed out",
                    sources=[],
                    error="Timeout",
                )
            except Exception as e:
                logger.error(f"Agent {agent.agent_id} failed: {e}")
                return AgentResult(
                    agent_id=agent.agent_id,
                    model=agent.model_name,
                    outcome=Outcome.INVALID,
                    confidence=0.0,
                    reasoning="Research failed",
                    sources=[],
                    error=str(e),
                )
        
        # Run all agents in parallel
        tasks = [run_agent(agent) for agent in self.agents]
        results = await asyncio.gather(*tasks)
        
        # Filter out completely failed results for logging
        successful = [r for r in results if r.error is None]
        failed = [r for r in results if r.error is not None]
        
        logger.info(
            "Agent research completed",
            total=len(results),
            successful=len(successful),
            failed=len(failed),
        )
        
        return list(results)
    
    async def get_result(self, request_id: str) -> Optional[OracleResult]:
        """
        Get result for a previous request.
        
        Note: In production, this would query a database.
        For now, returns None as results are returned synchronously.
        """
        # TODO: Implement result caching/storage
        return None
    
    async def close(self):
        """Clean up resources."""
        if self.ipfs_storage:
            await self.ipfs_storage.close()


# Convenience function for simple usage
async def resolve_question(
    question: str,
    resolution_criteria: str,
    num_agents: int = 3,
) -> OracleResult:
    """
    Simple function to resolve a question.
    
    Usage:
        result = await resolve_question(
            "Did Bitcoin reach $100k?",
            "BTC price >= $100,000 on major exchange",
        )
    """
    oracle = MultiAgentOracle(
        config=OracleConfig(num_agents=num_agents)
    )
    
    try:
        return await oracle.resolve(question, resolution_criteria)
    finally:
        await oracle.close()
