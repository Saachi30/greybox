#!/bin/bash
# GREYBOX Nikto Wrapper Script
# Web server vulnerability scanning

set -euo pipefail

TARGET="$1"
OUTPUT_DIR="${2:-/root/workdir/scans}"
TUNING="${3:-4,6,8,b}"
MAXTIME="${4:-8m}"     # was 30m — this is the main speed lever

if [ -z "$TARGET" ]; then
    echo "Usage: $0 <target_url> [output_dir] [tuning] [maxtime]"
    echo "Tuning options: 4=Injection, 6=XSS, 8=Command Exec, b=Software Identification"
    echo "Example: $0 https://example.com /root/scans 4,6,8,b 8m"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CLEAN_TARGET=$(echo "$TARGET" | sed 's|https\?://||' | sed 's|/|_|g')
OUTPUT_FILE="$OUTPUT_DIR/nikto_${CLEAN_TARGET}_${TIMESTAMP}"

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           GREYBOX Nikto Web Scanner                         ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Target: $TARGET"
echo "Tuning: $TUNING"
echo "Max time: $MAXTIME"
echo "Output: $OUTPUT_FILE"
echo ""

echo "[*] Starting Nikto scan..."
nikto -h "$TARGET" \
    -Tuning "$TUNING" \
    -output "$OUTPUT_FILE.txt" \
    -Format txt \
    -Display P \
    -nointeractive \
    -useragent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36" \
    -timeout 5 \
    -maxtime "$MAXTIME"

echo ""
echo "[+] Nikto scan completed!"
echo "[+] Results saved to: $OUTPUT_FILE.txt"
echo ""
echo "Files created:"
ls -lh "$OUTPUT_FILE.txt"