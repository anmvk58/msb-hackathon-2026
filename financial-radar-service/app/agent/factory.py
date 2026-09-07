import httpx

from app.agent.greennode_runtime import GreenNodeAgentRuntime
from app.agent.local_runtime import LocalAgentRuntime
from app.agent.runtime import AgentRuntime
from app.config import Settings, get_settings
from app.llm import GreenNodeLLMClient, MockLLMClient
from app.tools import ToolRegistry, build_tool_registry


def _build_llm_client(
    config: Settings, transport: httpx.BaseTransport | None = None
) -> MockLLMClient | GreenNodeLLMClient:
    provider = (config.llm_provider or "mock").lower()
    if provider == "mock":
        return MockLLMClient()
    if provider == "greennode":
        return GreenNodeLLMClient(
            base_url=config.llm_base_url or "",
            model=config.llm_model or "",
            api_key=config.llm_api_key or "",
            timeout_seconds=config.llm_timeout_seconds,
            structured_retries=config.llm_structured_retries,
            transport=transport,
        )
    raise ValueError(f"Unsupported LLM_PROVIDER: {config.llm_provider}")


def build_agent_runtime(
    *,
    settings: Settings | None = None,
    registry: ToolRegistry | None = None,
    llm_transport: httpx.BaseTransport | None = None,
) -> AgentRuntime:
    config = settings or get_settings()
    tools = registry or build_tool_registry()
    llm = _build_llm_client(config, llm_transport)
    if config.agent_runtime == "local":
        return LocalAgentRuntime(registry=tools, llm_client=llm)
    if config.agent_runtime == "greennode":
        if not isinstance(llm, GreenNodeLLMClient):
            raise ValueError("AGENT_RUNTIME=greennode requires LLM_PROVIDER=greennode")
        return GreenNodeAgentRuntime(registry=tools, llm_client=llm)
    raise ValueError(f"Unsupported agent runtime: {config.agent_runtime}")
