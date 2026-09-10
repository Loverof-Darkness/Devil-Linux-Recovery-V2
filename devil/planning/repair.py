"""Build a non-executing recovery plan from a resolved target.

The planner never runs shell commands. Every mutation is represented as an
explicit step with a risk level and a requirement for human confirmation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from devil.planning.target import TargetLayout


@dataclass(frozen=True)
class RepairStep:
    step_id: str
    title: str
    description: str
    operation: str
    risk: str
    requires_root: bool = True
    mutates_system: bool = True
    reversible: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RepairPlan:
    target: TargetLayout
    supported: bool
    safe_to_execute: bool
    reasons: tuple[str, ...]
    steps: tuple[RepairStep, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": asdict(self.target),
            "supported": self.supported,
            "safe_to_execute": self.safe_to_execute,
            "reasons": list(self.reasons),
            "steps": [step.to_dict() for step in self.steps],
        }


def build_repair_plan(target: TargetLayout) -> RepairPlan:
    reasons = list(target.reasons)
    if not target.safe:
        reasons.append("target layout is not safe")
        return RepairPlan(target, False, False, tuple(dict.fromkeys(reasons)))

    if target.firmware_mode.lower() != "uefi":
        reasons.append("automatic mutation is currently limited to UEFI targets")
    if not target.root_device:
        reasons.append("Linux root device is unresolved")
    if not target.efi_device:
        reasons.append("EFI System Partition is unresolved")

    if reasons:
        return RepairPlan(target, False, False, tuple(dict.fromkeys(reasons)))

    steps = (
        RepairStep(
            "capture-state",
            "Capture current boot state",
            "Record firmware mode, discovered EFI entries, target layout, and relevant boot files before mutation.",
            "capture_state",
            "LOW",
            reversible=True,
        ),
        RepairStep(
            "backup-efi",
            "Back up the EFI loader state",
            "Create a timestamped backup of the target EFI loader directory and preserve existing EFI files.",
            "backup_efi",
            "MEDIUM",
            reversible=True,
        ),
        RepairStep(
            "mount-target",
            "Mount the selected Linux target",
            "Mount root read-write only for the repair transaction, plus /boot and the selected EFI System Partition when required.",
            "mount_target",
            "MEDIUM",
            reversible=True,
        ),
        RepairStep(
            "install-grub",
            "Install/reinstall GRUB for UEFI",
            "Run the target distribution's GRUB installer against the selected EFI System Partition without touching unrelated operating systems.",
            "install_grub_uefi",
            "HIGH",
            reversible=True,
        ),
        RepairStep(
            "promote-bootorder",
            "Put the repaired Linux loader first",
            "Set the new DEVIL-GRUB EFI entry first in BootOrder while preserving every existing entry after it.",
            "promote_boot_order",
            "HIGH",
            reversible=True,
        ),
        RepairStep(
            "regenerate-config",
            "Regenerate GRUB configuration",
            "Generate a fresh /boot/grub/grub.cfg using the repaired Linux installation's own userspace tools.",
            "regenerate_grub_config",
            "MEDIUM",
            reversible=True,
        ),
        RepairStep(
            "verify-efi",
            "Verify EFI loaders and Windows preservation",
            "Re-read EFI entries and verify the Microsoft boot loader remains present when it existed before repair.",
            "verify_efi_state",
            "LOW",
            mutates_system=False,
            reversible=True,
        ),
        RepairStep(
            "cleanup",
            "Unmount and finalize report",
            "Remove temporary mounts, restore mount namespaces, and write a machine-readable repair report.",
            "cleanup",
            "LOW",
            mutates_system=False,
            reversible=True,
        ),
    )
    return RepairPlan(target, True, True, (), steps)


def render_repair_plan(plan: RepairPlan) -> str:
    lines = ["DEVIL Recovery Plan", "", f"Target: {plan.target.os_name}", f"OS ID:   {plan.target.os_id}", ""]
    if not plan.supported or not plan.safe_to_execute:
        lines.append("Status: BLOCKED")
        for reason in plan.reasons:
            lines.append(f"  - {reason}")
        return "\n".join(lines)

    lines.append("Status: READY FOR EXPLICIT USER CONFIRMATION")
    lines.append("")
    lines.append("Steps:")
    for index, step in enumerate(plan.steps, 1):
        mutation = "mutation" if step.mutates_system else "read-only"
        lines.append(f"{index}. [{step.risk}] {step.title} ({mutation})")
        lines.append(f"   {step.description}")
    return "\n".join(lines)
