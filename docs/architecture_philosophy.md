# Architecture Philosophy - Protocol-Based Repository Pattern

## TL;DR - The Pattern

```
Service Layer
    ↓ depends on
Repository Protocol (interface contract)
    ↓ implemented by
Concrete Repository (PostgresUserRepository, MongoUserRepository, etc.)
    ↓ internally uses
Adapter (session/transaction management)
```

**Key Principle**: Services depend on **Repository Protocols**, not concrete implementations. Repositories encapsulate adapters as internal implementation details.

**In Practice**: This is your established Kairos/Veridian pattern + Protocols for flexibility.

---

## Quick Example

```python
# Service depends on protocol
class UserService:
    def __init__(self, user_repo: UserRepository):  # Protocol type!
        self.user_repo = user_repo

# Repository implements protocol, uses adapter internally
class PostgresUserRepository:
    def __init__(self, db_adapter: DatabaseAdapter):
        self.db_adapter = db_adapter  # Hidden from service

    async def find_by_id(self, user_id: str) -> Optional[User]:
        async with self.db_adapter.session() as session:
            # Query logic

# Main.py wires it up
db_adapter = PostgresAdapter(settings.DATABASE_URL)
user_repo = PostgresUserRepository(db_adapter=db_adapter)
user_service = UserService(user_repo=user_repo)
```

---

## Why This Pattern?

### Problems It Solves

1. **Multiple storage backends** - Swap Postgres for MongoDB without changing services
2. **Testing simplicity** - Mock repository protocol, not adapters
3. **Clean separation** - Services don't know about infrastructure (adapters)
4. **Flexibility** - Protocol = contract, implementation = details

### What Makes It Different from Traditional Patterns

**Traditional Repository Pattern:**
```python
# Service depends on concrete repository class
class UserService:
    def __init__(self, user_repo: PostgresUserRepository):  # Concrete!
        self.user_repo = user_repo
```
❌ **Problem**: Tightly coupled to Postgres implementation

**This Pattern (Protocol-Based):**
```python
# Service depends on protocol interface
class UserService:
    def __init__(self, user_repo: UserRepository):  # Protocol!
        self.user_repo = user_repo
```
✅ **Benefit**: Any implementation of UserRepository works (Postgres, Mongo, Mock, etc.)

---

## Layer Breakdown

### Layer 1: Adapter (Infrastructure)

**Responsibility**: Connection lifecycle, session management, transaction boundaries

**Location**: `app/adapters/`

#### Adapter Protocol
```python
# app/adapters/protocols.py
from typing import Protocol, AsyncContextManager, Any

class DatabaseAdapter(Protocol):
    """Contract for database infrastructure"""

    async def session(self) -> AsyncContextManager[Any]:
        """Provide session with auto-commit/rollback"""
        ...

    async def init_db(self) -> None:
        """Initialize database schema"""
        ...

    async def health_check(self) -> bool:
        """Check connection health"""
        ...

    async def close(self) -> None:
        """Cleanup connections"""
        ...
```

#### Concrete Implementation
```python
# app/adapters/postgres_adapter.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy import text

class PostgresAdapter:
    """Postgres implementation of DatabaseAdapter protocol"""

    def __init__(self, connection_string: str):
        self.engine = create_async_engine(
            connection_string,
            pool_pre_ping=True,
            echo=False
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    @asynccontextmanager
    async def session(self):
        """Provide session with transaction management"""
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def init_db(self):
        """Initialize database schema"""
        async with self.engine.begin() as conn:
            # Create extensions if needed
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            # Create tables from SQLAlchemy models
            await conn.run_sync(Base.metadata.create_all)

    async def health_check(self) -> bool:
        """Check database connection"""
        try:
            async with self.session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def close(self):
        """Cleanup connections"""
        await self.engine.dispose()
```

---

### Layer 2: Repository (Data Access)

**Responsibility**: CRUD operations, queries, data transformation

**Location**: `app/repositories/`

