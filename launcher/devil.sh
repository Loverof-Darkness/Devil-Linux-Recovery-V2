#!/usr/bin/env bash
set -euo pipefail

DEVIL_REPO="Loverof-Darkness/Devil-Linux-Recovery-V2"
DEVIL_REF="main"
DEVIL_ROOT="${DEVIL_ROOT:-${TMPDIR:-/tmp}/devil-linux-recovery-v2}"

usage() {
  cat <<'EOF'
DEVIL Linux Recovery V2 bootstrap

Usage:
  devil.sh [--source] [--help] [DEVIL_ARGS...]

  --source    run the checked-out repository instead of downloading a release
EOF
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'DEVIL: required command not found: %s\n' "$1" >&2
    exit 2
  }
}

run_source() {
  local root
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  require_cmd python3
  exec python3 -m devil.cli "$@"
}

fetch_release() {
  require_cmd curl
  require_cmd tar
  require_cmd sha256sum

  mkdir -p "$DEVIL_ROOT"
  local archive="$DEVIL_ROOT/devil.tar.gz"
  local url="https://codeload.github.com/${DEVIL_REPO}/tar.gz/refs/heads/${DEVIL_REF}"

  curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 \
    "$url" -o "$archive"

  rm -rf "$DEVIL_ROOT/source"
  mkdir -p "$DEVIL_ROOT/source"
  tar -xzf "$archive" --strip-components=1 -C "$DEVIL_ROOT/source"

  require_cmd python3
  exec python3 -m devil.cli "$@"
}

main() {
  local source_mode=0
  local -a args=()
  while (($#)); do
    case "$1" in
      --source) source_mode=1 ;;
      --help|-h) usage; return 0 ;;
      *) args+=("$1") ;;
    esac
    shift
  done

  if (( source_mode )); then
    run_source "${args[@]}"
  else
    fetch_release "${args[@]}"
  fi
}

main "$@"
