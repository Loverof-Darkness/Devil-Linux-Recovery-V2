# DEVIL Linux Recovery V2

**Universal Linux Boot Recovery Platform**

DEVIL V2 is an open-source recovery tool for Linux systems that no longer boot correctly because a bootloader, EFI entry, GRUB configuration, or related boot configuration has been damaged, replaced, or made inaccessible.

The target recovery experience is:

```text
Boot a suitable Linux Live USB
        ↓
Open a terminal
        ↓
Run the DEVIL launcher
        ↓
Discover storage + firmware + boot entries
        ↓
Choose the Linux installation to repair
        ↓
Review the resolved target and repair plan
        ↓
Confirm explicitly
        ↓
Repair + verify + report
```

## What is implemented

The V2 core now has a complete discovery → target → plan → guarded execution pipeline for its first supported repair class: **UEFI systems using GRUB**.

Implemented capabilities include:

- canonical disk/partition/EFI/OS models
- read-only firmware, block-device and EFI discovery
- mounted Linux candidate detection
- conservative Linux-only target selection
- EFI System Partition ambiguity detection
- explainable repair plans with per-step risk labels
- explicit `REPAIR` confirmation for mutations
- root-privilege enforcement for actual recovery
- temporary target mount/chroot lifecycle management
- EFI backup before GRUB mutation
- UEFI `grub-install` execution inside the selected Linux installation
- GRUB configuration regeneration using the target system's own tooling
- post-repair EFI verification
- Windows Boot Manager preservation checks when a Windows entry existed before repair
- structured JSON repair reports
- dry-run and machine-readable discovery output
- automated unit tests and CI/release workflows

The executor is intentionally narrow. It does **not** format partitions, unlock encrypted storage automatically, modify Windows BCD, delete unrelated EFI entries, or guess across ambiguous layouts.

## Why DEVIL exists

Linux boot recovery is powerful but often requires distribution-specific knowledge: identifying the EFI System Partition, finding the correct Linux root, understanding Btrfs subvolumes, mounting the right filesystems, entering a chroot, selecting the correct GRUB target, and restoring firmware boot entries.

A mistake in those steps can make a recovery attempt worse.

DEVIL's purpose is to turn that expert workflow into a guided, inspect-first process. The user selects **which operating system** needs repair rather than manually guessing partition names and commands.

## Design principles

1. **Detect before changing anything.**
2. **Never guess a destructive target.** Ambiguous mappings stop the workflow.
3. **Operate on an operating-system model, not raw partition guesses.**
4. **Prefer reversible actions and backups where practical.**
5. **Keep execution close to native Linux tools.**
6. **Make every important decision explainable.**
7. **Fail closed.** Uncertainty must result in a safe stop, not an aggressive repair.

## Architecture

DEVIL V2 uses a mixed Bash + Python design.

```text
Bash launcher
    │
    ▼
Python CLI
    │
    ├── Discovery
    │     ├── lsblk / blkid
    │     ├── EFI / firmware
    │     └── OS candidates
    │
    ├── Target resolver
    │     └── ambiguity + confidence gates
    │
    ├── Repair planner
    │     └── explicit, explainable steps
    │
    └── Recovery executor
          ├── backup
          ├── mount/chroot
          ├── GRUB UEFI repair
          └── verification/report
```

The boundary is deliberate:

```text
Python decides and validates.
Native Linux tools perform only approved recovery operations.
```

The discovery command adapter has its own allowlist and cannot execute recovery commands. Mutation-capable code lives in the separate `devil.recovery` package.

## CLI

Read-only diagnosis:

```bash
python -m devil.cli --diagnose
```

Machine-readable discovery:

```bash
python -m devil.cli --json
```

Resolve a selected Linux target without changing anything:

```bash
python -m devil.cli --plan
```

Build the full executable repair plan without changing anything:

```bash
python -m devil.cli --repair-plan
```

Execute the supported UEFI GRUB repair interactively:

```bash
sudo python -m devil.cli --repair --report /tmp/devil-repair.json
```

For non-interactive automation, `--yes` supplies the exact `REPAIR` confirmation token:

```bash
sudo python -m devil.cli --repair --yes --report /tmp/devil-repair.json
```

`--yes` does not bypass target safety checks, firmware checks, root checks, or plan support checks.

## Current recovery behavior

For a supported target the recovery transaction is:

