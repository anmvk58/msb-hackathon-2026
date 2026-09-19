from importlib import import_module
from types import SimpleNamespace

from app.main import ChatIntentDecision, ChatMessage, FinancialChatRequest


main = import_module("app.main")


def test_chat_uses_structured_llm_intent_to_change_action(monkeypatch) -> None:
    captured = {}

    class FakeLLM:
        def generate_structured(self, **kwargs):
            captured.update(kwargs)
            return ChatIntentDecision(intent="ACCEPT_M_SINH_LOI", reply="Đã hiểu yêu cầu của bạn.")

    context = SimpleNamespace(
        customer=SimpleNamespace(preferred_safe_balance=5000000),
        accounts=[SimpleNamespace(account_type="PAYMENT", available_balance=30000000)],
        m_sinh_loi=None,
    )
    scan = SimpleNamespace(result=SimpleNamespace(analysis={"risk_flags": {"idle_cash": True}}, recommendations=[]))
    monkeypatch.setattr(main.registry.gateway, "get_financial_context", lambda customer_id: context)
    monkeypatch.setattr(main, "get_latest_completed_scan", lambda session, customer_id: scan)
    monkeypatch.setattr(main.runtime, "llm", FakeLLM())

    response = main.financial_chat(
        FinancialChatRequest(
            customer_id="C005",
            message="Được đấy, triển khai giúp mình",
            history=[ChatMessage(role="assistant", content="Bạn có thể cân nhắc M-Sinh lời.")],
        ),
        None,
    )
    assert captured["context"]["latest_user_message"] == "Được đấy, triển khai giúp mình"
    assert captured["context"]["history"][0]["role"] == "assistant"
    assert response.action_offer == "ACTIVATE_M_SINH_LOI"
    assert "chọn hành động" in response.reply.lower()


def test_chat_exploration_does_not_offer_action(monkeypatch) -> None:
    class FakeLLM:
        def generate_structured(self, **kwargs):
            return ChatIntentDecision(intent="EXPLORE_FLEXIBLE", reply="Bạn có thể cân nhắc M-Sinh lời để rút linh hoạt.")

    context = SimpleNamespace(
        customer=SimpleNamespace(preferred_safe_balance=5000000),
        accounts=[SimpleNamespace(account_type="PAYMENT", available_balance=30000000)],
        m_sinh_loi=None,
    )
    scan = SimpleNamespace(result=SimpleNamespace(analysis={"risk_flags": {"idle_cash": True}}, recommendations=[]))
    monkeypatch.setattr(main.registry.gateway, "get_financial_context", lambda customer_id: context)
    monkeypatch.setattr(main, "get_latest_completed_scan", lambda session, customer_id: scan)
    monkeypatch.setattr(main.runtime, "llm", FakeLLM())

    response = main.financial_chat(
        FinancialChatRequest(customer_id="C005", message="Mình có thể cần khoản tiền đó sớm"), None
    )
    assert response.action_offer is None
    assert "SBSI" in response.reply
