# 🔌 1024 Prediction Market Oracle Integration Guide

> How to integrate the Multi-Agent Oracle with 1024 Prediction Market for AI-powered settlement

## Overview

This guide covers integrating the AI Oracle with the 1024 Prediction Market for transparent, verifiable market resolution.

### Integration Points

1. **Backend API** - `1024-core/crates/gateway/src/prediction_market_oracle.rs`
2. **Frontend** - `1024-chain-frontend/src/components/prediction/`
3. **On-Chain** - `1024-prediction-market-program/`

### Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /prediction/oracle/resolve` | Trigger AI oracle resolution |
| `GET /prediction/oracle/sources/{id}` | Get detailed sources |

## Quick Start Integration

### Python SDK

```python
from oracle import MultiAgentOracle
from oracle.agents import GeminiDeepResearchAgent

# Initialize oracle
oracle = MultiAgentOracle(
    agents=[
        GeminiDeepResearchAgent(min_sources=50),
        GeminiDeepResearchAgent(min_sources=50),
        GeminiDeepResearchAgent(min_sources=50),
    ],
    consensus_threshold=0.67,
)

# Resolve a market
result = await oracle.resolve(
    question="Did SpaceX land Starship?",
    resolution_criteria="Controlled landing without explosion",
)

# Submit to blockchain (if consensus reached)
if result.reached:
    tx = await oracle.submit_to_chain(
        market_id=123,
        result=result,
    )
    print(f"Submitted: {tx.signature}")
```

### REST API

```bash
# Create resolution request
curl -X POST https://oracle.1024chain.com/api/v1/resolve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "market_id": 123,
    "question": "Did SpaceX land Starship?",
    "resolution_criteria": "Controlled landing without explosion",
    "callback_url": "https://your-app.com/webhook/oracle"
  }'

# Response
{
  "request_id": "req_abc123",
  "status": "processing",
  "estimated_time": 120
}
```

## Integration with 1024 Prediction Market

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    1024 Prediction Market Integration                        │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        1024 Backend (gateway)                          │  │
│  │                                                                        │  │
│  │  /prediction/markets/:id/request-resolution                           │  │
│  │       │                                                               │  │
│  │       │ 1. Trigger resolution                                         │  │
│  │       ↓                                                               │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │                  Multi-Agent Oracle Service                      │  │  │
│  │  │                                                                  │  │  │
│  │  │  • Run 3 Gemini agents in parallel                              │  │  │
│  │  │  • Collect 50+ sources each                                     │  │  │
│  │  │  • Calculate consensus                                          │  │  │
│  │  │  • Store research on IPFS                                       │  │  │
│  │  │                                                                  │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │       │                                                               │  │
│  │       │ 2. Submit result                                              │  │
│  │       ↓                                                               │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │              Prediction Market Program (Solana)                  │  │  │
│  │  │                                                                  │  │  │
│  │  │  ProposeResult {                                                 │  │  │
│  │  │    market_id: 123,                                              │  │  │
│  │  │    outcome: YES,                                                │  │  │
│  │  │    confidence: 8500,  // 85%                                    │  │  │
│  │  │    ipfs_cid: "Qm...",                                           │  │  │
│  │  │    source_count: 155,                                           │  │  │
│  │  │  }                                                              │  │  │
│  │  │                                                                  │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Backend Integration

Add to `1024-core/crates/gateway/src/prediction_market_api.rs`:

```rust
use oracle_client::MultiAgentOracle;

/// POST /prediction/markets/:id/request-resolution
async fn handle_request_resolution(
    State(state): State<PredictionMarketApiState>,
    Path(market_id): Path<i64>,
) -> (StatusCode, Json<ApiResponse<serde_json::Value>>) {
    // Get market details
    let market = state.service.get_market(market_id).await?;
    
    // Initialize oracle client
    let oracle = state.oracle_client.clone();
    
    // Request resolution (async)
    let request_id = oracle.request_resolution(
        market_id,
        &market.question,
        &market.resolution_criteria.unwrap_or_default(),
    ).await?;
    
    (StatusCode::OK, Json(ApiResponse::success(json!({
        "request_id": request_id,
        "status": "processing",
        "message": "Resolution requested, results will be submitted automatically"
    }))))
}

/// Webhook handler for oracle results
async fn handle_oracle_result(
    State(state): State<PredictionMarketApiState>,
    Json(result): Json<OracleResult>,
) -> StatusCode {
    if !result.consensus_reached {
        // Notify admin for manual review
        return StatusCode::ACCEPTED;
    }
    
    // Submit to chain
    let relayer = state.relayer.as_ref().unwrap();
    
    let outcome = match result.outcome.as_str() {
        "YES" => 0,
        "NO" => 1,
        _ => 2,  // Invalid/Undetermined
    };
    
    relayer.propose_oracle_result(
        result.market_id,
        outcome,
        result.confidence,
        &result.ipfs_cid,
        result.source_count,
    ).await?;
    
    StatusCode::OK
}
```

