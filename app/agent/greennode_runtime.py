from app.agent.local_runtime import LocalAgentRuntime
from app.llm import GreenNodeLLMClient
from app.tools import ToolRegistry


class GreenNodeAgentRuntime(LocalAgentRuntime):
    """MSB orchestration hosted as an AgentBase Custom Agent.

    AgentBase supplies the container runtime, IAM identity, endpoint, and
    observability. Business tools remain in-process for the MVP; MaaS performs
    only the constrained recommendation decision.
    """

    runtime_name = "GreenNodeAgentRuntime"

    def __init__(
        self, *, registry: ToolRegistry, llm_client: GreenNodeLLMClient
    ) -> None:
        super().__init__(registry=registry, llm_client=llm_client)

