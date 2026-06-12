# openSUSE-native build: based on SUSE Base Container Images (BCI), built with
# zypper — appropriate for a tool destined to ship inside openSUSE.

# ---- Stage 1: Builder ----
FROM registry.opensuse.org/opensuse/bci/python:3.11 AS builder

# Toolchain for compiling llama-cpp-python
RUN zypper --non-interactive install --no-recommends \
        gcc-c++ \
        cmake \
        git \
    && zypper clean --all

WORKDIR /app

COPY pyproject.toml README.md ./
COPY opensuse_ai/ opensuse_ai/

# Install deps into a venv for clean layering
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch==2.4.1+cpu"
RUN pip install --no-cache-dir ".[mcp]"


# ---- Stage 2: Runtime ----
FROM registry.opensuse.org/opensuse/bci/python:3.11 AS runtime

# Minimal runtime deps (libgomp for llama.cpp OpenMP support)
RUN zypper --non-interactive install --no-recommends \
        libgomp1 \
    && zypper clean --all

# Non-root user for security
RUN groupadd -r suseai && useradd -r -g suseai -m suseai

WORKDIR /app

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY opensuse_ai/ opensuse_ai/
COPY config.yaml .

# Data directory for models, vectorstore, scraped docs (mounted as a volume)
RUN mkdir -p /app/data && chown -R suseai:suseai /app/data
VOLUME ["/app/data"]

# Expose Gradio web UI port
EXPOSE 7860

USER suseai

LABEL org.opencontainers.image.title="openSUSE Leap AI Startup Guide"
LABEL org.opencontainers.image.description="AI onboarding assistant for openSUSE Leap (local SLM + RAG, openSUSE BCI base)"
LABEL org.opencontainers.image.source="https://github.com/anujagrawal380/openSUSE-leap-ai-startup-guide"
LABEL ai.resource.memory.recommended="8Gi"
LABEL ai.resource.cpu.recommended="4"

ENTRYPOINT ["suse-assist"]
CMD ["chat", "--demo"]
