"""
Integration test fixtures with in-memory stubs (no real database required)
"""
import pytest
import hashlib
import random
from typing import List
from uuid import UUID, uuid4
from datetime import datetime, timezone

from app.models.user_models import User, UserCreate, UserUpdate
from app.models.memory_models import Memory, MemoryCreate, MemoryUpdate
from app.models.project_models import Project, ProjectCreate, ProjectUpdate, ProjectSummary, ProjectStatus
from app.models.code_artifact_models import CodeArtifact, CodeArtifactCreate, CodeArtifactUpdate, CodeArtifactSummary
from app.models.document_models import Document, DocumentCreate, DocumentUpdate, DocumentSummary
from app.protocols.user_protocol import UserRepository
from app.protocols.memory_protocol import MemoryRepository
from app.protocols.project_protocol import ProjectRepository
from app.protocols.code_artifact_protocol import CodeArtifactRepository
from app.protocols.document_protocol import DocumentRepository
from app.services.user_service import UserService
from app.services.memory_service import MemoryService
from app.services.project_service import ProjectService
from app.services.code_artifact_service import CodeArtifactService
from app.services.document_service import DocumentService


class InMemoryUserRepository(UserRepository):
    """In-memory implementation of UserRepository for testing"""

    def __init__(self):
        self._users: dict[UUID, User] = {}
        self._external_id_index: dict[str, UUID] = {}

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        return self._users.get(user_id)

    async def get_user_by_external_id(self, external_id: str) -> User | None:
        user_id = self._external_id_index.get(external_id)
        if user_id:
            return self._users.get(user_id)
        return None

    async def create_user(self, user: UserCreate) -> User:
        user_id = uuid4()
        now = datetime.now(timezone.utc)

        new_user = User(
            id=user_id,
            external_id=user.external_id,
            name=user.name,
            email=user.email,
            notes=user.notes,
            idp_metadata=user.idp_metadata,
            created_at=now,
            updated_at=now
        )

        self._users[user_id] = new_user
        self._external_id_index[user.external_id] = user_id
        return new_user

    async def update_user(self, user_id: UUID, updated_user: UserUpdate) -> User | None:
        user = self._users.get(user_id)
        if not user:
            return None

        # Update fields
        update_data = updated_user.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field != "external_id":  # Don't update external_id
                setattr(user, field, value)

        user.updated_at = datetime.now(timezone.utc)
        return user


@pytest.fixture
def clean_test_data():
    """Fixture that provides a clean slate for each test"""
    # Setup: nothing needed
    yield
    # Teardown: nothing needed (new instance per test)


@pytest.fixture
def mock_user_repository():
    """Provides an in-memory user repository"""
    return InMemoryUserRepository()


@pytest.fixture
def test_user_service(mock_user_repository):
    """Provides a UserService with in-memory repository"""
    return UserService(mock_user_repository)


# ============ Memory Testing Fixtures ============


class MockEmbeddingsAdapter:
    """Mock embeddings adapter that returns deterministic 384-dim vectors"""

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    async def embed_text(self, text: str) -> List[float]:
        """Generate deterministic embeddings from text using hash-based seeding"""
        # Use MD5 hash for reproducibility (same text -> same embedding)
        hash_value = hashlib.md5(text.encode()).hexdigest()
        seed = int(hash_value[:8], 16)
        random.seed(seed)

        # Generate normalized vector
        vector = [random.random() for _ in range(self.dimensions)]

        # Normalize to unit length (typical for embeddings)
        magnitude = sum(x ** 2 for x in vector) ** 0.5
        normalized = [x / magnitude for x in vector]

        return normalized


