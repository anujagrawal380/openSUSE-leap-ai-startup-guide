"""Tests for web UI slow-inference helpers."""

import time
from pathlib import Path

from opensuse_ai.web_ui import (
    WebRuntimeStatus,
    _missing_runtime_guidance,
    _resolve_topic_shortcut,
    _runtime_status_md,
    _thinking_message,
)


def test_runtime_status_mentions_model_and_index(tmp_path: Path):
    status = WebRuntimeStatus(
        model_label="test: tiny.gguf",
        model_ready=False,
        rag_ready=False,
        model_path=tmp_path / "models" / "tiny.gguf",
        data_dir=tmp_path,
    )

    html = _runtime_status_md(status)

    assert "test: tiny.gguf" in html
    assert "loads on first question" in html
    assert "missing index" in html


def test_missing_runtime_guidance_is_actionable(tmp_path: Path):
    status = WebRuntimeStatus(
        model_label="test: tiny.gguf",
        model_ready=False,
        rag_ready=False,
        model_path=tmp_path / "models" / "tiny.gguf",
        data_dir=tmp_path,
    )

    guidance = _missing_runtime_guidance(status)

    assert "suse-assist setup --model-tier test" in guidance
    assert "suse-assist ingest" in guidance


def test_thinking_message_reports_elapsed_time():
    message = _thinking_message(time.monotonic() - 3.2, "Model is thinking")

    assert "Model is thinking" in message
    assert "Elapsed: 3s" in message


def test_resolve_topic_shortcut():
    assert "zypper" in _resolve_topic_shortcut("topic package_management")
    assert _resolve_topic_shortcut("How do I update?") == "How do I update?"
