import json
from types import SimpleNamespace

import pytest

from agents.accounting_manager import AccountingManagerAgent
from agents.cost_accountant import CostAccountantAgent
from agents.revenue_accountant import RevenueAccountantAgent
from agents.tax_agent_tz import TaxAgentTZ
from agents.tax_agent_us import TaxAgentUS


class CapturingMessages:
    def __init__(self, payload):
        self.payload = payload
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(text=json.dumps(self.payload))],
            stop_reason="end_turn",
        )


def _assert_user_ended_message_call(messages):
    sent = messages.kwargs["messages"]
    assert sent
    assert sent[-1]["role"] == "user"
    assert all(message["role"] != "assistant" for message in sent)


@pytest.mark.parametrize(
    ("agent_class", "payload", "expected_agent"),
    [
        (CostAccountantAgent, {"agent": "CostAccountant", "executive_summary": "ok"}, "CostAccountant"),
        (RevenueAccountantAgent, {"agent": "RevenueAccountant", "five_step_analysis": {}}, "RevenueAccountant"),
        (AccountingManagerAgent, {"agent": "AccountingManager", "close_status": "open"}, "AccountingManager"),
    ],
)
def test_accounting_agents_end_with_user_message(agent_class, payload, expected_agent):
    messages = CapturingMessages(payload)
    agent = agent_class.__new__(agent_class)
    agent.client = SimpleNamespace(messages=messages)
    agent.model = "claude-sonnet-4-6"
    agent.max_tokens = 16000

    result = agent.analyze(
        raw_data="test data",
        period="Q1 2026",
        tenant_id="test-tenant",
    )

    _assert_user_ended_message_call(messages)
    assert result["agent"] == expected_agent
    assert "error" not in result


@pytest.mark.parametrize(
    ("agent_class", "jurisdiction"),
    [(TaxAgentTZ, "Tanzania"), (TaxAgentUS, "United States")],
)
def test_tax_agents_end_with_user_message(agent_class, jurisdiction):
    messages = CapturingMessages({"summary": "ok", "flags": []})
    agent = agent_class.__new__(agent_class)
    agent.client = SimpleNamespace(messages=messages)
    agent.model = "claude-sonnet-4-6"
    agent.rules = {}
    agent.today = "2026-06-13"

    result = agent.analyze(
        raw_input="test data",
        tenant_id="test-tenant",
        period="Q1 2026",
    )

    _assert_user_ended_message_call(messages)
    assert result["jurisdiction"] == jurisdiction
    assert "error" not in result
