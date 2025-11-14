"""
Models used for tool registry
"""
from enum import Enum
from typing import List, Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass

from pydantic import BaseModel, Field

class ToolCategory(str, Enum):
    """Tool categories for organisation and filtering"""
    USER = "user"
    MEMORY = "memory"
    PROJECT = "project"
    CODE_ARTIFACT = "code_artifact"
    DOCUMENT = "document"
    ENTITY = "entity"
    LINKING = "linking"

class ToolParameter(BaseModel):
    """Parameters metadata for a tool"""
    name: str = Field(..., description="Name of the tool parameter to be passed in executing the tool")
    type: str = Field(..., description="The data type of the parameter")
    description: str = Field(..., description="Describes what the parameter does and how it impacts the behaviour of the method")
    required: bool = Field(default=False, description="Whether this parameter is required")
    default: Optional[Any] = Field(default=None, description="Default value if parameter is not provided")
    example: Optional[Any] = Field(default=None, description="Example value for this parameter")

class ToolMetadata(BaseModel):
    """Complete metadata for a tool"""
    name: str
    category: ToolCategory
    description: str
    parameters: List[ToolParameter]
    returns: str
    examples: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)

    def to_discovery_dict(self) -> Dict[str, Any]:
        """Returns minimal info for discover_tools (lightweight)"""
        return {
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "parameters": {
                param.name: {
                    "type": param.type,
                    "required": param.required,
                    "description": param.description,
                    "example": param.example
                }
                for param in self.parameters
            },
            "returns": self.returns,
            "example": self.examples[0] if self.examples else None
        }

    def to_detailed_dict(self) -> Dict[str, Any]:
        """Returns full info for how_to_use (comprehensive)"""
        return {
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "parameters": [
                {
                    "name": param.name,
                    "type": param.type,
                    "description": param.description,
                    "required": param.required,
                    "default": param.default,
                    "example": param.example,
                }
                for param in self.parameters
            ],
            "returns": self.returns,
            "examples": self.examples,
            "tags": self.tags,
            "json_schema": self._generate_json_schema()
        }

    def _generate_json_schema(self) -> Dict[str, Any]:
        """Generate JSON schema for tool parameters"""
        properties = {}
        required = []

        for param in self.parameters:
            # Skip ctx parameter in schema (internal use)
            if param.name == "ctx":
                continue

            properties[param.name] = {
                "description": param.description,
                "type": self._map_python_type_to_json_type(param.type),
            }

            if param.example is not None:
                properties[param.name]["example"] = param.example

            if param.required:
                required.append(param.name)

        schema = {
            "type": "object",
            "properties": properties,
        }

        if required:
            schema["required"] = required

        return schema

    def _map_python_type_to_json_type(self, python_type: str) -> str:
        """Map Python type hints to JSON schema types"""
        # Handle Optional types
        if python_type.startswith("Optional["):
            inner_type = python_type[9:-1]  # Extract inner type
            return self._map_python_type_to_json_type(inner_type)

        # Handle List types
        if python_type.startswith("List["):
            return "array"

        # Handle Dict types
        if python_type.startswith("Dict["):
            return "object"

        # Basic type mappings
        type_map = {
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "dict": "object",
            "list": "array",
        }

        return type_map.get(python_type.lower(), "string")

class ToolDataDetailed(ToolMetadata):
    """Extended tool metadata with additional examples (for backwards compatibility)"""
    json_schema: Dict[str, Any]
    further_examples: List[str] = Field(default_factory=list)


@dataclass
class ToolImplementation:
    """Stores tool metadata alongside its callable implementation"""
    metadata: ToolMetadata
    implementation: Callable[..., Awaitable[Any]]
    
    
