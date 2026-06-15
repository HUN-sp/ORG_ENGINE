"""LLM adapter. The ONLY file that knows which provider we use.

Swap providers via env (.env): LLM_PROVIDER=groq | ollama.
Everything else in the codebase just calls `llm(prompt)` or `llm_json(prompt)`.
"""
from __future__ import annotations
import json
import re
import time
import requests

from . import config


class LLMError(RuntimeError):
    pass


class RateLimit(LLMError):
    """Raised on HTTP 429 so the caller can wait the provider-suggested time."""
    def __init__(self, wait: float):
        self.wait = wait
        super().__init__(f"rate limited; retry in {wait}s")


def _parse_wait(text: str) -> float:
    m = re.search(r"try again in ([0-9.]+)s", text)
    return float(m.group(1)) if m else 0.0


_last_call = [0.0]  # wall-clock of the last real call, for throttling


def _throttle():
    """Sleep so consecutive real calls are at least MIN_CALL_INTERVAL apart."""
    interval = config.MIN_CALL_INTERVAL
    if interval <= 0:
        return
    dt = time.time() - _last_call[0]
    if dt < interval:
        time.sleep(interval - dt)
    _last_call[0] = time.time()


def _groq(messages, model, json_mode):
    if not config.GROQ_API_KEY:
        raise LLMError(
            "GROQ_API_KEY is not set. Put it in a .env file (see .env.example) "
            "or switch LLM_PROVIDER=ollama for a local model."
        )
    payload = {"model": model, "messages": messages, "temperature": 0.2}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {config.GROQ_API_KEY}"}
    r = requests.post(config.GROQ_URL, json=payload, headers=headers,
                      timeout=config.REQUEST_TIMEOUT)
    if r.status_code == 429:
        ra = r.headers.get("retry-after")
        wait = float(ra) if ra else (_parse_wait(r.text) or 5.0)
        raise RateLimit(wait)
    if r.status_code != 200:
        raise LLMError(f"Groq {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


def _openrouter(messages, model, json_mode):
    if not config.OPENROUTER_API_KEY:
        raise LLMError(
            "OPENROUTER_API_KEY is not set. Put it in your .env, or switch "
            "LLM_PROVIDER to groq/ollama/mock."
        )
    # No response_format: many free OpenRouter models reject it. We rely on the
    # 'Return a JSON object' instruction in the prompt + the robust _extract_json.
    payload = {"model": model, "messages": messages, "temperature": 0.2}
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://localhost",
        "X-Title": "Org Reasoning Engine",
    }
    r = requests.post(config.OPENROUTER_URL, json=payload, headers=headers,
                      timeout=config.REQUEST_TIMEOUT)
    if r.status_code == 429:
        ra = r.headers.get("retry-after")
        raise RateLimit(float(ra) if ra else (_parse_wait(r.text) or 5.0))
    if r.status_code != 200:
        raise LLMError(f"OpenRouter {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


def _ollama(messages, model, json_mode):
    payload = {"model": model, "messages": messages, "stream": False,
               "options": {"temperature": 0.2}}
    if json_mode:
        payload["format"] = "json"
    try:
        r = requests.post(config.OLLAMA_URL, json=payload,
                          timeout=config.REQUEST_TIMEOUT)
    except requests.exceptions.ConnectionError as e:
        raise LLMError(
            "Could not reach Ollama at " + config.OLLAMA_URL +
            ". Is it running? Try `ollama serve` and `ollama pull " +
            config.OLLAMA_MODEL + "`."
        ) from e
    if r.status_code != 200:
        raise LLMError(f"Ollama {r.status_code}: {r.text[:300]}")
    return r.json()["message"]["content"]


def _call(prompt, *, system=None, json_mode=False, judge=False, retries=6):
    provider = config.JUDGE_PROVIDER if judge else config.LLM_PROVIDER

    if provider == "mock":
        return _mock(prompt)

    backends = {"groq": (_groq, config.GROQ_MODEL),
                "ollama": (_ollama, config.OLLAMA_MODEL),
                "openrouter": (_openrouter, config.OPENROUTER_MODEL)}
    if provider not in backends:
        raise LLMError(f"Unknown LLM provider '{provider}'. Use groq/ollama/openrouter/mock.")
    fn, default_model = backends[provider]
    model = (config.JUDGE_MODEL or default_model) if judge else default_model

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last = None
    for attempt in range(retries):
        _throttle()  # stay under free-tier requests-per-minute
        try:
            return fn(messages, model, json_mode)
        except RateLimit as e:
            last = e
            if e.wait > 90:
                # a very long wait means a daily/quota cap, not a transient blip.
                raise LLMError(
                    f"{provider} is rate-limited for ~{int(e.wait)}s (likely a daily/quota "
                    f"cap). Switch LLM_PROVIDER in .env (openrouter/groq), use mock, or wait."
                )
            time.sleep(min(e.wait + 1.0, 20))
        except LLMError as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last


def llm(prompt, *, system=None, judge=False) -> str:
    """Free-form text completion."""
    return _call(prompt, system=system, judge=judge).strip()


def llm_json(prompt, *, system=None, judge=False) -> dict:
    """Completion expected to return a JSON object. Robust to models that wrap
    the JSON in prose or markdown fences."""
    raw = _call(prompt, system=system, json_mode=True, judge=judge)
    return _extract_json(raw)


def _mock(prompt: str) -> str:
    """No-API smoke-test backend. Returns schema-valid canned JSON so the whole
    loop runs offline. The Actor answers WEAKLY with no lessons and STRONGLY with
    lessons, so V2 (and generalized first answers) measurably beat V1. Enable with
    LLM_PROVIDER=mock. NOT for real results — use Groq/Ollama for those."""
    # ACTOR
    if '"reasoning_trace"' in prompt:
        ids = re.findall(r"\[([A-Za-z0-9\-]+)\]\s*\(", prompt)  # evidence ids in the prompt
        has_lessons = "(none yet)" not in prompt
        if has_lessons:
            return json.dumps({
                "answer": "MOCK strong answer: traces symptom -> the triggering commit/migration "
                          "-> the violated guideline -> the fix.",
                "root_cause": "MOCK: the underlying change that broke it (per the cited commit + guideline).",
                "reasoning_trace": ["identify symptom", "find triggering change", "check guideline", "confirm fix"],
                "evidence_used": ids[:6],
                "confidence": 0.85,
            })
        return json.dumps({
            "answer": "MOCK weak answer: reports the symptom (errors/latency spiked, rolled back) and stops.",
            "root_cause": "N/A",
            "reasoning_trace": ["noticed the symptom in the incident thread"],
            "evidence_used": ids[:2],
            "confidence": 0.4,
        })
    # JUDGE
    if '"similarity"' in prompt and "grading" in prompt:
        rc = 0 if "AI ROOT CAUSE: N/A" in prompt else 1
        return json.dumps({"similarity": 82 if rc else 46,
                           "root_cause_match": rc, "missing_points": ["MOCK"]})
    # GAP ANALYSIS
    if '"reasoning_gaps"' in prompt:
        return json.dumps({
            "reasoning_gaps": ["MOCK: stopped at the symptom; did not trace to the triggering change"],
            "root_cause_found": "AI ROOT CAUSE: N/A" not in prompt,
            "factual_errors": [],
            "what_ai_missed": "MOCK: did not trace symptom -> triggering commit -> violated guideline",
        })
    # LESSON
    if '"trigger_pattern"' in prompt:
        return json.dumps({
            "trigger_pattern": "why did X fail / get delayed / slow down",
            "tags": ["migration", "deploy", "commit", "guideline", "concurrently",
                     "index", "latency", "release", "incident", "blocked"],
            "what_ai_missed": "MOCK: stopped at the symptom",
            "reasoning_rule": "Trace symptom -> the triggering commit/migration near the incident "
                              "-> whether it violated a documented wiki guideline -> the fix.",
            "evidence_rule": "Cross-reference incident ticket + slack thread + triggering commit + "
                             "the relevant wiki guideline (migration / service-call).",
            "confidence_adjustment": "If no triggering commit is found, lower confidence and say so.",
        })
    return json.dumps({"mock": "unhandled prompt"})


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # strip ```json ... ``` fences
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    # grab the first balanced-looking object
    brace = re.search(r"\{.*\}", raw, re.DOTALL)
    if brace:
        try:
            return json.loads(brace.group(0))
        except json.JSONDecodeError:
            pass
    raise LLMError(f"Model did not return valid JSON:\n{raw[:500]}")
