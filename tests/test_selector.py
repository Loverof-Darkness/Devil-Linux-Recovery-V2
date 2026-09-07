from devil.models.discovery import OperatingSystem
from devil.discovery.selector import choose_linux, render_systems


def linux(name="Garuda Linux", confidence="high"):
    return OperatingSystem(
        os_id="linux-1",
        name=name,
        family="Linux",
        root_device="/dev/nvme0n1p2",
        root_filesystem="btrfs",
        root_mountpoint="/mnt/garuda",
        confidence=confidence,
    )


def test_selector_filters_non_linux():
    systems = [
        OperatingSystem(os_id="windows-1", name="Windows Boot Manager", family="Windows", confidence="high"),
        linux(),
    ]
    selected = choose_linux(systems, "1")
    assert selected is not None
    assert selected.name == "Garuda Linux"


def test_selector_rejects_low_confidence():
    assert choose_linux([linux("Unknown Linux", "low")], "1") is None


def test_render_contains_safety_status():
    output = render_systems([linux("Unknown Linux", "low")])
    assert "NOT SAFE TO SELECT" in output
