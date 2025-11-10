"""
Models used for tool registry
"""
from enum import Enum
from typing import List, Dict, Any

from pydantic import BaseModel, Field

class ToolCategory(str, Enum):
    """Tool categories for organisation and filtering"""
    MEMORY = "memory"
    PROJECT = "project"
    CODE_ARTIFACT = "code_artifact"
    DOCUMENT = "document"
    LINKING = "linking"
    
class ToolParameter(BaseModel):
    """Parameters metadata for a tool"""
    name: str = Field(...,description="Name of the tool parameter to be passed in executing the tool"
    )
    type: str = Field(..., description="The data type of the parameter")
    description: str = Field(..., description="Describes what the parameter parameter does and how it impacts the behaviour of the method")
    
class ToolMetadata(BaseModel):
    name: str 
    category: ToolCategory
    description: str 
    parameters: List[ToolParameter]
    returns: str
    examples: List[str]
    tags: List[str]
    
class ToolDataDetailed(ToolMetadata):
    json_schema: Dict[str, Any]
    further_examples: List[str]
    
    
