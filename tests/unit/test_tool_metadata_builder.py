"""
Unit tests for ToolMetadataBuilder

Tests metadata extraction from function signatures, type hints, and docstrings.
"""
import pytest
from typing import List, Optional

from app.utils.tool_metadata_builder import ToolMetadataBuilder
from app.models.tool_registry_models import ToolCategory, ToolDataDetailed


class TestToolMetadataBuilder:
    """Unit tests for ToolMetadataBuilder class"""

    def test_from_function_extracts_basic_metadata(self):
        """Test extracting basic metadata from a simple function"""

        def sample_tool(name: str, count: int) -> str:
            """A sample tool for testing"""
            return f"{name}: {count}"

        metadata = ToolMetadataBuilder.from_function(
            sample_tool,
            category=ToolCategory.MEMORY,
            examples=["sample_tool('test', 5)"],
            tags=["test"],
        )

        assert metadata.name == "sample_tool"
        assert metadata.category == ToolCategory.MEMORY
        assert "sample tool for testing" in metadata.description.lower()
        assert len(metadata.parameters) == 2
        assert metadata.examples == ["sample_tool('test', 5)"]
        assert metadata.tags == ["test"]

    def test_from_function_excludes_ctx_parameter(self):
        """Test that Context parameter is excluded from metadata"""

        # Simulate Context without importing fastmcp
        class FakeContext:
            pass

        def tool_with_context(param1: str, ctx: FakeContext, param2: int) -> str:
            """Tool with context parameter"""
            return "result"

        metadata = ToolMetadataBuilder.from_function(
            tool_with_context,
            category=ToolCategory.MEMORY,
        )

        # ctx should be excluded
        param_names = [p.name for p in metadata.parameters]
        assert "ctx" not in param_names
        assert "param1" in param_names
        assert "param2" in param_names

    def test_from_function_handles_optional_parameters(self):
        """Test handling of Optional type hints"""

        def tool_with_optional(
            required: str, optional: Optional[int] = None
        ) -> str:
            """Tool with optional parameter"""
            return required

        metadata = ToolMetadataBuilder.from_function(
            tool_with_optional,
            category=ToolCategory.PROJECT,
        )

        assert len(metadata.parameters) == 2

        # Check JSON schema has correct required fields
        assert "required" in metadata.json_schema.get("required", [])
        assert "optional" not in metadata.json_schema.get("required", [])

    def test_from_function_extracts_parameter_descriptions_from_docstring(self):
        """Test extracting parameter descriptions from Args section"""

        def documented_tool(name: str, count: int) -> str:
            """
            A well-documented tool

            Args:
                name: The name to use
                count: The number of items
            """
            return "result"

        metadata = ToolMetadataBuilder.from_function(
            documented_tool,
            category=ToolCategory.MEMORY,
        )

        param_dict = {p.name: p.description for p in metadata.parameters}
        assert "name to use" in param_dict["name"].lower()
        assert "number of items" in param_dict["count"].lower()

    def test_from_function_extracts_returns_from_docstring(self):
        """Test extracting return description from Returns section"""

        def tool_with_returns(value: int) -> str:
            """
            Tool with return documentation

            Args:
                value: Input value

            Returns:
                A formatted string representation
            """
            return str(value)

        metadata = ToolMetadataBuilder.from_function(
            tool_with_returns,
            category=ToolCategory.MEMORY,
        )

        assert "formatted string" in metadata.returns.lower()

    def test_type_to_string_handles_basic_types(self):
        """Test type conversion for basic Python types"""

        assert ToolMetadataBuilder._type_to_string(str) == "str"
        assert ToolMetadataBuilder._type_to_string(int) == "int"
        assert ToolMetadataBuilder._type_to_string(bool) == "bool"
        assert ToolMetadataBuilder._type_to_string(float) == "float"

    def test_type_to_string_handles_list_types(self):
        """Test type conversion for List types"""

        from typing import List

        list_str = ToolMetadataBuilder._type_to_string(List[str])
        # Should return something like "list[str]" or "List[str]"
        assert "list" in list_str.lower()
        # Note: depending on implementation, may just return "List" without args

    def test_type_to_json_schema_basic_types(self):
        """Test JSON Schema generation for basic types"""

        assert ToolMetadataBuilder._type_to_json_schema(str) == {"type": "string"}
        assert ToolMetadataBuilder._type_to_json_schema(int) == {"type": "integer"}
        assert ToolMetadataBuilder._type_to_json_schema(float) == {"type": "number"}
        assert ToolMetadataBuilder._type_to_json_schema(bool) == {"type": "boolean"}

    def test_type_to_json_schema_list_type(self):
        """Test JSON Schema generation for List types"""

        from typing import List

        schema = ToolMetadataBuilder._type_to_json_schema(List[str])
        assert schema["type"] == "array"
        assert schema["items"]["type"] == "string"

    def test_type_to_json_schema_dict_type(self):
        """Test JSON Schema generation for Dict types"""

        from typing import Dict

        schema = ToolMetadataBuilder._type_to_json_schema(Dict[str, int])
        assert schema["type"] == "object"

    def test_build_json_schema_includes_required_fields(self):
        """Test that JSON schema correctly identifies required vs optional fields"""

        def tool_with_defaults(
            required_param: str, optional_param: int = 5
        ) -> str:
            """Tool with default values"""
            return required_param

        import inspect
        from typing import get_type_hints

        sig = inspect.signature(tool_with_defaults)
        type_hints = get_type_hints(tool_with_defaults)

        schema = ToolMetadataBuilder._build_json_schema(sig, type_hints)

        assert "required" in schema
        assert "required_param" in schema["required"]
        assert "optional_param" not in schema["required"]

    def test_from_function_with_complex_docstring(self):
        """Test extracting metadata from tool with WHAT/WHEN/BEHAVIOR format"""

        def complex_tool(query: str, limit: int = 10) -> List[str]:
            """
            Search for items

            WHAT: Performs semantic search across items

            WHEN: User needs to find relevant items

            BEHAVIOR: Returns top-k results ranked by relevance

            Args:
                query: Search query string
                limit: Maximum number of results (default: 10)

            Returns:
                List of matching item names
            """
            return []

        metadata = ToolMetadataBuilder.from_function(
            complex_tool,
            category=ToolCategory.MEMORY,
            examples=["complex_tool('test', 5)"],
            tags=["search"],
        )

        assert metadata.name == "complex_tool"
        assert len(metadata.parameters) == 2
        assert "query" in [p.name for p in metadata.parameters]
        assert "limit" in [p.name for p in metadata.parameters]
        assert "list" in metadata.returns.lower()

    def test_from_function_with_no_docstring(self):
        """Test handling functions without docstrings"""

        def undocumented_tool(param: str) -> str:
            return param

        metadata = ToolMetadataBuilder.from_function(
            undocumented_tool,
            category=ToolCategory.PROJECT,
        )

        assert metadata.name == "undocumented_tool"
        assert len(metadata.parameters) == 1
        # Should have default description for parameter
        assert metadata.parameters[0].description is not None

    def test_from_function_includes_examples_and_further_examples(self):
        """Test that examples and further_examples are included"""

        def example_tool(value: int) -> str:
            """Example tool"""
            return str(value)

        metadata = ToolMetadataBuilder.from_function(
            example_tool,
            category=ToolCategory.MEMORY,
            examples=["example_tool(1)", "example_tool(2)"],
            further_examples=["example_tool(999)"],
        )

        assert len(metadata.examples) == 2
        assert len(metadata.further_examples) == 1
        assert "example_tool(1)" in metadata.examples
        assert "example_tool(999)" in metadata.further_examples

    def test_from_function_validates_is_tooldata_detailed(self):
        """Test that from_function returns ToolDataDetailed instance"""

        def simple_tool() -> str:
            """Simple tool"""
            return "result"

        metadata = ToolMetadataBuilder.from_function(
            simple_tool,
            category=ToolCategory.DOCUMENT,
        )

        assert isinstance(metadata, ToolDataDetailed)
        assert hasattr(metadata, "json_schema")
        assert hasattr(metadata, "further_examples")

    def test_parse_arg_descriptions_handles_multiline(self):
        """Test parsing multiline parameter descriptions"""

        docstring = """
        Tool description

        Args:
            long_param: This is a very long parameter description
                that spans multiple lines and needs to be
                properly concatenated.
        """

        descriptions = ToolMetadataBuilder._parse_arg_descriptions(docstring)

        assert "long_param" in descriptions
        # Multiline should be concatenated to single line
        assert "\n" not in descriptions["long_param"]
        assert "very long parameter" in descriptions["long_param"].lower()

    def test_extract_description_stops_at_section_headers(self):
        """Test that description extraction stops at Args/Returns/etc"""

        docstring = """
        This is the main description.
        It has multiple lines.

        WHAT: Some more text

        Args:
            param: Description
        """

        description = ToolMetadataBuilder._extract_description(docstring)

        # Should stop before WHAT section
        assert "main description" in description.lower()
        assert "WHAT" not in description
        assert "Args" not in description
