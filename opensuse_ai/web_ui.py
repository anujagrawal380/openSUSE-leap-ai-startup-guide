"""
Gradio-based web UI for the openSUSE Leap AI Startup Guide.

Provides a browser-based chat interface that wraps the same
Assistant + RAG pipeline used by the CLI.
"""

import logging

import gradio as gr

from opensuse_ai.assistant import ONBOARDING_TOPICS, Assistant
from opensuse_ai.config import Config
from opensuse_ai.rag import RAGPipeline
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
"""


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
    # ── Initialise backend ────────────────────────────────────────────────
    rag = RAGPipeline(config)
    assistant = Assistant(config, rag)
    assistant.load_model()

    if demo_mode:
        sys_ctx: SystemContext = simulated_opensuse_context()
    else:
        sys_ctx = detect_system_context()

    # ── Chat handler ──────────────────────────────────────────────────────
    def respond(user_message: str, history: list[dict]) -> str:
        """Process a single user turn and return the assistant reply."""
        if not user_message.strip():
            return ""

        # Handle topic shortcuts
        msg = user_message.strip()
        if msg.lower().startswith("topic "):
            topic_key = msg[6:].strip().lower().replace(" ", "_")
            if topic_key in ONBOARDING_TOPICS:
                msg = ONBOARDING_TOPICS[topic_key]

        # Sync web history → assistant history so context carries over
        assistant.conversation_history.clear()
        for turn in (history or []):
            assistant.conversation_history.append(turn)

        response = assistant.ask(msg, system_context=sys_ctx)

        reply = response.text + _format_sources(response.sources)
        reply += f"\n\n*⏱ {response.generation_time_ms:.0f} ms · {response.tokens_used} tokens*"
        return reply

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
        lines = sys_ctx.summary().split("\n")
        return "\n".join(f"- **{l.split(':')[0].strip()}:** {':'.join(l.split(':')[1:]).strip()}" for l in lines if ":" in l)

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
                chatbot = gr.ChatInterface(
                    fn=respond,
                    examples=[
                        "How do I install Firefox using zypper?",
                        "What is YaST and how do I use it?",
                        "How do I check for system updates?",
                        "topic welcome",
                        "topic package_management",
                    ],
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
    app = build_app(config, demo_mode=demo_mode, share=share)
    app.launch(
        server_name="0.0.0.0",
        server_port=server_port,
        share=share,
        show_error=True,
        css=CUSTOM_CSS,
    )
