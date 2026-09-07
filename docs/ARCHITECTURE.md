# DEVIL V2 Architecture

## System layers

```text
Live USB terminal
      │
      ▼
Bash bootstrap
  download / extract / launch
      │
      ▼
Python core
  CLI / UI / models / orchestration
      │
      ├── Detection adapters
      │     ├── disks + partitions
      │     ├── filesystems
      │     ├── EFI + firmware
      │     ├── Linux installations
      │     └── Windows boot components
      │
      ├── Planning engine
      │     ├── target selection
      │     ├── confidence
      │     ├── ambiguity checks
      │     └── repair plan
      │
      └── Recovery adapters
            ├── mounts / chroot lifecycle
            ├── EFI operations
            ├── GRUB operations
            └── verification
```

## Normalized discovery model

Raw command output must be converted into stable Python models before planning. Recovery code should consume normalized records rather than parse `lsblk`, `blkid`, `efibootmgr`, or Btrfs output independently.

The first model set is in `devil/models/system.py`.

## Command execution boundary

Native system commands are not treated as arbitrary shell strings. Recovery modules will construct structured operations, validate their inputs, and execute only after the plan has passed safety gates.

Future executor requirements:

- capture stdout/stderr and exit status
- preserve exact command arguments in the audit log
- support dry-run
- enforce timeouts where appropriate
- guarantee cleanup handlers execute on failure
- prevent accidental interpolation of untrusted device labels or paths

## Target model

A user-visible recovery target represents an operating system. It should contain enough evidence to map:

`OS → root → optional /boot → EFI System Partition → bootloader`

A target is repairable only when the mapping is sufficiently certain. Multiple plausible roots, ESPs, or loaders must produce an explicit ambiguity state.

## Recovery transaction

The intended mutation lifecycle is:

1. snapshot discovery state
2. present target and repair plan
3. require explicit confirmation
4. create appropriate backup/restore metadata
5. mount required filesystems
6. perform the smallest supported mutation
7. verify the resulting files/EFI state
8. cleanly unmount temporary mounts
9. write a final audit report

A later transaction manager will make these steps reusable across EFI and GRUB repair operations.