class InMemoryMemoryRepository(MemoryRepository):
    """In-memory implementation of MemoryRepository for testing"""

    def __init__(self):
        self._memories: dict[UUID, dict[int, Memory]] = {}  # user_id -> {memory_id -> Memory}
        self._links: dict[int, set[int]] = {}  # memory_id -> set of linked memory_ids
        self._next_id = 1

    async def create_memory(self, user_id: UUID, memory: MemoryCreate) -> Memory:
        """Create a new memory"""
        memory_id = self._next_id
        self._next_id += 1

        now = datetime.now(timezone.utc)

        new_memory = Memory(
            id=memory_id,
            title=memory.title,
            content=memory.content,
            context=memory.context,
            keywords=memory.keywords,
            tags=memory.tags,
            importance=memory.importance,
            project_ids=memory.project_ids or [],
            code_artifact_ids=memory.code_artifact_ids or [],
            document_ids=memory.document_ids or [],
            linked_memory_ids=[],
            created_at=now,
            updated_at=now
        )

        if user_id not in self._memories:
            self._memories[user_id] = {}

        self._memories[user_id][memory_id] = new_memory
        self._links[memory_id] = set()

        return new_memory

    async def get_memory_by_id(self, user_id: UUID, memory_id: int) -> Memory | None:
        """Retrieve memory by ID"""
        user_memories = self._memories.get(user_id, {})
        return user_memories.get(memory_id)

    async def search(
        self,
        user_id: UUID,
        query: str,
        query_context: str,
        k: int,
        importance_threshold: int | None,
        project_ids: List[int] | None,
        exclude_ids: List[int] | None = None
    ) -> List[Memory]:
        """Mock semantic search - returns memories sorted by importance"""
        user_memories = self._memories.get(user_id, {})

        memories = list(user_memories.values())

        # Filter out obsolete memories (soft delete)
        memories = [m for m in memories if not m.is_obsolete]

        # Apply filters
        if importance_threshold:
            memories = [m for m in memories if m.importance >= importance_threshold]

        if project_ids:
            memories = [m for m in memories if any(pid in m.project_ids for pid in project_ids)]

        if exclude_ids:
            memories = [m for m in memories if m.id not in exclude_ids]

        # Sort by importance (higher first) then by created_at (newer first)
        memories.sort(key=lambda m: (m.importance, m.created_at), reverse=True)

        return memories[:k]

    async def find_similar_memories(
        self,
        user_id: UUID,
        memory_id: int,
        max_links: int
    ) -> List[Memory]:
        """Find similar memories - uses keyword overlap as proxy for similarity"""
        user_memories = self._memories.get(user_id, {})

        source = user_memories.get(memory_id)
        if not source:
            return []

        # Get all memories except the source memory, filtering out obsolete memories
        candidates = [m for m in user_memories.values() if m.id != memory_id and not m.is_obsolete]

        # Calculate similarity based on keyword overlap
        similar = []
        for candidate in candidates:
            # Count overlapping keywords
            overlap = len(set(source.keywords) & set(candidate.keywords))
            # Only consider similar if there's at least 1 overlapping keyword
            if overlap > 0:
                similar.append(candidate)

        # Sort by importance
        similar.sort(key=lambda m: m.importance, reverse=True)

        return similar[:max_links]

    async def create_links_batch(
        self,
        user_id: UUID,
        source_id: int,
        target_ids: List[int]
    ) -> List[int]:
        """Create bidirectional links between memories"""
        if not target_ids:
            return []

        # Verify source exists
        source = await self.get_memory_by_id(user_id, source_id)
        if not source:
            return []

        created_links = []

        for target_id in target_ids:
            # Skip self-links
            if target_id == source_id:
                continue

            # Verify target exists
            target = await self.get_memory_by_id(user_id, target_id)
            if not target:
                continue

            # Ensure both source and target have link sets
            if source_id not in self._links:
                self._links[source_id] = set()
            if target_id not in self._links:
                self._links[target_id] = set()

            # Create bidirectional links
            if target_id not in self._links[source_id]:
                self._links[source_id].add(target_id)
                self._links[target_id].add(source_id)

                # Update linked_memory_ids in both memories
                source.linked_memory_ids.append(target_id)
                target.linked_memory_ids.append(source_id)

                created_links.append(target_id)

        return created_links

    async def get_linked_memories(
        self,
        user_id: UUID,
        memory_id: int,
        project_ids: List[int] | None,
        max_links: int = 5
    ) -> List[Memory]:
        """Get linked memories (1-hop neighbors)"""
        linked_ids = self._links.get(memory_id, set())

        memories = []
        for linked_id in linked_ids:
            memory = await self.get_memory_by_id(user_id, linked_id)
            if memory:
                # Filter out obsolete memories (soft delete)
                if memory.is_obsolete:
                    continue

                # Apply project filter if specified
                if project_ids:
                    if any(pid in memory.project_ids for pid in project_ids):
                        memories.append(memory)
                else:
                    memories.append(memory)

            if len(memories) >= max_links:
                break

        return memories

    async def update_memory(
        self,
        user_id: UUID,
        memory_id: int,
        updated_memory: MemoryUpdate,
        existing_memory: Memory,
        search_fields_changed: bool,
    ) -> Memory | None:
        """Update an existing memory"""
        memory = await self.get_memory_by_id(user_id, memory_id)
        if not memory:
            return None

        # Update fields
        update_data = updated_memory.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(memory, field, value)

        memory.updated_at = datetime.now(timezone.utc)
        return memory

    async def mark_obsolete(
        self,
        user_id: UUID,
        memory_id: int,
        reason: str,
        superseded_by: int | None = None
    ) -> bool:
        """Mark memory as obsolete (soft delete)"""
        memory = await self.get_memory_by_id(user_id, memory_id)
        if not memory:
            return False

        # Mark as obsolete but keep in storage for audit trail
        from datetime import datetime, timezone
        memory.is_obsolete = True
        memory.obsolete_reason = reason
        memory.superseded_by = superseded_by
        memory.obsoleted_at = datetime.now(timezone.utc)

        return True