```text
1. capture current EFI state
2. mount the selected Linux root read-write
3. mount separate /boot when explicitly identified
4. mount the selected EFI System Partition
5. bind /dev, /proc, /sys and /run into the chroot
6. back up the EFI tree
7. run the target system's grub-install for x86_64 UEFI
8. regenerate GRUB configuration
9. re-read EFI variables
10. confirm DEVIL-GRUB exists
11. confirm an existing Windows Boot Manager entry remains present
12. unmount temporary filesystems and write a report
```

The executor uses argument arrays rather than a shell, so user/device strings are not interpolated into shell commands.

## Detection scope

The discovery model is designed to grow toward:

- UEFI and legacy BIOS mode detection
- EFI System Partitions
- Linux filesystems and root candidates
- Btrfs subvolumes, including common `@` and `@root` layouts
- Ext4 and other common Linux filesystems
- LUKS awareness without silently unlocking encrypted storage
- LVM and software RAID awareness
- Windows Boot Manager detection
- multiple Linux installations
- existing GRUB installations and configuration locations
- firmware boot entries and BootOrder

At present, **mounted Linux roots are the conservative automatic OS candidates**. Unmounted filesystem probing, encrypted-root preparation, LVM activation, and RAID assembly are not silently attempted yet. They are explicit future compatibility work, because a Live USB must not assume that every block device can be safely mounted or activated.

## Safety model

DEVIL is recovery software, so knowing when **not** to act is a core feature.

The implementation enforces:

- read-only discovery by default
- explicit Linux target selection
- unique root/ESP resolution before mutation
- medium/high OS confidence before repair planning
- explicit confirmation before mutation
- root privilege requirement for recovery
- EFI backup before GRUB installation
- cleanup on success and failure
- verification after mutation
- no automatic encrypted-volume unlocking
- no Windows BCD modification
- no deletion of unrelated EFI entries
- fail-closed behavior on unsupported firmware or ambiguous target layouts

## Live USB bootstrap

The public launcher is intentionally small. A future stable release can provide a one-line bootstrap such as:

```bash
curl -fsSL https://raw.githubusercontent.com/Loverof-Darkness/Devil-Linux-Recovery-V2/main/launcher/devil.sh | bash
```

The bootstrap is responsible only for obtaining and launching a verified DEVIL payload. Recovery logic stays inside the versioned release package.

For development and offline testing:

```bash
bash launcher/devil.sh --source
```

## Repository structure

```text
.
├── launcher/             # Live-USB bootstrap and local launcher
├── devil/
│   ├── cli.py            # CLI orchestration
│   ├── models/           # Canonical normalized models
│   ├── discovery/        # Read-only discovery adapters
│   ├── planning/         # Target resolution + repair planning
│   └── recovery/         # Guarded UEFI/GRUB executor + reports
├── scripts/               # Small, reviewable shell operations
├── tests/                 # Unit and safety-focused tests
├── docs/                  # Architecture and safety documentation
├── .github/workflows/     # CI and release automation
└── pyproject.toml         # Python package metadata
```

## Development roadmap

### V2.1 — Discovery foundation

- canonical models
- firmware/block/EFI inventory
- conservative Linux candidate discovery
- JSON diagnostics
- safety-focused selection

### V2.2 — Target resolution

- unique root resolution
- EFI ambiguity checks
- firmware validation
- explainable target rendering

### V2.3 — Recovery planning

- risk-rated repair steps
- mutation/read-only boundaries
- explicit safety gates
- dry-run plan output

### V2.4 — First executable recovery class

- UEFI + GRUB executor
- target mount/chroot lifecycle
- EFI backup
- GRUB installation/configuration
- EFI verification
- Windows-entry preservation checks
- structured repair reports

### Next — Compatibility hardening

- safe unmounted filesystem probing
- Btrfs subvolume discovery and selection
- Arch/Garuda layouts
- Debian/Ubuntu/Mint layouts
- Fedora/RHEL-family layouts
- openSUSE layouts
- LUKS/LVM/RAID preparation as explicit user-approved operations
- BIOS/legacy GRUB recovery
- VM-based broken-boot regression lab
- signed release payloads and stable bootstrap verification

## Testing philosophy

DEVIL should be tested in two layers:

1. **Pure unit tests** for parsing, selection, target resolution, plan construction, and executor decision logic.
2. **Disposable VM scenarios** for real bootloader recovery, including broken EFI entries, missing GRUB configuration, separate /boot, Btrfs, and Windows dual boot.

The project should not claim universal compatibility until the relevant layouts have automated coverage.

## License

GPL-2.0. See [LICENSE](LICENSE).

## Repository

https://github.com/Loverof-Darkness/Devil-Linux-Recovery-V2
