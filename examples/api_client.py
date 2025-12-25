#!/usr/bin/env python3
"""
API Client example for Multi-Agent Oracle.

This example shows how to use the REST API to request oracle resolutions.

Requirements:
    - Oracle API server running (oracle serve --port 8090)

Usage:
    python examples/api_client.py
"""

import asyncio
import time

import httpx

API_BASE_URL = "http://localhost:8090"


async def main():
    """Demonstrate API client usage."""

    print("🔮 1024 Multi-Agent Oracle - API Client Example")
    print("=" * 50)

    async with httpx.AsyncClient() as client:
        # Health check
        print("\n📡 Checking API health...")
        try:
            response = await client.get(f"{API_BASE_URL}/health")
            health = response.json()
            print(f"   Status: {health['status']}")
            print(f"   Version: {health['version']}")
        except Exception as e:
            print(f"❌ API not available: {e}")
            print("   Make sure the server is running: oracle serve --port 8090")
            return

        # Submit resolution request
        print("\n📤 Submitting resolution request...")
        request_data = {
            "market_id": 12345,
            "question": "Did SpaceX successfully land Starship in December 2025?",
            "resolution_criteria": "Starship must complete controlled landing without rapid unscheduled disassembly (RUD)",
        }

        response = await client.post(
            f"{API_BASE_URL}/api/v1/resolve",
            json=request_data,
        )

        if response.status_code != 200:
            print(f"❌ Request failed: {response.text}")
            return

        result = response.json()
        request_id = result["request_id"]
        print(f"   Request ID: {request_id}")
        print(f"   Status: {result['status']}")
        print(f"   Estimated time: {result['estimated_time_seconds']}s")

        # Poll for result
        print("\n⏳ Waiting for result...")
        max_wait = 300  # 5 minutes
        start_time = time.time()

        while time.time() - start_time < max_wait:
            response = await client.get(f"{API_BASE_URL}/api/v1/result/{request_id}")
            result = response.json()

            if result["status"] == "completed":
                print("\n✅ Resolution completed!")
                print(f"   Outcome: {result['outcome']}")
                print(f"   Confidence: {result['confidence']:.1%}")
                print(f"   Agreement: {result['agreement_ratio']:.0%}")
                print(f"   Sources: {result['source_count']}")
                if result.get("ipfs_cid"):
                    print(f"   IPFS: {result['ipfs_cid']}")
                break

            elif result["status"] == "failed":
                print(f"\n❌ Resolution failed: {result.get('error')}")
                break

            else:
                elapsed = int(time.time() - start_time)
                print(f"   Still processing... ({elapsed}s elapsed)")
                await asyncio.sleep(10)
        else:
            print("\n⚠️ Timeout waiting for result")

        # Synchronous resolution example
        print("\n" + "=" * 50)
        print("📤 Trying synchronous resolution...")

        response = await client.post(
            f"{API_BASE_URL}/api/v1/resolve/sync",
            json={
                "market_id": 99999,
                "question": "Is the sky blue?",
                "resolution_criteria": "The sky appears blue during clear daytime weather",
            },
            timeout=300,
        )

        if response.status_code == 200:
            result = response.json()
            print(f"   Outcome: {result['outcome']}")
            print(f"   Confidence: {result['confidence']:.1%}")
        else:
            print(f"   Failed: {response.text}")

    print("\n✨ Done!")


if __name__ == "__main__":
    asyncio.run(main())
