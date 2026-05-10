#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
APPS_DIR="${HOME}/.local/share/applications"
OLD_CONFIG_DIR="${HOME}/.config/snip"
OLD_CACHE_DIR="${HOME}/.cache/snip"
CONFIG_DIR="${HOME}/.config/ragsnip"
CACHE_DIR="${HOME}/.cache/ragsnip"
CONFIG_FILE="${CONFIG_DIR}/config"

install -d "${BIN_DIR}" "${APPS_DIR}"

# --- Migrate config & cache from old `snip` paths if present ----------------
if [ -d "${OLD_CONFIG_DIR}" ] && [ ! -d "${CONFIG_DIR}" ]; then
    echo "Migrating ${OLD_CONFIG_DIR} -> ${CONFIG_DIR}"
    mv "${OLD_CONFIG_DIR}" "${CONFIG_DIR}"
fi
if [ -d "${OLD_CACHE_DIR}" ] && [ ! -d "${CACHE_DIR}" ]; then
    echo "Migrating ${OLD_CACHE_DIR} -> ${CACHE_DIR}"
    mv "${OLD_CACHE_DIR}" "${CACHE_DIR}"
fi
install -d "${CONFIG_DIR}" "${CACHE_DIR}"

# --- Install binary as `ragsnip` and keep `snip` as a symlink alias --------
install -m 755 "${SRC_DIR}/ragsnip.py" "${BIN_DIR}/ragsnip"

# Replace any prior snip binary/symlink with a symlink pointing at ragsnip
if [ -e "${BIN_DIR}/snip" ] || [ -L "${BIN_DIR}/snip" ]; then
    rm -f "${BIN_DIR}/snip"
fi
ln -s ragsnip "${BIN_DIR}/snip"

# --- Install desktop entry; remove old snip.desktop if present -------------
install -m 644 "${SRC_DIR}/ragsnip.desktop" "${APPS_DIR}/ragsnip.desktop"
if [ -f "${APPS_DIR}/snip.desktop" ]; then
    rm -f "${APPS_DIR}/snip.desktop"
fi

# --- Seed default config on first install ----------------------------------
if [ ! -f "${CONFIG_FILE}" ]; then
    cat > "${CONFIG_FILE}" <<'EOF'
# ragsnip configuration (the GUI Settings dialog rewrites this file on save)

# Upload host: catbox | 0x0 | imgur
host=catbox

# Imgur Client-ID (only used when host=imgur). Empty = built-in shared default.
client_id=

# Keep the local screenshot file in /tmp after upload (debugging).
keep_local=false

# Keep the GUI window above other windows.
always_on_top=true

# Number of recent snips to remember in history (1-200).
history_size=20
EOF
    chmod 600 "${CONFIG_FILE}"
fi

# --- Update thumbnail paths in migrated history.json ------------------------
HISTORY_FILE="${CONFIG_DIR}/history.json"
if [ -f "${HISTORY_FILE}" ]; then
    python3 - "${HISTORY_FILE}" "${OLD_CACHE_DIR}" "${CACHE_DIR}" <<'PYEOF' || true
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
old, new = sys.argv[2], sys.argv[3]
try:
    data = json.loads(path.read_text())
    changed = False
    for entry in data:
        t = entry.get("thumb")
        if isinstance(t, str) and t.startswith(old):
            entry["thumb"] = t.replace(old, new, 1)
            changed = True
    if changed:
        path.write_text(json.dumps(data, indent=2))
        print(f"Rewrote thumb paths in {path}")
except Exception as e:
    print(f"history rewrite skipped: {e}", file=sys.stderr)
PYEOF
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APPS_DIR}" 2>/dev/null || true
fi

case ":${PATH}:" in
    *":${BIN_DIR}:"*) ;;
    *) echo "warning: ${BIN_DIR} is not on your PATH; the menu entry will still work." >&2 ;;
esac

echo "Installed:"
echo "  ${BIN_DIR}/ragsnip"
echo "  ${BIN_DIR}/snip      -> ragsnip (compat alias)"
echo "  ${APPS_DIR}/ragsnip.desktop"
echo "  ${CONFIG_FILE}"
