"""
Gemini Deep Research Agent

Uses Google Gemini API with Google Search grounding to collect
sources and provide structured research results.
"""

import asyncio
import json
import os
import time
from urllib.parse import urlparse

import structlog
from google import genai  # New SDK
from google.genai import types as genai_types

from oracle.agents.base import AgentConfig, BaseAgent, SearchStrategy
from oracle.models import AgentResult, Outcome, ResearchSource, SourceCategory
from oracle.tools import get_all_tools, get_tool

logger = structlog.get_logger()


class GeminiDeepResearchAgent(BaseAgent):
    """
    Deep Research Agent powered by Google Gemini API.

    Uses Google Search grounding to collect sources
    and returns structured results with full citations.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash",
        agent_id: str | None = None,
        strategy: SearchStrategy = SearchStrategy.COMPREHENSIVE,
        config: AgentConfig | None = None,
    ):
        super().__init__(agent_id, strategy, config)

        self._model_name = model
        self._initialized = False
        self.client = None

        use_vertex = os.getenv("USE_VERTEX_AI", "false").lower() == "true"

        if use_vertex:
            try:
                # Support injecting GCP credentials JSON via env var (for Docker/EasyPanel)
                creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
                if creds_json and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                    import tempfile
                    fd, creds_path = tempfile.mkstemp(suffix=".json", prefix="gcp-sa-")
                    with os.fdopen(fd, "w") as f:
                        f.write(creds_json)
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path

                project = os.getenv("VERTEX_AI_PROJECT", "gen-lang-client-0475545182")
                location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
                self.client = genai.Client(vertexai=True, project=project, location=location)
                self._initialized = True
                logger.info(
                    "Initialized Gemini agent (Vertex AI)",
                    agent_id=self.agent_id,
                    model=model,
                    project=project,
                    location=location,
                    strategy=strategy.value,
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Vertex AI agent: {e}")
        else:
            api_key = api_key or os.getenv("GEMINI_API_KEY")
            self._api_key = api_key
            if api_key:
                try:
                    self.client = genai.Client(api_key=api_key)
                    self._initialized = True
                    logger.info(
                        "Initialized Gemini agent (AI Studio)",
                        agent_id=self.agent_id,
                        model=model,
                        strategy=strategy.value,
                    )
                except Exception as e:
                    logger.warning(f"Failed to initialize Gemini agent: {e}")
            else:
                logger.warning(
                    "GEMINI_API_KEY not set - agent will fail on research calls",
                    agent_id=self.agent_id,
                )

    @property
    def model_name(self) -> str:
        return self._model_name

    async def _execute_tool_call(self, function_call) -> dict:
        """Execute a Gemini function call by routing to the registered tool."""
        tool_name = function_call.name
        tool_args = dict(function_call.args) if function_call.args else {}

        tool = get_tool(tool_name)
        if not tool:
            logger.warning("Unknown tool called by Gemini", tool_name=tool_name)
            return {"error": f"Unknown tool: {tool_name}"}

        logger.info("Executing tool", tool_name=tool_name, args=tool_args)
        try:
            result = await tool.execute(**tool_args)
            logger.info("Tool result", tool_name=tool_name, result_keys=list(result.keys()))
            return result
        except Exception as e:
            logger.error("Tool execution failed", tool_name=tool_name, error=str(e))
            return {"error": str(e)}

    async def _phase1_tool_calls(self, prompt: str) -> tuple[list[dict], list[ResearchSource]]:
        """Phase 1: Let Gemini decide whether to call data tools (Binance, etc.).
        
        Uses function_declarations ONLY (no google_search — they can't coexist).
        Returns (tool_data_list, tool_sources) for injection into Phase 2.
        """
        all_tools = get_all_tools()
        if not all_tools:
            return [], []

        func_decls = [t.to_function_declaration() for t in all_tools]
        tool_prompt = (
            f"You have access to data tools. Decide if any are needed to answer this question.\n"
            f"If the question involves cryptocurrency prices, call get_crypto_price_at_timestamp or get_crypto_price_current.\n"
            f"If the question does NOT need real-time data APIs, just reply 'NO_TOOLS_NEEDED'.\n\n"
            f"Question: {prompt[:500]}"
        )

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self._model_name,
                contents=tool_prompt,
                config={
                    "tools": [genai_types.Tool(function_declarations=func_decls)],
                    "temperature": 0.0,
                    "max_output_tokens": 1024,
                },
            )
        except Exception as e:
            logger.warning("Phase 1 tool call failed", error=str(e))
            return [], []

        tool_data = []
        tool_sources = []

        # Process up to 3 rounds of function calls
        conversation = [tool_prompt]
        for round_num in range(3):
            if not response.candidates or len(response.candidates) == 0:
                break
            if not hasattr(response.candidates[0], 'content') or not response.candidates[0].content or not response.candidates[0].content.parts:
                break

            function_calls = [
                p.function_call
                for p in response.candidates[0].content.parts
                if hasattr(p, "function_call") and p.function_call and p.function_call.name
            ]

            if not function_calls:
                break

            logger.info("Phase 1: Gemini requested tools", round=round_num + 1, tools=[fc.name for fc in function_calls])

            function_responses = []
            for fc in function_calls:
                result = await self._execute_tool_call(fc)
                tool_data.append({"tool": fc.name, "args": dict(fc.args) if fc.args else {}, "result": result})
                function_responses.append(
                    genai_types.Part.from_function_response(name=fc.name, response=result)
                )
                source_name = result.get("source", fc.name)
                tool_sources.append(ResearchSource(
                    url=f"api://{source_name}/{fc.name}",
                    title=f"{fc.name} ({source_name})",
                    snippet=json.dumps(result, default=str)[:500],
                    category=SourceCategory.OFFICIAL,
                    relevance_score=1.0,
                    credibility_score=1.0,
                    cited_by=[self.agent_id],
                ))

            conversation.append(response.candidates[0].content)
            conversation.append(genai_types.Content(role="user", parts=function_responses))

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self._model_name,
                contents=conversation,
                config={
                    "tools": [genai_types.Tool(function_declarations=func_decls)],
                    "temperature": 0.0,
                    "max_output_tokens": 1024,
                },
            )

        if tool_data:
            logger.info("Phase 1 complete", agent_id=self.agent_id, tools_called=len(tool_data))
        else:
            logger.debug("Phase 1: no tools needed", agent_id=self.agent_id)

        return tool_data, tool_sources

    async def research(
        self,
        question: str,
        resolution_criteria: str,
        deadline: str | None = None,
    ) -> AgentResult:
        """
        Two-phase research:
          Phase 1 — Function Calling: Gemini decides if it needs data tools (Binance API, etc.)
          Phase 2 — Google Search: Web research with tool data injected into prompt
        """
        start_time = time.time()

        if not self._initialized or not self.client:
            return AgentResult(
                agent_id=self.agent_id,
                model=self.model_name,
                strategy=self.strategy.value,
                outcome=Outcome.INVALID,
                confidence=0.0,
                reasoning="Agent not initialized - missing API key",
                sources=[],
                research_duration_seconds=0,
                error="GEMINI_API_KEY not configured",
            )

        logger.info("Starting research", agent_id=self.agent_id, question=question[:100])

        try:
            prompt = self._build_research_prompt(question, resolution_criteria, deadline)

            # --- Phase 1: Tool Calls (function_declarations only) ---
            tool_data, tool_sources = await self._phase1_tool_calls(prompt)

            # Inject tool data into prompt for Phase 2
            if tool_data:
                data_block = "\n\n=== VERIFIED API DATA (from Phase 1 tool calls) ===\n"
                for td in tool_data:
                    data_block += f"\nTool: {td['tool']}({json.dumps(td['args'], default=str)})\n"
                    data_block += f"Result: {json.dumps(td['result'], default=str)}\n"
                data_block += "\nUse this verified API data as your PRIMARY evidence. It is more reliable than web search results.\n"
                data_block += "=== END VERIFIED API DATA ===\n"
                prompt = prompt + data_block

            # --- Phase 2: Google Search (grounding only) ---
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self._model_name,
                contents=prompt,
                config={
                    "tools": [{"google_search": {}}],
                    "temperature": self.config.temperature,
                    "max_output_tokens": self.config.max_tokens,
                },
            )

            # Merge sources: grounding sources + tool API sources
            sources = self._extract_sources(response) + tool_sources

            outcome, confidence, reasoning = self._parse_response(response)

            duration = time.time() - start_time

            result = AgentResult(
                agent_id=self.agent_id,
                model=self.model_name,
                strategy=self.strategy.value,
                outcome=outcome,
                confidence=confidence,
                reasoning=reasoning,
                sources=sources,
                research_duration_seconds=duration,
            )

            logger.info(
                "Research completed",
                agent_id=self.agent_id,
                outcome=outcome.value,
                confidence=confidence,
                source_count=len(sources),
                tool_sources=len(tool_sources),
                duration=f"{duration:.2f}s",
            )

            return result

        except Exception as e:
            logger.error(
                "Research failed",
                agent_id=self.agent_id,
                error=str(e),
            )

            return AgentResult(
                agent_id=self.agent_id,
                model=self.model_name,
                strategy=self.strategy.value,
                outcome=Outcome.INVALID,
                confidence=0.0,
                reasoning="Research failed due to error",
                sources=[],
                research_duration_seconds=time.time() - start_time,
                error=str(e),
            )

    def _build_research_prompt(
        self,
        question: str,
        resolution_criteria: str,
        deadline: str | None = None,
    ) -> str:
        """Build the research prompt for Gemini."""
        deadline_block = ""
        if deadline:
            deadline_block = f"""
RESOLUTION TIMESTAMP: {deadline}

*** TIME-AWARE RESOLUTION RULES ***
This prediction market resolves based on conditions at or near the timestamp above.

Priority order for finding evidence:
1. BEST: Data at the exact resolution timestamp (minute-level candle from exchanges)
2. GOOD: Data within 5 minutes of the resolution timestamp
3. ACCEPTABLE: Data within 1 hour — if the gap between the data and the threshold is large enough
   that the outcome would not change within that time window
4. USE COMMON SENSE: If BTC is at $66,000 and the question asks "above $97,000?", 
   the answer is clearly NO regardless of minor time differences — BTC cannot move 47% in minutes.

When to use UNDETERMINED:
- The data you found is very close to the threshold AND the time gap is significant
- Example: Question asks "above $66,500?" and closest data shows $66,400 from 30 min ago → UNDETERMINED
- Do NOT use UNDETERMINED when the answer is obvious from available data

Preferred time-sensitive data sources:
- Exchange price feeds (Binance BTC/USDT, Coinbase BTC-USD) with minute-level candles
- CoinGecko/CoinMarketCap with timestamped snapshots
- TradingView with exact time markers
- Bloomberg/Reuters timestamped feeds

Cross-reference at least 2 independent sources when possible.
"""

        strategy_instruction = {
            SearchStrategy.COMPREHENSIVE: """
Search comprehensively across multiple source types, with emphasis on timestamped data:
- Official sources (government, company announcements) with publication timestamps
- Major news outlets (Reuters, AP, Bloomberg, BBC) with article timestamps
- Financial data sources (CoinGecko, TradingView, CoinMarketCap) with exact time markers
- Exchange price feeds (Binance, Coinbase, Kraken) with minute-level candle data
- Expert analysis and reports with publication dates
""",
            SearchStrategy.FOCUSED: """
Focus on the most authoritative and time-precise sources:
- Official announcements and data with publication timestamps
- Primary exchange data (Binance BTC/USDT, Coinbase BTC-USD) with exact timestamps
- Primary news sources (Reuters, AP, Bloomberg) with article timestamps
- Verified factual data with temporal precision
""",
            SearchStrategy.DIVERSE: """
Gather diverse perspectives from different source types, all with timestamps:
- News from different regions and time zones
- Multiple exchanges (cross-verify prices at exact timestamps)
- Social media discussions with post timestamps
- Expert opinions and community forums
- On-chain data and blockchain explorers
""",
        }.get(self.strategy, "Search for relevant information with exact timestamps.")

        return f"""You are an AI oracle for a prediction market. Your task is to research and determine the outcome of a question based on VERIFIABLE, TIME-SPECIFIC evidence.

QUESTION: {question}

RESOLUTION CRITERIA: {resolution_criteria}
{deadline_block}
RESEARCH INSTRUCTIONS:
{strategy_instruction}

Search the web thoroughly using Google Search. Gather evidence from multiple sources.
For price-based or time-sensitive markets, you MUST find data at the exact resolution timestamp.
Do NOT use "current" prices — find the HISTORICAL price at the specified resolution moment.

After researching, provide your determination in the following JSON format:

```json
{{
    "outcome": "YES" or "NO" or "UNDETERMINED",
    "confidence": 0.0 to 1.0,
    "reasoning": "Your detailed reasoning with exact timestamps and source URLs",
    "key_facts": ["fact1 (source, timestamp)", "fact2 (source, timestamp)", "fact3 (source, timestamp)"]
}}
```

Be precise and base your answer on factual evidence from your search results.
Use common sense: if the available data clearly answers the question (e.g., price is well above/below threshold), give a definitive YES/NO even if the data is a few minutes old.
Only use UNDETERMINED when the data is very close to the threshold AND the time gap is significant.
"""

    def _extract_sources(self, response) -> list[ResearchSource]:
        """Extract sources from Gemini response grounding metadata."""
        sources = []

        try:
            if not hasattr(response, "candidates") or not response.candidates:
                return sources

            candidate = response.candidates[0]

            if not hasattr(candidate, "grounding_metadata") or not candidate.grounding_metadata:
                logger.info("No grounding metadata in response")
                return sources

            gm = candidate.grounding_metadata

            # Extract grounding chunks (sources)
            if hasattr(gm, "grounding_chunks") and gm.grounding_chunks:
                for chunk in gm.grounding_chunks:
                    if hasattr(chunk, "web") and chunk.web:
                        web = chunk.web
                        url = getattr(web, "uri", "") or ""
                        title = getattr(web, "title", "") or "Untitled"

                        if url:
                            source = ResearchSource(
                                url=url,
                                title=title,
                                snippet="",
                                category=self._categorize_url(url),
                                credibility_score=self._estimate_credibility(url),
                                cited_by=[self.agent_id],
                            )
                            sources.append(source)

            logger.info(f"Extracted {len(sources)} sources from grounding metadata")

        except Exception as e:
            logger.warning(f"Error extracting sources: {e}")

        return sources

    def _categorize_url(self, url: str) -> SourceCategory:
        """Categorize a URL into source type."""
        domain = urlparse(url).netloc.lower()

        # Official sources
        if any(x in domain for x in [".gov", "sec.gov", "treasury", "federal"]):
            return SourceCategory.OFFICIAL

        # Major news
        news_domains = [
            "reuters",
            "apnews",
            "bloomberg",
            "bbc",
            "cnn",
            "nytimes",
            "wsj",
            "ft.com",
            "cnbc",
            "forbes",
        ]
        if any(x in domain for x in news_domains):
            return SourceCategory.NEWS

        # Crypto/finance specific
        crypto_domains = [
            "coindesk",
            "cointelegraph",
            "coingecko",
            "coinmarketcap",
            "binance",
            "coinbase",
            "investopedia",
            "tradingview",
        ]
        if any(x in domain for x in crypto_domains):
            return SourceCategory.DOMAIN_SPECIFIC

        # Social
        if any(x in domain for x in ["twitter", "x.com", "reddit", "discord"]):
            return SourceCategory.SOCIAL

        # Fact check
        if any(x in domain for x in ["snopes", "factcheck", "politifact"]):
            return SourceCategory.FACT_CHECK

        return SourceCategory.DOMAIN_SPECIFIC

    def _estimate_credibility(self, url: str) -> float:
        """Estimate credibility score for a URL."""
        domain = urlparse(url).netloc.lower()

        high_cred = [".gov", "reuters", "apnews", "bloomberg", "bbc", "wikipedia"]
        medium_cred = ["coindesk", "cointelegraph", "investopedia", "forbes", "cnbc"]

        if any(x in domain for x in high_cred):
            return 0.9
        elif any(x in domain for x in medium_cred):
            return 0.7
        else:
            return 0.5

    def _parse_response(self, response) -> tuple[Outcome, float, str]:
        """Parse the Gemini response to extract outcome, confidence, and reasoning."""
        try:
            text = response.text if response.text else ""

            # Try to extract JSON from response
            json_match = None
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                if end > start:
                    json_match = text[start:end].strip()
            elif "{" in text and "}" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                json_match = text[start:end]

            if json_match:
                try:
                    data = json.loads(json_match)

                    outcome_str = data.get("outcome", "UNDETERMINED").upper()
                    if outcome_str == "YES":
                        outcome = Outcome.YES
                    elif outcome_str == "NO":
                        outcome = Outcome.NO
                    else:
                        outcome = Outcome.UNDETERMINED

                    confidence = float(data.get("confidence", 0.5))
                    reasoning = data.get("reasoning", text[:500])

                    return outcome, confidence, reasoning
                except json.JSONDecodeError:
                    pass

            # Fallback: parse from text
            text_lower = text.lower()

            if "yes" in text_lower and "no" not in text_lower[:100]:
                outcome = Outcome.YES
                confidence = 0.7
            elif "no" in text_lower and "yes" not in text_lower[:100]:
                outcome = Outcome.NO
                confidence = 0.7
            else:
                outcome = Outcome.UNDETERMINED
                confidence = 0.5

            return outcome, confidence, text[:500]

        except Exception as e:
            logger.warning(f"Error parsing response: {e}")
            return Outcome.UNDETERMINED, 0.0, str(e)

    async def close(self):
        """Cleanup resources."""
        pass
