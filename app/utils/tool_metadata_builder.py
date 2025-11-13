"""
Tool Metadata Builder

Extracts metadata from FastMCP decorated functions to populate the ToolRegistry.
"""
import inspect
import re
from typing import Any, Callable, Dict, List, Optional, get_args, get_origin, get_type_hints

from app.models.tool_registry_models import (
    ToolCategory,
    ToolDataDetailed,
    ToolParameter,
)


class ToolMetadataBuilder:
    """
    Builds ToolMetadata from FastMCP decorated functions.

    Extracts metadata from function signatures, type hints, and docstrings
    to create complete tool documentation for the registry.
    """

    @staticmethod
    def from_function(
        func: Callable,
        category: ToolCategory,
        examples: Optional[List[str]] = None,
        further_examples: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> ToolDataDetailed:
        """
        Extract metadata from a function decorated with @mcp.tool()

        Args:
            func: The decorated function to extract metadata from
            category: Tool category for organization
            examples: Basic usage examples (list of strings)
            further_examples: Advanced usage examples (list of strings)
            tags: Additional tags for discovery (list of strings)

        Returns:
            ToolDataDetailed with complete metadata including JSON schema

        Example:
            metadata = ToolMetadataBuilder.from_function(
                create_memory,
                category=ToolCategory.MEMORY,
                examples=['create_memory(title="...", ...)'],
                tags=["persistence", "auto-linking"]
            )
        """
        sig = inspect.signature(func)
        docstring = inspect.getdoc(func) or ""
        type_hints = get_type_hints(func)

        # Extract parameters (excluding 'ctx: Context')
        parameters = ToolMetadataBuilder._extract_parameters(sig, type_hints, docstring)

        # Build JSON schema
        json_schema = ToolMetadataBuilder._build_json_schema(sig, type_hints)

        # Extract description (first line or first paragraph)
        description = ToolMetadataBuilder._extract_description(docstring)

        # Extract return type description
        returns = ToolMetadataBuilder._extract_returns(docstring, type_hints)

        return ToolDataDetailed(
            name=func.__name__,
            category=category,
            description=description,
            parameters=parameters,
            returns=returns,
            examples=examples or [],
            tags=tags or [],
            json_schema=json_schema,
            further_examples=further_examples or [],
        )

    @staticmethod
    def _extract_parameters(
        sig: inspect.Signature, type_hints: Dict[str, Any], docstring: str
    ) -> List[ToolParameter]:
        """
        Extract parameter information from function signature and docstring

        Args:
            sig: Function signature from inspect.signature()
            type_hints: Type hints from get_type_hints()
            docstring: Function docstring

        Returns:
            List of ToolParameter objects
        """
        parameters = []
        param_descriptions = ToolMetadataBuilder._parse_arg_descriptions(docstring)

        for param_name, param in sig.parameters.items():
            # Skip Context parameter (MCP infrastructure)
            if param_name == "ctx":
                continue

            # Get type name
            param_type = type_hints.get(param_name, Any)
            type_str = ToolMetadataBuilder._type_to_string(param_type)

            # Get description from docstring
            description = param_descriptions.get(
                param_name, f"Parameter: {param_name}"
            )

            parameters.append(
                ToolParameter(
                    name=param_name, type=type_str, description=description
                )
            )

        return parameters

    @staticmethod
    def _parse_arg_descriptions(docstring: str) -> Dict[str, str]:
        """
        Parse Args section from docstring

        Expects format:
            Args:
                param_name: Description here
                another_param: Another description

        Returns:
            Dictionary mapping parameter names to descriptions
        """
        descriptions = {}

        # Find Args section
        args_match = re.search(
            r"Args:\s*\n((?:\s+\w+:.*\n?)*)", docstring, re.MULTILINE
        )
        if not args_match:
            return descriptions

        args_section = args_match.group(1)

        # Parse individual parameters
        param_pattern = r"^\s+(\w+):\s*(.+?)(?=^\s+\w+:|$)"
        for match in re.finditer(param_pattern, args_section, re.MULTILINE | re.DOTALL):
            param_name = match.group(1)
            description = match.group(2).strip()
            # Clean up multi-line descriptions
            description = re.sub(r"\s+", " ", description)
            descriptions[param_name] = description

        return descriptions

    @staticmethod
    def _extract_description(docstring: str) -> str:
        """
        Extract the description from docstring (first line or before Args section)

        Args:
            docstring: Function docstring

        Returns:
            Description string
        """
        if not docstring:
            return ""

        # Split by sections (Args:, Returns:, etc.)
        lines = docstring.split("\n")
        description_lines = []

        for line in lines:
            # Stop at section headers
            if re.match(r"^\s*(Args|Returns|Raises|Examples?|WHAT|WHEN|BEHAVIOR|NOT-USE):", line):
                break
            description_lines.append(line.strip())

        description = " ".join(description_lines).strip()
        return description

    @staticmethod
    def _extract_returns(docstring: str, type_hints: Dict[str, Any]) -> str:
        """
        Extract return type description

        Args:
            docstring: Function docstring
            type_hints: Type hints dictionary

        Returns:
            Description of return type
        """
        # Try to find Returns section in docstring
        returns_match = re.search(
            r"Returns:\s*\n\s+(.+?)(?=\n\s*\n|\n\s*[A-Z]|\Z)",
            docstring,
            re.MULTILINE | re.DOTALL,
        )
        if returns_match:
            return_desc = returns_match.group(1).strip()
            # Clean up multi-line descriptions
            return_desc = re.sub(r"\s+", " ", return_desc)
            return return_desc

        # Fall back to type hint
        return_type = type_hints.get("return", Any)
        return ToolMetadataBuilder._type_to_string(return_type)

    @staticmethod
    def _type_to_string(type_hint: Any) -> str:
        """
        Convert a type hint to a human-readable string

        Args:
            type_hint: Type hint from get_type_hints()

        Returns:
            String representation of the type
        """
        # Handle None/Any
        if type_hint is type(None):
            return "None"
        if type_hint is Any:
            return "Any"

        # Handle basic types
        if hasattr(type_hint, "__name__"):
            return type_hint.__name__

        # Handle generics (List[str], Dict[str, Any], etc.)
        origin = get_origin(type_hint)
        args = get_args(type_hint)

        if origin is not None:
            origin_name = getattr(origin, "__name__", str(origin))
            if args:
                args_str = ", ".join(
                    ToolMetadataBuilder._type_to_string(arg) for arg in args
                )
                return f"{origin_name}[{args_str}]"
            return origin_name

        # Fallback to string representation
        return str(type_hint)

    @staticmethod
    def _build_json_schema(
        sig: inspect.Signature, type_hints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build JSON Schema for function parameters

        Args:
            sig: Function signature from inspect.signature()
            type_hints: Type hints from get_type_hints()

        Returns:
            JSON Schema dictionary compatible with MCP protocol
        """
        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            # Skip Context parameter
            if param_name == "ctx":
                continue

            # Get type hint
            param_type = type_hints.get(param_name, Any)

            # Build property schema
            prop_schema = ToolMetadataBuilder._type_to_json_schema(param_type)

            properties[param_name] = prop_schema

            # Check if required (no default value)
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        schema = {
            "type": "object",
            "properties": properties,
        }

        if required:
            schema["required"] = required

        return schema

    @staticmethod
    def _type_to_json_schema(type_hint: Any) -> Dict[str, Any]:
        """
        Convert Python type hint to JSON Schema type

        Args:
            type_hint: Type hint from get_type_hints()

        Returns:
            JSON Schema property definition
        """
        # Handle None
        if type_hint is type(None):
            return {"type": "null"}

        # Handle basic types
        if type_hint is str:
            return {"type": "string"}
        if type_hint is int:
            return {"type": "integer"}
        if type_hint is float:
            return {"type": "number"}
        if type_hint is bool:
            return {"type": "boolean"}

        # Handle generics
        origin = get_origin(type_hint)
        args = get_args(type_hint)

        # List
        if origin is list:
            if args:
                item_schema = ToolMetadataBuilder._type_to_json_schema(args[0])
                return {"type": "array", "items": item_schema}
            return {"type": "array"}

        # Dict
        if origin is dict:
            return {"type": "object"}

        # Optional (Union with None)
        if origin is type(None) or (hasattr(origin, "__origin__") and origin.__origin__ is type(None)):
            # Optional[T] is Union[T, None]
            if args and len(args) == 2 and type(None) in args:
                # Get the non-None type
                real_type = args[0] if args[1] is type(None) else args[1]
                return ToolMetadataBuilder._type_to_json_schema(real_type)

        # Fallback for unknown types
        return {"type": "string", "description": f"Type: {type_hint}"}
