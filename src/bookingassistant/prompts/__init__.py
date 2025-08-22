from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8")


BASE_PROMPT = load_prompt("base")
SLOTS_PROMPT_TEMPLATE = load_prompt("slots_prompt_template")
COMPLETE_PROMPT_TEMPLATE = load_prompt("complete_prompt_template")
QUESTION_PROMPT = load_prompt("question_prompt")
CONFIRM_PROMPT = load_prompt("confirm_prompt")
FALLBACK_PROMPT = load_prompt("fallback_prompt")
YESNO_PROMPT = load_prompt("yesno_prompt")
HISTORY_PROMPT = load_prompt("history_prompt")
TIME_PROMPT = load_prompt("time_prompt")
