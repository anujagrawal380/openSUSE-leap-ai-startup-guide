"""
Performance benchmarking and resource monitoring.

Measures memory footprint, inference latency, and throughput — key metrics
the project proposal asks for in the "Performance and resource usage evaluation report".
"""

import logging
import os
import time
from dataclasses import dataclass, field

import psutil

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""

    query: str
    response_length: int
    latency_ms: float
    tokens_used: int
    tokens_per_second: float


@dataclass
class ResourceSnapshot:
    """Point-in-time resource usage snapshot."""

    timestamp: float
    process_memory_mb: float
    system_memory_used_percent: float
    cpu_percent: float


@dataclass
class BenchmarkReport:
    """Aggregated benchmark report."""

    model_name: str
    total_queries: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    avg_tokens_per_second: float = 0.0
    peak_memory_mb: float = 0.0
    baseline_memory_mb: float = 0.0
    model_memory_mb: float = 0.0
    results: list[BenchmarkResult] = field(default_factory=list)
    resource_snapshots: list[ResourceSnapshot] = field(default_factory=list)

    def summary(self) -> str:
        """Generate a human-readable summary."""
        return (
            f"=== Performance Benchmark Report ===\n"
            f"Model: {self.model_name}\n"
            f"Queries run: {self.total_queries}\n"
            f"Avg latency: {self.avg_latency_ms:.0f} ms\n"
            f"P95 latency: {self.p95_latency_ms:.0f} ms\n"
            f"Avg throughput: {self.avg_tokens_per_second:.1f} tokens/s\n"
            f"Baseline memory: {self.baseline_memory_mb:.0f} MB\n"
            f"Model memory footprint: {self.model_memory_mb:.0f} MB\n"
            f"Peak memory: {self.peak_memory_mb:.0f} MB\n"
        )


class Benchmarker:
    """Runs performance benchmarks on the assistant."""

    # Standard benchmark queries covering different question types
    BENCHMARK_QUERIES = [
        "How do I install a package using zypper?",
        "What is YaST and how do I open it?",
        "How do I add a new repository in openSUSE?",
        "My system won't boot after an update. What should I do?",
        "How do I configure the firewall using firewalld?",
        "Explain the difference between Tumbleweed and Leap.",
        "How do I set up SSH on openSUSE?",
        "What is snapper and how do I use it for system snapshots?",
    ]

    def __init__(self):
        self.process = psutil.Process(os.getpid())

    def snapshot_resources(self) -> ResourceSnapshot:
        """Take a resource usage snapshot."""
        mem_info = self.process.memory_info()
        return ResourceSnapshot(
            timestamp=time.time(),
            process_memory_mb=mem_info.rss / (1024 * 1024),
            system_memory_used_percent=psutil.virtual_memory().percent,
            cpu_percent=self.process.cpu_percent(interval=0.1),
        )

    def run(self, assistant, system_context=None) -> BenchmarkReport:
        """
        Run the full benchmark suite.

        Args:
            assistant: An initialized Assistant instance with model loaded.
            system_context: Optional SystemContext for grounding.
        """
        from opensuse_ai.assistant import Assistant  # noqa: F811

        report = BenchmarkReport(
            model_name=f"{assistant.config.model.repo_id}/{assistant.config.model.filename}",
        )

        # Baseline memory (before queries)
        baseline = self.snapshot_resources()
        report.baseline_memory_mb = baseline.process_memory_mb
        report.resource_snapshots.append(baseline)

        latencies = []
        tps_values = []

        for query in self.BENCHMARK_QUERIES:
            logger.info("Benchmarking: %s", query[:60])
            assistant.reset_conversation()

            response = assistant.ask(query, system_context=system_context)

            result = BenchmarkResult(
                query=query,
                response_length=len(response.text),
                latency_ms=response.generation_time_ms,
                tokens_used=response.tokens_used,
                tokens_per_second=(
                    response.tokens_used / (response.generation_time_ms / 1000)
                    if response.generation_time_ms > 0
                    else 0
                ),
            )
            report.results.append(result)
            latencies.append(result.latency_ms)
            tps_values.append(result.tokens_per_second)

            # Snapshot resources after each query
            snap = self.snapshot_resources()
            report.resource_snapshots.append(snap)

            logger.info(
                "  -> %d tokens in %.0f ms (%.1f tok/s, %.0f MB RSS)",
                result.tokens_used,
                result.latency_ms,
                result.tokens_per_second,
                snap.process_memory_mb,
            )

        # Aggregate
        report.total_queries = len(report.results)
        report.avg_latency_ms = sum(latencies) / len(latencies) if latencies else 0
        report.avg_tokens_per_second = sum(tps_values) / len(tps_values) if tps_values else 0

        # P95 latency
        sorted_latencies = sorted(latencies)
        p95_idx = int(len(sorted_latencies) * 0.95)
        report.p95_latency_ms = sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)]

        # Peak memory
        report.peak_memory_mb = max(s.process_memory_mb for s in report.resource_snapshots)
        report.model_memory_mb = report.peak_memory_mb - report.baseline_memory_mb

        return report
