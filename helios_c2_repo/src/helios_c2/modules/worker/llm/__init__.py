from __future__ import annotations

"""Stub LLM helpers for summaries/explanations."""

def llm_summarize(text: str, context: str) -> str:
    return f"[LLM stub] Summary based on context: {text[:120]}"


def llm_generate(prompt: str, max_tokens: int = 256, temperature: float = 0.2) -> str:
    return f"[LLM stub] {prompt[:160]}"
