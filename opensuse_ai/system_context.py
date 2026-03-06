"""
System context detection for openSUSE.

Gathers signals from the running system (or simulates them) to provide
contextual grounding for the AI assistant's responses. This is what makes
the assistant "system-aware" rather than a generic chatbot.
"""

import logging
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SystemContext:
    """Snapshot of the current system state relevant to onboarding."""

    distro: str = ""
    distro_version: str = ""
    kernel: str = ""
    arch: str = ""
    hostname: str = ""
    desktop_env: str = ""
    package_manager: str = ""
    installed_packages_count: int = 0
    disk_usage_percent: float = 0.0
    memory_total_gb: float = 0.0
    memory_available_gb: float = 0.0
    is_opensuse: bool = False
    boot_stage: str = "post-install"  # "installer", "first-boot", "post-install"
    pending_updates: int = 0
    firewall_active: bool = False
    services_failed: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Human-readable summary for LLM context injection."""
        lines = [
            f"Distribution: {self.distro} {self.distro_version}",
            f"Kernel: {self.kernel}",
            f"Architecture: {self.arch}",
            f"Desktop Environment: {self.desktop_env or 'Not detected'}",
            f"Package Manager: {self.package_manager}",
            f"Boot Stage: {self.boot_stage}",
            f"Memory: {self.memory_available_gb:.1f} GB available / {self.memory_total_gb:.1f} GB total",
            f"Disk Usage: {self.disk_usage_percent:.1f}%",
        ]
        if self.pending_updates > 0:
            lines.append(f"Pending Updates: {self.pending_updates}")
        if self.services_failed:
            lines.append(f"Failed Services: {', '.join(self.services_failed)}")
        return "\n".join(lines)


def detect_system_context() -> SystemContext:
    """
    Detect the current system context.

    Works on openSUSE systems natively; provides partial info on other
    systems (useful for development/testing).
    """
    ctx = SystemContext()

    # Basic platform info
    ctx.kernel = platform.release()
    ctx.arch = platform.machine()
    ctx.hostname = platform.node()

    # Detect distribution
    try:
        with open("/etc/os-release") as f:
            os_release = {}
            for line in f:
                if "=" in line:
                    key, _, value = line.strip().partition("=")
                    os_release[key] = value.strip('"')
            ctx.distro = os_release.get("NAME", "Unknown")
            ctx.distro_version = os_release.get("VERSION_ID", "")
            ctx.is_opensuse = "opensuse" in ctx.distro.lower() or "suse" in ctx.distro.lower()
    except FileNotFoundError:
        ctx.distro = platform.system()

    # Package manager detection
    if shutil.which("zypper"):
        ctx.package_manager = "zypper"
    elif shutil.which("dnf"):
        ctx.package_manager = "dnf"
    elif shutil.which("apt"):
        ctx.package_manager = "apt"
    else:
        ctx.package_manager = "unknown"

    # Desktop environment
    ctx.desktop_env = os.environ.get("XDG_CURRENT_DESKTOP", "") or os.environ.get("DESKTOP_SESSION", "")

    # Memory info
    try:
        import psutil
        mem = psutil.virtual_memory()
        ctx.memory_total_gb = mem.total / (1024 ** 3)
        ctx.memory_available_gb = mem.available / (1024 ** 3)
    except ImportError:
        pass

    # Disk usage
    try:
        import psutil
        disk = psutil.disk_usage("/")
        ctx.disk_usage_percent = disk.percent
    except (ImportError, OSError):
        pass

    # openSUSE-specific signals
    if ctx.package_manager == "zypper":
        _detect_zypper_state(ctx)

    # systemd failed services
    _detect_failed_services(ctx)

    return ctx


def _detect_zypper_state(ctx: SystemContext) -> None:
    """Gather zypper-specific information."""
    try:
        result = subprocess.run(
            ["zypper", "--quiet", "lu", "--best-effort"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            # Count lines that look like package updates
            lines = [l for l in result.stdout.splitlines() if "|" in l and "v |" not in l.lower()]
            ctx.pending_updates = max(0, len(lines) - 2)  # subtract header lines
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    try:
        result = subprocess.run(
            ["rpm", "-qa", "--qf", "x"],
            capture_output=True, text=True, timeout=30,
        )
        ctx.installed_packages_count = len(result.stdout)
    except (subprocess.SubprocessError, FileNotFoundError):
        pass


def _detect_failed_services(ctx: SystemContext) -> None:
    """Detect failed systemd services."""
    try:
        result = subprocess.run(
            ["systemctl", "--failed", "--no-pager", "--plain", "--no-legend"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                parts = line.split()
                if parts:
                    ctx.services_failed.append(parts[0])
    except (subprocess.SubprocessError, FileNotFoundError):
        pass


def simulated_opensuse_context() -> SystemContext:
    """
    Return a simulated openSUSE Leap context for development/demo use.

    Useful when developing on macOS or non-openSUSE systems.
    """
    return SystemContext(
        distro="openSUSE Leap",
        distro_version="15.6",
        kernel="6.4.0-150600.23.25-default",
        arch="x86_64",
        hostname="localhost",
        desktop_env="KDE",
        package_manager="zypper",
        installed_packages_count=1847,
        disk_usage_percent=34.2,
        memory_total_gb=16.0,
        memory_available_gb=11.3,
        is_opensuse=True,
        boot_stage="first-boot",
        pending_updates=12,
        firewall_active=True,
        services_failed=[],
    )
