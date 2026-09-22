"""Every LLM call is cached; a cache hit costs $0 and is logged in the ledger."""
import csv
from types import SimpleNamespace as NS

from src import budget
from src.llm import LLMClient


class FakeOpenAI:
    def __init__(self):
        self.calls = 0
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.calls += 1
        msg = NS(content='{"decision": "VERIFIED"}', tool_calls=None)
        usage = NS(prompt_tokens=100, completion_tokens=20, cost=0.0001,
                   prompt_tokens_details=NS(cached_tokens=0), completion_tokens_details=NS(reasoning_tokens=5))
        return NS(choices=[NS(message=msg)], usage=usage)


def test_cache_hit_is_free(tmp_path):
    fake = FakeOpenAI()
    c = LLMClient(client=fake, cache_dir=tmp_path)
    before = budget.total_spent()
    msgs = [{"role": "user", "content": "hi"}]
    r1 = c.chat("openai/gpt-4o-mini", msgs, meta={"experiment_id": "test_cache"})
    r2 = c.chat("openai/gpt-4o-mini", msgs, meta={"experiment_id": "test_cache"})
    assert fake.calls == 1 and not r1.cache_hit and r2.cache_hit and r2.cost_usd == 0
    assert r1.cost_source == "reported" and r1.usage["reasoning_tokens"] == 5
    assert abs(budget.total_spent() - before - 0.0001) < 1e-9
    rows = [r for r in csv.DictReader(open(budget.ledger_path())) if r["experiment_id"] == "test_cache"]
    assert [r["cache_hit"] for r in rows] == ["0", "1"]
