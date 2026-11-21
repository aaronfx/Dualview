"""Spending controls for paid AI calls (one choke point: every paid provider is wrapped in `BudgetedProvider`).

Rules (all enforced in code, before a request is sent):

1. **Paid calls are off by default.** Nothing is sent unless `APEX_AI_PAID_ENABLED=1`.
2. **Only low-cost models by default.** A model must be in `LOW_COST_MODELS`, or be approved explicitly by name in
   `APEX_AI_APPROVED_MODELS` (comma-separated). Premium models (Opus, Fable, GPT-5.x "sol"/pro, ...) are never
   used unless the owner adds them there.
3. **No automatic escalation.** An experiment is bound to exactly one model; the wrapper refuses a call if the
   provider's model has changed, and nothing in APEX switches models on failure.
4. **Strict budgets.** Each experiment has a call limit (`APEX_AI_MAX_CALLS`, default 3), a per-call output cap
   (`APEX_AI_MAX_OUTPUT_TOKENS`, default 6000), a per-experiment spend cap (`APEX_AI_EXPERIMENT_BUDGET_USD`,
   default 0.10) and a cumulative cap over the ledger (`APEX_AI_TOTAL_BUDGET_USD`, default 1.00). A call is refused
   if its *worst-case* cost (full prompt + the whole output cap) would cross either cap.
5. **Every experiment is reported.** The ledger (`APEX_AI_LEDGER`, default `apex_data/ai_ledger.jsonl`) gets one
   record per experiment: model, reason, the pre-run estimate (upper bound), per-call estimates, actual cost (from
   the provider's usage report, else computed from token counts and the price table), calls and outcome.
   An experiment needs a non-empty reason.

Prices come from `model_prices.json` (a snapshot of OpenRouter's free public model listing). A model without a
known price is refused, because its cost cannot be bounded.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

PRICES_PATH = Path(__file__).with_name("model_prices.json")

# Low-cost models usable without explicit approval (output price at most ~$0.50 per million tokens).
LOW_COST_MODELS = ("anthropic/claude-haiku-5.5", "deepseek/deepseek-v4.1-flash", "qwen/qwen3.8-flash", "openai/gpt-5-nano")
DEFAULT_MODEL = "anthropic/claude-haiku-5.5"
CHARS_PER_TOKEN = 3.2  # conservative (over-estimates tokens for JSON-heavy prompts)


class BudgetError(RuntimeError):
    """A paid call was refused by the spending policy (nothing was sent)."""


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass
class BudgetPolicy:
    paid_enabled: bool = False
    approved_models: tuple = ()
    max_calls: int = 3
    max_output_tokens: int = 6000
    experiment_budget_usd: float = 0.10
    total_budget_usd: float = 1.00
    ledger_path: str = "apex_data/ai_ledger.jsonl"

    @classmethod
    def from_env(cls) -> "BudgetPolicy":
        return cls(paid_enabled=os.environ.get("APEX_AI_PAID_ENABLED", "0") == "1",
                   approved_models=tuple(m.strip() for m in os.environ.get("APEX_AI_APPROVED_MODELS", "").split(",") if m.strip()),
                   max_calls=int(_env_float("APEX_AI_MAX_CALLS", 3)),
                   max_output_tokens=int(_env_float("APEX_AI_MAX_OUTPUT_TOKENS", 6000)),
                   experiment_budget_usd=_env_float("APEX_AI_EXPERIMENT_BUDGET_USD", 0.10),
                   total_budget_usd=_env_float("APEX_AI_TOTAL_BUDGET_USD", 1.00),
                   ledger_path=os.environ.get("APEX_AI_LEDGER", "apex_data/ai_ledger.jsonl"))

    def model_allowed(self, model: str) -> bool:
        return model in LOW_COST_MODELS or model in self.approved_models


def load_prices(path: Path = PRICES_PATH) -> Dict[str, Dict[str, float]]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["models"]


def price_of(model: str, prices: Optional[Dict[str, Dict[str, float]]] = None) -> Dict[str, float]:
    prices = prices if prices is not None else load_prices()
    if model not in prices:
        raise BudgetError(f"no known price for model {model!r}: its cost cannot be bounded, so it is refused "
                          "(refresh model_prices.json from the free OpenRouter model listing)")
    return prices[model]


def tokens_of(text: str) -> int:
    return int(len(text or "") / CHARS_PER_TOKEN) + 1


def ledger_total(path: str) -> float:
    if not os.path.exists(path):
        return 0.0
    total = 0.0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rec = json.loads(line)
                total += float(rec.get("actual_usd") or 0.0)
    return total


@dataclass
class Experiment:
    """One paid AI experiment: a fixed model, a reason, and a hard budget."""
    model: str
    reason: str
    policy: BudgetPolicy = field(default_factory=BudgetPolicy.from_env)
    prices: Optional[Dict[str, Dict[str, float]]] = None
    id: str = field(default_factory=lambda: time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:6])
    calls: List[Dict[str, Any]] = field(default_factory=list)
    started_utc: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    finished: bool = False

    def __post_init__(self) -> None:
        if not self.reason or not self.reason.strip():
            raise BudgetError("a paid AI experiment needs a reason (why this call is worth paying for)")
        if not self.policy.paid_enabled:
            raise BudgetError("paid AI calls are disabled (set APEX_AI_PAID_ENABLED=1 to allow them)")
        if not self.policy.model_allowed(self.model):
            raise BudgetError(f"model {self.model!r} is not approved: low-cost models are {', '.join(LOW_COST_MODELS)}; "
                              "any other model needs the owner's explicit approval in APEX_AI_APPROVED_MODELS")
        self.price = price_of(self.model, self.prices)
        self.prior_total = ledger_total(self.policy.ledger_path)

    # -- money
    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens * self.price["input_per_mtok"] + output_tokens * self.price["output_per_mtok"]) / 1e6

    @property
    def spent(self) -> float:
        return sum(c["actual_usd"] for c in self.calls)

    def upper_bound(self, prompt_chars: int) -> float:
        """Worst case for the whole experiment: every allowed call with a full prompt and the full output cap."""
        return self.policy.max_calls * self.cost(int(prompt_chars / CHARS_PER_TOKEN) + 1, self.policy.max_output_tokens)

    def before_call(self, system: str, user: str, max_tokens: int) -> int:
        """Check the call against every limit; returns the output-token cap to send. Raises BudgetError (nothing sent)."""
        if len(self.calls) >= self.policy.max_calls:
            raise BudgetError(f"call limit reached ({self.policy.max_calls} calls for this experiment)")
        out_cap = min(max_tokens, self.policy.max_output_tokens)
        worst = self.cost(tokens_of(system) + tokens_of(user), out_cap)
        if self.spent + worst > self.policy.experiment_budget_usd + 1e-12:
            raise BudgetError(f"experiment budget: spent ${self.spent:.4f}, next call could cost up to ${worst:.4f}, "
                              f"cap ${self.policy.experiment_budget_usd:.2f}")
        if self.prior_total + self.spent + worst > self.policy.total_budget_usd + 1e-12:
            raise BudgetError(f"total budget: ledger ${self.prior_total:.4f} + this experiment ${self.spent:.4f} + "
                              f"next call up to ${worst:.4f} exceeds ${self.policy.total_budget_usd:.2f}")
        self._pending = {"estimated_usd_upper": round(worst, 6), "output_cap": out_cap,
                         "estimated_input_tokens": tokens_of(system) + tokens_of(user)}
        return out_cap

    def after_call(self, usage: Optional[Dict[str, Any]], system: str, user: str, reply: str, model_used: str) -> None:
        usage = usage or {}
        tin = usage.get("prompt_tokens") or usage.get("input_tokens")
        tout = usage.get("completion_tokens") or usage.get("output_tokens")
        if usage.get("cost") is not None:
            actual, source = float(usage["cost"]), "provider usage report"
        elif tin is not None and tout is not None:
            actual, source = self.cost(int(tin), int(tout)), "token counts x price table"
        else:  # no usage at all: charge the conservative estimate, never zero
            tin, tout = tokens_of(system) + tokens_of(user), tokens_of(reply)
            actual, source = self.cost(tin, tout), "estimated from text length (no usage report)"
        self.calls.append(dict(self._pending, n=len(self.calls) + 1, model=model_used, input_tokens=tin, output_tokens=tout,
                               actual_usd=round(actual, 6), actual_source=source))

    def record(self, status: str, note: str = "") -> Dict[str, Any]:
        rec = {"experiment": self.id, "started_utc": self.started_utc, "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "model": self.model, "reason": self.reason, "status": status, "note": note[:500],
               "limits": {"max_calls": self.policy.max_calls, "max_output_tokens": self.policy.max_output_tokens,
                          "experiment_budget_usd": self.policy.experiment_budget_usd, "total_budget_usd": self.policy.total_budget_usd},
               "estimated_usd_upper": round(sum(c["estimated_usd_upper"] for c in self.calls), 6),
               "actual_usd": round(self.spent, 6), "calls": self.calls}
        return rec

    def finish(self, status: str, note: str = "") -> Dict[str, Any]:
        rec = self.record(status, note)
        if not self.finished:
            self.finished = True
            os.makedirs(os.path.dirname(os.path.abspath(self.policy.ledger_path)), exist_ok=True)
            with open(self.policy.ledger_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
        return rec


class BudgetedProvider:
    """Wraps a paid provider: every call is checked against the experiment's limits and recorded."""

    def __init__(self, inner, experiment: Experiment):
        if getattr(inner, "model", None) != experiment.model:
            raise BudgetError("provider model and experiment model differ")
        self.inner, self.experiment = inner, experiment
        self.name, self.model = inner.name, inner.model

    def complete(self, system: str, user: str, max_tokens: int = 8000) -> str:
        if self.inner.model != self.experiment.model:  # no escalation, ever
            raise BudgetError(f"model changed from {self.experiment.model!r} to {self.inner.model!r} mid-experiment")
        cap = self.experiment.before_call(system, user, max_tokens)
        reply = self.inner.complete(system, user, max_tokens=cap)
        self.experiment.after_call(getattr(self.inner, "last_usage", None), system, user, reply or "", self.inner.model)
        return reply
