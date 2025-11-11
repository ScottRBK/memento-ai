"""
POC test to verify environment override mechanism works for e2e tests.

This test disables auto-linking and verifies that:
1. Similar memories are NOT automatically linked
2. Manual linking via link_memories works correctly
"""
import pytest
from fastmcp.client import Client

# Module-level environment override - disables auto-linking for all tests in this file
DOCKER_ENV_OVERRIDE = {
    "MEMORY_NUM_AUTO_LINK": "0"
}


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_auto_linking_disabled_e2e(docker_services, mcp_server_url):
    """
    POC: Verify that MEMORY_NUM_AUTO_LINK=0 actually disables auto-linking

    Creates two very similar memories and verifies they DON'T auto-link,
    proving the environment override mechanism works.
    """
    async with Client(mcp_server_url) as client:
        # Create first memory about Python asyncio
        result1 = await client.call_tool("create_memory", {
            "title": "Python AsyncIO POC Test 1",
            "content": "AsyncIO is Python's framework for concurrent I/O using async/await syntax",
            "context": "POC test - verifying auto-link is disabled",
            "keywords": ["python", "asyncio", "concurrency"],
            "tags": ["python", "poc"],
            "importance": 7
        })

        assert result1.data is not None
        memory1_id = result1.data.id

        # Verify no auto-links were created (should be empty)
        assert result1.data.linked_memory_ids == [], \
            f"Expected no auto-links, but got: {result1.data.linked_memory_ids}"

        # Create second VERY similar memory
        result2 = await client.call_tool("create_memory", {
            "title": "Python AsyncIO POC Test 2",
            "content": "Python's asyncio enables concurrent I/O operations through async/await",
            "context": "POC test - very similar to first memory",
            "keywords": ["python", "asyncio", "concurrent"],
            "tags": ["python", "poc"],
            "importance": 7
        })

        assert result2.data is not None
        memory2_id = result2.data.id

        # Verify no auto-links even though memories are very similar
        assert result2.data.linked_memory_ids == [], \
            f"Expected no auto-links, but got: {result2.data.linked_memory_ids}"

        # Now manually link them
        link_result = await client.call_tool("link_memories", {
            "memory_id": memory1_id,
            "related_ids": [memory2_id]
        })

        # With auto-linking disabled, manual linking should return the ID
        assert link_result.data is not None
        assert isinstance(link_result.data, list)
        assert memory2_id in link_result.data, \
            f"Expected manual link to return [{memory2_id}], got: {link_result.data}"

        # Query to verify the link persists
        query_result = await client.call_tool("query_memory", {
            "query": "Python AsyncIO POC",
            "query_context": "verifying manual link persisted",
            "k": 10,
            "include_links": False
        })

        # Find memory1 and verify it has the link
        found_memory1 = None
        for memory in query_result.data.primary_memories:
            if memory.id == memory1_id:
                found_memory1 = memory
                break

        assert found_memory1 is not None
        assert memory2_id in found_memory1.linked_memory_ids, \
            "Manual link should persist in database"

        print("✅ POC Success: Environment override mechanism works!")
        print(f"   - Auto-linking disabled (MEMORY_NUM_AUTO_LINK=0)")
        print(f"   - Manual linking works correctly")
        print(f"   - Links persist to database")
