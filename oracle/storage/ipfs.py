"""
IPFS Storage

Stores research data on IPFS for transparency and verifiability.
"""

import json
import os
from typing import Optional
from datetime import datetime
import httpx
from pydantic import BaseModel, Field
import structlog

from oracle.models import (
    AgentResult,
    ConsensusResult,
    ResearchSource,
    IPFSResearchData,
)

logger = structlog.get_logger()


class IPFSConfig(BaseModel):
    """Configuration for IPFS storage."""
    
    # Web3.Storage API
    web3_storage_token: Optional[str] = Field(
        default=None,
        description="Web3.Storage API token",
    )
    
    # IPFS Gateway
    gateway_url: str = Field(
        default="https://w3s.link",
        description="IPFS gateway URL",
    )
    
    # Pinata (alternative)
    pinata_api_key: Optional[str] = Field(default=None)
    pinata_secret: Optional[str] = Field(default=None)
    
    # Timeout
    timeout_seconds: int = Field(default=60)


class IPFSStorage:
    """
    IPFS storage client for research data.
    
    Supports multiple IPFS providers:
    - Web3.Storage (primary)
    - Pinata (backup)
    - Local IPFS node (development)
    """
    
    def __init__(self, config: Optional[IPFSConfig] = None):
        self.config = config or IPFSConfig(
            web3_storage_token=os.getenv("WEB3_STORAGE_TOKEN"),
            pinata_api_key=os.getenv("PINATA_API_KEY"),
            pinata_secret=os.getenv("PINATA_SECRET"),
        )
        
        self.client = httpx.AsyncClient(timeout=self.config.timeout_seconds)
        
        logger.info(
            "Initialized IPFS storage",
            has_web3_token=bool(self.config.web3_storage_token),
            has_pinata=bool(self.config.pinata_api_key),
        )
    
    async def store_research(
        self,
        market_id: int,
        question: str,
        resolution_criteria: str,
        agent_results: list[AgentResult],
        consensus: ConsensusResult,
        merged_sources: list[ResearchSource],
    ) -> str:
        """
        Store complete research data on IPFS.
        
        Returns:
            IPFS CID (Content Identifier)
        """
        # Build research data
        data = IPFSResearchData(
            version="1.0.0",
            market_id=market_id,
            question=question,
            resolution_criteria=resolution_criteria,
            research_timestamp=datetime.utcnow().isoformat(),
            agents=agent_results,
            consensus=consensus,
            merged_sources=merged_sources,
        )
        
        # Convert to JSON
        json_data = data.to_json()
        
        # Store on IPFS
        cid = await self._upload(json_data, f"oracle-{market_id}.json")
        
        logger.info(
            "Stored research on IPFS",
            market_id=market_id,
            cid=cid,
            size_bytes=len(json_data),
        )
        
        return cid
    
    async def retrieve(self, cid: str) -> IPFSResearchData:
        """
        Retrieve research data from IPFS.
        
        Args:
            cid: IPFS Content Identifier
            
        Returns:
            IPFSResearchData
        """
        url = f"{self.config.gateway_url}/ipfs/{cid}"
        
        response = await self.client.get(url)
        response.raise_for_status()
        
        data = response.json()
        return IPFSResearchData(**data)
    
    async def _upload(self, content: str, filename: str) -> str:
        """Upload content to IPFS."""
        
        # Try Web3.Storage first
        if self.config.web3_storage_token:
            try:
                return await self._upload_web3_storage(content, filename)
            except Exception as e:
                logger.warning(f"Web3.Storage upload failed: {e}")
        
        # Try Pinata
        if self.config.pinata_api_key:
            try:
                return await self._upload_pinata(content, filename)
            except Exception as e:
                logger.warning(f"Pinata upload failed: {e}")
        
        # Fallback: store locally and return mock CID
        logger.warning("No IPFS provider configured, using mock storage")
        return await self._mock_upload(content, filename)
    
    async def _upload_web3_storage(self, content: str, filename: str) -> str:
        """Upload to Web3.Storage."""
        url = "https://api.web3.storage/upload"
        
        headers = {
            "Authorization": f"Bearer {self.config.web3_storage_token}",
            "X-Name": filename,
        }
        
        response = await self.client.post(
            url,
            headers=headers,
            content=content.encode(),
        )
        response.raise_for_status()
        
        result = response.json()
        return result["cid"]
    
    async def _upload_pinata(self, content: str, filename: str) -> str:
        """Upload to Pinata."""
        url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
        
        headers = {
            "pinata_api_key": self.config.pinata_api_key,
            "pinata_secret_api_key": self.config.pinata_secret,
            "Content-Type": "application/json",
        }
        
        payload = {
            "pinataContent": json.loads(content),
            "pinataMetadata": {
                "name": filename,
            },
        }
        
        response = await self.client.post(
            url,
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        
        result = response.json()
        return result["IpfsHash"]
    
    async def _mock_upload(self, content: str, filename: str) -> str:
        """Mock upload for development/testing."""
        import hashlib
        
        # Generate a mock CID based on content hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        mock_cid = f"Qm{content_hash[:44]}"  # Simulates CIDv0 format
        
        # Optionally save to local file for debugging
        debug_dir = os.path.join(os.getcwd(), ".ipfs_mock")
        os.makedirs(debug_dir, exist_ok=True)
        
        filepath = os.path.join(debug_dir, f"{mock_cid}.json")
        with open(filepath, "w") as f:
            f.write(content)
        
        logger.info(f"Mock IPFS: saved to {filepath}")
        
        return mock_cid
    
    def get_gateway_url(self, cid: str) -> str:
        """Get gateway URL for a CID."""
        return f"{self.config.gateway_url}/ipfs/{cid}"
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
