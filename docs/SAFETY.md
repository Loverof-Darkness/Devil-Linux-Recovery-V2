# DEVIL V2 Safety Policy

DEVIL handles bootloader and firmware-adjacent operations. Safety is therefore a functional requirement, not just documentation.

## Mandatory rules

### Read-only discovery first

Device discovery, filesystem identification, OS detection, EFI inventory, and diagnostics must not modify disks, filesystems, firmware variables, or installed operating-system files.

### Explicit target

No recovery operation may infer a target merely because it is the first Linux partition found. The target must be represented as an identified operating system with evidence linking its root, boot, and EFI components.

### Ambiguity stops recovery

When DEVIL cannot distinguish between multiple plausible roots, ESPs, bootloader installations, or firmware targets, it must stop and ask the user to resolve the ambiguity.

### Plan before mutation

Every mutation must be converted into a human-readable repair plan before execution. The plan should explain what will change and what will not change.

### Confirmation before mutation

The recovery executor must require explicit confirmation for system changes. A diagnostics command must never implicitly escalate into repair.

### No silent encrypted-volume unlocking

LUKS, LVM, and RAID may be detected and described. Unlocking, activation, or assembly must be an explicit operator action until a dedicated, audited workflow exists.

### Preserve other operating systems

Windows BCD is outside the scope of the initial recovery engine. EFI operations must avoid deleting unrelated loaders, and Windows Boot Manager should be detected and preserved.

### Cleanup on every path

Temporary mounts, bind mounts, chroots, loop devices, and other recovery resources must have deterministic cleanup on success, failure, interruption, and user cancellation.

## Release rule

A release must pass automated unit/shell checks before publication. Recovery functionality must additionally gain scenario coverage in the VM recovery lab before being advertised as supported.
