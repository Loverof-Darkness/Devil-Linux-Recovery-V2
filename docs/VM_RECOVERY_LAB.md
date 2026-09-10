# VM Recovery Lab

The DEVIL recovery executor must be tested against disposable virtual disks before a physical recovery is attempted.

The repository includes `scripts/recovery-lab.sh`, a small QEMU launcher for that purpose.

## Safety model

The launcher refuses `/dev`, `/sys`, `/proc`, and `/run` paths and requires the disk argument to be a regular file. QEMU is always started with a snapshot-backed guest disk, so guest writes are discarded when the VM exits.

This lab does not modify the host's EFI variables or physical disks.

## Host prerequisites

Install:

- QEMU x86_64
- `qemu-img`
- an OVMF UEFI firmware package
- KVM support when available (the launcher falls back to TCG)

Check the environment with:

```bash
bash scripts/recovery-lab.sh --check
```

## Disposable guest image

Create a dedicated qcow2 image for the lab. Do not point the lab at a physical block device or an image containing data you need to preserve.

Example:

```bash
qemu-img create -f qcow2 "$HOME/devil-recovery-lab.qcow2" 16G
```

Install a supported Linux guest into that image using a Linux installer ISO. The preferred first scenario is a UEFI guest with a single Linux root, GRUB, and an EFI System Partition.

## Broken-boot scenarios

Each scenario should begin from a known-good guest snapshot or disposable copy, then intentionally introduce one failure:

1. Remove or invalidate the Linux EFI boot entry while leaving the EFI files intact.
2. Remove the GRUB configuration while preserving the installed Linux root.
3. Replace or corrupt the Linux GRUB EFI loader while preserving the Microsoft loader when a Windows test guest is used.
4. Exercise a Btrfs root using the actual root subvolume, such as `@`.
5. Repeat with a separate `/boot` partition.

The expected DEVIL behavior is detect → select → resolve → preflight → backup → repair → verify, with ambiguous targets blocked rather than guessed.

## Run the disposable VM

```bash
bash scripts/recovery-lab.sh --run "$HOME/devil-recovery-lab.qcow2"
```

Boot the VM into the DEVIL Live environment, run the discovery and repair workflow against the guest disk, then shut down the VM. Because the disk is opened in snapshot mode, the guest's mutations are discarded after the process exits.

For meaningful recovery validation, preserve the guest's initial EFI and GRUB state, record the injected failure, run DEVIL, and verify the guest can boot normally on a subsequent non-snapshot test copy.

## Acceptance criteria

A recovery scenario is considered successful only when all of the following hold:

- the intended Linux installation is selected unambiguously
- the exact root filesystem and Btrfs subvolume are mounted
- the selected ESP is mounted at `/boot/efi`
- the target contains the required GRUB tooling
- an EFI backup exists before bootloader mutation
- GRUB installation succeeds
- GRUB configuration generation succeeds
- the repaired Linux EFI entry is promoted without dropping unrelated entries
- an existing Windows Boot Manager entry remains present
- all temporary mounts are cleaned up
- the machine-readable repair report records the complete transaction
- the repaired guest boots successfully after the test is repeated without snapshot mode

The repository should not claim universal recovery compatibility until these scenarios have automated or repeatable VM coverage.
