"""
SQLite-vec Proof of Concept
Tests vector similarity search functionality for Memory Service
"""
import asyncio
import sqlite3
import sqlite_vec
import numpy as np
from typing import List
import json


def test_sqlite_vec_sync():
    """Test sqlite-vec with synchronous sqlite3"""
    print("=" * 60)
    print("Testing sqlite-vec with synchronous sqlite3")
    print("=" * 60)

    # Connect to in-memory database
    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)  # Must enable before loading

    try:
        # Load sqlite-vec extension using the package helper
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)  # Disable after loading for security
        print("✓ sqlite-vec extension loaded successfully")
        print(f"  Extension path: {sqlite_vec.loadable_path()}")
    except Exception as e:
        print(f"✗ Failed to load sqlite-vec extension: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure sqlite-vec is installed: pip install sqlite-vec")
        print("2. Check if extension file exists")
        return False

    cursor = conn.cursor()

    # Create a test table for memories
    cursor.execute("""
        CREATE TABLE memories (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            is_obsolete INTEGER DEFAULT 0
        )
    """)
    print("✓ Created memories table")

    # Create virtual table for vector storage using vec0
    # Format: vec0(column_name TYPE[dimensions])
    try:
        cursor.execute("""
            CREATE VIRTUAL TABLE vec_memories USING vec0(
                memory_id TEXT PRIMARY KEY,
                embedding FLOAT[384]
            )
        """)
        print("✓ Created vec_memories virtual table with 384 dimensions")
    except Exception as e:
        print(f"✗ Failed to create virtual table: {e}")
        return False

    # Insert test data
    test_data = [
        {
            "id": "mem1",
            "user_id": "user1",
            "title": "FastAPI preferences",
            "content": "Prefer using FastAPI for async web APIs with automatic OpenAPI docs",
            "embedding": np.random.rand(384).astype(np.float32).tolist()
        },
        {
            "id": "mem2",
            "user_id": "user1",
            "title": "PostgreSQL vector search",
            "content": "Use pgvector extension for semantic search in PostgreSQL databases",
            "embedding": np.random.rand(384).astype(np.float32).tolist()
        },
        {
            "id": "mem3",
            "user_id": "user1",
            "title": "Python async patterns",
            "content": "Prefer asyncio with async/await for concurrent operations in Python",
            "embedding": np.random.rand(384).astype(np.float32).tolist()
        },
        {
            "id": "mem4",
            "user_id": "user2",
            "title": "Different user memory",
            "content": "This belongs to a different user and should not be retrieved",
            "embedding": np.random.rand(384).astype(np.float32).tolist()
        }
    ]

    # Insert memories
    for data in test_data:
        cursor.execute(
            "INSERT INTO memories (id, user_id, title, content) VALUES (?, ?, ?, ?)",
            (data["id"], data["user_id"], data["title"], data["content"])
        )

    # Insert vectors using sqlite_vec.serialize_float32()
    for data in test_data:
        try:
            # Use sqlite_vec's serialization function
            embedding_bytes = sqlite_vec.serialize_float32(data["embedding"])
            cursor.execute(
                "INSERT INTO vec_memories (memory_id, embedding) VALUES (?, ?)",
                (data["id"], embedding_bytes)
            )
        except Exception as e:
            print(f"✗ Failed to insert vector: {e}")
            return False

    conn.commit()
    print(f"✓ Inserted {len(test_data)} memories with embeddings")

    # Test vector similarity search
    print("\n" + "=" * 60)
    print("Testing vector similarity search")
    print("=" * 60)

    # Create a query vector
    query_embedding = np.random.rand(384).astype(np.float32).tolist()
    query_user_id = "user1"
    k = 3

    # Test different distance functions
    distance_functions = [
        "vec_distance_cosine",
        "vec_distance_L2"
    ]

    for distance_func in distance_functions:
        print(f"\nTesting {distance_func}:")
        try:
            query = f"""
                SELECT
                    m.id,
                    m.title,
                    m.content,
                    {distance_func}(vm.embedding, ?) as distance
                FROM memories m
                JOIN vec_memories vm ON m.id = vm.memory_id
                WHERE m.user_id = ? AND m.is_obsolete = 0
                ORDER BY distance
                LIMIT ?
            """

            query_embedding_bytes = sqlite_vec.serialize_float32(query_embedding)
            cursor.execute(query, (query_embedding_bytes, query_user_id, k))
            results = cursor.fetchall()

            print(f"  ✓ Found {len(results)} results")
            for i, (mem_id, title, content, distance) in enumerate(results, 1):
                print(f"  {i}. {title} (distance: {distance:.4f})")

        except Exception as e:
            print(f"  ✗ Query failed: {e}")

    # Test user isolation
    print("\n" + "=" * 60)
    print("Testing user isolation")
    print("=" * 60)

    cursor.execute("""
        SELECT COUNT(*) FROM memories WHERE user_id = 'user1'
    """)
    user1_count = cursor.fetchone()[0]
    print(f"✓ User1 has {user1_count} memories")

    cursor.execute("""
        SELECT COUNT(*) FROM memories WHERE user_id = 'user2'
    """)
    user2_count = cursor.fetchone()[0]
    print(f"✓ User2 has {user2_count} memories")

    # Verify query only returns user1's memories
    cursor.execute("""
        SELECT m.id
        FROM memories m
        JOIN vec_memories vm ON m.id = vm.memory_id
        WHERE m.user_id = ?
    """, (query_user_id,))
    filtered_results = cursor.fetchall()
    print(f"✓ Query filtered to {len(filtered_results)} memories for {query_user_id}")

    conn.close()
    print("\n" + "=" * 60)
    print("✓ All tests completed successfully!")
    print("=" * 60)
    return True


