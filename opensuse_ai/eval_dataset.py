"""
Evaluation dataset for answer-quality benchmarking.

Each item pairs an onboarding question with a concise gold-standard answer
(used for embedding similarity) and a list of expected facts (used by the
LLM judge as a grounding checklist). Answers are written from the official
openSUSE Leap documentation so a correct, grounded response scores well.
"""

from dataclasses import dataclass, field


@dataclass
class EvalItem:
    """A single quality-evaluation question with its reference answer."""

    id: str
    query: str
    reference: str
    expected_facts: list[str] = field(default_factory=list)


EVAL_ITEMS: list[EvalItem] = [
    EvalItem(
        id="install_package",
        query="How do I install a package using zypper?",
        reference=(
            "Use 'sudo zypper install <package>' (short form 'sudo zypper in "
            "<package>') to install a package. zypper resolves dependencies "
            "automatically and prompts for confirmation before downloading and "
            "installing."
        ),
        expected_facts=["zypper install", "sudo", "dependency resolution"],
    ),
    EvalItem(
        id="add_repo",
        query="How do I add a new software repository in openSUSE?",
        reference=(
            "Add a repository with 'sudo zypper addrepo <URL> <alias>' (short "
            "'zypper ar'), then refresh metadata with 'sudo zypper refresh'. "
            "The first refresh imports and asks you to trust the repository's "
            "GPG key. List repositories with 'zypper repos' (zypper lr)."
        ),
        expected_facts=["zypper addrepo", "zypper refresh", "GPG key", "alias"],
    ),
    EvalItem(
        id="update_system",
        query="How do I keep my openSUSE Leap system up to date?",
        reference=(
            "Refresh repositories then apply updates with 'sudo zypper refresh' "
            "followed by 'sudo zypper update' (zypper up) for package updates, "
            "or 'sudo zypper dup' for a full distribution upgrade when moving "
            "between versions. YaST Online Update is the graphical alternative."
        ),
        expected_facts=["zypper update", "zypper refresh", "sudo"],
    ),
    EvalItem(
        id="snapper_rollback",
        query="How do I roll back my system after a bad update using snapshots?",
        reference=(
            "On a Btrfs root with Snapper configured, list snapshots with "
            "'sudo snapper list', then roll back the system to a known-good "
            "snapshot with 'sudo snapper rollback <number>' and reboot. Snapper "
            "takes pre/post snapshots automatically around zypper operations, "
            "and you can also boot a read-only snapshot from the GRUB menu."
        ),
        expected_facts=["snapper rollback", "Btrfs", "snapper list", "reboot"],
    ),
    EvalItem(
        id="firewall",
        query="How do I open a port in the firewall on openSUSE Leap?",
        reference=(
            "openSUSE Leap uses firewalld. Open a port persistently with "
            "'sudo firewall-cmd --permanent --add-port=<port>/tcp' (or add a "
            "service with --add-service), then apply it with "
            "'sudo firewall-cmd --reload'. Check state with 'firewall-cmd "
            "--list-all'. YaST also provides a firewall module."
        ),
        expected_facts=["firewalld", "firewall-cmd", "--permanent", "--reload"],
    ),
    EvalItem(
        id="nvidia_driver",
        query="How do I install the proprietary NVIDIA graphics driver?",
        reference=(
            "Add the NVIDIA repository for your Leap version with 'sudo zypper "
            "addrepo', refresh, then install the driver with 'sudo zypper "
            "install-new-recommends' or the matching nvidia packages "
            "('zypper in x11-video-nvidiaG0x'). Reboot afterwards so the kernel "
            "module loads. The driver is also available via YaST."
        ),
        expected_facts=["NVIDIA repository", "zypper", "reboot", "kernel module"],
    ),
    EvalItem(
        id="yast",
        query="What is YaST and what can I do with it?",
        reference=(
            "YaST (Yet another Setup Tool) is openSUSE's central system "
            "administration tool. It manages software installation, "
            "repositories, network and firewall settings, users, services, "
            "partitioning and more, with both a graphical (Qt/GTK) and a "
            "text-mode (ncurses) interface launched via 'sudo yast2' or 'sudo "
            "yast'."
        ),
        expected_facts=["system administration", "software", "graphical and text mode"],
    ),
    EvalItem(
        id="tumbleweed_vs_leap",
        query="What is the difference between openSUSE Leap and Tumbleweed?",
        reference=(
            "Leap is the stable, point-release distribution sharing its core "
            "with SUSE Linux Enterprise — best for servers and users wanting "
            "stability. Tumbleweed is a rolling release with the newest "
            "packages, updated continuously — best for users wanting the "
            "latest software. Both use zypper and YaST."
        ),
        expected_facts=["Leap stable point release", "Tumbleweed rolling release"],
    ),
    EvalItem(
        id="packman_vendor_change",
        query="How do I enable Packman and switch multimedia packages to it safely?",
        reference=(
            "Add the Packman repository for your openSUSE version, refresh "
            "metadata, then perform a vendor switch only for the Packman repo, "
            "for example with 'sudo zypper dup --from packman "
            "--allow-vendor-change'. Review the transaction carefully because "
            "vendor changes replace packages from the openSUSE vendor with "
            "Packman builds. Keep repositories enabled and use 'zypper lr -d' "
            "to verify aliases and priorities."
        ),
        expected_facts=[
            "Packman repository",
            "zypper dup --from packman",
            "--allow-vendor-change",
            "review transaction",
        ],
    ),
    EvalItem(
        id="codecs",
        query="How do I install multimedia codecs on openSUSE Leap?",
        reference=(
            "For patent-restricted multimedia codecs, openSUSE users commonly "
            "enable the Packman repository and install or switch the relevant "
            "GStreamer, ffmpeg, and VLC-related packages from Packman. Refresh "
            "repositories first, then use zypper to install the needed codec "
            "packages or perform the Packman vendor switch. Check the official "
            "openSUSE wiki guidance for the exact repository matching your "
            "Leap version."
        ),
        expected_facts=["Packman", "GStreamer", "ffmpeg", "zypper", "Leap version"],
    ),
    EvalItem(
        id="wifi_bluetooth",
        query="Wi-Fi or Bluetooth is not working after installing openSUSE. What should I check?",
        reference=(
            "First check whether the device is detected with tools such as "
            "'lspci', 'lsusb', 'ip link', 'rfkill list', and Bluetooth service "
            "status. Make sure airplane mode or rfkill is not blocking the "
            "device, NetworkManager is running for Wi-Fi, and bluetooth.service "
            "is enabled/running for Bluetooth. Some adapters need firmware "
            "packages from the openSUSE repositories; install missing firmware "
            "and reboot or reload the driver."
        ),
        expected_facts=[
            "rfkill",
            "NetworkManager",
            "bluetooth.service",
            "firmware packages",
            "lspci or lsusb",
        ],
    ),
    EvalItem(
        id="disk_full_snapshots",
        query="My disk is full because of Btrfs snapshots. How do I free space safely?",
        reference=(
            "Check space with 'btrfs filesystem usage /' and inspect snapshots "
            "with 'sudo snapper list'. Use Snapper cleanup policies first, for "
            "example 'sudo snapper cleanup number' or timeline cleanup, instead "
            "of deleting files inside /.snapshots manually. You can adjust "
            "Snapper limits in the root config and should keep at least one "
            "known-good snapshot before removing old ones."
        ),
        expected_facts=[
            "btrfs filesystem usage",
            "snapper list",
            "snapper cleanup",
            "do not manually delete /.snapshots",
        ],
    ),
    EvalItem(
        id="failed_systemd_services",
        query="How do I investigate failed systemd services on openSUSE?",
        reference=(
            "List failed units with 'systemctl --failed'. Inspect one service "
            "with 'systemctl status <unit>' and read logs with 'journalctl -u "
            "<unit> -b'. After fixing the cause, restart the service with "
            "'sudo systemctl restart <unit>' and clear the failed state with "
            "'sudo systemctl reset-failed <unit>' if needed."
        ),
        expected_facts=[
            "systemctl --failed",
            "systemctl status",
            "journalctl -u",
            "restart",
            "reset-failed",
        ],
    ),
]
