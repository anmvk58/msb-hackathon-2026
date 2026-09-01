from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from app.agent.state import RadarState


class AgentRuntime(ABC):
    """Provider-neutral orchestration boundary.

    A GreenNode AgentBase adapter can implement this contract after its official
    Python SDK/runtime request contract is available and configured.
    """

    @abstractmethod
    def run(
        self,
        session: Session,
        *,
        customer_id: str,
        message: str,
        as_of: object,
        selected_option_id: str | None = None,
    ) -> RadarState: ...

    @abstractmethod
    def confirm(self, session: Session, *, action_id: str, confirmed: bool) -> RadarState: ...

