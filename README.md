# DEVIL Linux Recovery V2

**Universal Linux Boot Recovery Platform**

DEVIL V2 is an open-source recovery tool for Linux systems that no longer boot correctly because a bootloader, EFI entry, GRUB configuration, or related boot configuration has been damaged, replaced, or made inaccessible.

The project is designed for one simple recovery experience:

```text
Boot any suitable Linux Live USB
        ↓
Open a terminal
        ↓
Run one command
        ↓
DEVIL downloads and starts
        ↓
Detect all installed operating systems
        ↓
Choose the Linux installation to repair
        ↓
Review the proposed repair
        ↓
Confirm
        ↓
Repair + verify + report
```

## Why DEVIL exists

Linux boot recovery is powerful but often requires distribution-specific knowledge: identifying the EFI System Partition, finding the correct Linux root, understanding Btrfs subvolumes, mounting the right filesystems, entering a chroot, selecting the correct GRUB target, and restoring firmware boot entries.

A mistake in those steps can make a recovery attempt worse.

DEVIL's purpose is to turn that expert workflow into a guided, inspect-first process. The user should select **which operating system** needs repair rather than manually guessing partition names and commands.

### Benefits

- **Accessible recovery:** useful to beginners without hiding the technical work from advanced users.
- **Multi-boot aware:** identify Linux installations and Windows boot components before proposing a repair.
- **Safety oriented:** diagnostics are read-only; mutations require an explicit confirmation step.
- **Transparent:** show the detected target, planned changes, commands, warnings, and results.
- **Cross-distribution:** build adapters so recovery logic is not tied to one Linux family.
- **Live-USB friendly:** no permanent installation is required for the recovery session.
- **Self-contained distribution:** the GitHub project contains the complete source; the bootstrap command retrieves the required release payload automatically.
- **Auditable:** preserve logs, detected topology, chosen target, repair actions, and verification results.

## Design principles

1. **Detect before changing anything.**
2. **Never guess a destructive target.** Ambiguous mappings stop the workflow.
3. **Operate on an operating-system model, not raw partition guesses.**
4. **Prefer reversible actions and backups where practical.**
5. **Keep the execution layer close to native Linux tools.**
6. **Make every important decision explainable.**
7. **Fail closed.** Uncertainty must result in a safe stop, not an aggressive repair.

## Architecture

DEVIL V2 uses a mixed Bash + Python design.

- **Bash bootstrap:** must be usable from a normal Linux Live USB terminal and handle download, extraction, launch, and basic environment checks.
- **Python core:** discovery, normalized system models, repair planning, safety checks, terminal UI, structured logging, and reporting.
- **Shell adapters:** execute carefully reviewed native operations such as `mount`, `btrfs`, `efibootmgr`, `grub-install`, and GRUB configuration generation.

The guiding boundary is:

```text
Python decides and validates.
Bash/native tools perform approved system operations.
```

No third-party Python package should be required merely to start the recovery engine. Optional dependencies, when introduced later, must have a clear Live-USB fallback.

## Planned detection scope

The initial design targets:

- UEFI and legacy BIOS mode detection
- EFI System Partitions
- Linux filesystems and root candidates
- Btrfs subvolumes, including common `@` and `@root` layouts
- Ext4 and other common Linux filesystems
- LUKS awareness without silently unlocking encrypted storage
- LVM and software RAID awareness
- Windows Boot Manager detection
- Multiple Linux installations
- Existing GRUB installations and configuration locations
- Firmware boot entries and BootOrder

DEVIL must refuse to guess when several targets remain plausible.

## Recovery scope

The recovery engine is being built incrementally around safe, reviewable operations:

- Restore or recreate a Linux EFI boot entry when the mapping is unambiguous
- Repair/regenerate GRUB configuration for a selected Linux installation
- Guided GRUB reinstall for supported UEFI layouts
- Validate BootOrder and restore the selected Linux entry when appropriate
- Preserve existing Windows boot components rather than modifying Windows BCD
- Verify the result after each mutation
- Record a recovery report and command transcript

Filesystem unlock, LVM activation, RAID assembly, and other environment-specific preparation will remain explicit operations rather than hidden guesses.

## User experience goal

Example discovery screen:

```text
DEVIL Linux Recovery V2

Scanning storage and firmware...

Detected operating systems:

  1. Garuda Linux        Btrfs    /dev/nvme0n1p2
  2. Ubuntu 24.04        Ext4     /dev/nvme0n1p5
  3. Windows Boot Manager        EFI

Select the Linux installation to repair [1-3]:
>
```

