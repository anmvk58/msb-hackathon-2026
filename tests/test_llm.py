import pytest

from app.agent.state import RecommendationResult
from app.llm import LLMNotConfiguredError, MockLLMClient
from app.llm.client import UnconfiguredLLMClient


def test_mock_llm_validates_structured_output() -> None:
    result = MockLLMClient().generate_structured(
        system_prompt="system",
        user_prompt="user",
        response_model=RecommendationResult,
        context={
            "grounded_candidate": {
                "problem": "Cashflow risk",
                "severity": "HIGH",
                "summary": "Forecast is below safe balance.",
                "evidence": [
                    {"source": "forecast_cashflow", "metric": "gap", "value": -1}
                ],
                "options": [
                    {
                        "option_id": "A",
                        "title": "Create budget",
                        "description": "Cap shopping spend.",
                        "action_type": "create_budget",
                        "parameters": {},
                        "expected_impact": "Reduce discretionary spend",
                    }
                ],
                "recommended_option_id": "A",
                "reasoning_summary": "Grounded in forecast evidence.",
            }
        },
    )
    assert result.recommended_option_id == "A"


def test_unconfigured_llm_fails_fast() -> None:
    with pytest.raises(LLMNotConfiguredError):
        UnconfiguredLLMClient().generate(system_prompt="", user_prompt="")

