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

# When the assistant runs inside a container, the container's own rootfs is not
# the host. Set SUSE_AI_HOST_ROOT to a read-only bind-mount of the host root
# (e.g. `-v /:/host:ro -e SUSE_AI_HOST_ROOT=/host`) so detection reports the
# real openSUSE host instead of the container base image. Empty = native run.
HOST_ROOT = os.environ.get("SUSE_AI_HOST_ROOT", "").rstrip("/")


def _host_path(path: str) -> str:
    """Map an absolute system path to the host bind-mount, if configured."""
    return f"{HOST_ROOT}{path}" if HOST_ROOT else path


@dataclass
class SystemContext:
    """Snapshot of the current system state relevant to onboarding."""

    distro: str = ""
    distro_version: str = ""
    kernel: str = ""
    arch: str = ""
    hostname: str = ""
    desktop_env: str = ""
    installed_desktops: list[str] = field(default_factory=list)
    display_server: str = ""  # "wayland", "x11", or "" when unknown
    package_manager: str = ""
    installed_packages_count: int = 0
    root_filesystem: str = ""  # e.g. "btrfs", "ext4", "xfs"
    snapper_configured: bool = False
    gpu: str = ""  # e.g. "Intel", "AMD", "NVIDIA", "NVIDIA + Intel"
    locale: str = ""
    network_online: bool = False
    network_manager: str = ""  # "NetworkManager", "wicked", or ""
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
        desktop = self.desktop_env
        if not desktop and self.installed_desktops:
            desktop = f"{'/'.join(self.installed_desktops)} installed (no active session detected)"
        if desktop and self.display_server:
            desktop = f"{desktop} ({self.display_server})"

        fs_line = f"Root Filesystem: {self.root_filesystem or 'Not detected'}"
        if self.root_filesystem == "btrfs":
            fs_line += (
                " (Snapper snapshots configured — 'snapper rollback' available)"
                if self.snapper_configured
                else " (Snapper not configured)"
            )

        lines = [
            f"Distribution: {self.distro} {self.distro_version}",
            f"Kernel: {self.kernel}",
            f"Architecture: {self.arch}",
            f"Desktop Environment: {desktop or 'Not detected'}",
            f"Package Manager: {self.package_manager}",
            fs_line,
            f"Boot Stage: {self.boot_stage}",
            f"Memory: {self.memory_available_gb:.1f} GB available / {self.memory_total_gb:.1f} GB total",
            f"Disk Usage: {self.disk_usage_percent:.1f}%",
        ]
        if self.gpu:
            lines.append(f"GPU: {self.gpu}")
        if self.locale:
            lines.append(f"Locale: {self.locale}")
        network = "online" if self.network_online else "offline or unknown"
        if self.network_manager:
            network += f" (managed by {self.network_manager})"
        lines.append(f"Network: {network}")
        lines.append(f"Firewall: {'active (firewalld)' if self.firewall_active else 'not detected'}")
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
        with open(_host_path("/etc/os-release")) as f:
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

    # Package manager detection. When reading a host bind-mount, the container's
    # own PATH is irrelevant — probe the host filesystem for the binaries.
    if HOST_ROOT:
        if os.path.exists(_host_path("/usr/bin/zypper")):
            ctx.package_manager = "zypper"
        elif os.path.exists(_host_path("/usr/bin/dnf")):
            ctx.package_manager = "dnf"
        elif os.path.exists(_host_path("/usr/bin/apt")):
            ctx.package_manager = "apt"
        else:
            ctx.package_manager = "unknown"
    elif shutil.which("zypper"):
        ctx.package_manager = "zypper"
    elif shutil.which("dnf"):
        ctx.package_manager = "dnf"
    elif shutil.which("apt"):
        ctx.package_manager = "apt"
    else:
        ctx.package_manager = "unknown"

    # Desktop environment — active session (env vars) plus installed DEs
    # (session files survive into the host bind-mount where env vars don't).
    ctx.desktop_env = os.environ.get("XDG_CURRENT_DESKTOP", "") or os.environ.get("DESKTOP_SESSION", "")
    ctx.display_server = os.environ.get("XDG_SESSION_TYPE", "")
    ctx.installed_desktops = _detect_installed_desktops()

    # Filesystem, snapshots, GPU, locale, network
    ctx.root_filesystem = _detect_root_filesystem()
    # Either marker works; /.snapshots remains stat-able from a container
    # where SELinux denies reading /etc/snapper/configs contents.
    ctx.snapper_configured = os.path.exists(
        _host_path("/etc/snapper/configs/root")
    ) or os.path.isdir(_host_path("/.snapshots"))
    ctx.gpu = _detect_gpu()
    ctx.locale = _detect_locale()
    _detect_network(ctx)
    _detect_firewall(ctx)

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
        disk = psutil.disk_usage(HOST_ROOT or "/")
        ctx.disk_usage_percent = disk.percent
    except (ImportError, OSError):
        pass

    # zypper/systemctl probes run host binaries — only valid on a native run.
    # When reading a host bind-mount from inside a container, skip them rather
    # than report the container's (wrong) update/service state.
    if not HOST_ROOT:
        if ctx.package_manager == "zypper":
            _detect_zypper_state(ctx)
        _detect_failed_services(ctx)

    return ctx


