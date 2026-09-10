#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  recovery-lab.sh --check
  recovery-lab.sh --run <qcow2-or-raw-disk>

The lab is intentionally disposable. --run always starts QEMU with snapshot
mode, so guest writes are discarded when the VM exits. No host block device
may be passed directly; the argument must be a regular file.
EOF
}

fail() {
    printf 'recovery-lab: ERROR: %s\n' "$*" >&2
    exit 2
}

find_ovmf() {
    local candidate
    for candidate in \
        /usr/share/edk2/x64/OVMF_CODE.fd \
        /usr/share/edk2/x64/OVMF_CODE_4M.fd \
        /usr/share/edk2/ovmf/x64/OVMF_CODE.fd \
        /usr/share/edk2/ovmf/x64/OVMF_CODE_4M.fd \
        /usr/share/OVMF/OVMF_CODE.fd \
        /usr/share/OVMF/OVMF_CODE_4M.fd; do
        if [[ -f "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

check_lab() {
    local missing=()
    command -v qemu-system-x86_64 >/dev/null 2>&1 || missing+=(qemu-system-x86_64)
    command -v qemu-img >/dev/null 2>&1 || missing+=(qemu-img)

    if ! find_ovmf >/dev/null 2>&1; then
        missing+=(OVMF-firmware)
    fi

    if ((${#missing[@]})); then
        printf 'recovery-lab: missing: %s\n' "${missing[*]}" >&2
        return 2
    fi

    printf 'recovery-lab: QEMU .............. OK\n'
    printf 'recovery-lab: qemu-img .......... OK\n'
    printf 'recovery-lab: UEFI/OVMF ......... %s\n' "$(find_ovmf)"
    printf 'recovery-lab: guest writes ...... SNAPSHOT-ONLY\n'
    printf 'recovery-lab: host disks ........ REFUSED\n'
}

run_lab() {
    [[ $# -eq 1 ]] || { usage; exit 2; }
    local disk=$1
    [[ -f "$disk" ]] || fail "disk image must be a regular file: $disk"

    case "$disk" in
        /dev/*|/sys/*|/proc/*|/run/*) fail "refusing non-file storage path: $disk" ;;
    esac

    command -v qemu-system-x86_64 >/dev/null 2>&1 || fail "qemu-system-x86_64 not found"
    command -v qemu-img >/dev/null 2>&1 || fail "qemu-img not found"

    local ovmf format
    ovmf=$(find_ovmf) || fail "OVMF UEFI firmware not found"
    format=$(qemu-img info "$disk" | awk -F: '/^file format:/ {gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit}')
    [[ -n "$format" ]] || fail "could not determine disk image format"

    case "$format" in
        qcow2|raw) ;;
        *) fail "unsupported guest image format: $format (expected qcow2 or raw)" ;;
    esac

    printf 'recovery-lab: launching disposable UEFI VM\n'
    printf 'recovery-lab: disk image: %s\n' "$disk"
    printf 'recovery-lab: format:     %s\n' "$format"
    printf 'recovery-lab: snapshot:   enabled (guest writes discarded)\n'

    exec qemu-system-x86_64 \
        -machine q35,accel=kvm:tcg \
        -cpu max \
        -m 4096 \
        -smp 2 \
        -bios "$ovmf" \
        -drive "file=$disk,format=$format,if=virtio,snapshot=on" \
        -boot menu=on \
        -display gtk \
        -serial mon:stdio
}

case "${1:-}" in
    --check)
        [[ $# -eq 1 ]] || { usage; exit 2; }
        check_lab
        ;;
    --run)
        shift
        run_lab "$@"
        ;;
    *)
        usage
        exit 2
        ;;
esac
