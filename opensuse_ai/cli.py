"""
CLI interface for the openSUSE AI Onboarding Assistant.

Provides an interactive, Rich-powered terminal UI for chatting with
the assistant, running onboarding workflows, and benchmarking.
"""

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from opensuse_ai.config import (
    MODEL_TIERS,
    Config,
)
from opensuse_ai.config import (
    available_ram_gb as detect_available_ram_gb,
)

console = Console()


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group()
@click.option("--config", "-c", default="config.yaml", help="Path to config file")
@click.pass_context
def main(ctx: click.Context, config: str) -> None:
    """openSUSE Leap AI Startup Guide — your local, private Linux guide."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = Config.from_yaml(config)


@main.command()
@click.option("--demo", is_flag=True, help="Use simulated openSUSE system context")
@click.option(
    "--model-tier",
    type=click.Choice(["auto", "test", "lite", "standard", "full", "custom"]),
    default=None,
    help="Override configured model tier for this run",
)
@click.pass_context
def chat(ctx: click.Context, demo: bool, model_tier: str | None) -> None:
    """Start an interactive chat session with the assistant."""
    cfg: Config = ctx.obj["config"]
    resolved_tier = _apply_model_tier(cfg, model_tier)
    setup_logging(cfg.log_level)

    from opensuse_ai.assistant import Assistant
    from opensuse_ai.rag import RAGPipeline
    from opensuse_ai.system_context import (
        detect_system_context,
        simulated_opensuse_context,
    )

    console.print(
        Panel(
            "[bold green]openSUSE Leap AI Startup Guide[/bold green]\n"
            "Your local, private AI guide for openSUSE Leap.\n"
            "Type [bold]quit[/bold] to exit, [bold]reset[/bold] to clear history,\n"
            "[bold]topics[/bold] to see guided onboarding topics.",
            title="🦎 suse-assist",
            border_style="green",
        )
    )

    # Initialize components
    with console.status("[bold cyan]Loading RAG pipeline..."):
        rag = RAGPipeline(cfg)
        if rag.is_populated:
            console.print(f"  ✓ Vector store loaded ({rag.vector_store.count} chunks)")
        else:
            console.print(
                "  ⚠ No documents indexed yet. Run [bold]suse-assist ingest[/bold] first.",
                style="yellow",
            )

    with console.status("[bold cyan]Loading language model..."):
        assistant = Assistant(cfg, rag)
        assistant.load_model()
        console.print(f"  ✓ Model loaded ({resolved_tier} tier)")

    # System context
    if demo:
        sys_ctx = simulated_opensuse_context()
        console.print("  ℹ Using simulated openSUSE Leap context", style="dim")
    else:
        sys_ctx = detect_system_context()
        console.print(f"  ✓ Detected: {sys_ctx.distro} {sys_ctx.distro_version}")

    console.print()

    # Interactive loop
    while True:
        try:
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye![/dim]")
            break

        if user_input.lower() == "reset":
            assistant.reset_conversation()
            console.print("[dim]Conversation history cleared.[/dim]")
            continue

        if user_input.lower() == "topics":
            _show_topics()
            continue

        if user_input.lower().startswith("topic "):
            topic_key = user_input[6:].strip().lower().replace(" ", "_")
            from opensuse_ai.assistant import ONBOARDING_TOPICS

            if topic_key in ONBOARDING_TOPICS:
                user_input = ONBOARDING_TOPICS[topic_key]
                console.print(f"[dim]→ {user_input}[/dim]")
            else:
                console.print(
                    f"[red]Unknown topic '{topic_key}'. "
                    "Type 'topics' to see available ones.[/red]"
                )
                continue

        # Get response
        with console.status("[bold cyan]Thinking..."):
            response = assistant.ask(user_input, system_context=sys_ctx)

        # Display response
        console.print()
        console.print(Panel(
            Markdown(response.text),
            title="[bold green]Assistant[/bold green]",
            border_style="green",
            padding=(1, 2),
        ))

        # Show sources if available
        if response.sources:
            source_text = Text()
            for src in response.sources[:3]:
                relevance = f"{src['relevance']:.0%}"
                source_text.append(f"  • {src['title']} ({relevance})\n", style="dim")
                source_text.append(f"    {src['url']}\n", style="dim blue")
            console.print(Panel(source_text, title="[dim]Sources[/dim]", border_style="dim"))

        # Performance stats
        console.print(
            f"[dim]⏱ {response.generation_time_ms:.0f}ms · {response.tokens_used} tokens[/dim]"
        )
        console.print()


def _show_topics() -> None:
    """Display available onboarding topics."""
    from opensuse_ai.assistant import ONBOARDING_TOPICS

    table = Table(title="Guided Onboarding Topics", border_style="cyan")
    table.add_column("Topic", style="bold cyan")
    table.add_column("Description")
    for key, prompt in ONBOARDING_TOPICS.items():
        table.add_row(key, prompt[:80])
    console.print(table)
    console.print("[dim]Use: topic <name> — e.g. 'topic package_management'[/dim]\n")


def _apply_model_tier(cfg: Config, requested_tier: str | None) -> str:
    """Resolve and apply the configured model tier."""
    resolved = cfg.apply_model_tier(requested_tier)
    if resolved == "custom":
        console.print(
            f"  ℹ Using custom model: {cfg.model.repo_id}/{cfg.model.filename}",
            style="dim",
        )
        return "custom"

    tier = MODEL_TIERS[resolved]
    console.print(
        f"  ℹ Model tier: {tier.label} ({cfg.model.repo_id}/{cfg.model.filename})",
        style="dim",
    )
    return resolved


@main.command()
@click.option("--max-pages", type=int, default=None, help="Override max pages to scrape per source")
@click.pass_context
def ingest(ctx: click.Context, max_pages: int | None) -> None:
    """Scrape openSUSE documentation and build the vector store."""
    cfg: Config = ctx.obj["config"]
    setup_logging(cfg.log_level)

    from opensuse_ai.rag import RAGPipeline
    from opensuse_ai.scraper import scrape_all_sources

    if max_pages:
        for src in cfg.doc_sources:
            src.max_pages = max_pages

    data_dir = Path(cfg.data_dir)

    console.print("[bold]Step 1/2:[/bold] Scraping openSUSE documentation...\n")
    pages = scrape_all_sources(cfg.doc_sources, data_dir)

    if not pages:
        console.print("[red]No pages scraped. Check your network connection.[/red]")
        sys.exit(1)

    console.print(f"\n[bold]Step 2/2:[/bold] Building vector store from {len(pages)} pages...\n")
    rag = RAGPipeline(cfg)
    num_chunks = rag.ingest(pages)

    console.print(
        f"\n[bold green]✓ Done![/bold green] Indexed {num_chunks} chunks from {len(pages)} pages.\n"
        f"  Vector store: {cfg.rag.persist_directory}\n"
        f"  Raw docs: {data_dir / 'raw_docs'}"
    )


@main.command()
@click.option("--demo", is_flag=True, help="Use simulated openSUSE system context")
@click.option(
    "--model-tier",
    type=click.Choice(["auto", "test", "lite", "standard", "full", "custom"]),
    default=None,
    help="Override configured model tier for this run",
)
@click.pass_context
def benchmark(ctx: click.Context, demo: bool, model_tier: str | None) -> None:
    """Run performance benchmarks and generate a report."""
    cfg: Config = ctx.obj["config"]
    _apply_model_tier(cfg, model_tier)
    setup_logging(cfg.log_level)

    from opensuse_ai.assistant import Assistant
    from opensuse_ai.benchmark import Benchmarker
    from opensuse_ai.rag import RAGPipeline
    from opensuse_ai.system_context import (
        detect_system_context,
        simulated_opensuse_context,
    )

    console.print("[bold]Running performance benchmarks...[/bold]\n")

    rag = RAGPipeline(cfg)
    assistant = Assistant(cfg, rag)

    with console.status("[bold cyan]Loading model..."):
        assistant.load_model()

    sys_ctx = simulated_opensuse_context() if demo else detect_system_context()

    benchmarker = Benchmarker()
    report = benchmarker.run(assistant, system_context=sys_ctx)

    console.print()
    console.print(Panel(report.summary(), title="Benchmark Results", border_style="cyan"))

    # Save report
    report_path = Path(cfg.data_dir) / "benchmark_report.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report.summary())
    console.print(f"[dim]Report saved to {report_path}[/dim]")


@main.command()
@click.pass_context
def sysinfo(ctx: click.Context) -> None:
    """Display detected system context information."""
    from opensuse_ai.system_context import detect_system_context

    sys_ctx = detect_system_context()
    console.print(Panel(sys_ctx.summary(), title="System Context", border_style="cyan"))


@main.command()
@click.option("--demo", is_flag=True, help="Use simulated openSUSE system context")
@click.option("--share", is_flag=True, help="Create a public Gradio share link")
@click.option("--port", type=int, default=7860, help="Port for the web server")
@click.option(
    "--model-tier",
    type=click.Choice(["auto", "test", "lite", "standard", "full", "custom"]),
    default=None,
    help="Override configured model tier for this run",
)
@click.pass_context
def web(ctx: click.Context, demo: bool, share: bool, port: int, model_tier: str | None) -> None:
    """Launch the Gradio web UI in the browser."""
    cfg: Config = ctx.obj["config"]
    _apply_model_tier(cfg, model_tier)
    setup_logging(cfg.log_level)

    from opensuse_ai.web_ui import launch_web_ui

    console.print(
        Panel(
            "[bold green]openSUSE Leap AI Startup Guide — Web UI[/bold green]\n"
            f"Starting on [bold]http://localhost:{port}[/bold]\n"
            + ("Public share link will be generated..." if share else ""),
            title="🦎 suse-assist web",
            border_style="green",
        )
    )

    launch_web_ui(cfg, demo_mode=demo, share=share, server_port=port)


@main.group()
def models() -> None:
    """Inspect and select local model tiers."""


@models.command("recommend")
@click.option(
    "--available-ram-gb",
    type=float,
    default=None,
    help="Override detected available RAM for testing",
)
@click.pass_context
def recommend_model(ctx: click.Context, available_ram_gb: float | None) -> None:
    """Recommend a model tier without downloading a model."""
    cfg: Config = ctx.obj["config"]
    ram_gb = available_ram_gb if available_ram_gb is not None else detect_available_ram_gb()
    recommended = cfg.apply_model_tier("auto", ram_gb=ram_gb)

    table = Table(title="Model Tier Recommendation", border_style="cyan")
    table.add_column("Tier", style="bold cyan")
    table.add_column("Min Available RAM")
    table.add_column("Model")
    table.add_column("Context")
    table.add_column("Notes")

    for name, tier in MODEL_TIERS.items():
        marker = "recommended" if name == recommended else ""
        table.add_row(
            f"{tier.label} {marker}".strip(),
            f"{tier.min_available_ram_gb:.0f} GB",
            f"{tier.repo_id}/{tier.filename}",
            f"{tier.n_ctx:,}",
            tier.description,
        )

    console.print(table)
    console.print(
        f"[dim]Detected available RAM: {ram_gb:.1f} GB. "
        f"Use --model-tier {recommended} to force this tier.[/dim]"
    )


if __name__ == "__main__":
    main()
