"""
REST API Server for Multi-Agent Oracle.

Provides HTTP endpoints for requesting oracle resolutions.

API Version: v1 (Enhanced with full verification support)
"""

import ipaddress
import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from urllib.parse import urlparse

# Load environment variables early
from dotenv import load_dotenv

load_dotenv()

import structlog
import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from oracle.core import MultiAgentOracle, OracleConfig

logger = structlog.get_logger()


# ============================================================================
# Request/Response Models (v1 - Full Featured)
# ============================================================================


class ResolutionRequest(BaseModel):
    """
    Request to resolve a prediction market question (binary: YES/NO).

    Supports full verification with oracle config and on-chain hashes.
    """

    market_id: int = Field(..., description="Prediction market ID")
    question: str = Field(..., max_length=2000, description="Question to resolve")
    resolution_criteria: str = Field(..., max_length=5000, description="Criteria for resolution")
    deadline: str | None = Field(None, description="Resolution deadline")
    callback_url: str | None = Field(None, description="Webhook callback URL")

    # Oracle config for verifiability
    oracle_config_cid: str | None = Field(
        None, description="IPFS CID of pre-stored oracle configuration"
    )
    oracle_config_hash: str | None = Field(
        None, description="SHA256 hash of oracle configuration for verification"
    )

    # Agent configuration (optional, defaults to standard)
    agent_count: int | None = Field(None, description="Number of agents (default: 5)")
    consensus_threshold: float | None = Field(
        None, ge=0.5, le=1.0, description="Consensus threshold (default: 0.66)"
    )


class MultiOutcomeResolutionRequest(BaseModel):
    """
    Request to resolve a multi-outcome prediction market question.

    Unlike binary resolution, this accepts a list of outcome labels
    and returns the winning outcome index.
    """

    market_id: int = Field(..., description="Prediction market ID")
    question: str = Field(..., max_length=2000, description="Question to resolve")
    resolution_criteria: str = Field(..., max_length=5000, description="Criteria for resolution")
    outcomes: list[str] = Field(..., min_length=2, max_length=50, description="List of possible outcome labels")
    num_outcomes: int = Field(..., ge=2, le=50, description="Number of outcomes")
    deadline: str | None = Field(None, description="Resolution deadline")
    callback_url: str | None = Field(None, description="Webhook callback URL")

    oracle_config_cid: str | None = Field(None, description="IPFS CID of oracle config")
    oracle_config_hash: str | None = Field(None, description="SHA256 hash of oracle config")

    agent_count: int | None = Field(None, description="Number of agents (default: 5)")
    consensus_threshold: float | None = Field(
        None, ge=0.5, le=1.0, description="Consensus threshold (default: 0.80 for multi-outcome)"
    )


class ResolutionResponse(BaseModel):
    """Response for resolution request."""

    request_id: str
    status: str  # processing, completed, failed
    estimated_time_seconds: int = 180


class ResultResponse(BaseModel):
    """
    Oracle result response with full verification data.

    Includes all data needed for on-chain verification.
    """

    request_id: str
    market_id: int
    status: str  # processing, completed, failed

    # Core result
    outcome: str | None = None
    confidence: float | None = None
    agreement_ratio: float | None = None
    weighted_ratio: float | None = None

    # Consensus status
    consensus_reached: bool | None = None
    agent_count: int | None = None
    valid_agent_count: int | None = None

    # Source statistics
    total_sources: int | None = None
    unique_sources: int | None = None
    tier1_sources: int | None = None
    tier2_sources: int | None = None

    # IPFS references with hashes (for on-chain verification)
    oracle_config_cid: str | None = None
    oracle_config_hash: str | None = None
    research_data_cid: str | None = None
    research_data_hash: str | None = None

    # Verification status
    verification_passed: bool | None = None
    verification_issues: list[str] | None = None

    # Manual review flags
    requires_manual_review: bool | None = None
    review_reason: str | None = None

    # Disagreement analysis (if applicable)
    disagreement_analysis: dict | None = None

    # Error info
    error: str | None = None

    # Timestamps
    research_started_at: str | None = None
    research_completed_at: str | None = None

    # IPFS storage indicator (false = real IPFS, true = local mock storage)
    ipfs_mock: bool = False


class MultiOutcomeResultResponse(BaseModel):
    """
    Oracle result response for multi-outcome markets.

    Returns the winning outcome index instead of YES/NO.
    """

    request_id: str
    market_id: int
    status: str

    # Multi-outcome result
    outcome_index: int | None = None
    outcome_label: str | None = None
    outcomes: list[str] | None = None
    vote_distribution: dict[str, int] | None = None

    # Shared fields
    confidence: float | None = None
    agreement_ratio: float | None = None
    weighted_ratio: float | None = None

    consensus_reached: bool | None = None
    agent_count: int | None = None
    valid_agent_count: int | None = None

    total_sources: int | None = None
    unique_sources: int | None = None
    tier1_sources: int | None = None
    tier2_sources: int | None = None

    oracle_config_cid: str | None = None
    oracle_config_hash: str | None = None
    research_data_cid: str | None = None
    research_data_hash: str | None = None

    verification_passed: bool | None = None
    verification_issues: list[str] | None = None

    requires_manual_review: bool | None = None
    review_reason: str | None = None

    disagreement_analysis: dict | None = None

    error: str | None = None

    research_started_at: str | None = None
    research_completed_at: str | None = None

    ipfs_mock: bool = False


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    timestamp: str
    agents_configured: int | None = None
    ipfs_enabled: bool | None = None


