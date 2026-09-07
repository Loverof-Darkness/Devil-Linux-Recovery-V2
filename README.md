# DEVIL Linux Recovery V2

**Devil Emergency Verification & Intelligent Linux Recovery — V2**

A safety-first Linux boot and recovery toolkit focused on deterministic diagnostics, explicit operator control, reversible repairs, and strong separation between inspection and mutation.

## Status

🚧 **V2 foundation / active development**

This repository is the next-generation development line for DEVIL. The stable V1 implementation remains in [`Loverof-Darkness/Linux_Recovery`](https://github.com/Loverof-Darkness/Linux_Recovery).

## Design Goals

- Read-only diagnostics by default
- Explicit, reviewable recovery plans
- No guessing of disks, roots, ESPs, or boot targets
- Safe handling of Btrfs, EFI, GRUB, LUKS/LVM/RAID environments
- Backups before every mutation
- Reversible operations where technically possible
- Auditable command execution and recovery transcripts
- Test and dry-run modes for every recovery workflow
- Clear separation of detection, planning, execution, and verification
- Bash-native and suitable for Live ISO environments

## Planned Architecture

```text
src/
├── core/          # runtime, logging, state, safety policy
├── detect/        # firmware, storage, filesystem, OS, bootloader detection
├── plan/          # deterministic recovery plan generation
├── recover/       # guarded recovery operations
├── verify/        # post-repair verification
├── ui/            # terminal interface
└── report/        # reports and audit artifacts

tests/             # unit, integration, safety, and fixture tests
docs/              # architecture, recovery flows, threat model, operator guide
scripts/            # development and validation utilities
```

## Safety Principle

DEVIL V2 must **never turn uncertainty into an irreversible action**. When target mapping, firmware mode, mount layout, or required tooling is ambiguous, the operation must stop and request an explicit operator decision.

## License

GPL-2.0. See [`LICENSE`](LICENSE).
