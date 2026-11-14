#!/bin/sh
# pico installer — POSIX. No root, no pip, no network.
set -e
SRC=$(cd "$(dirname "$0")" && pwd)
DEST="${PICO_HOME:-$HOME/.pico}"

command -v python3 >/dev/null 2>&1 || { echo "python3 is required"; exit 1; }
PY=$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')
python3 -c 'import sys;sys.exit(0 if sys.version_info>=(3,8) else 1)' || {
  echo "pico needs Python 3.8+ (found $PY)"; exit 1; }

mkdir -p "$DEST/rules" "$DEST/templates"
cp -f "$SRC/pico.py" "$HOME/pico.py"
cp -Rf "$SRC/pico" "$DEST/pkg"
cp -f "$SRC"/packs/*.py "$DEST/rules/"
cp -f "$SRC"/templates/*.txt "$DEST/templates/" 2>/dev/null || true
cp -Rf "$SRC/web" "$DEST/web"

echo "installed to $DEST"
echo "run:  PICO_HOME=$DEST python3 $HOME/pico.py"
echo "ui:   PICO_HOME=$DEST python3 $HOME/pico.py --ui"
