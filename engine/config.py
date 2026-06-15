"""Central config + paths. Everything is driven by environment variables so the
LLM provider is a one-line change (see .env.example)."""
from __future__ import annotations
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()  # load a local .env if present
except Exception:
    pass

# ---- Paths -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOURCES = DATA / "sources"
QUESTIONS_FILE = DATA / "questions" / "question_feed.json"
GROUND_TRUTH_FILE = DATA / "ground_truth" / "expert_answers.json"
LESSONS_FILE = DATA / "memory" / "lessons.json"
RUN_LOG_FILE = DATA / "run_log.json"
EXPERIMENT_LOG_FILE = DATA / "experiment_log.json"

# ---- LLM provider ----------------------------------------------------------
# Primary model (answers + reflection). "groq" or "ollama".
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Judge model — used ONLY for the similarity / root-cause judgement.
# Default: reuse the primary. You can point this at a stronger free-tier model
# (e.g. Groq 70B) even if a smaller model does the answering.
JUDGE_PROVIDER = os.getenv("JUDGE_PROVIDER", LLM_PROVIDER).lower()
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "")  # "" -> use the provider's default model
# mock means fully offline: don't let a .env JUDGE_PROVIDER leak real API calls.
if LLM_PROVIDER == "mock":
    JUDGE_PROVIDER = "mock"

# ---- Knobs -----------------------------------------------------------------
TOP_K_EVIDENCE = int(os.getenv("TOP_K_EVIDENCE", "6"))   # docs retrieved per question
TOP_K_LESSONS = int(os.getenv("TOP_K_LESSONS", "3"))     # lessons injected (Reflexion bound)
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "60"))
# Minimum seconds between real LLM calls — throttles us under free-tier
# requests-per-minute limits (OpenRouter free ~20/min). 0 disables.
MIN_CALL_INTERVAL = float(os.getenv("LLM_MIN_INTERVAL", "4"))