### Rust Oracle Client

```rust
// 1024-core/crates/oracle-client/src/lib.rs

use reqwest::Client;
use serde::{Deserialize, Serialize};

pub struct MultiAgentOracle {
    client: Client,
    base_url: String,
    api_key: String,
}

#[derive(Debug, Serialize)]
pub struct ResolutionRequest {
    pub market_id: i64,
    pub question: String,
    pub resolution_criteria: String,
    pub callback_url: String,
}

#[derive(Debug, Deserialize)]
pub struct ResolutionResponse {
    pub request_id: String,
    pub status: String,
}

#[derive(Debug, Deserialize)]
pub struct OracleResult {
    pub market_id: i64,
    pub outcome: String,
    pub confidence: f64,
    pub agreement_ratio: f64,
    pub source_count: u32,
    pub ipfs_cid: String,
    pub consensus_reached: bool,
}

impl MultiAgentOracle {
    pub fn new(base_url: &str, api_key: &str) -> Self {
        Self {
            client: Client::new(),
            base_url: base_url.to_string(),
            api_key: api_key.to_string(),
        }
    }
    
    pub async fn request_resolution(
        &self,
        market_id: i64,
        question: &str,
        criteria: &str,
    ) -> Result<String, OracleError> {
        let response = self.client
            .post(&format!("{}/api/v1/resolve", self.base_url))
            .header("Authorization", format!("Bearer {}", self.api_key))
            .json(&ResolutionRequest {
                market_id,
                question: question.to_string(),
                resolution_criteria: criteria.to_string(),
                callback_url: std::env::var("ORACLE_CALLBACK_URL")?,
            })
            .send()
            .await?
            .json::<ResolutionResponse>()
            .await?;
        
        Ok(response.request_id)
    }
    
    pub async fn get_result(&self, request_id: &str) -> Result<OracleResult, OracleError> {
        let response = self.client
            .get(&format!("{}/api/v1/result/{}", self.base_url, request_id))
            .header("Authorization", format!("Bearer {}", self.api_key))
            .send()
            .await?
            .json::<OracleResult>()
            .await?;
        
        Ok(response)
    }
}
```

## Custom Integration

### Webhook Integration

Set up a webhook to receive oracle results:

```python
from fastapi import FastAPI, Request
from pydantic import BaseModel

app = FastAPI()

class OracleResult(BaseModel):
    request_id: str
    market_id: int
    outcome: str  # YES, NO, UNDETERMINED
    confidence: float
    agreement_ratio: float
    source_count: int
    ipfs_cid: str
    consensus_reached: bool

@app.post("/webhook/oracle")
async def handle_oracle_result(result: OracleResult):
    """Handle oracle result webhook."""
    
    if not result.consensus_reached:
        # Handle no consensus
        await notify_admin(result)
        return {"status": "needs_review"}
    
    # Update your prediction market
    await your_market_contract.submit_result(
        market_id=result.market_id,
        outcome=result.outcome,
        ipfs_proof=result.ipfs_cid,
    )
    
    return {"status": "processed"}
```

### Polling Integration

If webhooks aren't possible, poll for results:

```python
import asyncio

async def poll_for_result(request_id: str, timeout: int = 300):
    """Poll oracle API for result."""
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        result = await oracle_client.get_result(request_id)
        
        if result.status == "completed":
            return result
        elif result.status == "failed":
            raise OracleError(result.error)
        
        await asyncio.sleep(5)  # Poll every 5 seconds
    
    raise TimeoutError(f"Oracle result not ready after {timeout}s")

# Usage
request_id = await oracle.request_resolution(market_id, question, criteria)
result = await poll_for_result(request_id)
```

## EVM Integration

### Solidity Interface

```solidity
// contracts/interfaces/IMultiAgentOracle.sol

interface IMultiAgentOracle {
    struct OracleResult {
        uint256 marketId;
        uint8 outcome;      // 0=NO, 1=YES, 2=UNDETERMINED
        uint16 confidence;  // 0-10000 (0-100.00%)
        string ipfsCid;
        uint8 agentCount;
        uint16 sourceCount;
        uint16 agreementRatio;
    }
    
    event ResolutionRequested(
        bytes32 indexed requestId,
        uint256 indexed marketId,
        string question
    );
    
    event ResultSubmitted(
        bytes32 indexed requestId,
        uint256 indexed marketId,
        uint8 outcome,
        string ipfsCid
    );
    
    function requestResolution(
        uint256 marketId,
        string calldata question,
        string calldata criteria
    ) external returns (bytes32 requestId);
    
    function getResult(bytes32 requestId) 
        external view returns (OracleResult memory);
    
    function submitResult(
        bytes32 requestId,
        OracleResult calldata result,
        bytes calldata signature
    ) external;
}
```

