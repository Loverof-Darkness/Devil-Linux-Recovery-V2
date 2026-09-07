from devil.models.system import OperatingSystem
from devil.discovery.selector import choose_linux, render_systems


def test_selector_filters_non_linux():
    systems = (
        OperatingSystem(name="Windows Boot Manager", family="Windows", confidence=0.99),
        OperatingSystem(name="Garuda Linux", family="Linux", root_device="/dev/nvme0n1p2", root_filesystem="btrfs", confidence=0.98),
    )
    selected = choose_linux(systems, "1")
    assert selected is not None
    assert selected.name == "Garuda Linux"


def test_selector_rejects_low_confidence():
    systems = (OperatingSystem(name="Unknown Linux", family="Linux", root_device="/dev/sda2", root_filesystem="ext4", confidence=0.5),)
    assert choose_linux(systems, "1") is None


def test_render_contains_safety_status():
    systems = (OperatingSystem(name="Linux", family="Linux", confidence=0.5),)
    output = render_systems(systems)
    assert "NOT SAFE TO SELECT" in output
