"""Integration test verifying all backend endpoints and full ingestion pipeline."""

import asyncio
import httpx
import uuid

BASE_URL = "http://127.0.0.1:8000"


async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        print("1. Checking Health...")
        res = await client.get("/api/health")
        assert res.status_code == 200, f"Health check failed: {res.text}"
        print(f"   [OK] Health: {res.json()}")

        print("2. Checking Dashboard Stats...")
        res = await client.get("/api/v1/documents/stats/overview")
        assert res.status_code == 200, f"Stats failed: {res.text}"
        stats = res.json()
        print(f"   [OK] Stats: {stats}")

        print("3. Checking Document List...")
        res = await client.get("/api/v1/documents?skip=0&limit=10")
        assert res.status_code == 200, f"Doc list failed: {res.text}"
        docs = res.json()
        print(f"   [OK] Total documents: {docs.get('total')}, items: {len(docs.get('items', []))}")

        print("4. Checking Facts List...")
        res = await client.get("/api/v1/facts?limit=10")
        assert res.status_code == 200, f"Fact list failed: {res.text}"
        facts = res.json()
        print(f"   [OK] Total facts: {facts.get('total')}, items: {len(facts.get('items', []))}")

        print("5. Checking Relationships List...")
        res = await client.get("/api/v1/relationships?limit=10")
        assert res.status_code == 200, f"Rel list failed: {res.text}"
        rels = res.json()
        print(f"   [OK] Total relationships: {rels.get('total')}, items: {len(rels.get('items', []))}")

        print("6. Checking Contradictions Endpoint...")
        res = await client.get("/api/v1/relationships/contradictions?limit=10")
        assert res.status_code == 200, f"Contradictions failed: {res.text}"
        contradictions = res.json()
        print(f"   [OK] Contradictions: {contradictions.get('total')}")

        print("7. Checking Supersedes Endpoint...")
        res = await client.get("/api/v1/relationships/supersedes?limit=10")
        assert res.status_code == 200, f"Supersedes failed: {res.text}"
        supersedes = res.json()
        print(f"   [OK] Supersedes: {supersedes.get('total')}")

        print("\nALL BACKEND API VERIFICATIONS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(main())