@pytest.fixture
def mock_embeddings_adapter():
    """Provides a mock embeddings adapter"""
    return MockEmbeddingsAdapter(dimensions=384)


@pytest.fixture
def mock_memory_repository():
    """Provides an in-memory memory repository"""
    return InMemoryMemoryRepository()


@pytest.fixture
def test_memory_service(mock_memory_repository):
    """Provides a MemoryService with in-memory repository"""
    return MemoryService(mock_memory_repository)


# ============ Project Testing Fixtures ============


class InMemoryProjectRepository(ProjectRepository):
    """In-memory implementation of ProjectRepository for testing"""

    def __init__(self):
        self._projects: dict[UUID, dict[int, Project]] = {}  # user_id -> {project_id -> Project}
        self._next_id = 1
        # Track memories per project for memory_count calculation
        self._project_memories: dict[int, set[int]] = {}  # project_id -> set of memory_ids

    async def list_projects(
        self,
        user_id: UUID,
        status: ProjectStatus | None = None,
        repo_name: str | None = None
    ) -> List[ProjectSummary]:
        """List projects with optional filtering"""
        user_projects = self._projects.get(user_id, {})

        projects = list(user_projects.values())

        # Apply filters
        if status:
            projects = [p for p in projects if p.status == status]

        if repo_name:
            projects = [p for p in projects if p.repo_name == repo_name]

        # Sort by creation date (newest first)
        projects.sort(key=lambda p: p.created_at, reverse=True)

        # Convert to ProjectSummary
        summaries = [
            ProjectSummary(
                id=p.id,
                name=p.name,
                project_type=p.project_type,
                status=p.status,
                repo_name=p.repo_name,
                memory_count=p.memory_count,
                created_at=p.created_at,
                updated_at=p.updated_at
            )
            for p in projects
        ]

        return summaries

    async def get_project_by_id(
        self,
        user_id: UUID,
        project_id: int
    ) -> Project | None:
        """Get single project by ID"""
        user_projects = self._projects.get(user_id, {})
        return user_projects.get(project_id)

    async def create_project(
        self,
        user_id: UUID,
        project_data: ProjectCreate
    ) -> Project:
        """Create new project"""
        project_id = self._next_id
        self._next_id += 1

        now = datetime.now(timezone.utc)

        new_project = Project(
            id=project_id,
            name=project_data.name,
            description=project_data.description,
            project_type=project_data.project_type,
            status=project_data.status,
            repo_name=project_data.repo_name,
            notes=project_data.notes,
            memory_count=0,
            created_at=now,
            updated_at=now
        )

        if user_id not in self._projects:
            self._projects[user_id] = {}

        self._projects[user_id][project_id] = new_project
        self._project_memories[project_id] = set()

        return new_project

    async def update_project(
        self,
        user_id: UUID,
        project_id: int,
        project_data: ProjectUpdate
    ) -> Project:
        """Update existing project"""
        project = await self.get_project_by_id(user_id, project_id)
        if not project:
            from app.exceptions import NotFoundError
            raise NotFoundError(f"Project with id {project_id} not found")

        # Update fields using PATCH semantics
        update_data = project_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(project, field, value)

        project.updated_at = datetime.now(timezone.utc)
        return project

    async def delete_project(
        self,
        user_id: UUID,
        project_id: int
    ) -> bool:
        """Delete project"""
        user_projects = self._projects.get(user_id, {})
        if project_id in user_projects:
            del user_projects[project_id]
            # Clean up memory tracking
            if project_id in self._project_memories:
                del self._project_memories[project_id]
            return True
        return False


