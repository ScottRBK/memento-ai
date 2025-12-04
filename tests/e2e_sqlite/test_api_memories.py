"""
E2E tests for Memory REST API endpoints.

Uses in-memory SQLite for test isolation.
Tests the /api/v1/memories endpoints.
"""
import pytest


class TestMemoryAPIList:
    """Test GET /api/v1/memories endpoint."""

    @pytest.mark.asyncio
    async def test_list_memories_empty(self, http_client):
        """GET /api/v1/memories returns empty list initially."""
        response = await http_client.get("/api/v1/memories")
        assert response.status_code == 200
        data = response.json()
        assert data["memories"] == []
        assert data["total"] == 0
        assert data["limit"] == 20
        assert data["offset"] == 0

    @pytest.mark.asyncio
    async def test_list_memories_with_data(self, http_client):
        """GET /api/v1/memories returns created memories."""
        # Create a memory first
        payload = {
            "title": "Test Memory for List",
            "content": "This is test content for listing.",
            "context": "Testing the list API",
            "keywords": ["test", "api"],
            "tags": ["test"],
            "importance": 7
        }
        create_response = await http_client.post("/api/v1/memories", json=payload)
        assert create_response.status_code == 201

        # Now list
        response = await http_client.get("/api/v1/memories")
        assert response.status_code == 200
        data = response.json()
        assert len(data["memories"]) >= 1
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_with_pagination(self, http_client):
        """GET /api/v1/memories respects limit and offset."""
        # Create 3 memories
        for i in range(3):
            payload = {
                "title": f"Pagination Memory {i}",
                "content": f"Content for pagination test {i}",
                "context": "Pagination test",
                "keywords": ["pagination"],
                "tags": ["test"],
                "importance": 7
            }
            await http_client.post("/api/v1/memories", json=payload)

        # Get first page with limit=2
        response = await http_client.get("/api/v1/memories?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["memories"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0

        # Get second page
        response = await http_client.get("/api/v1/memories?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["memories"]) >= 1
        assert data["offset"] == 2

    @pytest.mark.asyncio
    async def test_list_with_importance_filter(self, http_client):
        """GET /api/v1/memories filters by importance_min."""
        # Create memories with different importance
        await http_client.post("/api/v1/memories", json={
            "title": "Low importance memory",
            "content": "Low importance content",
            "context": "Filter test",
            "keywords": ["filter"],
            "tags": ["test"],
            "importance": 3
        })
        await http_client.post("/api/v1/memories", json={
            "title": "High importance memory",
            "content": "High importance content",
            "context": "Filter test",
            "keywords": ["filter"],
            "tags": ["test"],
            "importance": 9
        })

        # Filter by importance >= 8
        response = await http_client.get("/api/v1/memories?importance_min=8")
        assert response.status_code == 200
        data = response.json()
        for memory in data["memories"]:
            assert memory["importance"] >= 8


class TestMemoryAPICreate:
    """Test POST /api/v1/memories endpoint."""

    @pytest.mark.asyncio
    async def test_create_memory(self, http_client):
        """POST /api/v1/memories creates a new memory."""
        payload = {
            "title": "Created Memory",
            "content": "This is the content of the created memory.",
            "context": "Testing memory creation via API",
            "keywords": ["create", "test"],
            "tags": ["api"],
            "importance": 7
        }
        response = await http_client.post("/api/v1/memories", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["title"] == "Created Memory"

    @pytest.mark.asyncio
    async def test_create_memory_with_optional_project(self, http_client):
        """POST /api/v1/memories accepts project_ids field."""
        # Create memory without project (project_ids is optional)
        payload = {
            "title": "Memory without Project",
            "content": "This memory has no project.",
            "context": "Testing project linking as optional",
            "keywords": ["project"],
            "tags": ["test"],
            "importance": 7,
            "project_ids": []  # Empty list is valid
        }
        response = await http_client.post("/api/v1/memories", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["project_ids"] == []

    @pytest.mark.asyncio
    async def test_create_memory_invalid_body(self, http_client):
        """POST /api/v1/memories returns 400 for invalid body."""
        # Missing required fields
        payload = {"title": "Only Title"}
        response = await http_client.post("/api/v1/memories", json=payload)
        assert response.status_code == 400


class TestMemoryAPIGet:
    """Test GET /api/v1/memories/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_memory(self, http_client):
        """GET /api/v1/memories/{id} returns the memory."""
        # Create a memory first
        payload = {
            "title": "Memory to Get",
            "content": "Content for get test.",
            "context": "Testing get endpoint",
            "keywords": ["get"],
            "tags": ["test"],
            "importance": 7
        }
        create_response = await http_client.post("/api/v1/memories", json=payload)
        memory_id = create_response.json()["id"]

        # Get the memory
        response = await http_client.get(f"/api/v1/memories/{memory_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == memory_id
        assert data["title"] == "Memory to Get"

    @pytest.mark.asyncio
    async def test_get_memory_not_found(self, http_client):
        """GET /api/v1/memories/{id} returns 404 for missing memory."""
        response = await http_client.get("/api/v1/memories/99999")
        assert response.status_code == 404


class TestMemoryAPIUpdate:
    """Test PUT /api/v1/memories/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_memory(self, http_client):
        """PUT /api/v1/memories/{id} updates the memory."""
        # Create a memory
        payload = {
            "title": "Memory to Update",
            "content": "Original content.",
            "context": "Testing update",
            "keywords": ["update"],
            "tags": ["test"],
            "importance": 5
        }
        create_response = await http_client.post("/api/v1/memories", json=payload)
        memory_id = create_response.json()["id"]

        # Update the memory
        update_payload = {"title": "Updated Title", "importance": 9}
        response = await http_client.put(
            f"/api/v1/memories/{memory_id}",
            json=update_payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["importance"] == 9

    @pytest.mark.asyncio
    async def test_update_memory_not_found(self, http_client):
        """PUT /api/v1/memories/{id} returns 404 for missing memory."""
        response = await http_client.put(
            "/api/v1/memories/99999",
            json={"title": "Updated"}
        )
        assert response.status_code == 404


class TestMemoryAPIDelete:
    """Test DELETE /api/v1/memories/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_memory(self, http_client):
        """DELETE /api/v1/memories/{id} marks memory as obsolete."""
        # Create a memory
        payload = {
            "title": "Memory to Delete",
            "content": "Content to delete.",
            "context": "Testing delete",
            "keywords": ["delete"],
            "tags": ["test"],
            "importance": 7
        }
        create_response = await http_client.post("/api/v1/memories", json=payload)
        memory_id = create_response.json()["id"]

        # Delete the memory
        response = await http_client.request(
            "DELETE",
            f"/api/v1/memories/{memory_id}",
            json={"reason": "Test deletion"}
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify it's not in default list (include_obsolete=false)
        list_response = await http_client.get("/api/v1/memories")
        memory_ids = [m["id"] for m in list_response.json()["memories"]]
        assert memory_id not in memory_ids

        # Verify we can still GET the obsolete memory directly
        get_response = await http_client.get(f"/api/v1/memories/{memory_id}")
        assert get_response.status_code == 200
        assert get_response.json()["is_obsolete"] is True
        assert get_response.json()["obsolete_reason"] == "Test deletion"


class TestMemoryAPISearch:
    """Test POST /api/v1/memories/search endpoint."""

    @pytest.mark.asyncio
    async def test_search_memories(self, http_client):
        """POST /api/v1/memories/search performs semantic search."""
        # Create a memory to search for
        payload = {
            "title": "Python Logging Best Practices",
            "content": "Use QueueHandler for async logging to prevent blocking.",
            "context": "Documenting Python logging patterns",
            "keywords": ["python", "logging", "async"],
            "tags": ["pattern"],
            "importance": 8
        }
        await http_client.post("/api/v1/memories", json=payload)

        # Search for it
        search_payload = {
            "query": "python logging async",
            "query_context": "Looking for logging best practices",
            "k": 5
        }
        response = await http_client.post("/api/v1/memories/search", json=search_payload)
        assert response.status_code == 200
        data = response.json()
        assert "primary_memories" in data
        assert "token_count" in data
        assert data["query"] == "python logging async"

    @pytest.mark.asyncio
    async def test_search_invalid_body(self, http_client):
        """POST /api/v1/memories/search returns 400 for invalid body."""
        # Missing required query_context
        response = await http_client.post(
            "/api/v1/memories/search",
            json={"query": "test"}
        )
        assert response.status_code == 400


class TestMemoryAPILinks:
    """Test /api/v1/memories/{id}/links endpoints."""

    @pytest.mark.asyncio
    async def test_link_memories(self, http_client):
        """POST /api/v1/memories/{id}/links creates links."""
        # Create two memories with very different content to avoid auto-linking
        m1 = await http_client.post("/api/v1/memories", json={
            "title": "Astronomy Star Gazing",
            "content": "Observing celestial objects through telescopes.",
            "context": "Hobby related to space",
            "keywords": ["astronomy", "stars"],
            "tags": ["hobby"],
            "importance": 7
        })
        m2 = await http_client.post("/api/v1/memories", json={
            "title": "Baking Bread Recipe",
            "content": "Mix flour, water, yeast, and salt. Knead and bake.",
            "context": "Cooking techniques",
            "keywords": ["baking", "bread"],
            "tags": ["cooking"],
            "importance": 7
        })

        m1_id = m1.json()["id"]
        m2_id = m2.json()["id"]

        # Link them - response indicates newly created links
        response = await http_client.post(
            f"/api/v1/memories/{m1_id}/links",
            json={"related_ids": [m2_id]}
        )
        assert response.status_code == 200

        # Verify the link exists by checking the memory's linked_memory_ids
        get_response = await http_client.get(f"/api/v1/memories/{m1_id}")
        assert get_response.status_code == 200
        assert m2_id in get_response.json()["linked_memory_ids"]

    @pytest.mark.asyncio
    async def test_get_memory_links(self, http_client):
        """GET /api/v1/memories/{id}/links returns linked memories."""
        # Create and link memories
        m1 = await http_client.post("/api/v1/memories", json={
            "title": "Memory with Links",
            "content": "Has linked memories",
            "context": "Testing get links",
            "keywords": ["link"],
            "tags": ["test"],
            "importance": 7
        })
        m2 = await http_client.post("/api/v1/memories", json={
            "title": "Linked Memory",
            "content": "Is linked to first",
            "context": "Testing get links",
            "keywords": ["link"],
            "tags": ["test"],
            "importance": 7
        })

        m1_id = m1.json()["id"]
        m2_id = m2.json()["id"]

        # Create link
        await http_client.post(
            f"/api/v1/memories/{m1_id}/links",
            json={"related_ids": [m2_id]}
        )

        # Get links
        response = await http_client.get(f"/api/v1/memories/{m1_id}/links")
        assert response.status_code == 200
        data = response.json()
        assert data["memory_id"] == m1_id
        linked_ids = [m["id"] for m in data["linked_memories"]]
        assert m2_id in linked_ids

    @pytest.mark.asyncio
    async def test_link_missing_related_ids(self, http_client):
        """POST /api/v1/memories/{id}/links returns 400 without related_ids."""
        # Create a memory
        m = await http_client.post("/api/v1/memories", json={
            "title": "Memory",
            "content": "Content",
            "context": "Test",
            "keywords": ["test"],
            "tags": ["test"],
            "importance": 7
        })
        m_id = m.json()["id"]

        response = await http_client.post(
            f"/api/v1/memories/{m_id}/links",
            json={}
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_link_not_implemented(self, http_client):
        """DELETE /api/v1/memories/{id}/links/{target_id} returns 501."""
        response = await http_client.delete("/api/v1/memories/1/links/2")
        assert response.status_code == 501


class TestMemoryAPIValidation:
    """Test strict query parameter validation - returns 400 on invalid params."""

    @pytest.mark.asyncio
    async def test_list_invalid_limit_returns_400(self, http_client):
        """GET /api/v1/memories?limit=abc returns 400."""
        response = await http_client.get("/api/v1/memories?limit=abc")
        assert response.status_code == 400
        assert "limit" in response.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_list_invalid_offset_returns_400(self, http_client):
        """GET /api/v1/memories?offset=xyz returns 400."""
        response = await http_client.get("/api/v1/memories?offset=xyz")
        assert response.status_code == 400
        assert "offset" in response.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_list_negative_offset_returns_400(self, http_client):
        """GET /api/v1/memories?offset=-5 returns 400."""
        response = await http_client.get("/api/v1/memories?offset=-5")
        assert response.status_code == 400
        assert "offset" in response.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_list_limit_zero_returns_400(self, http_client):
        """GET /api/v1/memories?limit=0 returns 400."""
        response = await http_client.get("/api/v1/memories?limit=0")
        assert response.status_code == 400
        assert "limit" in response.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_list_limit_over_max_returns_400(self, http_client):
        """GET /api/v1/memories?limit=999 returns 400."""
        response = await http_client.get("/api/v1/memories?limit=999")
        assert response.status_code == 400
        assert "limit" in response.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_list_invalid_sort_by_returns_400(self, http_client):
        """GET /api/v1/memories?sort_by=invalid returns 400."""
        response = await http_client.get("/api/v1/memories?sort_by=invalid")
        assert response.status_code == 400
        assert "sort_by" in response.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_list_invalid_sort_order_returns_400(self, http_client):
        """GET /api/v1/memories?sort_order=random returns 400."""
        response = await http_client.get("/api/v1/memories?sort_order=random")
        assert response.status_code == 400
        assert "sort_order" in response.json()["error"].lower()


class TestMemoryAPIIncludeObsolete:
    """Test include_obsolete parameter actually works."""

    @pytest.mark.asyncio
    async def test_include_obsolete_returns_deleted(self, http_client):
        """GET with include_obsolete=true returns soft-deleted memories."""
        # Create a memory
        payload = {
            "title": "Memory to Mark Obsolete",
            "content": "This will be soft deleted.",
            "context": "Testing include_obsolete",
            "keywords": ["obsolete"],
            "tags": ["test"],
            "importance": 7
        }
        create_response = await http_client.post("/api/v1/memories", json=payload)
        assert create_response.status_code == 201
        memory_id = create_response.json()["id"]

        # Delete the memory (soft delete)
        await http_client.request(
            "DELETE",
            f"/api/v1/memories/{memory_id}",
            json={"reason": "Testing obsolete"}
        )

        # Without include_obsolete, should NOT see the memory
        response = await http_client.get("/api/v1/memories")
        memory_ids = [m["id"] for m in response.json()["memories"]]
        assert memory_id not in memory_ids

        # With include_obsolete=true, SHOULD see the memory
        response = await http_client.get("/api/v1/memories?include_obsolete=true")
        memory_ids = [m["id"] for m in response.json()["memories"]]
        assert memory_id in memory_ids


class TestMemoryAPIPagination:
    """Test pagination total count and offset work correctly."""

    @pytest.mark.asyncio
    async def test_pagination_total_reflects_full_count(self, http_client):
        """GET with limit=2 shows total=5 (not total=2) when 5 memories exist."""
        # Create 5 memories
        for i in range(5):
            payload = {
                "title": f"Pagination Total Test {i}",
                "content": f"Content {i}",
                "context": "Pagination total test",
                "keywords": ["pagination"],
                "tags": ["pagination-test"],
                "importance": 7
            }
            await http_client.post("/api/v1/memories", json=payload)

        # Request with limit=2
        response = await http_client.get("/api/v1/memories?limit=2&tags=pagination-test")
        data = response.json()

        assert len(data["memories"]) == 2
        assert data["total"] == 5  # Total should be full count, not limited count
        assert data["limit"] == 2
        assert data["offset"] == 0

    @pytest.mark.asyncio
    async def test_pagination_offset_works(self, http_client):
        """GET with offset=2 skips first 2 memories."""
        # Create 5 memories with unique identifiers
        created_ids = []
        for i in range(5):
            payload = {
                "title": f"Offset Test Memory {i}",
                "content": f"Content for offset test {i}",
                "context": "Offset pagination test",
                "keywords": ["offset-test"],
                "tags": ["offset-test"],
                "importance": 7
            }
            resp = await http_client.post("/api/v1/memories", json=payload)
            created_ids.append(resp.json()["id"])

        # Get first page (no offset)
        first_page = await http_client.get("/api/v1/memories?limit=2&offset=0&tags=offset-test")
        first_page_ids = [m["id"] for m in first_page.json()["memories"]]

        # Get second page (offset=2)
        second_page = await http_client.get("/api/v1/memories?limit=2&offset=2&tags=offset-test")
        second_page_ids = [m["id"] for m in second_page.json()["memories"]]

        # Pages should have no overlap
        assert not set(first_page_ids).intersection(set(second_page_ids))
        assert len(first_page_ids) == 2
        assert len(second_page_ids) == 2


class TestMemoryAPISorting:
    """Test sorting by different fields and orders."""

    @pytest.mark.asyncio
    async def test_sort_by_importance_desc(self, http_client):
        """GET with sort_by=importance&sort_order=desc returns highest first."""
        # Create memories with different importance levels
        for importance in [3, 9, 5]:
            payload = {
                "title": f"Importance {importance} Memory",
                "content": f"Memory with importance {importance}",
                "context": "Sort by importance test",
                "keywords": ["sort"],
                "tags": ["sort-importance"],
                "importance": importance
            }
            await http_client.post("/api/v1/memories", json=payload)

        # Sort by importance descending
        response = await http_client.get(
            "/api/v1/memories?sort_by=importance&sort_order=desc&tags=sort-importance"
        )
        memories = response.json()["memories"]

        # Should be sorted high to low
        importances = [m["importance"] for m in memories]
        assert importances == sorted(importances, reverse=True)
        assert importances[0] == 9  # Highest first

    @pytest.mark.asyncio
    async def test_sort_by_importance_asc(self, http_client):
        """GET with sort_by=importance&sort_order=asc returns lowest first."""
        # Create memories with different importance levels
        for importance in [8, 2, 6]:
            payload = {
                "title": f"Asc Importance {importance}",
                "content": f"Memory with importance {importance}",
                "context": "Sort by importance asc test",
                "keywords": ["sort"],
                "tags": ["sort-importance-asc"],
                "importance": importance
            }
            await http_client.post("/api/v1/memories", json=payload)

        # Sort by importance ascending
        response = await http_client.get(
            "/api/v1/memories?sort_by=importance&sort_order=asc&tags=sort-importance-asc"
        )
        memories = response.json()["memories"]

        # Should be sorted low to high
        importances = [m["importance"] for m in memories]
        assert importances == sorted(importances)
        assert importances[0] == 2  # Lowest first


class TestMemoryAPITagFilter:
    """Test tag filtering with OR logic."""

    @pytest.mark.asyncio
    async def test_filter_by_single_tag(self, http_client):
        """GET with tags=alpha returns only memories with that tag."""
        # Create memories with different tags
        await http_client.post("/api/v1/memories", json={
            "title": "Alpha Only",
            "content": "Has alpha tag",
            "context": "Tag filter test",
            "keywords": ["tag"],
            "tags": ["alpha", "unique-tag-test"],
            "importance": 7
        })
        await http_client.post("/api/v1/memories", json={
            "title": "Beta Only",
            "content": "Has beta tag",
            "context": "Tag filter test",
            "keywords": ["tag"],
            "tags": ["beta", "unique-tag-test"],
            "importance": 7
        })

        # Filter by alpha tag
        response = await http_client.get("/api/v1/memories?tags=alpha")
        memories = response.json()["memories"]

        # Should only include alpha-tagged memory
        titles = [m["title"] for m in memories]
        assert "Alpha Only" in titles
        assert "Beta Only" not in titles

    @pytest.mark.asyncio
    async def test_filter_by_multiple_tags_or_logic(self, http_client):
        """GET with tags=tagA,tagB returns memories with ANY of those tags."""
        # Create memories with different tags
        await http_client.post("/api/v1/memories", json={
            "title": "Has TagA",
            "content": "Has tagA",
            "context": "Multi-tag filter test",
            "keywords": ["multi"],
            "tags": ["tagA", "multi-tag-test"],
            "importance": 7
        })
        await http_client.post("/api/v1/memories", json={
            "title": "Has TagB",
            "content": "Has tagB",
            "context": "Multi-tag filter test",
            "keywords": ["multi"],
            "tags": ["tagB", "multi-tag-test"],
            "importance": 7
        })
        await http_client.post("/api/v1/memories", json={
            "title": "Has TagC",
            "content": "Has tagC only",
            "context": "Multi-tag filter test",
            "keywords": ["multi"],
            "tags": ["tagC", "multi-tag-test"],
            "importance": 7
        })

        # Filter by tagA,tagB (OR logic)
        response = await http_client.get("/api/v1/memories?tags=tagA,tagB")
        memories = response.json()["memories"]
        titles = [m["title"] for m in memories]

        # Should include tagA and tagB memories, but not tagC
        assert "Has TagA" in titles
        assert "Has TagB" in titles
        assert "Has TagC" not in titles
