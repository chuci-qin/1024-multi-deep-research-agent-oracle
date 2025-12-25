"""
REST API Server for Multi-Agent Oracle.

Provides HTTP endpoints for requesting oracle resolutions.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

# Load environment variables early
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import structlog
import uvicorn

from oracle.core import MultiAgentOracle, OracleConfig
from oracle.models import OracleResult, Outcome

logger = structlog.get_logger()


# ============================================================================
# Request/Response Models
# ============================================================================

class ResolutionRequest(BaseModel):
    """Request to resolve a prediction market question."""
    market_id: int = Field(..., description="Prediction market ID")
    question: str = Field(..., description="Question to resolve")
    resolution_criteria: str = Field(..., description="Criteria for resolution")
    deadline: Optional[str] = Field(None, description="Resolution deadline")
    callback_url: Optional[str] = Field(None, description="Webhook callback URL")


class EnhancedResolutionRequest(BaseModel):
    """
    Enhanced request with oracle config reference.
    
    Task 2.9.1-2.9.2 from IMPLEMENTATION-TRACKER.md
    """
    market_id: int = Field(..., description="Prediction market ID")
    question: str = Field(..., description="Question to resolve")
    resolution_criteria: str = Field(..., description="Criteria for resolution")
    deadline: Optional[str] = Field(None, description="Resolution deadline")
    callback_url: Optional[str] = Field(None, description="Webhook callback URL")
    
    # Enhanced fields for verifiability
    oracle_config_cid: Optional[str] = Field(
        None,
        description="IPFS CID of pre-stored oracle configuration"
    )
    oracle_config_hash: Optional[str] = Field(
        None,
        description="SHA256 hash of oracle configuration for verification"
    )
    
    # Agent configuration (optional, defaults to standard)
    agent_count: Optional[int] = Field(
        None,
        description="Number of agents (default: 5)"
    )
    consensus_threshold: Optional[float] = Field(
        None,
        ge=0.5,
        le=1.0,
        description="Consensus threshold (default: 0.67)"
    )


class ResolutionResponse(BaseModel):
    """Response for resolution request."""
    request_id: str
    status: str  # processing, completed, failed
    estimated_time_seconds: int = 120


class ResultResponse(BaseModel):
    """Oracle result response."""
    request_id: str
    market_id: int
    status: str
    outcome: Optional[str] = None
    confidence: Optional[float] = None
    agreement_ratio: Optional[float] = None
    source_count: Optional[int] = None
    ipfs_cid: Optional[str] = None
    consensus_reached: Optional[bool] = None
    error: Optional[str] = None


class EnhancedResultResponse(BaseModel):
    """
    Enhanced result response with full verification data.
    
    Task 2.9.3-2.9.6 from IMPLEMENTATION-TRACKER.md
    """
    request_id: str
    market_id: int
    status: str  # processing, completed, failed
    
    # Core result
    outcome: Optional[str] = None
    confidence: Optional[float] = None
    agreement_ratio: Optional[float] = None
    weighted_ratio: Optional[float] = None
    
    # Consensus status
    consensus_reached: Optional[bool] = None
    agent_count: Optional[int] = None
    valid_agent_count: Optional[int] = None
    
    # Source statistics
    total_sources: Optional[int] = None
    unique_sources: Optional[int] = None
    tier1_sources: Optional[int] = None
    tier2_sources: Optional[int] = None
    
    # IPFS references with hashes (for on-chain verification)
    oracle_config_cid: Optional[str] = None
    oracle_config_hash: Optional[str] = None
    research_data_cid: Optional[str] = None
    research_data_hash: Optional[str] = None
    
    # Verification status
    verification_passed: Optional[bool] = None
    verification_issues: Optional[list[str]] = None
    
    # Manual review flags
    requires_manual_review: Optional[bool] = None
    review_reason: Optional[str] = None
    
    # Disagreement analysis (if applicable)
    disagreement_analysis: Optional[dict] = None
    
    # Error info
    error: Optional[str] = None
    
    # Timestamps
    research_started_at: Optional[str] = None
    research_completed_at: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: str
    agents_configured: Optional[int] = None
    ipfs_enabled: Optional[bool] = None


# ============================================================================
# In-Memory Result Store (for demo - use Redis/DB in production)
# ============================================================================

class ResultStore:
    """Simple in-memory result store."""
    
    def __init__(self):
        self._results: dict[str, OracleResult] = {}
        self._status: dict[str, str] = {}
    
    def set_processing(self, request_id: str):
        self._status[request_id] = "processing"
    
    def set_completed(self, request_id: str, result: OracleResult):
        self._results[request_id] = result
        self._status[request_id] = "completed"
    
    def set_failed(self, request_id: str, error: str):
        self._status[request_id] = f"failed: {error}"
    
    def get(self, request_id: str) -> tuple[str, Optional[OracleResult]]:
        status = self._status.get(request_id, "not_found")
        result = self._results.get(request_id)
        return status, result


# ============================================================================
# API Application
# ============================================================================

class OracleAPI:
    """Oracle API application."""
    
    def __init__(self):
        self.oracle: Optional[MultiAgentOracle] = None
        self.result_store = ResultStore()
        # Enhanced storage for v2
        self.enhanced_requests: dict[str, EnhancedResolutionRequest] = {}
        self.enhanced_results: dict[str, EnhancedResultResponse] = {}
    
    async def initialize(self):
        """Initialize the oracle."""
        import os
        num_agents = int(os.getenv("MIN_AGENTS", "5"))
        
        self.oracle = MultiAgentOracle(
            config=OracleConfig(
                num_agents=num_agents,
                enable_ipfs=True,
            )
        )
        logger.info("Oracle API initialized", num_agents=num_agents)
    
    async def shutdown(self):
        """Shutdown the oracle."""
        if self.oracle:
            await self.oracle.close()
        logger.info("Oracle API shutdown")


# Global API instance
api_instance = OracleAPI()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    await api_instance.initialize()
    yield
    await api_instance.shutdown()


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    
    app = FastAPI(
        title="1024 Multi-Agent Deep Research Oracle",
        description="AI-powered decentralized oracle for prediction markets",
        version="0.1.0",
        lifespan=lifespan,
    )
    
    # CORS
    cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # ========================================================================
    # Endpoints
    # ========================================================================
    
    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint."""
        return HealthResponse(
            status="healthy",
            version="0.1.0",
            timestamp=datetime.utcnow().isoformat(),
        )
    
    @app.post("/api/v1/resolve", response_model=ResolutionResponse)
    async def request_resolution(
        request: ResolutionRequest,
        background_tasks: BackgroundTasks,
    ):
        """
        Request oracle resolution for a prediction market.
        
        The resolution runs asynchronously. Poll /api/v1/result/{request_id}
        for the result, or provide a callback_url for webhook notification.
        """
        if not api_instance.oracle:
            raise HTTPException(status_code=503, detail="Oracle not initialized")
        
        # Generate request ID
        import uuid
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        
        # Mark as processing
        api_instance.result_store.set_processing(request_id)
        
        # Run resolution in background
        background_tasks.add_task(
            _run_resolution,
            request_id,
            request,
        )
        
        return ResolutionResponse(
            request_id=request_id,
            status="processing",
            estimated_time_seconds=120,
        )
    
    @app.get("/api/v1/result/{request_id}", response_model=ResultResponse)
    async def get_result(request_id: str):
        """Get the result of a resolution request."""
        status, result = api_instance.result_store.get(request_id)
        
        if status == "not_found":
            raise HTTPException(status_code=404, detail="Request not found")
        
        if status == "processing":
            return ResultResponse(
                request_id=request_id,
                market_id=0,
                status="processing",
            )
        
        if status.startswith("failed"):
            return ResultResponse(
                request_id=request_id,
                market_id=0,
                status="failed",
                error=status.replace("failed: ", ""),
            )
        
        if result:
            return ResultResponse(
                request_id=request_id,
                market_id=result.market_id,
                status="completed",
                outcome=result.consensus.outcome.value,
                confidence=result.consensus.confidence,
                agreement_ratio=result.consensus.agreement_ratio,
                source_count=len(result.merged_sources),
                ipfs_cid=result.ipfs_cid,
                consensus_reached=result.consensus.reached,
            )
        
        raise HTTPException(status_code=500, detail="Unknown error")
    
    @app.post("/api/v1/resolve/sync", response_model=ResultResponse)
    async def resolve_sync(request: ResolutionRequest):
        """
        Synchronously resolve a prediction market question.
        
        This endpoint blocks until resolution is complete.
        Use /api/v1/resolve for async operation.
        """
        if not api_instance.oracle:
            raise HTTPException(status_code=503, detail="Oracle not initialized")
        
        try:
            result = await api_instance.oracle.resolve(
                question=request.question,
                resolution_criteria=request.resolution_criteria,
                market_id=request.market_id,
                deadline=request.deadline,
            )
            
            return ResultResponse(
                request_id=result.request_id,
                market_id=result.market_id,
                status="completed",
                outcome=result.consensus.outcome.value,
                confidence=result.consensus.confidence,
                agreement_ratio=result.consensus.agreement_ratio,
                source_count=len(result.merged_sources),
                ipfs_cid=result.ipfs_cid,
                consensus_reached=result.consensus.reached,
            )
        except Exception as e:
            logger.error(f"Resolution failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # ========================================================================
    # Enhanced V2 Endpoints (Task 2.9)
    # ========================================================================
    
    @app.post("/api/v2/resolve", response_model=ResolutionResponse)
    async def request_resolution_v2(
        request: EnhancedResolutionRequest,
        background_tasks: BackgroundTasks,
    ):
        """
        Enhanced resolution request with oracle config verification.
        
        Task 2.9.1-2.9.2: Support oracle_config_cid and oracle_config_hash.
        
        The resolution runs asynchronously with enhanced verification.
        Poll /api/v2/result/{request_id} for the enhanced result.
        """
        if not api_instance.oracle:
            raise HTTPException(status_code=503, detail="Oracle not initialized")
        
        # Generate request ID
        import uuid
        request_id = f"req_v2_{uuid.uuid4().hex[:12]}"
        
        # Mark as processing
        api_instance.result_store.set_processing(request_id)
        
        # Store enhanced request info
        api_instance.enhanced_requests[request_id] = request
        
        # Run resolution in background
        background_tasks.add_task(
            _run_enhanced_resolution,
            request_id,
            request,
        )
        
        return ResolutionResponse(
            request_id=request_id,
            status="processing",
            estimated_time_seconds=180,  # Enhanced takes longer
        )
    
    @app.get("/api/v2/result/{request_id}", response_model=EnhancedResultResponse)
    async def get_enhanced_result(request_id: str):
        """
        Get enhanced result with full verification data.
        
        Task 2.9.3-2.9.6: Return comprehensive result data.
        """
        status, result = api_instance.result_store.get(request_id)
        enhanced_result = api_instance.enhanced_results.get(request_id)
        
        if status == "not_found":
            raise HTTPException(status_code=404, detail="Request not found")
        
        if status == "processing":
            return EnhancedResultResponse(
                request_id=request_id,
                market_id=0,
                status="processing",
            )
        
        if status.startswith("failed"):
            return EnhancedResultResponse(
                request_id=request_id,
                market_id=0,
                status="failed",
                error=status.replace("failed: ", ""),
            )
        
        if enhanced_result:
            return enhanced_result
        
        # Fallback to basic result
        if result:
            return EnhancedResultResponse(
                request_id=request_id,
                market_id=result.market_id,
                status="completed",
                outcome=result.consensus.outcome.value,
                confidence=result.consensus.confidence,
                agreement_ratio=result.consensus.agreement_ratio,
                total_sources=len(result.merged_sources),
                research_data_cid=result.ipfs_cid,
                consensus_reached=result.consensus.reached,
            )
        
        raise HTTPException(status_code=500, detail="Unknown error")
    
    @app.post("/api/v2/resolve/sync", response_model=EnhancedResultResponse)
    async def resolve_sync_v2(request: EnhancedResolutionRequest):
        """
        Synchronous enhanced resolution with full verification.
        
        This endpoint blocks until resolution is complete and returns
        comprehensive verification data including hashes for on-chain submission.
        """
        if not api_instance.oracle:
            raise HTTPException(status_code=503, detail="Oracle not initialized")
        
        try:
            import uuid
            request_id = f"req_v2_{uuid.uuid4().hex[:12]}"
            
            # Run enhanced resolution
            enhanced_result = await _execute_enhanced_resolution(
                request_id,
                request,
            )
            
            return enhanced_result
            
        except Exception as e:
            logger.error(f"Enhanced resolution failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v2/strategies")
    async def list_strategies():
        """
        List available agent strategies.
        
        Returns all configured research strategies that can be used
        for agent differentiation.
        """
        from oracle.agents.strategies import StrategyFactory
        return {
            "strategies": StrategyFactory.list_all_profiles(),
            "recommended_5_agents": [
                p.value for p in StrategyFactory.get_recommended_profiles(5)
            ],
        }
    
    return app


async def _run_resolution(request_id: str, request: ResolutionRequest):
    """Background task to run resolution."""
    try:
        if not api_instance.oracle:
            api_instance.result_store.set_failed(request_id, "Oracle not initialized")
            return
        
        result = await api_instance.oracle.resolve(
            question=request.question,
            resolution_criteria=request.resolution_criteria,
            market_id=request.market_id,
            deadline=request.deadline,
        )
        
        api_instance.result_store.set_completed(request_id, result)
        
        # Send webhook if configured
        if request.callback_url:
            await _send_webhook(request.callback_url, result)
        
    except Exception as e:
        logger.error(f"Resolution failed: {e}")
        api_instance.result_store.set_failed(request_id, str(e))


async def _send_webhook(url: str, result: OracleResult):
    """Send webhook notification."""
    import httpx
    
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                url,
                json={
                    "request_id": result.request_id,
                    "market_id": result.market_id,
                    "outcome": result.consensus.outcome.value,
                    "confidence": result.consensus.confidence,
                    "source_count": len(result.merged_sources),
                    "ipfs_cid": result.ipfs_cid,
                    "consensus_reached": result.consensus.reached,
                },
                timeout=10,
            )
        logger.info(f"Webhook sent to {url}")
    except Exception as e:
        logger.error(f"Webhook failed: {e}")


