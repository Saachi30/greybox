#!/bin/bash
# GREYBOX Subdomain Enumeration Script
# Uses subfinder and theHarvester for subdomain discovery.
#
# amass was dropped: as of v5, it moved to a client-server "engine"
# architecture, and the simple one-shot CLI invocation this script used
# to make (`amass enum -passive -d domain -o file`) is no longer
# guaranteed to work the same way. Rather than ship an unverified
# integration, subfinder + theHarvester alone already produce solid
# results - add amass back once its v5 usage is properly tested.

set -euo pipefail

DOMAIN="$1"
OUTPUT_DIR="${2:-/root/workdir/scans}"

if [ -z "$DOMAIN" ]; then
    echo "Usage: $0 <domain> [output_dir]"
    echo "Example: $0 example.com /root/scans"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="$OUTPUT_DIR/subdomains_${DOMAIN}_${TIMESTAMP}.txt"

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           GREYBOX Subdomain Enumeration                     ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Domain: $DOMAIN"
echo "Output: $OUTPUT_FILE"
echo ""

# Each tool below is individually fault-tolerant (|| ...) on purpose: this
# used to abort the entire script the instant one tool failed (set -e
# doesn't distinguish "this one source is unavailable" from "something is
# actually broken"), which meant a single failure lost ALL results,
# including ones already gathered, and skipped the final "Results saved
# to" line entirely - silently breaking anything downstream that depends
# on that file existing (like httprobe's auto-chaining).

echo "[*] Running subfinder..."
subfinder -d "$DOMAIN" -silent -o "$OUTPUT_DIR/subfinder_${DOMAIN}_${TIMESTAMP}.txt" \
    || echo "[!] subfinder failed or found nothing - continuing with other sources"

echo "[*] Running theHarvester..."
theHarvester -d "$DOMAIN" -b all -f "$OUTPUT_DIR/theharvester_${DOMAIN}_${TIMESTAMP}" \
    || echo "[!] theHarvester failed or found nothing - continuing with other sources"

echo "[*] Merging and deduplicating results..."
cat "$OUTPUT_DIR"/subfinder_*.txt \
    2>/dev/null | sort -u > "$OUTPUT_FILE" || true

SUBDOMAIN_COUNT=$(wc -l < "$OUTPUT_FILE" 2>/dev/null || echo 0)

echo ""
echo "[+] Subdomain enumeration completed!"
echo "[+] Found $SUBDOMAIN_COUNT unique subdomains"
echo "[+] Results saved to: $OUTPUT_FILE"
echo ""
echo "Top 10 subdomains:"
head -10 "$OUTPUT_FILE" 2>/dev/null || echo "(none found)"