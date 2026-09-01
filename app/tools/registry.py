from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.tools.contracts import BusinessTool, ToolExecutionError, ToolMetadata
from app.tools.implementations import MVP_TOOLS


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BusinessTool] = {}

    def register(self, tool: BusinessTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool name: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BusinessTool:
        try:
            return self._tools[name]
        except KeyError as error:
            raise ToolExecutionError(f"Unknown tool: {name}") from error

    def metadata(self) -> list[ToolMetadata]:
        return [
            ToolMetadata(
                name=tool.name,
                description=tool.description,
                risk_level=tool.risk_level,
                confirmation_policy=tool.confirmation_policy,
                input_schema=tool.input_model.model_json_schema(),
                output_schema=tool.output_model.model_json_schema(),
            )
            for tool in self._tools.values()
        ]

    def validate_input(self, name: str, arguments: dict[str, Any]) -> BaseModel:
        tool = self.get(name)
        try:
            return tool.input_model.model_validate(arguments)
        except ValidationError as error:
            raise ToolExecutionError(f"Invalid input for {name}: {error}") from error

    def execute(self, session: Session, name: str, arguments: dict[str, Any]) -> BaseModel:
        tool = self.get(name)
        validated = self.validate_input(name, arguments)
        output = tool.execute(session, validated)
        return tool.output_model.model_validate(output)


def build_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for tool in MVP_TOOLS:
        registry.register(tool)
    return registry

