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

DESTRUCTIVE_COMMAND_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\brm\s+-[^\n`]*r[^\n`]*f\b"),
    re.compile(r"\b(mkfs|wipefs|fdisk|parted|sgdisk|dd)\b"),
    re.compile(r"\bbtrfs\s+subvolume\s+delete\b"),
    re.compile(r"\bsnapper\s+rollback\b"),
    re.compile(r"\bzypper\s+(dup|dist-upgrade)\b"),
    re.compile(r"\b--allow-vendor-change\b|\bvendor\s+change\b", re.IGNORECASE),
)

COMMAND_PATTERN = re.compile(
    r"(```[\s\S]*?```|`[^`]+`|\b(sudo\s+)?(zypper|systemctl|snapper|podman|firewall-cmd|"
    r"nmcli|wicked|modprobe|grub2-mkconfig|transactional-update)\b)",
    re.IGNORECASE,
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


def contains_command_recommendation(text: str) -> bool:
    """Return whether output appears to recommend shell commands."""
    return bool(COMMAND_PATTERN.search(text))


def contains_destructive_command(text: str) -> bool:
    """Return whether output mentions commands that can alter data or boot state."""
    lowered = text.lower()
    return any(pattern.search(lowered) for pattern in DESTRUCTIVE_COMMAND_PATTERNS)


def apply_output_guardrails(text: str, sources: list[dict]) -> str:
    """Add practical safety notes for command-heavy answers."""
    additions: list[str] = []

    if contains_destructive_command(text) and "Before running destructive" not in text:
        additions.append(
            "**Safety note:** Before running destructive storage, rollback, or vendor-change "
            "commands, make sure you understand the impact and have a current backup or "
            "Snapper snapshot."
        )

    if contains_command_recommendation(text) and sources and "References:" not in text:
        titles = []
        for source in sources[:3]:
            title = source.get("title", "").strip()
            if title and title not in titles:
                titles.append(title)
        if titles:
            additions.append("**References:** " + "; ".join(titles))

    if not additions:
        return text
    return text.rstrip() + "\n\n" + "\n\n".join(additions)
