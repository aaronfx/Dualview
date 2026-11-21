"""Spending controls for paid AI calls, verified offline with a mock HTTP transport (no network, no credits)."""
import json

import httpx
import pytest

from apex.ai.budget import BudgetedProvider, BudgetError, BudgetPolicy, Experiment, ledger_total
from apex.ai.director import PlanningError, StoryDirector
from apex.ai.providers import OpenAICompatibleProvider, provider_from_env

CHEAP = "anthropic/claude-haiku-5.5"


def _policy(tmp_path, **kw):
    base = dict(paid_enabled=True, ledger_path=str(tmp_path / "ledger.jsonl"))
    base.update(kw)
    return BudgetPolicy(**base)


def _mock_provider(model=CHEAP, reply="{}", cost=None, sent=None):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if sent is not None:
            sent.append(body)
        usage = {"prompt_tokens": 1000, "completion_tokens": 500}
        if cost is not None:
            usage["cost"] = cost
        return httpx.Response(200, json={"choices": [{"message": {"content": reply}}], "usage": usage})
    return OpenAICompatibleProvider("https://mock.invalid/api/v1", "dummy", model, "openrouter", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_paid_calls_are_disabled_by_default(monkeypatch):
    monkeypatch.delenv("APEX_AI_PAID_ENABLED", raising=False)
    monkeypatch.setenv("APEX_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy")
    with pytest.raises(BudgetError, match="disabled"):
        provider_from_env(reason="test")


def test_default_model_is_low_cost_and_premium_needs_explicit_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("APEX_AI_PAID_ENABLED", "1")
    monkeypatch.setenv("APEX_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy")
    monkeypatch.setenv("APEX_AI_LEDGER", str(tmp_path / "l.jsonl"))
    monkeypatch.delenv("APEX_AI_MODEL", raising=False)
    monkeypatch.delenv("APEX_AI_APPROVED_MODELS", raising=False)
    assert provider_from_env(reason="test").model == CHEAP
    for premium in ("anthropic/claude-opus-5.5", "anthropic/claude-sonnet-5.5", "anthropic/claude-fable-5.2", "openai/gpt-5.6-sol"):
        monkeypatch.setenv("APEX_AI_MODEL", premium)
        with pytest.raises(BudgetError, match="not approved"):
            provider_from_env(reason="test")
    monkeypatch.setenv("APEX_AI_MODEL", "anthropic/claude-sonnet-5.5")
    monkeypatch.setenv("APEX_AI_APPROVED_MODELS", "anthropic/claude-sonnet-5.5")  # the owner's explicit approval
    assert provider_from_env(reason="approved test").model == "anthropic/claude-sonnet-5.5"


def test_reason_is_required_and_unknown_prices_are_refused(tmp_path):
    with pytest.raises(BudgetError, match="reason"):
        Experiment(model=CHEAP, reason=" ", policy=_policy(tmp_path))
    with pytest.raises(BudgetError, match="price"):
        Experiment(model="vendor/unknown-model", reason="x", policy=_policy(tmp_path, approved_models=("vendor/unknown-model",)))


def test_call_limit_and_output_cap(tmp_path):
    sent = []
    exp = Experiment(model=CHEAP, reason="limit test", policy=_policy(tmp_path, max_calls=2, max_output_tokens=3000))
    p = BudgetedProvider(_mock_provider(sent=sent), exp)
    p.complete("sys", "user", max_tokens=16000)
    p.complete("sys", "user", max_tokens=16000)
    with pytest.raises(BudgetError, match="call limit"):
        p.complete("sys", "user")
    assert len(sent) == 2 and all(b["max_tokens"] == 3000 for b in sent)  # the cap is what is sent
    assert sent[0]["usage"] == {"include": True}  # ask OpenRouter for the actual charged cost


def test_worst_case_budget_refuses_before_sending(tmp_path):
    sent = []
    # Sonnet-priced worst case for 6000 output tokens is ~$0.06: a $0.05 cap refuses before anything is sent
    exp = Experiment(model="anthropic/claude-sonnet-5.5", reason="cap test",
                     policy=_policy(tmp_path, approved_models=("anthropic/claude-sonnet-5.5",), experiment_budget_usd=0.05))
    p = BudgetedProvider(_mock_provider(model="anthropic/claude-sonnet-5.5", sent=sent), exp)
    with pytest.raises(BudgetError, match="experiment budget"):
        p.complete("sys", "user", max_tokens=6000)
    assert sent == []


def test_total_budget_counts_the_ledger(tmp_path):
    pol = _policy(tmp_path, total_budget_usd=0.01)
    with open(pol.ledger_path, "w") as fh:
        fh.write(json.dumps({"experiment": "old", "actual_usd": 0.0099, "calls": []}) + "\n")
    p = BudgetedProvider(_mock_provider(sent=[]), Experiment(model=CHEAP, reason="total", policy=pol))
    with pytest.raises(BudgetError, match="total budget"):
        p.complete("sys", "user", max_tokens=6000)


def test_actual_cost_is_recorded_and_ledgered(tmp_path):
    pol = _policy(tmp_path)
    exp = Experiment(model=CHEAP, reason="ledger test", policy=pol)
    p = BudgetedProvider(_mock_provider(cost=0.00123), exp)
    p.complete("sys", "user", max_tokens=2000)
    rec = exp.finish("done")
    assert rec["actual_usd"] == pytest.approx(0.00123) and rec["calls"][0]["actual_source"] == "provider usage report"
    assert rec["estimated_usd_upper"] >= rec["actual_usd"] * 0 and rec["model"] == CHEAP and rec["reason"] == "ledger test"
    assert ledger_total(pol.ledger_path) == pytest.approx(0.00123)
    exp2 = Experiment(model=CHEAP, reason="no reported cost", policy=pol)
    BudgetedProvider(_mock_provider(cost=None), exp2).complete("s", "u", max_tokens=2000)
    c = exp2.finish("done")["calls"][0]
    assert c["actual_source"] == "token counts x price table" and c["actual_usd"] == pytest.approx((1000 * 0.1 + 500 * 0.5) / 1e6)


def test_no_model_escalation_mid_experiment(tmp_path):
    inner = _mock_provider()
    p = BudgetedProvider(inner, Experiment(model=CHEAP, reason="escalation", policy=_policy(tmp_path)))
    inner.model = "anthropic/claude-opus-5.5"
    with pytest.raises(BudgetError, match="model changed"):
        p.complete("s", "u")


def test_director_stops_on_budget_and_ledgers_the_experiment(tmp_path):
    pol = _policy(tmp_path, max_calls=2)
    exp = Experiment(model=CHEAP, reason="director", policy=pol)
    d = StoryDirector(BudgetedProvider(_mock_provider(reply="not json"), exp), max_repairs=7)  # asks for 8, policy allows 2
    with pytest.raises(PlanningError, match="spending policy"):
        d.plan("a story")
    assert len(d.log) == 2 and d.cost_record["status"] == "failed" and len(d.cost_record["calls"]) == 2
    assert ledger_total(pol.ledger_path) > 0


def test_reasoning_is_off_by_default_and_reasoning_tokens_are_recorded(tmp_path):
    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}],
                                         "usage": {"prompt_tokens": 10, "completion_tokens": 600, "cost": 0.0003,
                                                   "completion_tokens_details": {"reasoning_tokens": 590}}})
    inner = OpenAICompatibleProvider("https://mock.invalid/api/v1", "dummy", CHEAP, "openrouter", client=httpx.Client(transport=httpx.MockTransport(handler)))
    exp = Experiment(model=CHEAP, reason="reasoning", policy=_policy(tmp_path))
    BudgetedProvider(inner, exp).complete("s", "u", max_tokens=2000)
    assert sent[0]["reasoning"] == {"enabled": False}
    assert exp.finish("done")["calls"][0]["reasoning_tokens"] == 590


def test_unknown_proportion_keys_are_a_schema_error_not_a_crash():
    from apex.scene.schema import CharacterSpec
    with pytest.raises(ValueError, match="unknown proportions"):
        CharacterSpec(id="a", name="A", proportions={"height": 175})