def _detect_root_filesystem() -> str:
    """
    Detect the filesystem type of the (host) root volume.

    Reads /proc/mounts and looks for the mountpoint matching the host root —
    "/" natively, or the bind-mount path (e.g. "/host") inside a container.
    A bind-mount preserves the original fstype, so this works in both modes.
    """
    target = HOST_ROOT or "/"
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3 and parts[1] == target:
                    return parts[2]
    except OSError:
        pass
    return ""


def _detect_installed_desktops() -> list[str]:
    """List installed desktop environments from X11/Wayland session files."""
    desktops: set[str] = set()
    for sessions_dir in ("/usr/share/xsessions", "/usr/share/wayland-sessions"):
        try:
            for entry in os.listdir(_host_path(sessions_dir)):
                if entry.endswith(".desktop"):
                    name = entry[: -len(".desktop")].lower()
                    if "plasma" in name or name.startswith("kde"):
                        desktops.add("KDE Plasma")
                    elif "gnome" in name:
                        desktops.add("GNOME")
                    elif "xfce" in name:
                        desktops.add("Xfce")
                    else:
                        desktops.add(entry[: -len(".desktop")])
        except OSError:
            continue
    return sorted(desktops)


# PCI vendor IDs as they appear in /sys/class/drm/card*/device/vendor
_GPU_VENDORS = {
    "0x10de": "NVIDIA",
    "0x1002": "AMD",
    "0x8086": "Intel",
    "0x1af4": "virtio (VM)",
    "0x15ad": "VMware",
    "0x1234": "QEMU",
}


def _detect_gpu() -> str:
    """
    Detect GPU vendor(s) from sysfs DRM entries.

    Avoids spawning lspci; works natively and through a recursive host
    bind-mount (/host/sys). Returns e.g. "Intel", "NVIDIA + Intel", or "".
    """
    vendors: list[str] = []
    drm_dir = _host_path("/sys/class/drm")
    try:
        for card in sorted(os.listdir(drm_dir)):
            # cards only, not connectors like card0-HDMI-A-1
            if not card.startswith("card") or "-" in card:
                continue
            vendor_file = os.path.join(drm_dir, card, "device", "vendor")
            try:
                with open(vendor_file) as f:
                    vendor_id = f.read().strip()
            except OSError:
                continue
            vendor = _GPU_VENDORS.get(vendor_id, vendor_id)
            if vendor not in vendors:
                vendors.append(vendor)
    except OSError:
        pass
    return " + ".join(vendors)


def _detect_locale() -> str:
    """Detect the system locale from the environment or /etc/locale.conf."""
    if not HOST_ROOT:
        for var in ("LC_ALL", "LANG"):
            value = os.environ.get(var, "")
            if value:
                return value
    try:
        with open(_host_path("/etc/locale.conf")) as f:
            for line in f:
                key, _, value = line.strip().partition("=")
                if key in ("LANG", "LC_ALL") and value:
                    return value.strip('"')
    except OSError:
        pass
    return ""


def _detect_network(ctx: SystemContext) -> None:
    """
    Detect network state without making any network calls.

    Online = a default route exists in /proc/net/route (destination 00000000).
    With --network=host the container shares the host network namespace, so
    this is accurate in both native and container modes.
    """
    try:
        with open("/proc/net/route") as f:
            next(f, None)  # header
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "00000000":
                    ctx.network_online = True
                    break
    except OSError:
        pass

    # Which network management stack is in charge — runtime state dirs work
    # through the host bind-mount; env-independent.
    if os.path.isdir(_host_path("/run/NetworkManager")):
        ctx.network_manager = "NetworkManager"
    elif os.path.exists(_host_path("/run/wicked")) or os.path.isdir(_host_path("/var/run/wicked")):
        ctx.network_manager = "wicked"


def _detect_firewall(ctx: SystemContext) -> None:
    """Detect whether firewalld is running (runtime dir works in both modes)."""
    if os.path.isdir(_host_path("/run/firewalld")):
        ctx.firewall_active = True
        return
    if not HOST_ROOT and shutil.which("systemctl"):
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "--quiet", "firewalld"],
                timeout=5,
            )
            ctx.firewall_active = result.returncode == 0
        except subprocess.SubprocessError:
            pass


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
        installed_desktops=["KDE Plasma"],
        display_server="wayland",
        package_manager="zypper",
        installed_packages_count=1847,
        root_filesystem="btrfs",
        snapper_configured=True,
        gpu="Intel",
        locale="en_US.UTF-8",
        network_online=True,
        network_manager="NetworkManager",
        disk_usage_percent=34.2,
        memory_total_gb=16.0,
        memory_available_gb=11.3,
        is_opensuse=True,
        boot_stage="first-boot",
        pending_updates=12,
        firewall_active=True,
        services_failed=[],
    )
