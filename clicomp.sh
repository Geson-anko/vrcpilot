# vrcpilot CLI completion bootstrap for bash.
#
# Usage (must be sourced, not executed):
#     . ./clicomp.sh
#   or
#     source ./clicomp.sh
#
# Steps:
#   1. If `.venv` exists, activate it.
#   2. If `vrcpilot` is still not on PATH, run `just setup` and re-activate
#      (`just setup` calls `uv venv --clear`, so re-sourcing is required).
#   3. Register argcomplete for `vrcpilot` in the current shell.
#   4. After this script returns, the venv stays activated and completion
#      stays enabled in your current bash session.

# Refuse to be executed: a subshell would lose the venv and completion.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "clicomp.sh: must be sourced, not executed." >&2
    echo "  . ./clicomp.sh    # or: source ./clicomp.sh" >&2
    exit 1
fi

# Resolve repo root from this script's location so the script works from
# any cwd (e.g. `. /path/to/clicomp.sh`).
_clicomp_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
_clicomp_activate="$_clicomp_dir/.venv/bin/activate"

_clicomp_cleanup() {
    unset _clicomp_dir _clicomp_activate
    unset -f _clicomp_cleanup _clicomp_activate_venv
}

_clicomp_activate_venv() {
    # shellcheck source=/dev/null
    . "$_clicomp_activate"
}

if [[ -f "$_clicomp_activate" ]]; then
    _clicomp_activate_venv || {
        echo "clicomp.sh: failed to activate $_clicomp_activate" >&2
        _clicomp_cleanup
        return 1
    }
fi

if ! command -v vrcpilot >/dev/null 2>&1; then
    if ! command -v just >/dev/null 2>&1; then
        echo "clicomp.sh: 'just' is required but not found on PATH." >&2
        _clicomp_cleanup
        return 1
    fi
    echo "clicomp.sh: 'vrcpilot' not found - running 'just setup' in $_clicomp_dir"
    (cd -- "$_clicomp_dir" && just setup) || {
        echo "clicomp.sh: 'just setup' failed." >&2
        _clicomp_cleanup
        return 1
    }
    _clicomp_activate_venv || {
        echo "clicomp.sh: failed to activate $_clicomp_activate after setup" >&2
        _clicomp_cleanup
        return 1
    }
fi

if ! command -v register-python-argcomplete >/dev/null 2>&1; then
    echo "clicomp.sh: 'register-python-argcomplete' not found (argcomplete missing?)." >&2
    _clicomp_cleanup
    return 1
fi

# Enable argcomplete-driven completion for `vrcpilot` in this session.
eval "$(register-python-argcomplete vrcpilot)" || {
    echo "clicomp.sh: failed to register argcomplete for vrcpilot." >&2
    _clicomp_cleanup
    return 1
}

_clicomp_cleanup
echo "clicomp.sh: vrcpilot completion enabled in this shell."
