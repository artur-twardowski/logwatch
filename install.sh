#!/bin/bash
# Generated with ChatGPT, with some manual adjustments

# List of Python script filenames to link
SCRIPTS=("lwrun.py" "lwserver.py" "lwview.py")

# Defaults
PREFIX="lw"
TARGET_DIR="/bin"
DRY_RUN=0
UNINSTALL=0

# Usage message
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -p, --prefix PREFIX     Prefix for installed symlinks (default: '$PREFIX')"
    echo "  -t, --target DIR        Target directory for symlinks (default: '$TARGET_DIR')"
    echo "  -D, --dry-run           Show actions without performing them"
    echo "  -u, --uninstall         Remove symlinks created with the given prefix"
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--prefix)
            [[ -n "$2" && ! "$2" =~ ^- ]] && PREFIX="$2" && shift 2 || { echo "Missing argument for $1"; usage; }
            ;;
        -t|--target)
            [[ -n "$2" && ! "$2" =~ ^- ]] && TARGET_DIR="$2" && shift 2 || { echo "Missing argument for $1"; usage; }
            ;;
        -D|--dry-run)
            DRY_RUN=1
            shift
            ;;
        -u|--uninstall)
            UNINSTALL=1
            shift
            ;;
        -*)
            echo "Unknown option: $1"
            usage
            ;;
        *)
            echo "Unexpected argument: $1"
            usage
            ;;
    esac
done

# Ensure target directory is an absolute path
if [[ ! "$TARGET_DIR" =~ ^/ ]]; then
    echo "Target directory must be an absolute path."
    exit 1
fi

# Get the path of the install script
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Determine if root or sudo is needed
IS_ROOT=0
if [[ "$EUID" -eq 0 ]]; then
    IS_ROOT=1
elif [[ $DRY_RUN -eq 0 && ! $(command -v sudo) ]]; then
    echo "sudo is required to modify files in $TARGET_DIR. Please run as root or install sudo."
    exit 1
fi

echo "Prefix:     $PREFIX"
echo "Target dir: $TARGET_DIR"
[[ $DRY_RUN -eq 1 ]] && echo "Dry run mode enabled - no changes will be applied"
[[ $UNINSTALL -eq 1 ]] && echo "Uninstall mode enabled"

# Perform installation or uninstallation
for script in "${SCRIPTS[@]}"; do
    base_name="${script%.py}"                      # e.g., lwrun
    short_name="${base_name#lw}"                   # e.g., run
    link_path="${TARGET_DIR}/${PREFIX}${short_name}"
    script_path="${INSTALL_DIR}/${script}"

    if [[ $UNINSTALL -eq 1 ]]; then
        if [[ -L "$link_path" ]]; then
            [[ $DRY_RUN -eq 0 ]] && {
                [[ $IS_ROOT -eq 1 ]] && rm -f "$link_path" || sudo rm -f "$link_path"
                echo "Removed $link_path"
            } || {
            echo "Would remove: $link_path"
            }
        else
            echo "No symlink found at: $link_path"
        fi
    else
        if [[ -f "$script_path" ]]; then
            [[ $DRY_RUN -eq 0 ]] && {
                [[ $IS_ROOT -eq 1 ]] && {
                    ln -sf "$script_path" "$link_path"
                    chmod +x "$script_path"
                } || {
                    sudo ln -sf "$script_path" "$link_path"
                    sudo chmod +x "$script_path"
                }
                echo "Linked $script_path -> $link_path"
            } || {
                echo "Would link: $script_path -> $link_path"
            }
        else
            echo "File not found: $script_path"
        fi
    fi
done

echo "Done."
