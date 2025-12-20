"""
REST API Server for Multi-Agent Oracle.

Provides HTTP endpoints for requesting oracle resolutions.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

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


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: str


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
    
    async def initialize(self):
        """Initialize the oracle."""
        import os
        num_agents = int(os.getenv("MIN_AGENTS", "3"))
        
        self.oracle = MultiAgentOracle(
            config=OracleConfig(
                num_agents=num_agents,
                enable_ipfs=True,
            )
        )
        logger.info("Oracle API initialized")
    
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


# Create global app instance for uvicorn
app = create_app()


def run_server(host: str = "0.0.0.0", port: int = 8090):
    """Run the API server."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
