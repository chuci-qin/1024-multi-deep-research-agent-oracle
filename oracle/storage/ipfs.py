"""
IPFS Storage

Stores research data on IPFS for transparency and verifiability.
Supports Storacha (web3.storage w3up protocol) as the primary storage.
"""

import json
import os
import subprocess
from datetime import datetime

import httpx
import structlog
from pydantic import BaseModel, Field

from oracle.models import (
    AgentResult,
    ConsensusResult,
    IPFSResearchData,
    ResearchSource,
)

logger = structlog.get_logger()


class IPFSConfig(BaseModel):
    """Configuration for IPFS storage."""

    # Storacha (w3up) Space DID - 现在是主要的认证方式
    storacha_space_did: str | None = Field(
        default=None,
        description="Storacha Space DID (did:key:z6Mk...)",
    )

    # Legacy Web3.Storage API token (deprecated but still supported)
    web3_storage_token: str | None = Field(
        default=None,
        description="Web3.Storage API token (deprecated)",
    )

    # IPFS Gateway
    gateway_url: str = Field(
        default="https://w3s.link",
        description="IPFS gateway URL",
    )

    # Pinata (alternative)
    pinata_api_key: str | None = Field(default=None)
    pinata_secret: str | None = Field(default=None)

    # Timeout
    timeout_seconds: int = Field(default=60)
    
    # Enable CLI upload via storacha CLI (recommended for production)
    use_cli: bool = Field(default=True, description="Use storacha CLI for upload")