@pytest.fixture
def mock_project_repository():
    """Provides an in-memory project repository"""
    return InMemoryProjectRepository()


@pytest.fixture
def test_project_service(mock_project_repository):
    """Provides a ProjectService with in-memory repository"""
    return ProjectService(mock_project_repository)


# ============ Code Artifact Testing Fixtures ============


class InMemoryCodeArtifactRepository(CodeArtifactRepository):
    """In-memory implementation of CodeArtifactRepository for testing"""

    def __init__(self):
        self._artifacts: dict[UUID, dict[int, CodeArtifact]] = {}
        self._next_id = 1

    async def create_code_artifact(self, user_id: UUID, artifact_data: CodeArtifactCreate) -> CodeArtifact:
        artifact_id = self._next_id
        self._next_id += 1
        now = datetime.now(timezone.utc)

        new_artifact = CodeArtifact(
            id=artifact_id,
            title=artifact_data.title,
            description=artifact_data.description,
            code=artifact_data.code,
            language=artifact_data.language.lower(),
            tags=artifact_data.tags,
            project_id=None,
            created_at=now,
            updated_at=now
        )

        if user_id not in self._artifacts:
            self._artifacts[user_id] = {}
        self._artifacts[user_id][artifact_id] = new_artifact
        return new_artifact

    async def get_code_artifact_by_id(self, user_id: UUID, artifact_id: int) -> CodeArtifact | None:
        user_artifacts = self._artifacts.get(user_id, {})
        return user_artifacts.get(artifact_id)

    async def list_code_artifacts(
        self, user_id: UUID, project_id: int | None = None, language: str | None = None, tags: List[str] | None = None
    ) -> List[CodeArtifactSummary]:
        user_artifacts = self._artifacts.get(user_id, {})
        artifacts = list(user_artifacts.values())

        if project_id is not None:
            artifacts = [a for a in artifacts if a.project_id == project_id]
        if language:
            artifacts = [a for a in artifacts if a.language == language.lower()]
        if tags:
            artifacts = [a for a in artifacts if any(t in a.tags for t in tags)]

        artifacts.sort(key=lambda a: a.created_at, reverse=True)
        return [CodeArtifactSummary.model_validate(a) for a in artifacts]

    async def update_code_artifact(self, user_id: UUID, artifact_id: int, artifact_data: CodeArtifactUpdate) -> CodeArtifact:
        artifact = await self.get_code_artifact_by_id(user_id, artifact_id)
        if not artifact:
            from app.exceptions import NotFoundError
            raise NotFoundError(f"Code artifact {artifact_id} not found")

        update_data = artifact_data.model_dump(exclude_unset=True)
        if "language" in update_data and update_data["language"]:
            update_data["language"] = update_data["language"].lower()

        for field, value in update_data.items():
            setattr(artifact, field, value)
        artifact.updated_at = datetime.now(timezone.utc)
        return artifact

    async def delete_code_artifact(self, user_id: UUID, artifact_id: int) -> bool:
        user_artifacts = self._artifacts.get(user_id, {})
        if artifact_id in user_artifacts:
            del user_artifacts[artifact_id]
            return True
        return False