async def _run_enhanced_resolution(
    request_id: str,
    request: EnhancedResolutionRequest,
):
    """Background task for enhanced resolution."""
    try:
        enhanced_result = await _execute_enhanced_resolution(request_id, request)
        api_instance.enhanced_results[request_id] = enhanced_result
        
        # Also update basic result store
        if enhanced_result.status == "completed":
            api_instance.result_store._status[request_id] = "completed"
        else:
            api_instance.result_store._status[request_id] = f"failed: {enhanced_result.error}"
        
        # Send webhook if configured
        if request.callback_url and enhanced_result.status == "completed":
            await _send_enhanced_webhook(request.callback_url, enhanced_result)
        
    except Exception as e:
        logger.error(f"Enhanced resolution failed: {e}")
        api_instance.result_store.set_failed(request_id, str(e))
        api_instance.enhanced_results[request_id] = EnhancedResultResponse(
            request_id=request_id,
            market_id=request.market_id,
            status="failed",
            error=str(e),
        )


async def _execute_enhanced_resolution(
    request_id: str,
    request: EnhancedResolutionRequest,
) -> EnhancedResultResponse:
    """Execute enhanced resolution with full verification data."""
    from oracle.storage import (
        OracleResearchDataBuilder,
        OracleConfigData,
        to_canonical_json,
        calculate_sha256,
    )
    from oracle.consensus import StrictConsensusEngine, StrictConsensusConfig
    from oracle.agents import StrategyFactory, StrategyProfile
    
    if not api_instance.oracle:
        return EnhancedResultResponse(
            request_id=request_id,
            market_id=request.market_id,
            status="failed",
            error="Oracle not initialized",
        )
    
    research_started_at = datetime.utcnow().isoformat()
    
    try:
        # Step 1: Run basic resolution
        result = await api_instance.oracle.resolve(
            question=request.question,
            resolution_criteria=request.resolution_criteria,
            market_id=request.market_id,
            deadline=request.deadline,
        )
        
        research_completed_at = datetime.utcnow().isoformat()
        
        # Step 2: Build enhanced data
        builder = OracleResearchDataBuilder(
            market_id=request.market_id,
            question=request.question,
            resolution_criteria=request.resolution_criteria,
            deadline=request.deadline,
        )
        builder.research_started_at = research_started_at
        builder.research_completed_at = research_completed_at
        
        # Add agent results
        for agent_result in result.agent_results:
            builder.add_agent_result(agent_result)
        
        # Set consensus
        builder.set_consensus(result.consensus)
        builder.set_merged_sources(result.merged_sources)
        
        # Build oracle config
        agent_count = request.agent_count or 5
        strategies = [p.value for p in StrategyFactory.get_recommended_profiles(agent_count)]
        
        oracle_config = builder.build_config(
            agent_count=agent_count,
            agent_strategies=strategies,
            consensus_threshold=request.consensus_threshold or 0.67,
        )
        
        # Calculate hashes
        _, config_hash = oracle_config.get_hash_data()
        
        # Build research data
        research_data = builder.build()
        _, research_hash = research_data.get_hash_data()
        
        # Step 3: Run strict consensus check
        strict_engine = StrictConsensusEngine(
            config=StrictConsensusConfig(
                threshold=request.consensus_threshold or 0.67,
            )
        )
        
        strict_consensus, provable_data = strict_engine.calculate_strict(
            result.agent_results
        )
        
        # Step 4: Build enhanced response
        return EnhancedResultResponse(
            request_id=request_id,
            market_id=request.market_id,
            status="completed",
            outcome=result.consensus.outcome.value,
            confidence=result.consensus.confidence,
            agreement_ratio=result.consensus.agreement_ratio,
            weighted_ratio=result.consensus.weighted_ratio,
            consensus_reached=result.consensus.reached,
            agent_count=len(result.agent_results),
            valid_agent_count=sum(1 for r in result.agent_results if r.is_valid),
            total_sources=sum(len(r.sources) for r in result.agent_results),
            unique_sources=len(result.merged_sources),
            tier1_sources=provable_data.verification.tier1_sources,
            tier2_sources=provable_data.verification.tier2_sources,
            oracle_config_cid=request.oracle_config_cid,
            oracle_config_hash=config_hash,
            research_data_cid=result.ipfs_cid,
            research_data_hash=research_hash,
            verification_passed=provable_data.verification.passed,
            verification_issues=provable_data.verification.issues,
            requires_manual_review=(
                strict_consensus.requires_human_review
                or (provable_data.disagreement and provable_data.disagreement.requires_manual_review)
            ),
            review_reason=(
                provable_data.disagreement.review_reason
                if provable_data.disagreement
                else None
            ),
            disagreement_analysis=(
                provable_data.disagreement.model_dump()
                if provable_data.disagreement and provable_data.disagreement.has_disagreement
                else None
            ),
            research_started_at=research_started_at,
            research_completed_at=research_completed_at,
        )
        
    except Exception as e:
        logger.error(f"Enhanced resolution execution failed: {e}")
        return EnhancedResultResponse(
            request_id=request_id,
            market_id=request.market_id,
            status="failed",
            error=str(e),
        )


async def _send_enhanced_webhook(url: str, result: EnhancedResultResponse):
    """Send enhanced webhook notification."""
    import httpx
    
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                url,
                json=result.model_dump(),
                timeout=10,
            )
        logger.info(f"Enhanced webhook sent to {url}")
    except Exception as e:
        logger.error(f"Enhanced webhook failed: {e}")


# Create global app instance for uvicorn
app = create_app()


def run_server(host: str = None, port: int = None):
    """Run the API server."""
    # Load from environment variables if not provided
    from dotenv import load_dotenv
    load_dotenv()
    
    if host is None:
        host = os.getenv("API_HOST", "0.0.0.0")
    if port is None:
        port = int(os.getenv("API_PORT", "8989"))
    
    logger.info("Starting Oracle API server", host=host, port=port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
