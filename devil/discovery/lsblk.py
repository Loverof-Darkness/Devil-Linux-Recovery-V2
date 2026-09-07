from __future__ import annotations

import json
from typing import Any

from devil.discovery.commands import CommandRunner


def collect(runner: CommandRunner) -> list[dict[str, Any]]:
    result = runner.run(
        "lsblk",
        "--json",
        "--bytes",
        "--paths",
        "-o",
        "NAME,KNAME,PATH,TYPE,FSTYPE,LABEL,UUID,PARTUUID,PARTTYPE,SIZE,MOUNTPOINTS,PKNAME,PARTFLAGS",
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    return payload.get("blockdevices", [])
