from abc import ABC, abstractmethod

from sqlalchemy.orm import Session
from pydantic import BaseModel

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
    ) -> RadarState: ...

    @abstractmethod
    def select(
        self, session: Session, *, recommendation_id: str, option_id: str
    ) -> RadarState: ...

    @abstractmethod
    def confirm(self, session: Session, *, action_id: str, confirmed: bool) -> RadarState: ...

    @abstractmethod
    def prepare_action(
        self,
        session: Session,
        *,
        customer_id: str,
        tool_name: str,
        arguments: dict,
    ) -> RadarState: ...

    @abstractmethod
    def trace_tool(
        self,
        session: Session,
        *,
        customer_id: str,
        tool_name: str,
        arguments: dict,
        signal_id: str | None = None,
        recommendation_id: str | None = None,
    ) -> BaseModel: ...