# ============================================================================
# Oracle Config Request/Response Models (Phase A - 2026-01-09)
# ============================================================================


class UploadConfigRequest(BaseModel):
    """Request to upload oracle configuration to IPFS."""

    market_id: int = Field(..., description="Prediction market ID")
    question: str = Field(..., description="Market question")
    resolution_criteria: str = Field(..., description="Resolution criteria text")
    resolution_deadline: str | None = Field(None, description="Deadline ISO8601")

    # LLM configuration
    llm_config: dict | None = Field(
        default=None, description="LLM configuration (model, agent_count, threshold)"
    )

    # Source requirements
    trusted_sources: list[str] = Field(
        default_factory=list, description="List of trusted sources for verification"
    )

    # Agent configuration
    agent_strategies: list[str] | None = Field(None, description="Agent strategy names")


class UploadConfigResponse(BaseModel):
    """Response for config upload request."""

    success: bool
    market_id: int
    config_cid: str = Field(default="", description="IPFS CID of uploaded config")
    config_hash: str = Field(default="", description="SHA256 hash of canonical JSON")
    gateway_url: str | None = Field(None, description="IPFS gateway URL")
    error: str | None = None


class GetConfigResponse(BaseModel):
    """Response for config retrieval."""

    success: bool
    cid: str
    config: dict | None = None
    verified: bool = False
    expected_hash: str | None = None
    actual_hash: str | None = None
    error: str | None = None


# ============================================================================
# In-Memory Result Store (for demo - use Redis/DB in production)
# ============================================================================


class ResultStore:
    """In-memory result store with TTL-based eviction."""

    MAX_ENTRIES = 1000
    TTL_SECONDS = 3600

    def __init__(self):
        self._results: dict[str, ResultResponse | MultiOutcomeResultResponse] = {}
        self._status: dict[str, str] = {}
        self._timestamps: dict[str, float] = {}

    def _evict_stale(self):
        import time
        now = time.time()
        stale_keys = [
            k for k, ts in self._timestamps.items()
            if now - ts > self.TTL_SECONDS
        ]
        for k in stale_keys:
            self._results.pop(k, None)
            self._status.pop(k, None)
            self._timestamps.pop(k, None)
        if len(self._timestamps) > self.MAX_ENTRIES:
            oldest = sorted(self._timestamps, key=self._timestamps.get)[:len(self._timestamps) - self.MAX_ENTRIES]
            for k in oldest:
                self._results.pop(k, None)
                self._status.pop(k, None)
                self._timestamps.pop(k, None)

    def set_processing(self, request_id: str):
        import time
        self._evict_stale()
        self._status[request_id] = "processing"
        self._timestamps[request_id] = time.time()

    def set_completed(self, request_id: str, result: ResultResponse):
        import time
        self._results[request_id] = result
        self._status[request_id] = "completed"
        self._timestamps[request_id] = time.time()

    def set_failed(self, request_id: str, error: str):
        import time
        self._status[request_id] = f"failed: {error}"
        self._timestamps[request_id] = time.time()

    def get(self, request_id: str) -> tuple[str, ResultResponse | MultiOutcomeResultResponse | None]:
        status = self._status.get(request_id, "not_found")
        result = self._results.get(request_id)
        return status, result


# ============================================================================
# API Application
# ============================================================================


class _BoundedRequestStore:
    """Dict-like store with TTL eviction and max size for request metadata."""

    MAX_ENTRIES = 1000
    TTL_SECONDS = 86400  # 24 hours

    def __init__(self):
        self._data: dict[str, ResolutionRequest] = {}
        self._timestamps: dict[str, float] = {}

    def _evict(self):
        import time
        now = time.time()
        stale = [k for k, ts in self._timestamps.items() if now - ts > self.TTL_SECONDS]
        for k in stale:
            self._data.pop(k, None)
            self._timestamps.pop(k, None)
        if len(self._data) > self.MAX_ENTRIES:
            oldest = sorted(self._timestamps, key=self._timestamps.get)[: len(self._data) - self.MAX_ENTRIES]
            for k in oldest:
                self._data.pop(k, None)
                self._timestamps.pop(k, None)

    def __setitem__(self, key: str, value: ResolutionRequest):
        import time
        self._evict()
        self._data[key] = value
        self._timestamps[key] = time.time()

    def __getitem__(self, key: str):
        return self._data[key]

    def get(self, key: str, default=None):
        return self._data.get(key, default)