#### Repository Protocol
```python
# app/repositories/protocols.py
from typing import Protocol, Optional, List
from app.models.models import User

class UserRepository(Protocol):
    """Contract for user data access"""

    async def find_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        ...

    async def find_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        ...

    async def find_all(self, limit: int = 100, offset: int = 0) -> List[User]:
        """List users with pagination"""
        ...

    async def create(self, user: User) -> User:
        """Create new user"""
        ...

    async def update(self, user_id: str, updates: dict) -> Optional[User]:
        """Update user"""
        ...

    async def delete(self, user_id: str) -> bool:
        """Delete user"""
        ...
```

#### Concrete Implementation
```python
# app/repositories/user_repository.py
from typing import Optional, List
from sqlalchemy import select, update, delete
from app.adapters.protocols import DatabaseAdapter
from app.models.models import User

class PostgresUserRepository:
    """
    Postgres implementation of UserRepository protocol.

    Adapter is encapsulated - service layer never sees it.
    """

    def __init__(self, db_adapter: DatabaseAdapter):
        """
        Inject adapter at construction.

        Args:
            db_adapter: Database adapter for session management
        """
        self.db_adapter = db_adapter

    async def find_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        async with self.db_adapter.session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            return result.scalar_one_or_none()

    async def find_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        async with self.db_adapter.session() as session:
            result = await session.execute(
                select(User).where(User.email == email)
            )
            return result.scalar_one_or_none()

    async def find_all(self, limit: int = 100, offset: int = 0) -> List[User]:
        """List users with pagination"""
        async with self.db_adapter.session() as session:
            result = await session.execute(
                select(User).limit(limit).offset(offset)
            )
            return list(result.scalars().all())

    async def create(self, user: User) -> User:
        """Create new user"""
        async with self.db_adapter.session() as session:
            session.add(user)
            await session.flush()  # Get ID before commit
            await session.refresh(user)  # Ensure all fields populated
            return user

    async def update(self, user_id: str, updates: dict) -> Optional[User]:
        """Update user"""
        async with self.db_adapter.session() as session:
            # Fetch existing
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                return None

            # Apply updates
            for key, value in updates.items():
                if hasattr(user, key):
                    setattr(user, key, value)

            await session.flush()
            await session.refresh(user)
            return user

    async def delete(self, user_id: str) -> bool:
        """Delete user"""
        async with self.db_adapter.session() as session:
            result = await session.execute(
                delete(User).where(User.id == user_id)
            )
            return result.rowcount > 0
```

#### Alternative Implementation (MongoDB Example)
```python
# app/repositories/user_repository_mongo.py
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorClient
from app.models.models import User

class MongoUserRepository:
    """
    MongoDB implementation of UserRepository protocol.

    Different infrastructure, same interface!
    """

    def __init__(self, mongo_client: AsyncIOMotorClient, database: str = "myapp"):
        self.client = mongo_client
        self.db = self.client[database]
        self.users = self.db.users

    async def find_by_id(self, user_id: str) -> Optional[User]:
        doc = await self.users.find_one({"_id": user_id})
        return User(**doc) if doc else None

    async def find_by_email(self, email: str) -> Optional[User]:
        doc = await self.users.find_one({"email": email})
        return User(**doc) if doc else None

    async def find_all(self, limit: int = 100, offset: int = 0) -> List[User]:
        cursor = self.users.find().skip(offset).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [User(**doc) for doc in docs]

    async def create(self, user: User) -> User:
        doc = user.dict()
        await self.users.insert_one(doc)
        return user

    async def update(self, user_id: str, updates: dict) -> Optional[User]:
        result = await self.users.find_one_and_update(
            {"_id": user_id},
            {"$set": updates},
            return_document=True
        )
        return User(**result) if result else None

    async def delete(self, user_id: str) -> bool:
        result = await self.users.delete_one({"_id": user_id})
        return result.deleted_count > 0
```

---

### Layer 3: Service (Business Logic)

**Responsibility**: Business rules, validation, orchestration

**Location**: `app/services/`

