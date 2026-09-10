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

find_ovmf_code() {
    local candidate
    for candidate in \
        /usr/share/edk2/x64/OVMF_CODE.4m.fd \
        /usr/share/edk2/x64/OVMF_CODE.fd \
        /usr/share/edk2/x64/OVMF_CODE_4M.fd \
        /usr/share/edk2/ovmf/x64/OVMF_CODE.4m.fd \
        /usr/share/edk2/ovmf/x64/OVMF_CODE.fd \
        /usr/share/edk2/ovmf/x64/OVMF_CODE_4M.fd \
        /usr/share/edk2-ovmf/x64/OVMF_CODE.4m.fd \
        /usr/share/edk2-ovmf/x64/OVMF_CODE.fd \
        /usr/share/edk2-ovmf/x64/OVMF_CODE_4M.fd \
        /usr/share/OVMF/OVMF_CODE.4m.fd \
        /usr/share/OVMF/OVMF_CODE.fd \
        /usr/share/OVMF/OVMF_CODE_4M.fd; do
        if [[ -f "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

find_ovmf_vars() {
    local candidate
    for candidate in \
        /usr/share/edk2/x64/OVMF_VARS.4m.fd \
        /usr/share/edk2/x64/OVMF_VARS.fd \
        /usr/share/edk2/x64/OVMF_VARS_4M.fd \
        /usr/share/edk2/ovmf/x64/OVMF_VARS.4m.fd \
        /usr/share/edk2/ovmf/x64/OVMF_VARS.fd \
        /usr/share/edk2/ovmf/x64/OVMF_VARS_4M.fd \
        /usr/share/edk2-ovmf/x64/OVMF_VARS.4m.fd \
        /usr/share/edk2-ovmf/x64/OVMF_VARS.fd \
        /usr/share/edk2-ovmf/x64/OVMF_VARS_4M.fd \
        /usr/share/OVMF/OVMF_VARS.4m.fd \
        /usr/share/OVMF/OVMF_VARS.fd \
        /usr/share/OVMF/OVMF_VARS_4M.fd; do
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

    if ! find_ovmf_code >/dev/null 2>&1; then
        missing+=(OVMF-firmware)
    fi

    if ! find_ovmf_vars >/dev/null 2>&1; then
        missing+=(OVMF-variable-store)
    fi

    if ((${#missing[@]})); then
        printf 'recovery-lab: missing: %s\n' "${missing[*]}" >&2
        return 2
    fi

    printf 'recovery-lab: QEMU .............. OK\n'
    printf 'recovery-lab: qemu-img .......... OK\n'
    printf 'recovery-lab: UEFI/OVMF code .... %s\n' "$(find_ovmf_code)"
    printf 'recovery-lab: UEFI/OVMF vars .... %s\n' "$(find_ovmf_vars)"
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

    local ovmf_code ovmf_vars format vars_copy
    ovmf_code=$(find_ovmf_code) || fail "OVMF UEFI firmware not found"
    ovmf_vars=$(find_ovmf_vars) || fail "OVMF variable store not found"
    format=$(qemu-img info "$disk" | awk -F: '/^file format:/ {gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit}')
    [[ -n "$format" ]] || fail "could not determine disk image format"

    case "$format" in
        qcow2|raw) ;;
        *) fail "unsupported guest image format: $format (expected qcow2 or raw)" ;;
    esac

    vars_copy=$(mktemp --tmpdir recovery-lab-ovmf-vars.XXXXXX.fd)
    cp --reflink=auto "$ovmf_vars" "$vars_copy"
    trap 'rm -f -- "$vars_copy"' EXIT HUP INT TERM

    printf 'recovery-lab: launching disposable UEFI VM\n'
    printf 'recovery-lab: disk image: %s\n' "$disk"
    printf 'recovery-lab: format:     %s\n' "$format"
    printf 'recovery-lab: UEFI code:  %s\n' "$ovmf_code"
    printf 'recovery-lab: UEFI vars:  %s (disposable copy)\n' "$vars_copy"
    printf 'recovery-lab: snapshot:   enabled (guest writes discarded)\n'

    exec qemu-system-x86_64 \
        -machine q35,accel=kvm:tcg \
        -cpu max \
        -m 4096 \
        -smp 2 \
        -drive "if=pflash,format=raw,readonly=on,file=$ovmf_code" \
        -drive "if=pflash,format=raw,file=$vars_copy" \
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