class IPFSStorage:
    """
    IPFS storage client for research data.

    Supports multiple IPFS providers (priority order):
    1. Storacha via CLI (recommended, uses w3up protocol)
    2. Web3.Storage token (legacy, deprecated)
    3. Pinata (backup)
    4. Local mock storage (development only)
    """

    def __init__(self, config: IPFSConfig | None = None):
        self.config = config or IPFSConfig(
            storacha_space_did=os.getenv("STORACHA_SPACE_DID"),
            web3_storage_token=os.getenv("WEB3_STORAGE_TOKEN"),
            pinata_api_key=os.getenv("PINATA_API_KEY"),
            pinata_secret=os.getenv("PINATA_SECRET"),
            gateway_url=os.getenv("IPFS_GATEWAY", "https://w3s.link"),
            use_cli=os.getenv("STORACHA_USE_CLI", "true").lower() == "true",
        )

        self.client = httpx.AsyncClient(timeout=self.config.timeout_seconds)
        
        # Check if storacha CLI is available and configured
        self._storacha_cli_available = self._check_storacha_cli()
        
        # Determine if real IPFS is available
        has_real_ipfs = (
            self._storacha_cli_available 
            or bool(self.config.web3_storage_token)
            or bool(self.config.pinata_api_key)
        )

        logger.info(
            "Initialized IPFS storage",
            has_storacha_space=bool(self.config.storacha_space_did),
            storacha_cli_available=self._storacha_cli_available,
            has_web3_token=bool(self.config.web3_storage_token),
            has_pinata=bool(self.config.pinata_api_key),
            use_cli=self.config.use_cli,
            real_ipfs_available=has_real_ipfs,
        )
        
        if not has_real_ipfs:
            logger.warning(
                "⚠️ No real IPFS provider configured! Using mock storage.\n"
                "   Data will be stored locally in .ipfs_mock/ directory.\n"
                "   For production, please configure Storacha:"
            )
            print(self.get_setup_instructions())
    
    def _check_storacha_cli(self) -> bool:
        """Check if storacha CLI is installed and configured."""
        try:
            # Check if CLI is installed
            result = subprocess.run(
                ["storacha", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return False
                
            logger.info(f"Storacha CLI available: {result.stdout.strip()}")
            
            # Check if space is configured and has a provider
            space_info = subprocess.run(
                ["storacha", "space", "info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if "Providers: none" in space_info.stdout:
                logger.warning(
                    "⚠️ Storacha space has no storage provider configured!\n"
                    "   To enable real IPFS storage, run these commands:\n"
                    "   1. storacha login\n"
                    "   2. storacha space provision 1024-oracle --customer your-email@example.com\n"
                    "   Using mock storage for now."
                )
                return False
            
            return True
            
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning(f"Storacha CLI not available: {e}")
        return False
    
    def get_setup_instructions(self) -> str:
        """Get instructions for setting up Storacha."""
        return """
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🌐 Storacha IPFS Setup Instructions                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  1. Install Storacha CLI:                                                    ║
║     npm install -g @storacha/cli                                             ║
║                                                                              ║
║  2. Login to your account:                                                   ║
║     storacha login                                                           ║
║     (Follow the email verification)                                          ║
║                                                                              ║
║  3. Create a space (if you don't have one):                                  ║
║     storacha space create "1024-oracle" --no-recovery                        ║
║                                                                              ║
║  4. Add billing/storage provider:                                            ║
║     storacha space provision 1024-oracle --customer your-email@example.com   ║
║                                                                              ║
║  5. Update your .env file:                                                   ║
║     STORACHA_SPACE_DID=did:key:z6Mk...  (from: storacha space ls)            ║
║     STORACHA_USE_CLI=true                                                    ║
║                                                                              ║
║  6. Restart the Oracle service                                               ║
║                                                                              ║
║  📚 Docs: https://storacha.network/docs/                                     ║
║  🎫 Console: https://console.storacha.network/                               ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

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

        # Priority 1: Storacha CLI (recommended, uses w3up protocol)
        if self.config.use_cli and self._storacha_cli_available and self.config.storacha_space_did:
            try:
                return await self._upload_storacha_cli(content, filename)
            except Exception as e:
                logger.warning(f"Storacha CLI upload failed: {e}")

        # Priority 2: Web3.Storage token (legacy)
        if self.config.web3_storage_token:
            try:
                return await self._upload_web3_storage(content, filename)
            except Exception as e:
                logger.warning(f"Web3.Storage upload failed: {e}")

        # Priority 3: Pinata
        if self.config.pinata_api_key:
            try:
                return await self._upload_pinata(content, filename)
            except Exception as e:
                logger.warning(f"Pinata upload failed: {e}")

        # Fallback: store locally and return mock CID
        logger.warning(
            "No IPFS provider configured or all providers failed, using mock storage. "
            "For production, install storacha CLI: npm install -g @storacha/cli"
        )
        return await self._mock_upload(content, filename)

    async def _upload_storacha_cli(self, content: str, filename: str) -> str:
        """
        Upload to Storacha using the CLI tool.
        
        Requires:
        1. npm install -g @storacha/cli
        2. storacha login (one-time authentication)
        3. storacha space use <your-space-did>
        """
        import asyncio
        import tempfile
        
        # Write content to a temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", 
            suffix=".json", 
            delete=False,
            prefix="oracle-"
        ) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            # Use storacha CLI to upload
            # First, ensure we're using the correct space
            space_did = self.config.storacha_space_did
            
            # Select the space (if configured)
            if space_did:
                space_result = await asyncio.to_thread(
                    subprocess.run,
                    ["storacha", "space", "use", space_did],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if space_result.returncode != 0 and "already" not in space_result.stderr.lower():
                    logger.warning(f"Space selection warning: {space_result.stderr}")
            
            # Upload the file
            result = await asyncio.to_thread(
                subprocess.run,
                ["storacha", "up", temp_path, "--json"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            
            if result.returncode != 0:
                raise Exception(f"Storacha CLI upload failed: {result.stderr}")
            
            # Parse the JSON output to get the CID
            try:
                output = json.loads(result.stdout)
                # Storacha CLI returns the root CID
                cid = output.get("root", {}).get("/", output.get("cid", result.stdout.strip()))
                if isinstance(cid, dict):
                    cid = cid.get("/", str(cid))
            except json.JSONDecodeError:
                # Fallback: extract CID from plain text output
                cid = result.stdout.strip().split()[-1]
            
            logger.info(
                "Uploaded to Storacha via CLI",
                filename=filename,
                cid=cid,
                space_did=space_did[:20] + "..." if space_did else None,
            )
            
            return cid
            
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    async def _upload_web3_storage(self, content: str, filename: str) -> str:
        """Upload to Web3.Storage (legacy API, deprecated)."""
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

    async def store_config(self, config_data, filename: str = None) -> str:
        """
        Store oracle config data on IPFS.

        Args:
            config_data: OracleConfigData or any HashableData object
            filename: Optional filename for the upload

        Returns:
            IPFS CID (Content Identifier)
        """
        from oracle.storage.canonical import HashableData

        # Get canonical JSON
        if isinstance(config_data, HashableData):
            json_data = config_data.to_canonical_json()
        else:
            json_data = json.dumps(config_data, sort_keys=True, separators=(",", ":"))

        # Generate filename if not provided
        if filename is None:
            filename = f"oracle-config-{getattr(config_data, 'market_id', 'unknown')}.json"

        # Store on IPFS
        cid = await self._upload(json_data, filename)

        logger.info(
            "Stored config on IPFS",
            filename=filename,
            cid=cid,
            size_bytes=len(json_data),
        )

        return cid

    async def fetch(self, cid: str) -> dict | None:
        """
        Fetch raw JSON data from IPFS.

        Args:
            cid: IPFS Content Identifier

        Returns:
            dict or None if not found
        """
        # First try local mock storage
        mock_dir = os.path.join(os.getcwd(), ".ipfs_mock")
        mock_path = os.path.join(mock_dir, f"{cid}.json")
        if os.path.exists(mock_path):
            with open(mock_path, "r") as f:
                return json.load(f)

        # Try fetching from IPFS gateways
        gateways = [
            self.config.gateway_url,
            "https://w3s.link",
            "https://dweb.link",
            "https://ipfs.io",
        ]

        for gateway in gateways:
            try:
                url = f"{gateway}/ipfs/{cid}"
                response = await self.client.get(url, timeout=10)
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                logger.warning(f"Failed to fetch from {gateway}: {e}")
                continue

        return None

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
