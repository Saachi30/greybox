#!/bin/bash
# greybox Whatweb Wrapper Script
# Website technology identification (CMS, server, JS frameworks, etc.)

set -euo pipefail

TARGET="$1"
OUTPUT_DIR="${2:-/root/workdir/scans}"
AGGRESSION="${3:-1}"   # whatweb only accepts 1, 3, or 4 (there is no 2)

if [ -z "$TARGET" ]; then
    echo "Usage: $0 <target_url> [output_dir] [aggression]"
    echo "Aggression: 1 (stealthy/default), 3 (aggressive), 4 (heavy)"
    echo "Example: $0 https://example.com /root/scans 1"
    exit 1
fi

case "$AGGRESSION" in
    1|3|4) ;;
    *)
        echo "Error: aggression level must be 1, 3, or 4 (got '$AGGRESSION')." >&2
        echo "  1 = passive/stealthy, 3 = aggressive, 4 = heavy" >&2
        exit 1
        ;;
esac

mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CLEAN_TARGET=$(echo "$TARGET" | sed 's|https\?://||' | sed 's|/|_|g')
OUTPUT_FILE="$OUTPUT_DIR/whatweb_${CLEAN_TARGET}_${TIMESTAMP}"

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           greybox Whatweb Scanner                          ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Target: $TARGET"
echo "Aggression: $AGGRESSION"
echo "Output: $OUTPUT_FILE"
echo ""

echo "[*] Fingerprinting web technologies..."
whatweb -a "$AGGRESSION" "$TARGET" \
    --color=never \
    --quiet \
    --log-brief="$OUTPUT_FILE.txt" \
    --log-json="$OUTPUT_FILE.json"

echo ""
echo "[+] Whatweb scan completed!"
echo "[+] Results saved to: $OUTPUT_FILE.*"
echo ""
cat "$OUTPUT_FILE.txt"