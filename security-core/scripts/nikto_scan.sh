#!/bin/bash
# GREYBOX Nikto Wrapper Script
# Web server vulnerability scanning

set -euo pipefail

TARGET="$1"
OUTPUT_DIR="${2:-/root/workdir/scans}"
TUNING="${3:-4,6,8,b}"

if [ -z "$TARGET" ]; then
    echo "Usage: $0 <target_url> [output_dir] [tuning]"
    echo "Tuning options: 4=Injection, 6=XSS, 8=Command Exec, b=Software Identification"
    echo "Example: $0 https://example.com /root/scans 4,6,8,b"
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
echo "Output: $OUTPUT_FILE"
echo ""

echo "[*] Starting Nikto scan..."
# Single run, text output only - the XML output this used to also generate
# was never consumed anywhere downstream, so running the full scan twice
# was pure wasted time. -Display P makes nikto report its own progress
# periodically instead of going silent for long stretches. The browser
# User-Agent reduces trivial UA-based blocking - it will NOT get past
# enterprise WAF/TLS fingerprinting (Akamai, Cloudflare, etc.), which is a
# real, unavoidable limitation of any scanner against a heavily-protected
# production site, not something fixable from this script.
nikto -h "$TARGET" \
    -Tuning "$TUNING" \
    -output "$OUTPUT_FILE.txt" \
    -Format txt \
    -Display P \
    -useragent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36" \
    -timeout 10 \
    -maxtime 30m

echo ""
echo "[+] Nikto scan completed!"
echo "[+] Results saved to: $OUTPUT_FILE.txt"
echo ""
echo "Files created:"
ls -lh "$OUTPUT_FILE.txt"