class OracleAPI:
    """Oracle API application."""

    def __init__(self):
        self.oracle: MultiAgentOracle | None = None
        self.result_store = ResultStore()
        self.requests = _BoundedRequestStore()

    async def initialize(self):
        """Initialize the oracle."""
        num_agents = int(os.getenv("MIN_AGENTS", "3"))

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
        version="1.0.0",
        lifespan=lifespan,
    )

    # API Key authentication
    # Set ORACLE_API_KEY env var to enable. If not set, authentication is disabled.
    api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
    oracle_api_key = os.getenv("ORACLE_API_KEY")

    if not oracle_api_key:
        logger.warning(
            "⚠️  ORACLE_API_KEY not set — authentication is DISABLED. "
            "Set ORACLE_API_KEY env var before deploying to production."
        )

    async def verify_api_key(api_key: str | None = Security(api_key_header)):
        """Verify API key for protected endpoints."""
        if not oracle_api_key:
            return
        if api_key != oracle_api_key:
            raise HTTPException(status_code=403, detail="Invalid or missing API key")

    # CORS — allow all 1024 platform origins + Vercel preview deployments
    cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8082")
    cors_origins = [o.strip() for o in cors_origins_str.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_origin_regex=r"https://(.*\.)?(1024ex\.com|1024chain\.com|1024.*\.vercel\.app)",
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key", "Authorization"],
    )

    # ========================================================================
    # Health & Info Endpoints
    # ========================================================================

    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """
        Health check endpoint.

        Returns oracle status including:
        - agents_configured: Number of agents configured
        - ipfs_enabled: Whether IPFS storage is enabled
        """
        oracle = api_instance.oracle
        return HealthResponse(
            status="healthy" if oracle else "initializing",
            version="1.0.0",
            timestamp=datetime.now(UTC).isoformat(),
            agents_configured=oracle.config.num_agents if oracle else None,
            ipfs_enabled=oracle.config.enable_ipfs if oracle else None,
        )

    # ========================================================================
    # Oracle Config Endpoints (Phase A - 2026-01-09)
    # ========================================================================

    @app.post(
        "/api/v1/config/upload",
        response_model=UploadConfigResponse,
        dependencies=[Depends(verify_api_key)],
    )
    async def upload_oracle_config(request: UploadConfigRequest):
        """
        Upload oracle configuration to IPFS.

        This endpoint:
        1. Builds an OracleConfigData structure
        2. Converts to canonical JSON (RFC 8785)
        3. Calculates SHA256 hash
        4. Uploads to IPFS
        5. Returns CID and hash for on-chain storage
        """
        from oracle.agents.strategies import StrategyFactory
        from oracle.storage import IPFSStorage, OracleConfigData

        try:
            # Build agent strategies
            agent_count = 5
            if request.llm_config and "agent_count" in request.llm_config:
                agent_count = request.llm_config.get("agent_count", 5)

            strategies = request.agent_strategies
            if not strategies:
                strategies = [
                    p.value for p in StrategyFactory.get_recommended_profiles(agent_count)
                ]

            consensus_threshold = float(os.getenv("CONSENSUS_THRESHOLD", "0.66"))
            if request.llm_config and "consensus_threshold" in request.llm_config:
                consensus_threshold = request.llm_config.get(
                    "consensus_threshold", consensus_threshold
                )

            # Build config data
            config = OracleConfigData(
                version="1.0.0",
                market_id=request.market_id,
                question=request.question,
                resolution_criteria=request.resolution_criteria,
                deadline=request.resolution_deadline,
                created_at=datetime.now(UTC).isoformat(),
                agent_count=agent_count,
                agent_strategies=strategies,
                consensus_threshold=consensus_threshold,
                min_sources_per_agent=3,
                min_source_categories=2,
                require_tier1_sources=True,
                min_tier1_count=2,
                min_tier2_count=3,
                metadata={
                    "trusted_sources": request.trusted_sources,
                },
            )

            # Get canonical JSON and hash
            canonical_json, config_hash = config.get_hash_data()

            # Upload to IPFS
            ipfs = IPFSStorage()
            cid = await ipfs.store_config(config, f"oracle-config-{request.market_id}.json")

            gateway_url = ipfs.get_gateway_url(cid) if cid else None

            logger.info(
                f"Uploaded oracle config for market {request.market_id}",
                cid=cid,
                hash=config_hash[:16] + "...",
            )

            return UploadConfigResponse(
                success=True,
                market_id=request.market_id,
                config_cid=cid or "",
                config_hash=config_hash,
                gateway_url=gateway_url,
            )

        except Exception as e:
            logger.error(f"Failed to upload oracle config: {e}")
            return UploadConfigResponse(
                success=False,
                market_id=request.market_id,
                config_cid="",
                config_hash="",
                error=str(e),
            )

    @app.get("/api/v1/config/{cid}", response_model=GetConfigResponse)
    async def get_oracle_config(cid: str, expected_hash: str | None = None):
        """
        Get oracle configuration from IPFS and optionally verify its hash.

        Args:
            cid: IPFS CID of the config
            expected_hash: Optional SHA256 hash to verify against
        """
        from oracle.storage import IPFSStorage, calculate_sha256, to_canonical_json

        try:
            # Fetch from IPFS
            ipfs = IPFSStorage()
            config_data = await ipfs.fetch(cid)

            if config_data is None:
                return GetConfigResponse(
                    success=False,
                    cid=cid,
                    error="Config not found on IPFS",
                )

            # Calculate hash
            canonical_json = to_canonical_json(config_data)
            actual_hash = calculate_sha256(canonical_json)

            # Verify if expected hash provided
            verified = True
            if expected_hash:
                verified = actual_hash == expected_hash

            return GetConfigResponse(
                success=True,
                cid=cid,
                config=config_data,
                verified=verified,
                expected_hash=expected_hash,
                actual_hash=actual_hash,
            )

        except Exception as e:
            logger.error(f"Failed to fetch oracle config: {e}")
            return GetConfigResponse(
                success=False,
                cid=cid,
                error=str(e),
            )

    @app.get("/api/v1/strategies")
    async def list_strategies():
        """
        List available agent strategies.

        Returns all configured research strategies that can be used
        for agent differentiation.
        """
        from oracle.agents.strategies import StrategyFactory

        return {
            "strategies": StrategyFactory.list_all_profiles(),
            "recommended_5_agents": [p.value for p in StrategyFactory.get_recommended_profiles(5)],
        }

    # ========================================================================
    # Resolution Endpoints (v1 - Full Featured)
    # ========================================================================

    @app.post(
        "/api/v1/resolve", response_model=ResolutionResponse, dependencies=[Depends(verify_api_key)]
    )
    async def request_resolution(
        request: ResolutionRequest,
        background_tasks: BackgroundTasks,
    ):
        """
        Request oracle resolution for a prediction market.

        The resolution runs asynchronously with full verification.
        Poll /api/v1/result/{request_id} for the result,
        or provide a callback_url for webhook notification.

        Supports:
        - oracle_config_cid/hash for config verification
        - Custom agent_count and consensus_threshold
        - Full verification data in response
        """
        if not api_instance.oracle:
            raise HTTPException(status_code=503, detail="Oracle not initialized")

        request_id = f"req_{uuid.uuid4().hex[:12]}"

        # Mark as processing
        api_instance.result_store.set_processing(request_id)

        # Store request info
        api_instance.requests[request_id] = request

        # Run resolution in background
        background_tasks.add_task(
            _run_resolution,
            request_id,
            request,
        )

        return ResolutionResponse(
            request_id=request_id,
            status="processing",
            estimated_time_seconds=180,
        )

    @app.get("/api/v1/result/{request_id}", response_model=ResultResponse)
    async def get_result(request_id: str):
        """
        Get the result of a resolution request.

        Returns full verification data including:
        - Consensus details (outcome, confidence, agreement)
        - Source statistics (tier1/tier2 sources)
        - IPFS CIDs and hashes for on-chain verification
        - Manual review flags if applicable
        """
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
            return result

        raise HTTPException(status_code=500, detail="Unknown error")

    @app.post(
        "/api/v1/resolve/sync",
        response_model=ResultResponse,
        dependencies=[Depends(verify_api_key)],
    )
    async def resolve_sync(request: ResolutionRequest):
        """
        Synchronously resolve a prediction market question.

        This endpoint blocks until resolution is complete and returns
        comprehensive verification data including hashes for on-chain submission.

        Use /api/v1/resolve for async operation.
        """
        if not api_instance.oracle:
            raise HTTPException(status_code=503, detail="Oracle not initialized")

        try:
            request_id = f"req_{uuid.uuid4().hex[:12]}"

            # Run resolution
            result = await _execute_resolution(
                request_id,
                request,
            )

            return result

        except Exception as e:
            logger.error(f"Resolution failed: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    # ========================================================================
    # Multi-Outcome Resolution Endpoints
    # ========================================================================

    @app.post(
        "/api/v1/resolve-multi/sync",
        response_model=MultiOutcomeResultResponse,
        dependencies=[Depends(verify_api_key)],
    )
    async def resolve_multi_sync(request: MultiOutcomeResolutionRequest):
        """
        Synchronously resolve a multi-outcome prediction market question.

        Accepts a list of outcome labels and returns the winning outcome index.
        Uses MultiOutcomeConsensusEngine with N+1 bins (outcomes + UNDETERMINED).
        Default consensus threshold is 0.80 (4/5) for multi-outcome markets.
        """
        if not api_instance.oracle:
            raise HTTPException(status_code=503, detail="Oracle not initialized")

        if len(request.outcomes) != request.num_outcomes:
            raise HTTPException(
                status_code=400,
                detail=f"outcomes length ({len(request.outcomes)}) must match num_outcomes ({request.num_outcomes})",
            )

        try:
            request_id = f"req_{uuid.uuid4().hex[:12]}"

            result = await _execute_multi_outcome_resolution(
                request_id,
                request,
            )

            return result

        except Exception as e:
            logger.error(f"Multi-outcome resolution failed: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    # ========================================================================
    # SSE Streaming Resolution Endpoints
    # ========================================================================

    @app.post(
        "/api/v1/resolve/stream",
        dependencies=[Depends(verify_api_key)],
    )
    async def resolve_stream(request: ResolutionRequest):
        """
        SSE streaming resolution for binary prediction markets.

        Streams progress events as Server-Sent Events, then the final result.
        Each event is a JSON-encoded SSE `data:` line with an `event:` type.
        A heartbeat `:heartbeat` comment is sent every 15 seconds to keep
        the connection alive.
        """
        if not api_instance.oracle:
            raise HTTPException(status_code=503, detail="Oracle not initialized")

        async def _generate():
            import json as _json
            import time as _time

            request_id = f"req_{uuid.uuid4().hex[:12]}"
            api_instance.result_store.set_processing(request_id)

            last_heartbeat = _time.monotonic()
            heartbeat_interval = 15.0

            try:
                async for event in api_instance.oracle.resolve_with_progress(
                    question=request.question,
                    resolution_criteria=request.resolution_criteria,
                    market_id=request.market_id,
                    deadline=request.deadline,
                    request_id=request_id,
                ):
                    now = _time.monotonic()
                    if now - last_heartbeat >= heartbeat_interval:
                        yield ":heartbeat\n\n"
                        last_heartbeat = now

                    event_type = event.get("event_type", "progress")
                    oracle_result = event.pop("_result", None)

                    data = _json.dumps(event, default=str, ensure_ascii=False)
                    yield f"event: {event_type}\ndata: {data}\n\n"

                    if event_type == "resolution:completed" and oracle_result:
                        try:
                            final_response = await _build_result_response_from_oracle_result(
                                request_id, request, oracle_result
                            )
                            api_instance.result_store.set_completed(request_id, final_response)
                        except Exception as e:
                            logger.error(f"Failed to build final response: {e}")
                            api_instance.result_store.set_failed(request_id, str(e))

                    if event_type == "resolution:error":
                        api_instance.result_store.set_failed(
                            request_id, event.get("error", "Unknown error")
                        )

            except Exception as e:
                logger.error(f"SSE stream error: {e}")
                error_data = _json.dumps({"event_type": "resolution:error", "error": str(e)})
                yield f"event: resolution:error\ndata: {error_data}\n\n"
                api_instance.result_store.set_failed(request_id, str(e))

        return StreamingResponse(
            _generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @app.post(
        "/api/v1/resolve-multi/stream",
        dependencies=[Depends(verify_api_key)],
    )
    async def resolve_multi_stream(request: MultiOutcomeResolutionRequest):
        """
        SSE streaming resolution for multi-outcome prediction markets.

        Same SSE format as /api/v1/resolve/stream but with multi-outcome events.
        """
        if not api_instance.oracle:
            raise HTTPException(status_code=503, detail="Oracle not initialized")

        if len(request.outcomes) != request.num_outcomes:
            raise HTTPException(
                status_code=400,
                detail=f"outcomes length ({len(request.outcomes)}) must match num_outcomes ({request.num_outcomes})",
            )

        async def _generate():
            import json as _json
            import time as _time

            request_id = f"req_{uuid.uuid4().hex[:12]}"
            api_instance.result_store.set_processing(request_id)

            last_heartbeat = _time.monotonic()
            heartbeat_interval = 15.0

            threshold = request.consensus_threshold or float(
                os.getenv("MULTI_OUTCOME_CONSENSUS_THRESHOLD", "0.80")
            )

            try:
                async for event in api_instance.oracle.resolve_multi_outcome_with_progress(
                    question=request.question,
                    resolution_criteria=request.resolution_criteria,
                    outcomes=request.outcomes,
                    market_id=request.market_id,
                    deadline=request.deadline,
                    consensus_threshold=threshold,
                    request_id=request_id,
                ):
                    now = _time.monotonic()
                    if now - last_heartbeat >= heartbeat_interval:
                        yield ":heartbeat\n\n"
                        last_heartbeat = now

                    event_type = event.get("event_type", "progress")
                    oracle_result = event.pop("_result", None)

                    data = _json.dumps(event, default=str, ensure_ascii=False)
                    yield f"event: {event_type}\ndata: {data}\n\n"

                    if event_type == "resolution:completed" and oracle_result:
                        try:
                            final_response = await _build_result_response_from_oracle_result(
                                request_id, request, oracle_result
                            )
                            api_instance.result_store.set_completed(request_id, final_response)
                        except Exception as e:
                            logger.error(f"Failed to build multi-outcome final response: {e}")
                            api_instance.result_store.set_failed(request_id, str(e))

                    if event_type == "resolution:error":
                        api_instance.result_store.set_failed(
                            request_id, event.get("error", "Unknown error")
                        )

            except Exception as e:
                logger.error(f"Multi-outcome SSE stream error: {e}")
                error_data = _json.dumps({"event_type": "resolution:error", "error": str(e)})
                yield f"event: resolution:error\ndata: {error_data}\n\n"
                api_instance.result_store.set_failed(request_id, str(e))

        return StreamingResponse(
            _generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    return app


async def _build_result_response_from_oracle_result(
    request_id: str,
    request: ResolutionRequest,
    result,
) -> ResultResponse | MultiOutcomeResultResponse:
    """Build a ResultResponse (binary) or MultiOutcomeResultResponse (multi) from an OracleResult."""
    from oracle.agents import StrategyFactory
    from oracle.consensus import StrictConsensusConfig, StrictConsensusEngine
    from oracle.models import AgentResult, ConsensusResult, MultiOutcomeOracleResult, Outcome
    from oracle.storage import OracleResearchDataBuilder

    research_started_at = result.research_started_at
    research_completed_at = result.research_completed_at

    is_multi = isinstance(result, MultiOutcomeOracleResult)

    if is_multi:
        binary_agent_results = [
            AgentResult(
                agent_id=ar.agent_id,
                model=ar.model,
                strategy=ar.strategy,
                outcome=Outcome.YES if ar.outcome_index >= 0 else Outcome.UNDETERMINED,
                confidence=ar.confidence,
                reasoning=f"[Multi-outcome: {ar.outcome_label} (index={ar.outcome_index})] {ar.reasoning}",
                sources=ar.sources,
            )
            for ar in result.agent_results
        ]
        binary_consensus = ConsensusResult(
            reached=result.consensus.reached,
            outcome=Outcome.YES if result.consensus.winning_outcome.is_determined else Outcome.UNDETERMINED,
            confidence=result.consensus.confidence,
            agreement_ratio=result.consensus.agreement_ratio,
            weighted_ratio=result.consensus.weighted_ratio,
            agent_count=result.consensus.agent_count,
        )
    else:
        binary_agent_results = result.agent_results
        binary_consensus = result.consensus

    builder = OracleResearchDataBuilder(
        market_id=request.market_id,
        question=request.question,
        resolution_criteria=request.resolution_criteria,
        deadline=request.deadline,
    )
    builder.research_started_at = research_started_at
    builder.research_completed_at = research_completed_at

    for agent_result in binary_agent_results:
        builder.add_agent_result(agent_result)

    builder.set_consensus(binary_consensus)
    builder.set_merged_sources(result.merged_sources)

    agent_count = request.agent_count or 5
    strategies = [p.value for p in StrategyFactory.get_recommended_profiles(agent_count)]

    if is_multi:
        threshold = request.consensus_threshold or float(os.getenv("MULTI_OUTCOME_CONSENSUS_THRESHOLD", "0.80"))
    else:
        threshold = request.consensus_threshold or float(os.getenv("CONSENSUS_THRESHOLD", "0.66"))

    oracle_config = builder.build_config(
        agent_count=agent_count,
        agent_strategies=strategies,
        consensus_threshold=threshold,
    )
    _, config_hash = oracle_config.get_hash_data()

    research_data = builder.build()
    _, research_hash = research_data.get_hash_data()

    strict_engine = StrictConsensusEngine(
        config=StrictConsensusConfig(threshold=threshold)
    )
    strict_consensus, provable_data = strict_engine.calculate_strict(binary_agent_results)

    weighted_ratio = result.consensus.weighted_ratio

    ipfs_mock = (
        result.ipfs_cid is None
        or not result.ipfs_cid
        or os.path.exists(
            os.path.join(os.getcwd(), ".ipfs_mock", f"{result.ipfs_cid}.json")
        )
    )

    shared_kwargs = dict(
        request_id=request_id,
        market_id=request.market_id,
        status="completed",
        confidence=result.consensus.confidence,
        agreement_ratio=result.consensus.agreement_ratio,
        weighted_ratio=weighted_ratio,
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
            provable_data.disagreement.review_reason if provable_data.disagreement else None
        ),
        disagreement_analysis=(
            provable_data.disagreement.model_dump()
            if provable_data.disagreement and provable_data.disagreement.has_disagreement
            else None
        ),
        research_started_at=research_started_at,
        research_completed_at=research_completed_at,
        ipfs_mock=ipfs_mock,
    )

    if is_multi:
        winning = result.consensus.winning_outcome
        return MultiOutcomeResultResponse(
            **shared_kwargs,
            outcome_index=winning.outcome_index if hasattr(winning, "outcome_index") else None,
            outcome_label=winning.outcome_label,
            outcomes=result.outcomes if hasattr(result, "outcomes") else None,
            vote_distribution=result.consensus.vote_distribution,
        )

    return ResultResponse(
        **shared_kwargs,
        outcome=result.consensus.outcome.value,
    )


async def _run_resolution(request_id: str, request: ResolutionRequest):
    """Background task for resolution."""
    try:
        result = await _execute_resolution(request_id, request)
        api_instance.result_store.set_completed(request_id, result)

        # Send webhook if configured
        if request.callback_url and result.status == "completed":
            await _send_webhook(request.callback_url, result)

    except Exception as e:
        logger.error(f"Resolution failed: {e}")
        api_instance.result_store.set_failed(request_id, str(e))


async def _execute_resolution(
    request_id: str,
    request: ResolutionRequest,
) -> ResultResponse:
    """Execute resolution with full verification data."""
    from oracle.agents import StrategyFactory
    from oracle.consensus import StrictConsensusConfig, StrictConsensusEngine
    from oracle.storage import OracleResearchDataBuilder

    if not api_instance.oracle:
        return ResultResponse(
            request_id=request_id,
            market_id=request.market_id,
            status="failed",
            error="Oracle not initialized",
        )

    # Use timezone-aware UTC timestamps for RFC 3339 compliance
    # (Rust backend parses with DateTime::parse_from_rfc3339 which requires timezone)
    research_started_at = datetime.now(UTC).isoformat()

    try:
        # Step 1: Run resolution
        result = await api_instance.oracle.resolve(
            question=request.question,
            resolution_criteria=request.resolution_criteria,
            market_id=request.market_id,
            deadline=request.deadline,
        )

        research_completed_at = datetime.now(UTC).isoformat()

        # Step 2: Build research data
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
            consensus_threshold=request.consensus_threshold
            or float(os.getenv("CONSENSUS_THRESHOLD", "0.66")),
        )

        # Calculate hashes
        _, config_hash = oracle_config.get_hash_data()

        # Build research data and compute hash
        # NOTE: research_data_hash is computed from OracleResearchData (canonical schema),
        # while research_data_cid points to IPFSResearchData (which may have additional fields
        # like thinking_process, website_tracking). These are DIFFERENT data structures.
        # The hash verifies the canonical research summary; the CID provides access to the
        # full detailed data. This is by design — the hash is for DB integrity verification,
        # while the CID is for data retrieval.
        research_data = builder.build()
        _, research_hash = research_data.get_hash_data()

        # Step 3: Run strict consensus check
        strict_engine = StrictConsensusEngine(
            config=StrictConsensusConfig(
                threshold=request.consensus_threshold
                or float(os.getenv("CONSENSUS_THRESHOLD", "0.66")),
            )
        )

        strict_consensus, provable_data = strict_engine.calculate_strict(result.agent_results)

        # Step 4: Build response
        return ResultResponse(
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
                or (
                    provable_data.disagreement and provable_data.disagreement.requires_manual_review
                )
            ),
            review_reason=(
                provable_data.disagreement.review_reason if provable_data.disagreement else None
            ),
            disagreement_analysis=(
                provable_data.disagreement.model_dump()
                if provable_data.disagreement and provable_data.disagreement.has_disagreement
                else None
            ),
            research_started_at=research_started_at,
            research_completed_at=research_completed_at,
            # Detect mock IPFS: mock CIDs are locally generated SHA256 hashes
            ipfs_mock=(
                result.ipfs_cid is None
                or not result.ipfs_cid
                or os.path.exists(
                    os.path.join(os.getcwd(), ".ipfs_mock", f"{result.ipfs_cid}.json")
                )
            ),
        )

    except Exception as e:
        logger.error(f"Resolution execution failed: {e}")
        return ResultResponse(
            request_id=request_id,
            market_id=request.market_id,
            status="failed",
            error=str(e),
        )


def _validate_callback_url(url: str) -> None:
    """Validate callback URL is not targeting private/internal networks (SSRF prevention)."""
    import socket

    parsed = urlparse(url)
    hostname = parsed.hostname

    if not hostname:
        raise ValueError("Invalid callback URL: no hostname")

    if hostname in ("localhost", "localhost.localdomain"):
        raise ValueError(f"Callback URL targets localhost: {hostname}")

    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        resolved = socket.getaddrinfo(hostname, None)
        addr = ipaddress.ip_address(resolved[0][4][0])

    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
        raise ValueError(f"Callback URL resolves to non-public address: {addr}")


async def _send_webhook(url: str, result: ResultResponse):
    """Send webhook notification."""
    import httpx

    try:
        _validate_callback_url(url)
    except ValueError as e:
        logger.error(f"SSRF blocked: {e}")
        return

    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                url,
                json=result.model_dump(),
                timeout=10,
            )
        logger.info(f"Webhook sent to {url}")
    except Exception as e:
        logger.error(f"Webhook failed: {e}")


