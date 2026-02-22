#!/usr/bin/env bash
#
# Install / uninstall the Minecraft Skin 3D plugin into GIMP.
#
# Usage:
#   ./install.sh              Install the plugin
#   ./install.sh --uninstall  Remove the plugin
#   ./install.sh --help       Show usage
#
set -euo pipefail

PLUGIN_NAME="minecraft-skin-3d"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/$PLUGIN_NAME"

RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BOLD=$'\033[1m'
RESET=$'\033[0m'

info()  { echo "${GREEN}[+]${RESET} $*"; }
warn()  { echo "${YELLOW}[!]${RESET} $*"; }
error() { echo "${RED}[x]${RESET} $*"; }

# ── Detect GIMP installation ───────────────────────────────────────────────

find_gimp_binary() {
    for cmd in gimp gimp-2.99 gimp-3.0 flatpak; do
        if command -v "$cmd" &>/dev/null; then
            if [[ "$cmd" == "flatpak" ]]; then
                if flatpak list --app 2>/dev/null | grep -qi gimp; then
                    echo "flatpak"
                    return 0
                fi
            else
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

detect_gimp_version() {
    local bin="$1"
    if [[ "$bin" == "flatpak" ]]; then
        flatpak run org.gimp.GIMP --version 2>/dev/null | grep -oP '\d+\.\d+' | head -1
    else
        "$bin" --version 2>/dev/null | grep -oP '\d+\.\d+' | head -1
    fi
}

detect_plugin_dir() {
    local candidates=()

    # GIMP 3.0 locations
    candidates+=(
        "$HOME/.config/GIMP/3.0/plug-ins"
        "$HOME/.config/GIMP/2.99/plug-ins"
        "$HOME/Library/Application Support/GIMP/3.0/plug-ins"
        "$HOME/Library/Application Support/GIMP/2.99/plug-ins"
    )

    # Flatpak GIMP
    candidates+=(
        "$HOME/.var/app/org.gimp.GIMP/config/GIMP/3.0/plug-ins"
        "$HOME/.var/app/org.gimp.GIMP/config/GIMP/2.99/plug-ins"
    )

    # Snap GIMP
    candidates+=(
        "$HOME/snap/gimp/current/.config/GIMP/3.0/plug-ins"
    )

    # Windows (Git Bash / MSYS2)
    if [[ -n "${APPDATA:-}" ]]; then
        candidates+=("$APPDATA/GIMP/3.0/plug-ins")
    fi

    # Check which config parent already exists (= GIMP has run at least once)
    for dir in "${candidates[@]}"; do
        parent="$(dirname "$dir")"
        if [[ -d "$parent" ]]; then
            echo "$dir"
            return 0
        fi
    done

    # Fallback: first candidate
    echo "${candidates[0]}"
    return 1
}

# ── Install ────────────────────────────────────────────────────────────────

do_install() {
    echo "${BOLD}Minecraft Skin 3D — GIMP Plugin Installer${RESET}"
    echo ""

    # Verify source exists
    if [[ ! -d "$SOURCE_DIR" ]]; then
        error "Plugin source not found at $SOURCE_DIR"
        exit 1
    fi

    # Detect GIMP
    local gimp_bin=""
    if gimp_bin="$(find_gimp_binary)"; then
        local ver
        ver="$(detect_gimp_version "$gimp_bin" || echo "unknown")"
        info "Found GIMP ($gimp_bin, version $ver)"
    else
        warn "Could not find GIMP binary on PATH — installing anyway"
    fi

    # Detect plugin directory
    local plugin_dir=""
    if plugin_dir="$(detect_plugin_dir)"; then
        info "Plugin directory: $plugin_dir"
    else
        plugin_dir="$HOME/.config/GIMP/3.0/plug-ins"
        warn "Could not auto-detect plugin dir, using default: $plugin_dir"
    fi

    # Allow override via env var
    if [[ -n "${GIMP_PLUGIN_DIR:-}" ]]; then
        plugin_dir="$GIMP_PLUGIN_DIR"
        info "Using GIMP_PLUGIN_DIR override: $plugin_dir"
    fi

    local dest="$plugin_dir/$PLUGIN_NAME"

    # Remove previous installation if present
    if [[ -d "$dest" ]]; then
        warn "Removing previous installation at $dest"
        rm -rf "$dest"
    fi

    # Copy plugin files
    mkdir -p "$dest"
    cp -r "$SOURCE_DIR"/* "$dest"/
    chmod +x "$dest/$PLUGIN_NAME.py"
    info "Copied plugin files to $dest"

    # Verify entry point
    if [[ ! -f "$dest/$PLUGIN_NAME.py" ]]; then
        error "Entry point $dest/$PLUGIN_NAME.py not found after copy!"
        exit 1
    fi

    echo ""
    info "Installation complete!"
    echo "     Restart GIMP, then find the plugin under:"
    echo "     ${BOLD}Filters > Map > Minecraft Skin 3D Preview${RESET}"
}

# ── Uninstall ──────────────────────────────────────────────────────────────

do_uninstall() {
    echo "${BOLD}Minecraft Skin 3D — Uninstaller${RESET}"
    echo ""

    local plugin_dir=""
    if plugin_dir="$(detect_plugin_dir)"; then
        :
    else
        plugin_dir="$HOME/.config/GIMP/3.0/plug-ins"
    fi

    if [[ -n "${GIMP_PLUGIN_DIR:-}" ]]; then
        plugin_dir="$GIMP_PLUGIN_DIR"
    fi

    local dest="$plugin_dir/$PLUGIN_NAME"

    if [[ -d "$dest" ]]; then
        rm -rf "$dest"
        info "Removed $dest"
    else
        warn "Nothing to uninstall — $dest does not exist"
    fi
}

# ── Main ───────────────────────────────────────────────────────────────────

case "${1:-}" in
    --uninstall|-u)
        do_uninstall
        ;;
    --help|-h)
        echo "Usage: $0 [--uninstall | --help]"
        echo ""
        echo "  (no args)     Install the plugin into GIMP"
        echo "  --uninstall   Remove the plugin from GIMP"
        echo "  --help        Show this message"
        echo ""
        echo "Override the target directory with GIMP_PLUGIN_DIR:"
        echo "  GIMP_PLUGIN_DIR=/custom/path $0"
        ;;
    "")
        do_install
        ;;
    *)
        error "Unknown option: $1"
        echo "Run $0 --help for usage."
        exit 1
        ;;
esac
