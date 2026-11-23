#!/usr/bin/env bash
# Build the thesis from its source, the GIU template folder thesis/overleaf (main file bachelor.tex).
# Writes: thesis/thesis-draft.pdf, thesis/main.tex (single-file copy) and thesis/overleaf.zip (upload to Overleaf).
# Stops without changing anything if LaTeX fails or a reference or citation is undefined.
set -euo pipefail
cd "$(dirname "$0")"
tex="$(command -v tectonic || echo "$HOME/tectonic/tectonic")"
[ -x "$tex" ] || { echo "tectonic not found (expected on PATH or at ~/tectonic/tectonic)" >&2; exit 1; }
out="$(mktemp -d)"
trap 'rm -rf "$out"' EXIT
if ! (cd overleaf && "$tex" --outdir "$out" --keep-logs --keep-intermediates bachelor.tex > "$out/build.txt" 2>&1); then
  grep -E "^error|^!|Error" "$out/build.txt" | head -20 >&2
  echo "LaTeX build failed; nothing was changed." >&2
  exit 1
fi
if grep -qE "Reference .* undefined|Citation .* undefined" "$out/bachelor.log"; then
  grep -E "Reference .* undefined|Citation .* undefined" "$out/bachelor.log" | sort -u >&2
  echo "Undefined references or citations; nothing was changed." >&2
  exit 1
fi
python3 flatten.py "$out/bachelor.bbl"
cp "$out/bachelor.pdf" thesis-draft.pdf
rm -f overleaf.zip && (cd overleaf && zip -qr ../overleaf.zip . -x '.*')
pages=$(grep -o "Output written on [^(]*([0-9]* pages" "$out/bachelor.log" | grep -o "[0-9]* pages" || true)
echo "Built thesis-draft.pdf ${pages:+($pages) }; $(grep -c 'Overfull' "$out/bachelor.log" || true) overfull boxes. main.tex and overleaf.zip refreshed."
