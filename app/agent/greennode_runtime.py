from app.agent.local_runtime import LocalAgentRuntime
from app.llm import GreenNodeLLMClient
from app.tools import ToolRegistry


class GreenNodeAgentRuntime(LocalAgentRuntime):
    """MSB orchestration hosted as an AgentBase Custom Agent.

    AgentBase hosts and operates the container (lifecycle, endpoint, injected
    identity, and platform observability). This application—not AgentBase—owns
    every RadarState transition, business tool, policy/confirmation decision,
    and constrained MaaS recommendation call.
    """

    runtime_name = "GreenNodeAgentRuntime"

    def __init__(
        self, *, registry: ToolRegistry, llm_client: GreenNodeLLMClient
    ) -> None:
        super().__init__(registry=registry, llm_client=llm_client)