```python
# app/services/user_service.py
from typing import Optional
from app.repositories.protocols import UserRepository  # Protocol import!
from app.models.models import User
import bcrypt

class UserService:
    """
    User business logic.

    Depends on UserRepository protocol - doesn't know about:
    - Which database (Postgres, Mongo, etc.)
    - Adapters or infrastructure
    - Implementation details
    """

    def __init__(self, user_repo: UserRepository):
        """
        Inject repository via protocol.

        Args:
            user_repo: Any implementation of UserRepository protocol
        """
        self.user_repo = user_repo

    async def get_user(self, user_id: str) -> Optional[dict]:
        """
        Get user by ID.

        Business logic: Convert to dict for API response
        """
        user = await self.user_repo.find_by_id(user_id)
        return user.to_dict() if user else None

    async def register_user(self, email: str, password: str, name: str) -> dict:
        """
        Register new user.

        Business logic:
        - Validate email is unique
        - Hash password
        - Create user
        """
        # Business rule: Email must be unique
        existing = await self.user_repo.find_by_email(email)
        if existing:
            raise ValueError(f"User with email {email} already exists")

        # Business logic: Hash password
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        # Create user
        user = User(
            email=email,
            password_hash=password_hash,
            name=name
        )

        created = await self.user_repo.create(user)
        return created.to_dict()

    async def update_user(self, user_id: str, updates: dict) -> Optional[dict]:
        """
        Update user.

        Business logic: Validate updates before applying
        """
        # Business rule: Can't change email to existing email
        if "email" in updates:
            existing = await self.user_repo.find_by_email(updates["email"])
            if existing and existing.id != user_id:
                raise ValueError("Email already in use")

        # Business rule: If changing password, hash it
        if "password" in updates:
            updates["password_hash"] = bcrypt.hashpw(
                updates.pop("password").encode(),
                bcrypt.gensalt()
            ).decode()

        updated = await self.user_repo.update(user_id, updates)
        return updated.to_dict() if updated else None

    async def delete_user(self, user_id: str) -> bool:
        """Delete user"""
        return await self.user_repo.delete(user_id)

    async def authenticate(self, email: str, password: str) -> Optional[dict]:
        """
        Authenticate user.

        Business logic: Verify password hash
        """
        user = await self.user_repo.find_by_email(email)
        if not user:
            return None

        # Verify password
        if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            return None

        return user.to_dict()
```

---

## Application Integration

