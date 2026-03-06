# ---- Stage 1: Builder ----
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY opensuse_ai/ opensuse_ai/

# Install deps into a venv for clean layering
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir .


# ---- Stage 2: Runtime ----
FROM python:3.11-slim AS runtime

# Minimal runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN groupadd -r suseai && useradd -r -g suseai -m suseai

WORKDIR /app

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY opensuse_ai/ opensuse_ai/
COPY config.yaml .

# Data directory for models, vectorstore, scraped docs
RUN mkdir -p /app/data && chown -R suseai:suseai /app/data
VOLUME ["/app/data"]

USER suseai

# Resource limits guidance (enforced via docker run --memory / --cpus)
LABEL org.opencontainers.image.title="openSUSE Leap AI Startup Guide"
LABEL org.opencontainers.image.description="Containerized AI startup guide for openSUSE Leap"
LABEL org.opencontainers.image.source="https://github.com/anujagrawal380/opensuse-leap-ai-guide"
LABEL ai.resource.memory.recommended="4Gi"
LABEL ai.resource.cpu.recommended="4"

ENTRYPOINT ["suse-assist"]
CMD ["chat", "--demo"]