async def _execute_multi_outcome_resolution(
    request_id: str,
    request: MultiOutcomeResolutionRequest,
) -> MultiOutcomeResultResponse:
    """Execute multi-outcome resolution with full verification data."""
    from oracle.agents import StrategyFactory
    from oracle.consensus import StrictConsensusConfig, StrictConsensusEngine
    from oracle.storage import OracleResearchDataBuilder

    if not api_instance.oracle:
        return MultiOutcomeResultResponse(
            request_id=request_id,
            market_id=request.market_id,
            status="failed",
            error="Oracle not initialized",
        )

    research_started_at = datetime.now(UTC).isoformat()

    try:
        threshold = request.consensus_threshold or float(
            os.getenv("MULTI_OUTCOME_CONSENSUS_THRESHOLD", "0.80")
        )

        result = await api_instance.oracle.resolve_multi_outcome(
            question=request.question,
            resolution_criteria=request.resolution_criteria,
            outcomes=request.outcomes,
            market_id=request.market_id,
            deadline=request.deadline,
            consensus_threshold=threshold,
        )

        research_completed_at = datetime.now(UTC).isoformat()

        # Build research data for hashing
        builder = OracleResearchDataBuilder(
            market_id=request.market_id,
            question=request.question,
            resolution_criteria=request.resolution_criteria,
            deadline=request.deadline,
        )
        builder.research_started_at = research_started_at
        builder.research_completed_at = research_completed_at

        # Convert multi-outcome results to binary AgentResults for storage compatibility
        from oracle.models import AgentResult, ConsensusResult, Outcome

        for ar in result.agent_results:
            binary_ar = AgentResult(
                agent_id=ar.agent_id,
                model=ar.model,
                strategy=ar.strategy,
                outcome=Outcome.YES if ar.outcome_index >= 0 else Outcome.UNDETERMINED,
                confidence=ar.confidence,
                reasoning=f"[Multi-outcome: {ar.outcome_label} (index={ar.outcome_index})] {ar.reasoning}",
                sources=ar.sources,
            )
            builder.add_agent_result(binary_ar)

        binary_consensus = ConsensusResult(
            reached=result.consensus.reached,
            outcome=Outcome.YES if result.consensus.winning_outcome.is_determined else Outcome.UNDETERMINED,
            confidence=result.consensus.confidence,
            agreement_ratio=result.consensus.agreement_ratio,
            weighted_ratio=result.consensus.weighted_ratio,
            agent_count=result.consensus.agent_count,
        )
        builder.set_consensus(binary_consensus)
        builder.set_merged_sources(result.merged_sources)

        agent_count = request.agent_count or 5
        strategies = [p.value for p in StrategyFactory.get_recommended_profiles(agent_count)]

        oracle_config = builder.build_config(
            agent_count=agent_count,
            agent_strategies=strategies,
            consensus_threshold=threshold,
        )

        _, config_hash = oracle_config.get_hash_data()

        research_data = builder.build()
        _, research_hash = research_data.get_hash_data()

        # Run strict consensus for verification data
        strict_engine = StrictConsensusEngine(
            config=StrictConsensusConfig(threshold=threshold)
        )

        binary_results_for_strict = [
            AgentResult(
                agent_id=ar.agent_id,
                model=ar.model,
                strategy=ar.strategy,
                outcome=Outcome.YES if ar.outcome_index >= 0 else Outcome.UNDETERMINED,
                confidence=ar.confidence,
                reasoning=ar.reasoning,
                sources=ar.sources,
            )
            for ar in result.agent_results
        ]
        strict_consensus, provable_data = strict_engine.calculate_strict(binary_results_for_strict)

        winning = result.consensus.winning_outcome

        return MultiOutcomeResultResponse(
            request_id=request_id,
            market_id=request.market_id,
            status="completed",
            outcome_index=winning.outcome_index if winning.is_determined else None,
            outcome_label=winning.outcome_label,
            outcomes=request.outcomes,
            vote_distribution=result.consensus.vote_distribution,
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
                result.consensus.requires_human_review
                or (
                    provable_data.disagreement and provable_data.disagreement.requires_manual_review
                )
            ),
            review_reason=(
                result.consensus.reason
                or (provable_data.disagreement.review_reason if provable_data.disagreement else None)
            ),
            disagreement_analysis=(
                provable_data.disagreement.model_dump()
                if provable_data.disagreement and provable_data.disagreement.has_disagreement
                else None
            ),
            research_started_at=research_started_at,
            research_completed_at=research_completed_at,
            ipfs_mock=(
                result.ipfs_cid is None
                or not result.ipfs_cid
                or os.path.exists(
                    os.path.join(os.getcwd(), ".ipfs_mock", f"{result.ipfs_cid}.json")
                )
            ),
        )

    except Exception as e:
        logger.error(f"Multi-outcome resolution execution failed: {e}")
        return MultiOutcomeResultResponse(
            request_id=request_id,
            market_id=request.market_id,
            status="failed",
            error=str(e),
        )


# Create global app instance for uvicorn
app = create_app()


def run_server(host: str = None, port: int = None):
    """Run the API server."""
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