@pytest.fixture
def mock_code_artifact_repository():
    return InMemoryCodeArtifactRepository()


@pytest.fixture
def test_code_artifact_service(mock_code_artifact_repository):
    return CodeArtifactService(mock_code_artifact_repository)


# ============ Document Testing Fixtures ============


class InMemoryDocumentRepository(DocumentRepository):
    """In-memory implementation of DocumentRepository for testing"""

    def __init__(self):
        self._documents: dict[UUID, dict[int, Document]] = {}
        self._next_id = 1

    async def create_document(self, user_id: UUID, document_data: DocumentCreate) -> Document:
        document_id = self._next_id
        self._next_id += 1
        now = datetime.now(timezone.utc)

        size_bytes = document_data.size_bytes or len(document_data.content.encode('utf-8'))

        new_document = Document(
            id=document_id,
            title=document_data.title,
            description=document_data.description,
            content=document_data.content,
            document_type=document_data.document_type,
            filename=document_data.filename,
            size_bytes=size_bytes,
            tags=document_data.tags,
            project_id=None,
            created_at=now,
            updated_at=now
        )

        if user_id not in self._documents:
            self._documents[user_id] = {}
        self._documents[user_id][document_id] = new_document
        return new_document

    async def get_document_by_id(self, user_id: UUID, document_id: int) -> Document | None:
        user_documents = self._documents.get(user_id, {})
        return user_documents.get(document_id)

    async def list_documents(
        self, user_id: UUID, project_id: int | None = None, document_type: str | None = None, tags: List[str] | None = None
    ) -> List[DocumentSummary]:
        user_documents = self._documents.get(user_id, {})
        documents = list(user_documents.values())

        if project_id is not None:
            documents = [d for d in documents if d.project_id == project_id]
        if document_type:
            documents = [d for d in documents if d.document_type == document_type]
        if tags:
            documents = [d for d in documents if any(t in d.tags for t in tags)]

        documents.sort(key=lambda d: d.created_at, reverse=True)
        return [DocumentSummary.model_validate(d) for d in documents]

    async def update_document(self, user_id: UUID, document_id: int, document_data: DocumentUpdate) -> Document:
        document = await self.get_document_by_id(user_id, document_id)
        if not document:
            from app.exceptions import NotFoundError
            raise NotFoundError(f"Document {document_id} not found")

        update_data = document_data.model_dump(exclude_unset=True)
        if "content" in update_data and update_data["content"]:
            update_data["size_bytes"] = len(update_data["content"].encode('utf-8'))

        for field, value in update_data.items():
            setattr(document, field, value)
        document.updated_at = datetime.now(timezone.utc)
        return document

    async def delete_document(self, user_id: UUID, document_id: int) -> bool:
        user_documents = self._documents.get(user_id, {})
        if document_id in user_documents:
            del user_documents[document_id]
            return True
        return False


@pytest.fixture
def mock_document_repository():
    return InMemoryDocumentRepository()


@pytest.fixture
def test_document_service(mock_document_repository):
    return DocumentService(mock_document_repository)