### Oracle Contract

```solidity
// contracts/MultiAgentOracle.sol

contract MultiAgentOracle is IMultiAgentOracle, Ownable {
    mapping(bytes32 => OracleResult) public results;
    mapping(bytes32 => bool) public resultSubmitted;
    
    address public oracleOperator;
    uint256 public minAgents = 3;
    uint256 public minSources = 50;
    uint256 public minAgreement = 6700; // 67%
    
    function submitResult(
        bytes32 requestId,
        OracleResult calldata result,
        bytes calldata signature
    ) external {
        require(!resultSubmitted[requestId], "Already submitted");
        require(result.agentCount >= minAgents, "Insufficient agents");
        require(result.sourceCount >= minSources, "Insufficient sources");
        require(result.agreementRatio >= minAgreement, "Insufficient agreement");
        
        // Verify operator signature
        bytes32 hash = keccak256(abi.encode(requestId, result));
        require(
            recoverSigner(hash, signature) == oracleOperator,
            "Invalid signature"
        );
        
        results[requestId] = result;
        resultSubmitted[requestId] = true;
        
        emit ResultSubmitted(
            requestId,
            result.marketId,
            result.outcome,
            result.ipfsCid
        );
    }
}
```

## Frontend Integration

### Display Oracle Result

```tsx
// components/OracleResult.tsx

interface OracleResultProps {
  marketId: number;
}

export function OracleResult({ marketId }: OracleResultProps) {
  const { data: result, isLoading } = useOracleResult(marketId);
  
  if (isLoading) return <Spinner />;
  if (!result) return null;
  
  return (
    <div className="oracle-result">
      <h3>Oracle Resolution</h3>
      
      <div className="result-card">
        <div className="outcome">
          <span className={`badge ${result.outcome.toLowerCase()}`}>
            {result.outcome}
          </span>
          <span className="confidence">
            {(result.confidence * 100).toFixed(1)}% confidence
          </span>
        </div>
        
        <div className="stats">
          <div>
            <span>Agents</span>
            <span>{result.agentCount}</span>
          </div>
          <div>
            <span>Agreement</span>
            <span>{(result.agreementRatio * 100).toFixed(0)}%</span>
          </div>
          <div>
            <span>Sources</span>
            <span>{result.sourceCount}</span>
          </div>
        </div>
        
        <a 
          href={`https://ipfs.io/ipfs/${result.ipfsCid}`}
          target="_blank"
          className="view-research"
        >
          View Full Research →
        </a>
      </div>
    </div>
  );
}
```

### Source Viewer

```tsx
// components/ResearchSourceViewer.tsx

interface Source {
  url: string;
  title: string;
  category: string;
  relevance: number;
  citedBy: string[];
}

export function ResearchSourceViewer({ ipfsCid }: { ipfsCid: string }) {
  const { data: research } = useIPFSData(ipfsCid);
  
  const sources = research?.merged_sources || [];
  
  return (
    <div className="source-viewer">
      <h4>Research Sources ({sources.length})</h4>
      
      <div className="source-filters">
        <button>All</button>
        <button>Official ({countByCategory('official')})</button>
        <button>News ({countByCategory('news')})</button>
        <button>Social ({countByCategory('social')})</button>
      </div>
      
      <div className="source-list">
        {sources.map((source, i) => (
          <div key={i} className="source-item">
            <a href={source.url} target="_blank">
              {source.title}
            </a>
            <div className="source-meta">
              <span className={`category ${source.category}`}>
                {source.category}
              </span>
              <span className="cited">
                Cited by {source.citedBy.length} agents
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `INSUFFICIENT_AGENTS` | Less than 3 agents succeeded | Retry or check agent health |
| `NO_CONSENSUS` | Agents disagreed | Requires human review |
| `INSUFFICIENT_SOURCES` | Agent found < 50 sources | May need different search strategy |
| `API_RATE_LIMIT` | Gemini rate limit | Wait and retry |
| `IPFS_UPLOAD_FAILED` | IPFS unavailable | Retry with backup gateway |

### Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=10, max=60),
)
async def resolve_with_retry(oracle, question, criteria):
    """Resolve with automatic retry on failure."""
    return await oracle.resolve(question, criteria)
```

## Security Considerations

1. **API Key Protection**: Never expose API keys in frontend
2. **Signature Verification**: Verify oracle operator signature on-chain
3. **IPFS Pinning**: Pin research data to multiple gateways
4. **Rate Limiting**: Limit resolution requests per market

## Next Steps

1. See [ARCHITECTURE.md](./ARCHITECTURE.md) for system design
2. See [CONSENSUS-ALGORITHM.md](./CONSENSUS-ALGORITHM.md) for consensus details
3. See [GEMINI-API-GUIDE.md](./GEMINI-API-GUIDE.md) for Gemini integration
