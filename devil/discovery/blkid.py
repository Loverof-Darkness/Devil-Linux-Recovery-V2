from __future__ import annotations

from devil.discovery.commands import CommandRunner


def collect(runner: CommandRunner) -> dict[str, dict[str, str]]:
    result = runner.run("blkid", "-o", "export")
    records: dict[str, dict[str, str]] = {}
    if result.returncode != 0:
        return records
    current: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            if current.get("DEVNAME"):
                records[current["DEVNAME"]] = current
            current = {}
            continue
        key, sep, value = line.partition("=")
        if sep:
            current[key] = value
    if current.get("DEVNAME"):
        records[current["DEVNAME"]] = current
    return records
