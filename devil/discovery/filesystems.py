from __future__ import annotations

from pathlib import Path

from devil.discovery.commands import CommandRunner


def btrfs_subvolumes(runner: CommandRunner, mountpoint: str) -> list[str]:
    if not Path(mountpoint).is_dir():
        return []
    result = runner.run("btrfs", "subvolume", "list", "-o", mountpoint)
    if result.returncode != 0:
        return []
    values: list[str] = []
    for line in result.stdout.splitlines():
        marker = " path "
        if marker in line:
            values.append(line.split(marker, 1)[1].strip())
    return values
