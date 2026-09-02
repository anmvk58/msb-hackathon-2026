import httpx

from app.agent.greennode_runtime import GreenNodeAgentRuntime
from app.agent.local_runtime import LocalAgentRuntime
from app.agent.runtime import AgentRuntime
from app.config import Settings, get_settings
from app.llm import GreenNodeLLMClient, MockLLMClient
from app.tools import ToolRegistry, build_tool_registry


def build_agent_runtime(
    *,
    settings: Settings | None = None,
    registry: ToolRegistry | None = None,
    llm_transport: httpx.BaseTransport | None = None,
) -> AgentRuntime:
    config = settings or get_settings()
    tools = registry or build_tool_registry()
    if config.agent_runtime == "local":
        return LocalAgentRuntime(registry=tools, llm_client=MockLLMClient())
    if config.agent_runtime == "greennode":
        llm = GreenNodeLLMClient(
            base_url=config.llm_base_url or "",
            model=config.llm_model or "",
            api_key=config.llm_api_key or "",
            timeout_seconds=config.llm_timeout_seconds,
            structured_retries=config.llm_structured_retries,
            transport=llm_transport,
        )
        return GreenNodeAgentRuntime(registry=tools, llm_client=llm)
    raise ValueError(f"Unsupported agent runtime: {config.agent_runtime}")
