# DEVIL Safety Model

DEVIL treats boot recovery as a high-impact operation. The implementation is designed to stop rather than guess.

## State machine

```text
DISCOVER
   ↓
NORMALIZE
   ↓
SELECT LINUX OS
   ↓
RESOLVE UNIQUE ROOT + ESP
   ↓
BUILD REPAIR PLAN
   ↓
EXPLICIT CONFIRMATION
   ↓
EXECUTE GUARDED STEPS
   ↓
VERIFY
   ↓
CLEANUP + REPORT
```

A failure at any earlier stage prevents later mutation.

## Discovery safety

The discovery command adapter has a fixed read-only command allowlist. It cannot execute `mount`, `umount`, `chroot`, `grub-install`, or EFI mutation commands.

Filesystem probing is separate because a Live USB may need to inspect an unmounted installation. Such probes use temporary read-only mounts with `ro,nosuid,nodev,noexec`, inspect only known metadata, and attempt cleanup even after errors.

Encrypted storage, LVM, and RAID are not silently activated or unlocked.

## Target safety

A Linux repair target must resolve to a known Linux operating system with at least medium confidence. On UEFI systems the EFI System Partition must be uniquely resolved unless a future explicit operator selection mechanism is added.

Multiple ESPs therefore block automatic repair rather than causing DEVIL to choose the first one.

Device paths are required to be absolute `/dev/...` paths before mutation. Command arguments are passed as arrays to `subprocess` and are never assembled into shell strings.

## Mutation safety

Actual repair requires all of the following:

- a supported repair plan
- a safe target
- UEFI firmware
- a resolved Linux root and ESP
- root privileges
- the exact confirmation token `REPAIR`

The first executor supports UEFI + GRUB only.

Before changing boot state it captures `efibootmgr --verbose`, backs up the selected EFI tree, and records every major operation in the repair report.

The executor does not format partitions, delete unrelated EFI entries, or edit Windows BCD files.

## BootOrder safety

After `grub-install`, DEVIL identifies the newly-created `DEVIL-GRUB` entry, preserves every existing BootOrder item, and moves only that entry to the first position.

Verification requires:

- a `DEVIL-GRUB` EFI entry exists
- `DEVIL-GRUB` is first in BootOrder
- a pre-existing Windows Boot Manager entry remains present when it existed before repair

## Failure behavior

The executor stops at the first failed mutation. Cleanup is attempted in `finally` so temporary mounts are not intentionally left behind.

A failed recovery returns a non-zero process status and can write a JSON report using `--report`.

## Testing requirement

Unit tests prove parsing and decision logic. Real recovery compatibility must additionally be proven in disposable virtual machines for each supported filesystem/distribution layout. Universal compatibility must not be claimed from unit tests alone.
