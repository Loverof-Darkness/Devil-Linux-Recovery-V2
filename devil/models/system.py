"""Compatibility re-export for the canonical DEVIL discovery model.

The V2 codebase uses :mod:`devil.models.discovery` as the single source of
truth. This module remains as a stable import path for early callers.
"""

from devil.models.discovery import EfiEntry, OperatingSystem, Partition, DiscoverySnapshot

__all__ = ["Partition", "OperatingSystem", "EfiEntry", "DiscoverySnapshot"]
