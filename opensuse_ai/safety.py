"""Prompt and output hardening helpers."""

from __future__ import annotations

import re


PROMPT_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_instructions",
        re.compile(
            r"\b(ignore|disregard|forget|override)\b.{0,80}"
            r"\b(previous|above|system|developer|initial|hidden)\b.{0,40}"
            r"\b(instruction|prompt|rule|message)s?\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "reveal_prompt",
        re.compile(
            r"\b(show|print|reveal|dump|repeat)\b.{0,80}"
            r"\b(system|developer|hidden|initial)\b.{0,40}\b(prompt|instruction|message)s?\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "role_override",
        re.compile(
            r"\b(system|developer)\s*:\s*you\b|"
            r"\byou are now\b.{0,80}\b(system|developer|root|admin)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "jailbreak",
        re.compile(
            r"\b(jailbreak|developer mode|do anything now|DAN)\b",
            re.IGNORECASE,
        ),
    ),
)

SAFE_PROMPT_INJECTION_RESPONSE = (
    "I can't follow instructions that try to override or reveal my internal rules. "
    "Ask me an openSUSE setup or troubleshooting question and I can help using the "
    "available documentation."
)


def prompt_injection_findings(text: str) -> list[str]:
    """Return matched prompt-injection indicator names for user-supplied text."""
    return [name for name, pattern in PROMPT_INJECTION_PATTERNS if pattern.search(text)]


def is_prompt_injection_attempt(text: str) -> bool:
    """Detect obvious attempts to override system/developer instructions."""
    return bool(prompt_injection_findings(text))


def sanitize_model_output(text: str) -> str:
    """Strip hidden reasoning blocks and unsafe control characters from model output."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"</?think>", "", text, flags=re.IGNORECASE)
    return "".join(
        ch for ch in text if ch in "\n\t" or ord(ch) >= 32
    ).strip()
