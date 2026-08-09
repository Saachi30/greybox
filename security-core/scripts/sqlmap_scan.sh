#!/bin/bash
# GREYBOX SQLMap Wrapper Script
# SQL Injection vulnerability scanning

set -euo pipefail

TARGET="$1"
OUTPUT_DIR="${2:-/root/workdir/scans}"
LEVEL="${3:-3}"
RISK="${4:-2}"

if [ -z "$TARGET" ]; then
    echo "Usage: $0 <target_url> [output_dir] [level] [risk]"
    echo "Level: 1-5 (default: 3) - Depth of tests"
    echo "Risk: 1-3 (default: 2) - Risk of queries"
    echo "Example: $0 'https://example.com/page?id=1' /root/scans 4 2"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_SUBDIR="$OUTPUT_DIR/sqlmap_${TIMESTAMP}"
mkdir -p "$OUTPUT_SUBDIR"

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           GREYBOX SQLMap Scanner                            ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Target: $TARGET"
echo "Level: $LEVEL (1-5)"
echo "Risk: $RISK (1-3)"
echo "Output: $OUTPUT_SUBDIR"
echo ""

echo "[*] Starting SQLMap scan..."
sqlmap -u "$TARGET" \
    --batch \
    --level="$LEVEL" \
    --risk="$RISK" \
    --threads=5 \
    --output-dir="$OUTPUT_SUBDIR" \
    --dbs \
    --tables \
    --dump-all \
    --technique=BEUSTQ \
    --random-agent \
    --timeout=30 \
    --retries=3

echo ""
echo "[+] SQLMap scan completed!"
echo "[+] Results saved to: $OUTPUT_SUBDIR"
echo ""
echo "Files created:"
ls -lh "$OUTPUT_SUBDIR"