### Main Application Setup

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException
from app.config.settings import settings
from app.adapters.postgres_adapter import PostgresAdapter
from app.repositories.user_repository import PostgresUserRepository
from app.services.user_service import UserService
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize application dependencies on startup.

    Wiring: Adapter → Repository → Service
    """
    logger.info(f"Starting {settings.SERVICE_NAME}")

    # 1. Initialize adapters (infrastructure layer)
    db_adapter = PostgresAdapter(settings.DATABASE_URL)
    await db_adapter.init_db()
    logger.info("Database adapter initialized")

    # 2. Initialize repositories (inject adapters)
    user_repo = PostgresUserRepository(db_adapter=db_adapter)
    logger.info("Repositories initialized")

    # 3. Initialize services (inject repositories)
    user_service = UserService(user_repo=user_repo)
    logger.info("Services initialized")

    # Store in app state for dependency injection
    app.state.db_adapter = db_adapter
    app.state.user_service = user_service

    yield

    # Cleanup on shutdown
    logger.info("Shutting down adapters")
    await db_adapter.close()
    logger.info("Shutdown complete")

app = FastAPI(
    title=settings.SERVICE_NAME,
    description=settings.SERVICE_DESCRIPTION,
    version=settings.SERVICE_VERSION,
    lifespan=lifespan
)

# Dependency injection functions
def get_user_service(request: Request) -> UserService:
    """Get user service from app state"""
    return request.app.state.user_service

# API endpoints
@app.get("/users/{user_id}")
async def get_user(
    user_id: str,
    user_service: UserService = Depends(get_user_service)
):
    """Get user by ID"""
    user = await user_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/users/register")
async def register_user(
    email: str,
    password: str,
    name: str,
    user_service: UserService = Depends(get_user_service)
):
    """Register new user"""
    try:
        user = await user_service.register_user(email, password, name)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/users/{user_id}")
async def update_user(
    user_id: str,
    updates: dict,
    user_service: UserService = Depends(get_user_service)
):
    """Update user"""
    try:
        user = await user_service.update_user(user_id, updates)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    user_service: UserService = Depends(get_user_service)
):
    """Delete user"""
    deleted = await user_service.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deleted"}
```

---

## Testing Strategy

### Unit Testing Services

Mock the repository protocol - no infrastructure needed!

```python
# tests/unit/test_user_service.py
import pytest
from app.services.user_service import UserService
from app.models.models import User

class MockUserRepository:
    """Mock repository - implements protocol without infrastructure"""

    def __init__(self):
        self.users = {}
        self.next_id = 1

    async def find_by_id(self, user_id: str):
        return self.users.get(user_id)

    async def find_by_email(self, email: str):
        for user in self.users.values():
            if user.email == email:
                return user
        return None

    async def find_all(self, limit: int = 100, offset: int = 0):
        return list(self.users.values())[offset:offset + limit]

    async def create(self, user: User):
        user.id = str(self.next_id)
        self.next_id += 1
        self.users[user.id] = user
        return user

    async def update(self, user_id: str, updates: dict):
        user = self.users.get(user_id)
        if user:
            for key, value in updates.items():
                setattr(user, key, value)
        return user

    async def delete(self, user_id: str):
        if user_id in self.users:
            del self.users[user_id]
            return True
        return False


@pytest.mark.asyncio
async def test_register_user_success():
    """Test successful user registration"""
    mock_repo = MockUserRepository()
    service = UserService(user_repo=mock_repo)

    user = await service.register_user(
        email="test@example.com",
        password="password123",
        name="Test User"
    )

    assert user["email"] == "test@example.com"
    assert user["name"] == "Test User"
    assert "password" not in user  # Password should be hashed


@pytest.mark.asyncio
async def test_register_user_duplicate_email():
    """Test registration with duplicate email fails"""
    mock_repo = MockUserRepository()
    service = UserService(user_repo=mock_repo)

    # Register first user
    await service.register_user("test@example.com", "password123", "User 1")

    # Try to register with same email
    with pytest.raises(ValueError, match="already exists"):
        await service.register_user("test@example.com", "password456", "User 2")


@pytest.mark.asyncio
async def test_authenticate_success():
    """Test successful authentication"""
    mock_repo = MockUserRepository()
    service = UserService(user_repo=mock_repo)

    # Register user
    await service.register_user("test@example.com", "password123", "Test User")

    # Authenticate
    user = await service.authenticate("test@example.com", "password123")

    assert user is not None
    assert user["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_authenticate_wrong_password():
    """Test authentication with wrong password"""
    mock_repo = MockUserRepository()
    service = UserService(user_repo=mock_repo)

    # Register user
    await service.register_user("test@example.com", "password123", "Test User")

    # Try wrong password
    user = await service.authenticate("test@example.com", "wrongpassword")

    assert user is None
```

### Integration Testing Repositories

Test with real database adapter:

```python
# tests/integration/test_user_repository.py
import pytest
from app.adapters.postgres_adapter import PostgresAdapter
from app.repositories.user_repository import PostgresUserRepository
from app.models.models import User

@pytest.fixture
async def db_adapter():
    """Create test database adapter"""
    adapter = PostgresAdapter("postgresql+asyncpg://test:test@localhost/test_db")
    await adapter.init_db()
    yield adapter
    await adapter.close()

@pytest.fixture
async def user_repo(db_adapter):
    """Create user repository with test adapter"""
    return PostgresUserRepository(db_adapter=db_adapter)


@pytest.mark.asyncio
async def test_create_and_find_user(user_repo):
    """Test creating and retrieving user"""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        name="Test User"
    )

    created = await user_repo.create(user)
    assert created.id is not None

    found = await user_repo.find_by_id(created.id)
    assert found.email == "test@example.com"


@pytest.mark.asyncio
async def test_update_user(user_repo):
    """Test updating user"""
    user = User(email="test@example.com", password_hash="hash", name="Old Name")
    created = await user_repo.create(user)

    updated = await user_repo.update(created.id, {"name": "New Name"})

    assert updated.name == "New Name"


@pytest.mark.asyncio
async def test_delete_user(user_repo):
    """Test deleting user"""
    user = User(email="test@example.com", password_hash="hash", name="Test")
    created = await user_repo.create(user)

    deleted = await user_repo.delete(created.id)
    assert deleted is True

    found = await user_repo.find_by_id(created.id)
    assert found is None
```

---

## Swapping Implementations

The protocol pattern makes it trivial to swap implementations:

### Switch to MongoDB

```python
# app/main.py
from motor.motor_asyncio import AsyncIOMotorClient
from app.repositories.user_repository_mongo import MongoUserRepository

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Use MongoDB instead of Postgres
    mongo_client = AsyncIOMotorClient(settings.MONGODB_URL)
    user_repo = MongoUserRepository(mongo_client=mongo_client)

    # Service doesn't change!
    user_service = UserService(user_repo=user_repo)

    app.state.user_service = user_service
    yield

    mongo_client.close()
```

### Use Multiple Implementations

```python
# Different repositories for different entities
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Postgres for users (transactional data)
    db_adapter = PostgresAdapter(settings.DATABASE_URL)
    user_repo = PostgresUserRepository(db_adapter=db_adapter)

    # MongoDB for analytics (document data)
    mongo_client = AsyncIOMotorClient(settings.MONGODB_URL)
    analytics_repo = MongoAnalyticsRepository(mongo_client=mongo_client)

    # Services can use different storage backends!
    user_service = UserService(user_repo=user_repo)
    analytics_service = AnalyticsService(analytics_repo=analytics_repo)

    # ...
```

---

## Benefits Summary

| Aspect | Benefit |
|--------|---------|
| **Separation of Concerns** | Service → Business Logic, Repository → Data Access, Adapter → Infrastructure |
| **Flexibility** | Swap storage backends without changing services |
| **Testing** | Mock repositories easily, no infrastructure needed for unit tests |
| **Type Safety** | Protocols provide compile-time checking (mypy) |
| **No Coupling** | Services don't know about adapters or infrastructure details |
| **Consistency** | Matches Kairos/Veridian pattern you already use |

---

## When to Use This Pattern

**Use this pattern when:**
- Building microservices with potential for multiple storage backends
- You want clean separation between business logic and infrastructure
- Testing is important (easy mocking)
- Team is familiar with dependency injection

**This pattern is ideal for:**
- FastAPI/FastMCP microservices
- Services that might scale/evolve storage needs
- Projects requiring high test coverage
- Clean architecture advocates

---

## Comparison to Other Patterns

### vs. Traditional Repository (No Protocols)
```python
# Traditional - tightly coupled
class UserService:
    def __init__(self, user_repo: PostgresUserRepository):  # Concrete type!
        self.user_repo = user_repo
```
❌ Can't swap implementations without changing service

### vs. Direct Adapter Usage
```python
# Anti-pattern - service uses adapter directly
class UserService:
    def __init__(self, db_adapter: DatabaseAdapter):
        self.db = db_adapter

    async def get_user(self, user_id: str):
        async with self.db.session() as session:
            result = await session.execute(...)  # SQL in service!
```
❌ Business logic mixed with data access

### This Pattern - Protocol-Based
```python
# Clean - protocol interface
class UserService:
    def __init__(self, user_repo: UserRepository):  # Protocol!
        self.user_repo = user_repo
```
✅ Flexible, testable, clean separation

---

## Migration from Existing Code

If you have existing Kairos/Veridian code:

1. **Extract protocol** from repository class
2. **Keep repository implementation** exactly the same
3. **Update service type hints** to use protocol
4. **Done!** - No other changes needed

```python
# Before
class PostgresUserRepository:
    # ... existing code

class UserService:
    def __init__(self, user_repo: PostgresUserRepository):  # Concrete
        self.user_repo = user_repo

# After - Add protocol
class UserRepository(Protocol):
    async def find_by_id(self, user_id: str) -> Optional[User]: ...
    # ... other methods

class PostgresUserRepository:
    # ... same implementation, no changes!

class UserService:
    def __init__(self, user_repo: UserRepository):  # Protocol!
        self.user_repo = user_repo
```

---

## Key Takeaways

1. **Services depend on Repository Protocols** - not concrete implementations
2. **Repositories encapsulate Adapters** - infrastructure hidden from services
3. **Adapters manage infrastructure** - connections, sessions, transactions
4. **Wiring happens in main.py** - Adapter → Repository → Service
5. **This is Kairos/Veridian + Protocols** - same pattern, more flexibility

The pattern maintains clean separation while adding the flexibility to swap implementations when needed.
