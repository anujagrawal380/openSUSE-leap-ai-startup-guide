"""
SLM (Small Language Model) assistant engine.

Manages the locally-running language model and constructs prompts
with RAG context and system state awareness.
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from huggingface_hub import hf_hub_download
from llama_cpp import Llama

from opensuse_ai.config import Config, ModelConfig
from opensuse_ai.rag import RAGPipeline
from opensuse_ai.system_context import SystemContext

logger = logging.getLogger(__name__)

# System prompt that defines the assistant's persona and capabilities
SYSTEM_PROMPT = """\
You are an openSUSE Leap assistant. Give concise, accurate answers about openSUSE. \
Use zypper for packages, YaST for system admin. Be helpful and brief.

{system_context}

Documentation:
{rag_context}
"""


@dataclass
class AssistantResponse:
    """Structured response from the assistant."""

    text: str
    sources: list[dict]
    generation_time_ms: float
    tokens_used: int


class Assistant:
    """
    The core AI assistant that combines SLM inference with RAG retrieval
    and system context awareness.
    """

    def __init__(self, config: Config, rag_pipeline: RAGPipeline):
        self.config = config
        self.rag = rag_pipeline
        self.model: Llama | None = None
        self.conversation_history: list[dict] = []

    def load_model(self) -> None:
        """Download (if needed) and load the SLM model."""
        model_config = self.config.model
        model_dir = Path(self.config.data_dir) / "models"
        model_dir.mkdir(parents=True, exist_ok=True)

        model_path = model_dir / model_config.filename

        if not model_path.exists():
            logger.info(
                "Downloading model %s/%s ...",
                model_config.repo_id,
                model_config.filename,
            )
            downloaded_path = hf_hub_download(
                repo_id=model_config.repo_id,
                filename=model_config.filename,
                local_dir=str(model_dir),
            )
            model_path = Path(downloaded_path)
            logger.info("Model downloaded to %s", model_path)
        else:
            logger.info("Using cached model at %s", model_path)

        logger.info("Loading model into memory...")
        self.model = Llama(
            model_path=str(model_path),
            n_ctx=model_config.n_ctx,
            n_threads=model_config.n_threads,
            n_gpu_layers=model_config.n_gpu_layers,
            verbose=False,
        )
        logger.info("Model loaded successfully.")

    def ask(
        self,
        question: str,
        system_context: SystemContext | None = None,
    ) -> AssistantResponse:
        """
        Process a user question: retrieve context, build prompt, generate response.
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        # 1. Retrieve relevant documentation
        rag_results = []
        rag_context = "No documentation indexed yet."
        if self.rag.is_populated:
            rag_results = self.rag.retrieve(question)
            rag_context = self.rag.format_context(rag_results)

        # 2. Build system context string
        sys_ctx_str = ""
        if system_context:
            sys_ctx_str = (
                f"Current System State:\n{system_context.summary()}"
            )
        else:
            sys_ctx_str = "System context: Not available (running in demo mode)."

        # 3. Construct the full prompt
        system_message = SYSTEM_PROMPT.format(
            system_context=sys_ctx_str,
            rag_context=rag_context,
        )

        messages = [{"role": "system", "content": system_message}]

        # Add conversation history (keep last 2 turns — model is small)
        for msg in self.conversation_history[-2:]:
            messages.append(msg)

        messages.append({"role": "user", "content": question})

        # 4. Truncate if prompt is too long for context window
        #    Rough estimate: 1 token ≈ 4 chars
        max_prompt_chars = (self.config.model.n_ctx - self.config.model.max_tokens) * 4
        total_chars = sum(len(m["content"]) for m in messages)
        while total_chars > max_prompt_chars and len(messages) > 2:
            # Remove oldest conversation turn (keep system + current user msg)
            messages.pop(1)
            total_chars = sum(len(m["content"]) for m in messages)

        # 5. Generate response
        start_time = time.perf_counter()

        response = self.model.create_chat_completion(
            messages=messages,
            max_tokens=self.config.model.max_tokens,
            temperature=self.config.model.temperature,
            top_p=self.config.model.top_p,
            repeat_penalty=self.config.model.repeat_penalty,
        )

        generation_time = (time.perf_counter() - start_time) * 1000

        answer_text = response["choices"][0]["message"]["content"]
        tokens_used = response.get("usage", {}).get("total_tokens", 0)

        # 6. Update conversation history
        self.conversation_history.append({"role": "user", "content": question})
        self.conversation_history.append({"role": "assistant", "content": answer_text})

        # 7. Extract source references
        sources = [
            {
                "url": r["metadata"].get("source_url", ""),
                "title": r["metadata"].get("title", ""),
                "relevance": 1 - r["distance"],  # cosine similarity
            }
            for r in rag_results
        ]

        return AssistantResponse(
            text=answer_text,
            sources=sources,
            generation_time_ms=generation_time,
            tokens_used=tokens_used,
        )

    def reset_conversation(self) -> None:
        """Clear conversation history."""
        self.conversation_history.clear()


# -- Onboarding-specific prompt templates --

ONBOARDING_TOPICS = {
    "welcome": "Welcome me to openSUSE and give me a brief overview of what makes it special.",
    "package_management": "Explain how package management works in openSUSE with zypper. Show me the most common commands I'll need.",
    "yast": "What is YaST and how do I use it for system administration?",
    "repositories": "How do repositories work in openSUSE? How do I add, remove, and manage them?",
    "desktop": "Guide me through customizing my desktop environment on openSUSE.",
    "firewall": "How do I configure the firewall on openSUSE?",
    "updates": "How do I keep my openSUSE system up to date? Explain the update process.",
    "troubleshooting": "What are common troubleshooting steps when something goes wrong on openSUSE?",
    "community": "Tell me about the openSUSE community and how I can get involved.",
}
