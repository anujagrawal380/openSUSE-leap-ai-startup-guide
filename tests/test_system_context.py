"""Tests for system context detection."""

from opensuse_ai.system_context import (
    SystemContext,
    detect_system_context,
    simulated_opensuse_context,
)


def test_simulated_context():
    """Simulated context should represent a valid openSUSE Leap system."""
    ctx = simulated_opensuse_context()
    assert ctx.is_opensuse is True
    assert "Leap" in ctx.distro
    assert ctx.package_manager == "zypper"
    assert ctx.memory_total_gb > 0
    assert ctx.boot_stage == "first-boot"


def test_simulated_context_summary():
    """Summary should include key system information."""
    ctx = simulated_opensuse_context()
    summary = ctx.summary()
    assert "openSUSE Leap" in summary
    assert "zypper" in summary
    assert "first-boot" in summary
    assert "Memory" in summary


def test_detect_context_runs():
    """detect_system_context should not crash regardless of OS."""
    ctx = detect_system_context()
    assert isinstance(ctx, SystemContext)
    assert ctx.kernel != ""
    assert ctx.arch != ""


def test_context_summary_format():
    """Summary should be a multi-line string."""
    ctx = SystemContext(
        distro="TestOS",
        distro_version="1.0",
        kernel="5.0.0",
        arch="x86_64",
        package_manager="apt",
        memory_total_gb=8.0,
        memory_available_gb=4.0,
        disk_usage_percent=50.0,
    )
    summary = ctx.summary()
    lines = summary.strip().splitlines()
    assert len(lines) >= 5
    assert "TestOS" in summary
