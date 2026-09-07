from __future__ import annotations

import re

from devil.discovery.commands import CommandRunner
from devil.models.discovery import EfiEntry

_ENTRY = re.compile(r"^Boot(?P<num>[0-9A-Fa-f]{4})(?P<active>\*)?\s+(?P<label>.+?)(?:\s+HD\(.+)?$")
_PATH = re.compile(r"^\s*(?P<path>\\?\\?.*)$")


def collect(runner: CommandRunner) -> list[EfiEntry]:
    result = runner.run("efibootmgr", "--verbose")
    if result.returncode != 0:
        return []

    entries: list[EfiEntry] = []
    current_num: str | None = None
    current_label: str | None = None
    current_active = False
    current_path: str | None = None

    def flush() -> None:
        nonlocal current_num, current_label, current_active, current_path
        if current_num is not None and current_label is not None:
            entries.append(EfiEntry(current_num, current_label.strip(), current_path, current_active))
        current_num = current_label = current_path = None
        current_active = False

    for raw in result.stdout.splitlines():
        line = raw.rstrip()
        match = _ENTRY.match(line)
        if match:
            flush()
            current_num = match.group("num").upper()
            current_active = bool(match.group("active"))
            label = match.group("label")
            if "\t" in label:
                label = label.split("\t", 1)[0]
            if "HD(" in label:
                label = label.split("HD(", 1)[0]
            current_label = label.strip()
            if "File(" in line:
                current_path = line.split("File(", 1)[1].split(")", 1)[0]
        elif current_num is not None and "File(" in line:
            current_path = line.split("File(", 1)[1].split(")", 1)[0]
    flush()
    return entries
