"""
Pydantic models for graph visualization and subgraph traversal.

Used by the /api/v1/graph/subgraph endpoint.
"""
from typing import List, Dict, Any, Literal
from pydantic import BaseModel, Field


class SubgraphNode(BaseModel):
    """A node in the subgraph with depth information from center."""

    id: str = Field(
        ...,
        description="Prefixed node ID in format 'memory_123' or 'entity_456'"
    )
    type: Literal["memory", "entity"] = Field(
        ...,
        description="Node type: 'memory' or 'entity'"
    )
    depth: int = Field(
        ...,
        ge=0,
        description="Distance from center node (0 = center node)"
    )
    label: str = Field(
        ...,
        description="Display label (memory title or entity name)"
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Full node data including all relevant fields"
    )


class SubgraphEdge(BaseModel):
    """An edge connecting two nodes in the subgraph."""

    id: str = Field(
        ...,
        description="Unique edge identifier"
    )
    source: str = Field(
        ...,
        description="Source node ID (prefixed)"
    )
    target: str = Field(
        ...,
        description="Target node ID (prefixed)"
    )
    type: Literal["memory_link", "entity_memory", "entity_relationship"] = Field(
        ...,
        description="Edge type indicating relationship kind"
    )
    data: Dict[str, Any] | None = Field(
        default=None,
        description="Additional edge metadata (for entity_relationship: relationship_type, strength, confidence)"
    )


class SubgraphMeta(BaseModel):
    """Metadata about the subgraph traversal result."""

    center_node_id: str = Field(
        ...,
        description="The center node ID used for traversal"
    )
    depth: int = Field(
        ...,
        description="The depth parameter used for traversal"
    )
    node_types: List[str] = Field(
        ...,
        description="Node types included in traversal"
    )
    max_nodes: int = Field(
        ...,
        description="Maximum nodes limit used"
    )
    memory_count: int = Field(
        ...,
        ge=0,
        description="Number of memory nodes in result"
    )
    entity_count: int = Field(
        ...,
        ge=0,
        description="Number of entity nodes in result"
    )
    edge_count: int = Field(
        ...,
        ge=0,
        description="Total number of edges in result"
    )
    memory_link_count: int = Field(
        ...,
        ge=0,
        description="Number of memory-to-memory edges"
    )
    entity_relationship_count: int = Field(
        ...,
        ge=0,
        description="Number of entity-to-entity edges"
    )
    entity_memory_count: int = Field(
        ...,
        ge=0,
        description="Number of entity-to-memory edges"
    )
    truncated: bool = Field(
        False,
        description="True if max_nodes limit was reached and result is incomplete"
    )


class SubgraphResponse(BaseModel):
    """Complete response for subgraph traversal."""

    nodes: List[SubgraphNode] = Field(
        ...,
        description="List of nodes in the subgraph with depth info"
    )
    edges: List[SubgraphEdge] = Field(
        ...,
        description="List of edges between nodes in the subgraph"
    )
    meta: SubgraphMeta = Field(
        ...,
        description="Metadata about the traversal"
    )
