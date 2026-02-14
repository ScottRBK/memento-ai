"""
Scoped Permissions for Meta-Tools

Resolves OAuth-style scopes to sets of permitted tool names.
Two-layer model:
  1. Instance-level ceiling via FORGETFUL_SCOPES env var (default "*")
  2. Per-session restriction via OAuth token `scope` claim (intersection model)

Scope tokens:
  *                -> all tools
  read             -> all tools where mutates=False
  write            -> all tools where mutates=True
  read:<category>  -> category read tools only
  write:<category> -> category write tools only

Categories: users, memories, projects, code_artifacts, documents, entities
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.config.logging_config import logging
from app.models.tool_registry_models import ToolCategory

if TYPE_CHECKING:
    from fastmcp import Context
    from app.routes.mcp.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

# Map ToolCategory enum values to scope category names (plural)
CATEGORY_TO_SCOPE: dict[str, str] = {
    ToolCategory.USER.value: "users",
    ToolCategory.MEMORY.value: "memories",
    ToolCategory.PROJECT.value: "projects",
    ToolCategory.CODE_ARTIFACT.value: "code_artifacts",
    ToolCategory.DOCUMENT.value: "documents",
    ToolCategory.ENTITY.value: "entities",
    ToolCategory.LINKING.value: "entities",  # linking tools are entity-scoped
}

# Reverse map: scope category -> ToolCategory enum values
_SCOPE_TO_CATEGORIES: dict[str, list[str]] = {}
for _cat_value, _scope_name in CATEGORY_TO_SCOPE.items():
    _SCOPE_TO_CATEGORIES.setdefault(_scope_name, []).append(_cat_value)

VALID_ACTIONS = frozenset({"read", "write"})
VALID_CATEGORIES = frozenset(_SCOPE_TO_CATEGORIES.keys())


def parse_scopes(scope_string: str) -> frozenset[str]:
    """Parse and validate a comma-separated scope string.

    Args:
        scope_string: Comma-separated scopes (e.g. "*", "read", "read,write:memories")

    Returns:
        Frozen set of validated scope tokens

    Raises:
        ValueError: If any scope token is invalid
    """
    raw = scope_string.strip()
    if not raw:
        raise ValueError("Scope string cannot be empty")

    tokens = frozenset(t.strip() for t in raw.split(",") if t.strip())
    if not tokens:
        raise ValueError("Scope string cannot be empty")

    for token in tokens:
        if token == "*":
            continue

        if ":" in token:
            parts = token.split(":", 1)
            action, category = parts[0], parts[1]
            if action not in VALID_ACTIONS:
                raise ValueError(
                    f"Invalid scope action '{action}' in '{token}'. "
                    f"Valid actions: {', '.join(sorted(VALID_ACTIONS))}"
                )
            if category not in VALID_CATEGORIES:
                raise ValueError(
                    f"Invalid scope category '{category}' in '{token}'. "
                    f"Valid categories: {', '.join(sorted(VALID_CATEGORIES))}"
                )
        elif token in VALID_ACTIONS:
            # Bare "read" or "write" — applies to all categories
            continue
        else:
            raise ValueError(
                f"Invalid scope token '{token}'. "
                f"Valid formats: *, read, write, read:<category>, write:<category>"
            )

    return tokens


def resolve_permitted_tools(scopes: frozenset[str], registry: ToolRegistry) -> set[str]:
    """Resolve scope tokens to a set of permitted tool names.

    Args:
        scopes: Validated scope tokens from parse_scopes()
        registry: ToolRegistry with registered tools

    Returns:
        Set of tool names permitted by the scopes
    """
    if "*" in scopes:
        return {m.name for m in registry.list_all_tools()}

    permitted: set[str] = set()

    for token in scopes:
        if ":" in token:
            action, scope_category = token.split(":", 1)
            cat_values = _SCOPE_TO_CATEGORIES.get(scope_category, [])
            is_read = action == "read"
            for tool in registry.list_all_tools():
                if tool.category.value in cat_values:
                    if is_read and not tool.mutates:
                        permitted.add(tool.name)
                    elif not is_read and tool.mutates:
                        permitted.add(tool.name)
        elif token == "read":
            for tool in registry.list_all_tools():
                if not tool.mutates:
                    permitted.add(tool.name)
        elif token == "write":
            for tool in registry.list_all_tools():
                if tool.mutates:
                    permitted.add(tool.name)

    return permitted


def get_required_scope(tool_name: str, registry: ToolRegistry) -> str:
    """Get the scope required to access a specific tool (for error messages).

    Args:
        tool_name: Name of the tool
        registry: ToolRegistry instance

    Returns:
        Scope string like "write:memories" or "read:users"
    """
    tool = registry.get_tool(tool_name)
    if not tool:
        return "unknown"

    action = "write" if tool.metadata.mutates else "read"
    scope_category = CATEGORY_TO_SCOPE.get(tool.metadata.category.value, "unknown")
    return f"{action}:{scope_category}"


def get_effective_scopes(ctx: Context) -> tuple[set[str], frozenset[str]]:
    """Resolve effective permitted tools for the current request.

    Intersection model:
    1. Start with instance-level scopes from ctx.fastmcp._instance_permitted_tools
    2. If OAuth token has scopes, intersect with token-level permissions
    3. If no token scopes, fall back to instance-level permissions

    Args:
        ctx: FastMCP Context

    Returns:
        Tuple of (permitted_tool_names, effective_scope_tokens)
    """
    instance_permitted: set[str] = getattr(ctx.fastmcp, "_instance_permitted_tools", None) or set()
    instance_scopes: frozenset[str] = getattr(ctx.fastmcp, "_instance_scopes", frozenset({"*"}))

    if not instance_permitted:
        # Fallback: if not initialized, allow all (backwards compatible)
        all_tools = {m.name for m in ctx.fastmcp.registry.list_all_tools()}
        return all_tools, frozenset({"*"})

    # Check for OAuth token scopes
    token_scopes = _extract_token_scopes(ctx)

    if token_scopes is None:
        # No auth or no scope claim — fall back to instance ceiling
        return set(instance_permitted), instance_scopes

    # Resolve token scopes to tool names and intersect with instance ceiling
    registry: ToolRegistry = ctx.fastmcp.registry
    token_permitted = resolve_permitted_tools(token_scopes, registry)
    effective_permitted = instance_permitted & token_permitted
    effective_scopes = instance_scopes | token_scopes  # Union for display

    logger.debug(
        f"Scope intersection: instance={len(instance_permitted)} tools, "
        f"token={len(token_permitted)} tools, effective={len(effective_permitted)} tools"
    )

    return effective_permitted, effective_scopes


def _extract_token_scopes(ctx: Context) -> frozenset[str] | None:
    """Extract scopes from OAuth access token if present.

    Returns None if no auth is configured or token has no scope claim.
    Token scopes are space-separated per RFC 6749.
    """
    try:
        from fastmcp.server.dependencies import get_access_token
        token = get_access_token()
    except Exception:
        return None

    if token is None:
        return None

    scope_claim = token.claims.get("scope")
    if not scope_claim or not isinstance(scope_claim, str):
        return None

    # RFC 6749: scopes are space-separated
    raw_scopes = scope_claim.strip()
    if not raw_scopes:
        return None

    try:
        # Re-parse as comma-separated (our format) by converting spaces to commas
        return parse_scopes(raw_scopes.replace(" ", ","))
    except ValueError as e:
        logger.warning(f"Invalid scopes in OAuth token: {e}")
        return None
