from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner:
    """Read-only system command adapter. Recovery code must use a separate adapter."""

    def __init__(self, *, allow: set[str] | None = None) -> None:
        self.allow = allow or {
            "lsblk",
            "blkid",
            "findmnt",
            "mountpoint",
            "btrfs",
            "efibootmgr",
            "uname",
            "cat",
            "grep",
            "find",
        }

    def available(self, command: str) -> bool:
        return shutil.which(command) is not None

    def run(self, command: str, *args: str, timeout: int = 15) -> CommandResult:
        if command not in self.allow:
            raise ValueError(f"command is not allowed in discovery adapter: {command}")
        if not self.available(command):
            return CommandResult(127, "", f"command not found: {command}")
        completed = subprocess.run(
            [command, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)