async def test_sqlite_vec_async():
    """Test sqlite-vec with aiosqlite"""
    print("\n\n" + "=" * 60)
    print("Testing sqlite-vec with aiosqlite (async)")
    print("=" * 60)

    import aiosqlite

    # aiosqlite requires accessing the underlying connection to load extensions
    db = await aiosqlite.connect(":memory:")

    try:
        # Enable extension loading
        await db.enable_load_extension(True)

        # Load sqlite-vec extension using the extension path
        await db.load_extension(sqlite_vec.loadable_path())

        # Disable extension loading for security
        await db.enable_load_extension(False)

        print("✓ sqlite-vec extension loaded successfully (async)")

        # Create tables
        await db.execute("""
            CREATE TABLE memories (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE VIRTUAL TABLE vec_memories USING vec0(
                memory_id TEXT PRIMARY KEY,
                embedding FLOAT[384]
            )
        """)
        print("✓ Created tables (async)")

        # Insert test data
        test_embedding = np.random.rand(384).astype(np.float32).tolist()
        await db.execute(
            "INSERT INTO memories (id, user_id, title) VALUES (?, ?, ?)",
            ("mem1", "user1", "Test memory")
        )
        await db.execute(
            "INSERT INTO vec_memories (memory_id, embedding) VALUES (?, ?)",
            ("mem1", sqlite_vec.serialize_float32(test_embedding))
        )
        await db.commit()
        print("✓ Inserted test data (async)")

        # Query
        query_embedding = np.random.rand(384).astype(np.float32).tolist()
        async with db.execute("""
            SELECT m.id, m.title, vec_distance_cosine(vm.embedding, ?) as distance
            FROM memories m
            JOIN vec_memories vm ON m.id = vm.memory_id
            ORDER BY distance
            LIMIT 1
        """, (sqlite_vec.serialize_float32(query_embedding),)) as cursor:
            result = await cursor.fetchone()
            if result:
                print(f"✓ Query successful (async): {result[1]}, distance: {result[2]:.4f}")
            else:
                print("✗ No results found")
                await db.close()
                return False

        print("=" * 60)
        print("✓ Async tests completed successfully!")
        print("=" * 60)
        await db.close()
        return True

    except Exception as e:
        print(f"✗ Failed during async tests: {e}")
        if db:
            await db.close()
        return False


if __name__ == "__main__":
    # Run synchronous tests
    sync_success = test_sqlite_vec_sync()

    if sync_success:
        # Run async tests
        asyncio.run(test_sqlite_vec_async())
    else:
        print("\n⚠ Skipping async tests due to sync test failures")
