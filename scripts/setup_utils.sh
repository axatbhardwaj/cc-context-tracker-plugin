#!/usr/bin/env bash
# Shared utility functions for install/uninstall scripts

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
header() { echo -e "\n${BOLD}$1${NC}"; }

# Get the directory of the main script (cross-platform)
get_script_dir() {
    local source="${BASH_SOURCE[1]}"
    while [ -L "$source" ]; do
        local dir="$(cd -P "$(dirname "$source")" && pwd)"
        source="$(readlink "$source")"
        [[ $source != /* ]] && source="$dir/$source"
    done
    cd -P "$(dirname "$source")" && pwd
}

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check required dependencies
check_dependencies() {
    local missing=()

    for cmd in python3 git; do
        if ! command_exists "$cmd"; then
            missing+=("$cmd")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        error "Missing required dependencies: ${missing[*]}"
        echo "Please install them and try again."
        return 1
    fi

    # jq is optional but recommended
    if ! command_exists jq; then
        warn "jq not found. Using Python for JSON manipulation."
        export USE_PYTHON_JSON=true
    else
        export USE_PYTHON_JSON=false
    fi

    return 0
}

# Detect OS type
get_os_type() {
    case "$(uname -s)" in
        Linux*)  echo "linux" ;;
        Darwin*) echo "macos" ;;
        *)       echo "unknown" ;;
    esac
}

# Expand tilde in path
expand_path() {
    local path="$1"
    echo "${path/#\~/$HOME}"
}

# Create backup of a file
backup_file() {
    local file="$1"
    local timestamp=$(date +%Y%m%d_%H%M%S)

    if [ -f "$file" ]; then
        cp "$file" "${file}.backup.${timestamp}"
        echo "${file}.backup.${timestamp}"
    fi
}

# Validate JSON file
validate_json() {
    local file="$1"

    if [ ! -f "$file" ]; then
        return 1
    fi

    if command_exists jq; then
        jq empty "$file" 2>/dev/null
    else
        python3 -c "import json; json.load(open('$file'))" 2>/dev/null
    fi
}

# Prompt with default value
prompt_with_default() {
    local prompt="$1"
    local default="$2"
    local result

    read -p "$prompt [$default]: " result
    echo "${result:-$default}"
}

# Prompt for yes/no
prompt_yes_no() {
    local prompt="$1"
    local default="${2:-n}"
    local result

    if [ "$default" = "y" ]; then
        read -p "$prompt (Y/n): " result
        result="${result:-y}"
    else
        read -p "$prompt (y/N): " result
        result="${result:-n}"
    fi

    [[ "$result" =~ ^[Yy]$ ]]
}

# Convert comma-separated string to JSON array
csv_to_json_array() {
    local csv="$1"
    python3 -c "
import sys
import json
patterns = [p.strip() for p in '''$csv'''.split(',') if p.strip()]
print(json.dumps(patterns))
"
}

# Add hook to settings.json using jq
add_hook_jq() {
    local settings_file="$1"
    local hook_command="$2"

    jq --arg cmd "$hook_command" '
        .hooks //= {} |
        .hooks.Stop //= [] |
        .hooks.Stop += [{
            "hooks": [{
                "type": "command",
                "command": $cmd,
                "timeout": 30
            }]
        }]
    ' "$settings_file"
}

# Add hook to settings.json using Python
add_hook_python() {
    local settings_file="$1"
    local hook_command="$2"

    python3 << PYTHON
import json
import os

settings_path = "$settings_file"
hook_command = """$hook_command"""

if os.path.exists(settings_path):
    with open(settings_path, 'r') as f:
        settings = json.load(f)
else:
    settings = {}

settings.setdefault('hooks', {})
settings['hooks'].setdefault('Stop', [])

settings['hooks']['Stop'].append({
    'hooks': [{
        'type': 'command',
        'command': hook_command,
        'timeout': 30
    }]
})

print(json.dumps(settings, indent=2))
PYTHON
}

# Check if our hook already exists in settings
hook_exists() {
    local settings_file="$1"

    if [ ! -f "$settings_file" ]; then
        return 1
    fi

    if command_exists jq; then
        jq -e '.hooks.Stop[]?.hooks[]? | select(.command | contains("context-tracker"))' "$settings_file" >/dev/null 2>&1
    else
        python3 -c "
import json
import sys

with open('$settings_file', 'r') as f:
    settings = json.load(f)

for hook_group in settings.get('hooks', {}).get('Stop', []):
    for hook in hook_group.get('hooks', []):
        if 'context-tracker' in hook.get('command', ''):
            sys.exit(0)
sys.exit(1)
"
    fi
}

# Remove our hook from settings.json using jq
remove_hook_jq() {
    local settings_file="$1"

    jq '
        if .hooks.Stop then
            .hooks.Stop |= map(
                select(
                    (.hooks[0].command | contains("context-tracker")) | not
                )
            )
        else . end |
        if .hooks.Stop == [] then del(.hooks.Stop) else . end |
        if .hooks == {} then del(.hooks) else . end
    ' "$settings_file"
}

# Remove our hook from settings.json using Python
remove_hook_python() {
    local settings_file="$1"

    python3 << PYTHON
import json

with open("$settings_file", 'r') as f:
    settings = json.load(f)

if 'hooks' in settings and 'Stop' in settings['hooks']:
    settings['hooks']['Stop'] = [
        hook_group for hook_group in settings['hooks']['Stop']
        if not any('context-tracker' in h.get('command', '')
                   for h in hook_group.get('hooks', []))
    ]

    if not settings['hooks']['Stop']:
        del settings['hooks']['Stop']
    if not settings['hooks']:
        del settings['hooks']

print(json.dumps(settings, indent=2))
PYTHON
}
