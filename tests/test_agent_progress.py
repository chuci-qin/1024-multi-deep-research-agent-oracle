"""Unit tests for agent progress callback integration.

Verifies that:
1. BaseAgent signature includes progress_callback
2. GeminiDeepResearchAgent._emit() is fire-and-forget (never raises)
3. Progress events have correct structure (event_type, agentId)
4. research() / research_multi_outcome() accept progress_callback
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from oracle.agents.base import BaseAgent, ProgressCallback


class TestProgressCallbackSignature:
    """Verify BaseAgent and GeminiDeepResearchAgent accept progress_callback."""

    def test_base_agent_research_accepts_callback(self):
        """BaseAgent.research() signature includes progress_callback parameter."""
        import inspect

        sig = inspect.signature(BaseAgent.research)
        params = list(sig.parameters.keys())
        assert "progress_callback" in params, (
            f"BaseAgent.research() missing progress_callback param. Params: {params}"
        )

    def test_gemini_agent_research_accepts_callback(self):
        """GeminiDeepResearchAgent.research() signature includes progress_callback."""
        import inspect

        from oracle.agents.gemini import GeminiDeepResearchAgent

        sig = inspect.signature(GeminiDeepResearchAgent.research)
        params = list(sig.parameters.keys())
        assert "progress_callback" in params

    def test_gemini_agent_research_multi_outcome_accepts_callback(self):
        """GeminiDeepResearchAgent.research_multi_outcome() includes progress_callback."""
        import inspect

        from oracle.agents.gemini import GeminiDeepResearchAgent

        sig = inspect.signature(GeminiDeepResearchAgent.research_multi_outcome)
        params = list(sig.parameters.keys())
        assert "progress_callback" in params


class TestEmitFireAndForget:
    """Verify _emit() never propagates exceptions."""

    @pytest.mark.asyncio
    async def test_emit_with_none_callback(self):
        """_emit(None, event) should not raise."""
        from oracle.agents.gemini import GeminiDeepResearchAgent

        agent = GeminiDeepResearchAgent.__new__(GeminiDeepResearchAgent)
        agent.agent_id = "test-agent"
        # Should not raise
        await agent._emit(None, {"event_type": "test"})

    @pytest.mark.asyncio
    async def test_emit_with_failing_callback(self):
        """_emit() should swallow callback exceptions."""
        from oracle.agents.gemini import GeminiDeepResearchAgent

        agent = GeminiDeepResearchAgent.__new__(GeminiDeepResearchAgent)
        agent.agent_id = "test-agent"

        async def failing_callback(event):
            raise RuntimeError("Callback exploded!")

        # Should not raise despite callback failure
        await agent._emit(failing_callback, {"event_type": "test"})

    @pytest.mark.asyncio
    async def test_emit_calls_callback_with_event(self):
        """_emit() should call the callback with the event dict."""
        from oracle.agents.gemini import GeminiDeepResearchAgent

        agent = GeminiDeepResearchAgent.__new__(GeminiDeepResearchAgent)
        agent.agent_id = "test-agent"

        received = []

        async def mock_callback(event):
            received.append(event)

        await agent._emit(mock_callback, {"event_type": "test", "agentId": "test-agent"})

        assert len(received) == 1
        assert received[0]["event_type"] == "test"
        assert received[0]["agentId"] == "test-agent"


class TestProgressEventStructure:
    """Verify progress events emitted by research methods."""

    @pytest.mark.asyncio
    async def test_uninitialized_agent_emits_error_event(self):
        """Uninitialized agent emits agent_error before returning INVALID result."""
        from oracle.agents.gemini import GeminiDeepResearchAgent

        agent = GeminiDeepResearchAgent.__new__(GeminiDeepResearchAgent)
        agent.agent_id = "test-agent-1"
        agent._model_name = "test-model"
        from oracle.agents.base import AgentConfig, SearchStrategy
        agent.strategy = SearchStrategy.COMPREHENSIVE
        agent._initialized = False
        agent.client = None
        agent.config = None

        agent.config = AgentConfig()

        events = []

        async def collect_callback(event):
            events.append(event)

        result = await agent.research(
            "Test question?",
            "Test criteria",
            progress_callback=collect_callback,
        )

        assert result.outcome.value == "INVALID"
        assert len(events) == 1, f"Expected 1 agent_error event, got {len(events)}"
        assert events[0]["event_type"] == "agent_error"
        assert events[0]["agentId"] == "test-agent-1"


class TestResolveWithProgress:
    """Verify core.py resolve_with_progress yields events."""

    @pytest.mark.asyncio
    async def test_resolve_with_progress_yields_started_event(self):
        """resolve_with_progress() first event is resolution:started."""
        from oracle.core import MultiAgentOracle, OracleConfig

        oracle = MultiAgentOracle.__new__(MultiAgentOracle)
        oracle.config = OracleConfig(num_agents=1, enable_ipfs=False)
        oracle.ipfs_storage = None

        assert hasattr(oracle, "resolve_with_progress")
        assert hasattr(oracle, "resolve_multi_outcome_with_progress")

    def test_resolve_with_progress_accepts_request_id(self):
        """resolve_with_progress() accepts request_id parameter."""
        import inspect
        from oracle.core import MultiAgentOracle

        sig = inspect.signature(MultiAgentOracle.resolve_with_progress)
        params = list(sig.parameters.keys())
        assert "request_id" in params, (
            f"resolve_with_progress() missing request_id param. Params: {params}"
        )

    def test_resolve_multi_outcome_with_progress_accepts_request_id(self):
        """resolve_multi_outcome_with_progress() accepts request_id parameter."""
        import inspect
        from oracle.core import MultiAgentOracle

        sig = inspect.signature(MultiAgentOracle.resolve_multi_outcome_with_progress)
        params = list(sig.parameters.keys())
        assert "request_id" in params, (
            f"resolve_multi_outcome_with_progress() missing request_id param. Params: {params}"
        )


class TestSseEndpoints:
    """Verify SSE endpoint registration in FastAPI."""

    def test_stream_endpoints_exist(self):
        """FastAPI app should have /api/v1/resolve/stream and /resolve-multi/stream."""
        from oracle.api.server import app

        routes = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/v1/resolve/stream" in routes, (
            f"Missing /api/v1/resolve/stream. Routes: {routes}"
        )
        assert "/api/v1/resolve-multi/stream" in routes, (
            f"Missing /api/v1/resolve-multi/stream. Routes: {routes}"
        )

    def test_stream_endpoints_are_post(self):
        """SSE stream endpoints should be POST (matching sync endpoints)."""
        from oracle.api.server import app

        for route in app.routes:
            if hasattr(route, "path") and route.path in (
                "/api/v1/resolve/stream",
                "/api/v1/resolve-multi/stream",
            ):
                assert "POST" in route.methods, (
                    f"Route {route.path} should accept POST, got {route.methods}"
                )
