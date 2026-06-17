"""
Gradio-based web UI for the openSUSE Leap AI Startup Guide.

Provides a browser-based chat interface that wraps the same
Assistant + RAG pipeline used by the CLI.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

try:
    import gradio as gr
except ImportError:
    gr = None

from opensuse_ai.assistant import ONBOARDING_TOPICS, Assistant
from opensuse_ai.config import Config
from opensuse_ai.system_context import (
    SystemContext,
    detect_system_context,
    simulated_opensuse_context,
)

logger = logging.getLogger(__name__)

# ── CSS for openSUSE theming ──────────────────────────────────────────────────
CUSTOM_CSS = """
.gradio-container {
    max-width: 900px !important;
    margin: auto;
}
#title-area {
    text-align: center;
    padding: 0.5rem 0;
}
#title-area h1 {
    color: #73ba25;
    font-size: 1.8rem;
    margin-bottom: 0.2rem;
}
#title-area p {
    color: #888;
    font-size: 0.95rem;
}
footer { display: none !important; }
#runtime-status {
    color: #666;
    font-size: 0.9rem;
    margin: 0 0 0.75rem 0;
}
"""


@dataclass(frozen=True)
class WebRuntimeStatus:
    """Small status summary displayed above the chat."""

    model_label: str
    model_ready: bool
    rag_ready: bool
    model_path: Path
    data_dir: Path


class WebAssistantRuntime:
    """Lazy-load the expensive backend and expose slow-inference progress."""

    def __init__(self, config: Config, *, demo_mode: bool = False):
        from opensuse_ai.rag import RAGPipeline

        self.config = config
        self.rag = RAGPipeline(config)
        self.assistant = Assistant(config, self.rag)
        self.model_loaded = False
        if demo_mode:
            self.system_context: SystemContext = simulated_opensuse_context()
        else:
            self.system_context = detect_system_context()

    @property
    def status(self) -> WebRuntimeStatus:
        return WebRuntimeStatus(
            model_label=f"{self.config.model.tier}: {self.config.model.filename}",
            model_ready=self.model_loaded,
            rag_ready=self.rag.is_populated,
            model_path=Path(self.config.data_dir) / "models" / self.config.model.filename,
            data_dir=Path(self.config.data_dir),
        )

    def ensure_model_loaded(self) -> None:
        """Load the LLM once, on first user request."""
        if self.model_loaded:
            return
        self.assistant.load_model()
        self.model_loaded = True

    def ask(self, msg: str, history: list[dict]):
        """Synchronize Gradio history and ask the assistant."""
        self.assistant.conversation_history.clear()
        for turn in history or []:
            self.assistant.conversation_history.append(turn)
        return self.assistant.ask(msg, system_context=self.system_context)


def _format_sources(sources: list[dict]) -> str:
    """Render source citations as markdown."""
    if not sources:
        return ""
    lines = ["\n\n---\n**Sources:**"]
    for src in sources[:3]:
        relevance = f"{src['relevance']:.0%}"
        title = src.get("title", "Unknown")
        url = src.get("url", "")
        if url:
            lines.append(f"- [{title}]({url}) ({relevance})")
        else:
            lines.append(f"- {title} ({relevance})")
    return "\n".join(lines)


def _runtime_status_md(status: WebRuntimeStatus) -> str:
    """Render compact runtime state for the web UI."""
    model_state = "loaded" if status.model_ready else "loads on first question"
    rag_state = "ready" if status.rag_ready else "missing index"
    return (
        f"<div id='runtime-status'>"
        f"<strong>Model:</strong> {status.model_label} ({model_state}) · "
        f"<strong>Docs:</strong> {rag_state} · "
        f"<strong>Data:</strong> {status.data_dir}"
        f"</div>"
    )


def _missing_runtime_guidance(status: WebRuntimeStatus) -> str:
    """Return actionable setup guidance when local runtime files are absent."""
    messages = []
    if not status.model_path.exists():
        messages.append(
            f"Model file is missing: `{status.model_path}`. "
            "Run `suse-assist setup --model-tier "
            f"{status.model_label.split(':', 1)[0]}` or import an offline bundle."
        )
    if not status.rag_ready:
        messages.append(
            "Documentation index is missing. Run `suse-assist ingest` or "
            "`suse-assist bundle import <bundle>`."
        )
    if not messages:
        return ""
    return "\n\n".join(f"**Setup needed:** {message}" for message in messages)


def _thinking_message(started_at: float, phase: str) -> str:
    """Format an elapsed-time progress message for slow CPU inference."""
    elapsed = int(time.monotonic() - started_at)
    return f"_{phase}. Elapsed: {elapsed}s. CPU-only responses can take 70-120s._"


def _resolve_topic_shortcut(user_message: str) -> str:
    """Expand web topic shortcuts into full prompts."""
    msg = user_message.strip()
    if msg.lower().startswith("topic "):
        topic_key = msg[6:].strip().lower().replace(" ", "_")
        if topic_key in ONBOARDING_TOPICS:
            return ONBOARDING_TOPICS[topic_key]
    return msg


def build_app(
    config: Config,
    *,
    demo_mode: bool = False,
    share: bool = False,
) -> gr.Blocks:
    """
    Construct and return the Gradio Blocks app.

    Parameters
    ----------
    config : Config
        Application configuration (model, RAG, etc.)
    demo_mode : bool
        If True, use simulated openSUSE context instead of real detection.
    share : bool
        If True, Gradio creates a public share link.
    """
    if gr is None:
        raise ImportError("gradio is not installed. Install it to use `suse-assist web`.")

    # ── Initialise lightweight runtime; model loads lazily on first prompt ──
    runtime = WebAssistantRuntime(config, demo_mode=demo_mode)

    # ── Chat handler ──────────────────────────────────────────────────────
    def respond(user_message: str, history: list[dict]) -> Iterator[str]:
        """Process a single user turn and return the assistant reply."""
        if not user_message.strip():
            yield ""
            return

        msg = _resolve_topic_shortcut(user_message)
        started_at = time.monotonic()
        guidance = _missing_runtime_guidance(runtime.status)
        if guidance:
            yield guidance

        yield _thinking_message(started_at, "Preparing local model")
        try:
            runtime.ensure_model_loaded()
        except Exception as exc:
            yield (
                "**Could not load the local model.**\n\n"
                f"`{exc}`\n\n"
                "Run `suse-assist doctor` to see which runtime files are missing."
            )
            return

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(runtime.ask, msg, history or [])
            while not future.done():
                yield _thinking_message(started_at, "Model is thinking")
                time.sleep(1)
            try:
                response = future.result()
            except Exception as exc:
                yield (
                    "**The assistant hit an error while answering.**\n\n"
                    f"`{exc}`\n\n"
                    "Run `suse-assist doctor` and check the service logs."
                )
                return

        reply = response.text + _format_sources(response.sources)
        reply += f"\n\n*⏱ {response.generation_time_ms:.0f} ms · {response.tokens_used} tokens*"
        yield reply

    # ── Topics helper ─────────────────────────────────────────────────────
    def topics_md() -> str:
        rows = ["| Topic | Description |", "| --- | --- |"]
        for key, prompt in ONBOARDING_TOPICS.items():
            rows.append(f"| `{key}` | {prompt[:80]} |")
        rows.append(
            "\nType **topic &lt;name&gt;** in the chat — e.g. *topic package_management*"
        )
        return "\n".join(rows)

    # ── System info helper ────────────────────────────────────────────────
    def sysinfo_md() -> str:
        lines = runtime.system_context.summary().split("\n")
        return "\n".join(
            f"- **{line.split(':')[0].strip()}:** "
            f"{':'.join(line.split(':')[1:]).strip()}"
            for line in lines
            if ":" in line
        )

    # ── Build the Gradio UI ───────────────────────────────────────────────
    with gr.Blocks(title="opensuse-leap-ai-startup-guide") as app:
        # Header
        gr.HTML(
            """
            <div id="title-area">
                <h1>🦎 openSUSE Leap AI Startup Guide</h1>
                <p>Your local, private AI guide for openSUSE Leap</p>
            </div>
            """
        )

        with gr.Tabs():
            # ── Chat tab ──────────────────────────────────────────────────
            with gr.Tab("💬 Chat"):
                gr.HTML(_runtime_status_md(runtime.status))
                chatbot = gr.ChatInterface(
                    fn=respond,
                    examples=[
                        "How do I install Firefox using zypper?",
                        "What is YaST and how do I use it?",
                        "How do I check for system updates?",
                        "topic welcome",
                        "topic package_management",
                    ],
                    cache_examples=False,
                    chatbot=gr.Chatbot(
                        height=480,
                        placeholder="Ask me anything about openSUSE Leap...",
                    ),
                    textbox=gr.Textbox(
                        placeholder="Type your question here...",
                        scale=7,
                    ),
                )

            # ── Topics tab ────────────────────────────────────────────────
            with gr.Tab("📚 Topics"):
                gr.Markdown("## Guided Onboarding Topics")
                gr.Markdown(topics_md())

            # ── System Info tab ───────────────────────────────────────────
            with gr.Tab("🖥️ System Info"):
                gr.Markdown("## Detected System Context")
                mode_label = "🟡 Simulated (demo mode)" if demo_mode else "🟢 Live detection"
                gr.Markdown(f"**Mode:** {mode_label}\n\n{sysinfo_md()}")


    return app


def launch_web_ui(
    config: Config,
    *,
    demo_mode: bool = False,
    share: bool = False,
    server_port: int = 7860,
) -> None:
    """Build and launch the Gradio web UI."""
    if gr is None:
        raise ImportError("gradio is not installed. Install it to use `suse-assist web`.")
    app = build_app(config, demo_mode=demo_mode, share=share)
    app.launch(
        server_name="0.0.0.0",
        server_port=server_port,
        share=share,
        show_error=True,
        css=CUSTOM_CSS,
    )
