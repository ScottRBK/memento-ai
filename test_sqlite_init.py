"""
Quick test to verify SQLite initialization works
"""
import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config.settings import settings
from app.repositories.sqlite.sqlite_adapter import SqliteDatabaseAdapter


async def test_sqlite_init():
    """Test SQLite database initialization"""
    print("=" * 60)
    print("Testing SQLite Database Initialization")
    print("=" * 60)

    # Force SQLite mode
    settings.DATABASE = "SQLite"
    settings.SQLITE_MEMORY = True  # Use in-memory for testing
    print("\n✓ Settings configured:")
    print(f"  DATABASE: {settings.DATABASE}")
    print(f"  SQLITE_MEMORY: {settings.SQLITE_MEMORY}")

    # Create adapter
    print("\n✓ Creating SqliteDatabaseAdapter...")
    db_adapter = SqliteDatabaseAdapter()
    print("  Adapter created successfully")

    # Initialize database
    print("\n✓ Initializing database...")
    try:
        await db_adapter.init_db()
        print("  Database initialized successfully")
    except Exception as e:
        print(f"  ✗ Failed to initialize database: {e}")
        raise

    # Test creating a session
    print("\n✓ Testing session creation...")
    from uuid import uuid4

    test_user_id = uuid4()
    try:
        async with db_adapter.session(test_user_id) as session:
            print(f"  Session created successfully for user {test_user_id}")

            # Test a simple query
            from sqlalchemy import text

            result = await session.execute(text("SELECT COUNT(*) FROM users"))
            count = result.scalar()
            print(f"  ✓ Query successful: {count} users in database")

    except Exception as e:
        print(f"  ✗ Session test failed: {e}")
        raise

    # Test vec_memories table exists
    print("\n✓ Testing vec_memories virtual table...")
    try:
        async with db_adapter.system_session() as session:
            result = await session.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='vec_memories'"
                )
            )
            table_name = result.scalar()
            if table_name:
                print("  ✓ vec_memories virtual table exists")
            else:
                print("  ✗ vec_memories table not found")
                raise ValueError("vec_memories table not found")
    except Exception as e:
        print(f"  ✗ vec_memories test failed: {e}")
        raise

    # Cleanup
    print("\n✓ Cleaning up...")
    await db_adapter.dispose()
    print("  Adapter disposed successfully")

    print("\n" + "=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_sqlite_init())