Then:

```text
Repair plan

Target:       Garuda Linux
Root:         /dev/nvme0n1p2 (Btrfs subvolume @)
EFI:          /dev/nvme0n1p1
Firmware:     UEFI
GRUB target:  x86_64-efi

Planned actions:
  • create recovery metadata/backup
  • mount target filesystems
  • reinstall or repair the Linux EFI loader
  • regenerate GRUB configuration
  • verify EFI entry and generated configuration

No Windows files will be modified.

Proceed? [y/N]
```

## Command-line bootstrap

The public installation experience is intentionally small. A future stable release will provide a one-line bootstrap such as:

```bash
curl -fsSL https://raw.githubusercontent.com/Loverof-Darkness/Devil-Linux-Recovery-V2/main/launcher/devil.sh | bash
```

The bootstrap is responsible only for obtaining and launching a verified DEVIL release payload. Recovery logic remains inside the versioned project/release package.

For development and offline testing, the repository can also be executed directly:

```bash
bash launcher/devil.sh --source
```

## Repository structure

```text
.
├── launcher/             # Live-USB bootstrap and local launcher
├── devil/                # Python application package
│   ├── cli.py
│   ├── models/
│   ├── detectors/
│   ├── planners/
│   ├── recovery/
│   ├── adapters/
│   ├── ui/
│   └── reporting/
├── scripts/              # Small, reviewable shell operations
├── tests/                # Unit and safety-focused tests
├── docs/                 # Architecture, recovery model, safety policy
├── .github/workflows/    # CI and release automation
└── pyproject.toml        # Python project metadata and test configuration
```

## Development roadmap

### Phase 0 — Foundation

- Repository structure
- Bootstrap contract
- Python package skeleton
- Normalized data models
- Logging and error model
- CI on pushes and pull requests
- Tagged-release packaging

### Phase 1 — Read-only discovery

- Firmware mode detection
- Disk/partition inventory
- Filesystem identification
- EFI discovery
- Linux installation discovery
- Btrfs subvolume discovery
- Windows boot detection
- Boot-entry inventory
- Human-readable and JSON diagnostics

### Phase 2 — Target selection and repair planning

- Convert raw discovery into OS candidates
- Confidence scoring and ambiguity detection
- Explainable repair plans
- Safety gates
- Dry-run execution model

### Phase 3 — Recovery operations

- EFI entry recovery
- GRUB configuration recovery
- Guided UEFI GRUB reinstall
- Mount/chroot lifecycle management
- Backups and rollback metadata
- Post-repair verification

### Phase 4 — Compatibility hardening

- Arch/Garuda
- Debian/Ubuntu/Mint
- Fedora/RHEL family
- openSUSE
- additional supported layouts based on automated test coverage

### Phase 5 — Virtual-machine recovery lab

Build reproducible test scenarios for broken EFI entries, damaged GRUB configuration, multi-boot layouts, Btrfs roots, and common recovery failures. The project should prefer evidence from automated test fixtures over unsupported success-rate claims.

## Release and deployment model

GitHub Actions will enforce the development and release path:

### Pull requests and pushes

- Python syntax/type/lint checks where configured
- Unit tests
- Shell syntax checks
- Bootstrap smoke tests
- Package consistency checks

### Version tags

A release tag such as `v2.0.0` will:

1. Run the complete test suite.
2. Build the portable release archive.
3. Generate SHA-256 checksums.
4. Publish GitHub release assets.
5. Make the release the source of truth for the stable bootstrap payload.

Release automation must never publish an untested build.

## Safety model

DEVIL is recovery software, so correctness includes knowing when **not** to act.

The implementation must enforce:

- read-only discovery by default
- explicit target selection
- explicit confirmation before mutation
- command logging
- cleanup on success and failure
- refusal on ambiguous storage mappings
- no automatic unlocking of encrypted roots
- no Windows BCD modification
- no silent deletion of unknown EFI entries

## Project status

**Current stage:** V2 foundation.

The repository is intentionally being built in small, testable layers. Recovery actions will be added only after the discovery and safety model can accurately represent the systems they are expected to repair.

## License

GPL-2.0. See [LICENSE](LICENSE).

## Repository

https://github.com/Loverof-Darkness/Devil-Linux-Recovery-V2
