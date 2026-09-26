"""CRSV assessment with a local OpenAI-compatible server (llama-server + Qwen3.5-9B).

The system prompt is a fixed prefix (policy layers + examples) so the server can reuse its
cache; the item goes in the user message. Output is constrained by the JSON schema of
CRSVModelOutput, then the hard rules are applied by schema.finalize.
"""

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

from pydantic import ValidationError

from harmwatch.lexicon import RegionLexicon, age_indicators, guess_lang
from harmwatch.policy_loader import Policy, format_item
from harmwatch.schema import CRSVAssessment, CRSVModelOutput, finalize

DEFAULT_URL = "http://127.0.0.1:8080/v1"
DEFAULT_MODEL = "qwen3.5-9b"

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(base_url=os.getenv("LOCAL_LLM_URL", DEFAULT_URL), api_key="local", timeout=600)
    return _client


_QUOTE = re.compile(r'[«»"“”„]')


class Assessor:
    """One policy + one few-shot configuration. Thread-safe: call `assess` from many threads."""

    def __init__(self, policy: Policy, examples: list[dict] | None = None, model: str | None = None,
                 thinking: bool = False, max_tokens: int = 2500):
        self.policy = policy
        self.system = policy.system_prompt(examples)
        self.model = model or os.getenv("LOCAL_LLM_MODEL", DEFAULT_MODEL)
        self.thinking = thinking
        self.max_tokens = max_tokens
        self.schema = CRSVModelOutput.model_json_schema()
        self.lexicon = RegionLexicon(policy.entries)
        self.sv_lexicon = RegionLexicon(policy.entries, types=("RG-SVTERM",))

    def _call(self, user: str, system: str | None = None) -> tuple[CRSVModelOutput, dict]:
        response = _get_client().chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=self.max_tokens,
            messages=[{"role": "system", "content": system or self.system}, {"role": "user", "content": user}],
            response_format={"type": "json_schema",
                             "json_schema": {"name": "CRSVModelOutput", "schema": self.schema, "strict": True}},
            extra_body={"chat_template_kwargs": {"enable_thinking": self.thinking}, "cache_prompt": True},
        )
        content = response.choices[0].message.content or ""
        usage = response.usage.model_dump() if response.usage else {}
        return CRSVModelOutput.model_validate_json(content), usage

    def assess(self, item: dict, system: str | None = None, high_reach: bool = False) -> dict:
        """Returns {assessment, usage, seconds, error}. `system` overrides the prefix (e.g. leave-one-out)."""
        item = dict(item)
        item.setdefault("lang", guess_lang(item["text"]))
        full_text = item["text"] + "\n" + ((item.get("fwd_from") or {}).get("text") or "")
        start = time.time()
        error, usage, out = None, {}, None
        for _attempt in range(2):
            try:
                out, usage = self._call(format_item(item, self.policy.platform), system)
                break
            except (ValidationError, ValueError) as e:
                error = f"invalid_json: {str(e)[:200]}"
            except Exception as e:  # server error, timeout, context overflow: record, don't stop the batch
                error = f"{type(e).__name__}: {str(e)[:200]}"
                break
        if out is None:
            return {"assessment": None, "usage": usage, "seconds": time.time() - start, "error": error}

        a = finalize(
            out, item_id=str(item.get("id", "")), region=self.policy.region,
            profile_version=self.policy.profile_version, valid_ids=self.policy.valid_ids,
            age_indicator=bool(age_indicators(full_text)), sv_signal=bool(self.sv_lexicon.hits(full_text)),
            high_reach=high_reach,
            quote_present=bool(item.get("fwd_from")) or bool(_QUOTE.search(item["text"])),
        )
        if a.route != "restricted_escalation":
            det_hits = self.lexicon.hits(full_text)
            a.lexicon_hits = sorted(set(a.lexicon_hits) | set(det_hits))
            if item["lang"] not in self.policy.languages_covered:  # core.md: profile_gap
                for el in (a.elements.A, a.elements.B, a.elements.C):
                    el.confidence = min(el.confidence, 0.5)
                if "profile_gap" not in a.notes:
                    a.notes = (a.notes + " profile_gap").strip()
        return {"assessment": a, "usage": usage, "seconds": time.time() - start, "error": None}

    def assess_many(self, items: list[dict], workers: int = 8, systems: list[str] | None = None) -> list[dict]:
        systems = systems or [None] * len(items)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(lambda pair: self.assess(*pair), zip(items, systems)))


def assess_text(text: str, policy: Policy | None = None) -> CRSVAssessment | None:
    """Convenience for the platform: one post, default policy (REGION env)."""
    from harmwatch.policy_loader import load_policy

    global _default
    if policy is None:
        if _default is None:
            _default = Assessor(load_policy())
        assessor = _default
    else:
        assessor = Assessor(policy)
    return assessor.assess({"text": text})["assessment"]


_default: Assessor | None = None
